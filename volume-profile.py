# filename: volume_profile_analysis.py

import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timezone
import re
import time
import logging
from typing import List, Dict, Optional

# --- Configuration ---
SYMBOLS = ['BTCUSDT', 'ETHUSDT']
# MODIFIED LINE: Added 270, 180, and 120 day lookbacks
LOOKBACK_PERIODS_DAYS = [270, 180, 120, 60, 30, 21, 14, 7, 3, 2]
TIMEFRAME_FOR_PROFILE = '1h'  # Use 1h data for a good balance of detail and API efficiency
OUTPUT_FILENAME = "volume_profile_analysis.json"

# Volume Profile Parameters
NUM_BINS = 100  # Number of price buckets for the profile
VALUE_AREA_PERCENT = 0.70  # 70% is standard for the Value Area
HVN_THRESHOLD_MULTIPLIER = 1.5  # Volume > 1.5x average is a High Volume Node
LVN_THRESHOLD_MULTIPLIER = 0.5  # Volume < 0.5x average is a Low Volume Node

API_ENDPOINT = "https://api.binance.com/api/v3/klines"

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'My Volume Profile Bot'
})
DEFAULT_TIMEOUT = 20


def get_safe_symbol(symbol: str) -> str:
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol


def get_minutes_from_timeframe(tf_string: str) -> int:
    num_match = re.search(r'\d+', tf_string)
    unit_match = re.search(r'[a-zA-Z]', tf_string)
    if not num_match or not unit_match:
        return 0
    num = int(num_match.group(0))
    unit = unit_match.group(0).lower()
    return num if unit == 'm' else num * 60 if unit == 'h' else num * 60 * 24


def fetch_ohlcv_for_profile(symbol: str, interval: str, lookback_days: int, limit: int = 1000) -> Optional[
    pd.DataFrame]:
    """Fetches all necessary OHLCV data for a given lookback period."""
    all_data = []
    df = pd.DataFrame()
    try:
        minutes_per_tf = get_minutes_from_timeframe(interval)
        total_candles_needed = (lookback_days * 1440) // minutes_per_tf
        end_time_ms = None

        while len(all_data) < total_candles_needed:
            url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
            if end_time_ms:
                url += f'&endTime={end_time_ms}'

            r = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            data_chunk = r.json()

            if not data_chunk:
                break

            all_data = data_chunk + all_data
            end_time_ms = data_chunk[0][0] - 1
            if len(data_chunk) < limit:
                break
            time.sleep(0.3)

        if not all_data:
            return None

        df = pd.DataFrame(all_data, columns=[
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time',
            'Quote asset volume', 'Number of trades', 'Taker buy base asset volume',
            'Taker buy quote asset volume', 'Ignore'
        ])
        df = df.tail(int(total_candles_needed))  # Trim excess

        df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        df.set_index('Date', inplace=True)

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]

    except Exception as e:
        logging.error(f'Error fetching {symbol} {interval}: {e}')
        return None


def calculate_volume_profile(df: pd.DataFrame) -> Optional[Dict]:
    """Calculates Volume Profile metrics from an OHLCV DataFrame."""
    if df is None or df.empty:
        return None

    min_price = df['Low'].min()
    max_price = df['High'].max()

    # Create price bins
    price_bins = np.linspace(min_price, max_price, NUM_BINS + 1)

    # Use the closing price of each bar to distribute its volume
    df['price_bin'] = pd.cut(df['Close'], bins=price_bins, labels=price_bins[:-1], right=False)

    volume_by_price = df.groupby('price_bin')['Volume'].sum().sort_index()

    if volume_by_price.empty:
        return None

    # --- Calculate Key Metrics ---
    total_volume = volume_by_price.sum()
    poc_price = volume_by_price.idxmax()
    poc_volume = volume_by_price.max()

    # Calculate Value Area (VA)
    target_va_volume = total_volume * VALUE_AREA_PERCENT

    # Start from POC and expand outwards
    poc_index = volume_by_price.index.get_loc(poc_price)
    va_volume = poc_volume
    va_low_idx, va_high_idx = poc_index, poc_index

    while va_volume < target_va_volume:
        # Check bin above and below, add the one with more volume
        next_low_idx = va_low_idx - 1
        next_high_idx = va_high_idx + 1

        vol_low = volume_by_price.iloc[next_low_idx] if next_low_idx >= 0 else -1
        vol_high = volume_by_price.iloc[next_high_idx] if next_high_idx < len(volume_by_price) else -1

        if vol_low == -1 and vol_high == -1:
            break  # Reached ends of profile

        if vol_high > vol_low:
            va_volume += vol_high
            va_high_idx = next_high_idx
        else:
            va_volume += vol_low
            va_low_idx = next_low_idx

    value_area_low = volume_by_price.index[va_low_idx]
    value_area_high = volume_by_price.index[va_high_idx] + (
                price_bins[1] - price_bins[0])  # Add bin width for upper bound

    # Identify HVNs and LVNs
    avg_bin_volume = volume_by_price.mean()
    hvn_threshold = avg_bin_volume * HVN_THRESHOLD_MULTIPLIER
    lvn_threshold = avg_bin_volume * LVN_THRESHOLD_MULTIPLIER

    hvns = volume_by_price[volume_by_price > hvn_threshold]
    lvns = volume_by_price[volume_by_price < lvn_threshold]

    # Format the nodes for JSON output
    hvn_list = [{'price_level': float(p), 'volume': float(v)} for p, v in hvns.items()]
    lvn_list = [{'price_level': float(p), 'volume': float(v)} for p, v in lvns.items()]

    return {
        "point_of_control": float(poc_price),
        "value_area_low": float(value_area_low),
        "value_area_high": float(value_area_high),
        "high_volume_nodes": sorted(hvn_list, key=lambda x: x['volume'], reverse=True),
        "low_volume_nodes": sorted(lvn_list, key=lambda x: x['volume']),
        "full_profile": [{'price_level': float(p), 'volume': float(v)} for p, v in volume_by_price.items()]
    }


def main():
    logging.info("===== STARTING VOLUME PROFILE ANALYSIS =====")
    results = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        logging.info(f"--- Analyzing Volume Profile for {safe_symbol} ---")
        results[safe_symbol] = {}
        for days in LOOKBACK_PERIODS_DAYS:
            logging.info(f"  ... using {days}d lookback period on {TIMEFRAME_FOR_PROFILE} data.")
            df = fetch_ohlcv_for_profile(symbol, TIMEFRAME_FOR_PROFILE, lookback_days=days)
            profile_data = calculate_volume_profile(df)
            if profile_data:
                results[safe_symbol][f'{days}d'] = profile_data
            else:
                logging.warning(f"  Could not generate profile for {symbol} {days}d lookback.")
            time.sleep(1)  # Be nice to the API

    try:
        payload = {'data': results, 'last_updated': datetime.now(timezone.utc).isoformat()}
        with open(OUTPUT_FILENAME, 'w') as f:
            json.dump(payload, f, indent=4)
        logging.info(f"Volume profile analysis complete. Saved to {OUTPUT_FILENAME}")
    except IOError as e:
        logging.error(f"Could not write to file {OUTPUT_FILENAME}: {e}")

    logging.info("===== ALL ANALYSIS COMPLETE =====")
    SESSION.close()


if __name__ == "__main__":
    main()
