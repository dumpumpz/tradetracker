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

# MODIFIED LINE: Added 1095 (3y), 730 (2y), and 365 (1y)
LOOKBACK_PERIODS_DAYS = [1095, 730, 365, 270, 180, 120, 60, 30, 21, 14, 7, 3, 2]

TIMEFRAME_FOR_PROFILE = '1h'  # 1h data provides good granularity for long-term profiles
OUTPUT_FILENAME = "volume_profile_analysis.json"

# Volume Profile Parameters
NUM_BINS = 150  # Increased bins slightly for better resolution on 3-year charts
VALUE_AREA_PERCENT = 0.70
HVN_THRESHOLD_MULTIPLIER = 1.5
LVN_THRESHOLD_MULTIPLIER = 0.5

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
        # Calculate how many candles cover the lookback period
        total_candles_needed = (lookback_days * 1440) // minutes_per_tf
        end_time_ms = None

        logging.info(f"    Target: {total_candles_needed} candles (~{lookback_days} days)")

        while len(all_data) < total_candles_needed:
            url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
            if end_time_ms:
                url += f'&endTime={end_time_ms}'

            try:
                r = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
                r.raise_for_status()
                data_chunk = r.json()
            except Exception as req_err:
                logging.warning(f"    API Request failed, retrying... {req_err}")
                time.sleep(2)
                continue

            if not data_chunk:
                break

            all_data = data_chunk + all_data
            end_time_ms = data_chunk[0][0] - 1
            
            # Progress log for long downloads
            if len(all_data) % 5000 == 0:
                logging.info(f"    Downloaded {len(all_data)} / {total_candles_needed} candles...")

            if len(data_chunk) < limit:
                # Reached the beginning of the coin listing
                break
            
            # Small sleep to avoid hitting API rate limits too hard
            time.sleep(0.15)

        if not all_data:
            return None

        df = pd.DataFrame(all_data, columns=[
            'Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time',
            'Quote asset volume', 'Number of trades', 'Taker buy base asset volume',
            'Taker buy quote asset volume', 'Ignore'
        ])
        
        # Trim excess candles if we fetched slightly more than needed
        df = df.tail(int(total_candles_needed))

        df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        df.set_index('Date', inplace=True)

        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]

    except Exception as e:
        logging.error(f'Error fetching {symbol} {interval}: {e}')
        return None


def calculate_volume_profile(df: pd.DataFrame, price_bins: np.ndarray) -> Optional[Dict]:
    """
    Calculates an accurate Volume Profile using a pre-defined set of price bins.
    """
    if df is None or df.empty:
        return None

    # Get the overall range and bin size from the master bins
    min_price = price_bins[0]
    num_bins = len(price_bins) - 1
    bin_size = price_bins[1] - price_bins[0]
    
    if bin_size <= 0:
        logging.error("Bin size is zero or negative. Cannot process profile.")
        return None

    # Initialize a Series to hold the volume for each master price bin
    profile = pd.Series(index=price_bins[:-1], data=np.zeros(num_bins), dtype=float)

    # ACCURATE VOLUME DISTRIBUTION
    # This iterates over every candle. For 3 years of data (26k rows), this might take 1-2 seconds.
    for _, row in df.iterrows():
        low_price, high_price, volume = row['Low'], row['High'], row['Volume']
        
        start_bin_idx = int(max(0, (low_price - min_price) // bin_size))
        end_bin_idx = int(min(num_bins - 1, (high_price - min_price) // bin_size))
        
        num_bins_spanned = (end_bin_idx - start_bin_idx) + 1
        
        if num_bins_spanned > 0:
            volume_per_bin = volume / num_bins_spanned
            # Vectorized addition for speed
            if start_bin_idx == end_bin_idx:
                 profile.iloc[start_bin_idx] += volume
            else:
                profile.iloc[start_bin_idx : end_bin_idx + 1] += volume_per_bin
    
    volume_by_price = profile[profile > 0]

    if volume_by_price.empty:
        return None

    # Calculate Key Metrics
    total_volume = volume_by_price.sum()
    poc_price = volume_by_price.idxmax()
    poc_volume = volume_by_price.max()

    target_va_volume = total_volume * VALUE_AREA_PERCENT
    poc_index = volume_by_price.index.get_loc(poc_price)
    va_volume = poc_volume
    va_low_idx, va_high_idx = poc_index, poc_index

    # Value Area Calculation
    while va_volume < target_va_volume and (va_low_idx > 0 or va_high_idx < len(volume_by_price) - 1):
        next_low_idx = va_low_idx - 1
        next_high_idx = va_high_idx + 1
        vol_low = volume_by_price.iloc[next_low_idx] if next_low_idx >= 0 else -1
        vol_high = volume_by_price.iloc[next_high_idx] if next_high_idx < len(volume_by_price) else -1
        if vol_low == -1 and vol_high == -1: break
        if vol_high > vol_low:
            va_volume += vol_high
            va_high_idx = next_high_idx
        else:
            va_volume += vol_low
            va_low_idx = next_low_idx

    value_area_low = volume_by_price.index[va_low_idx]
    value_area_high = volume_by_price.index[va_high_idx] + bin_size

    avg_bin_volume = volume_by_price.mean()
    hvn_threshold = avg_bin_volume * HVN_THRESHOLD_MULTIPLIER
    lvn_threshold = avg_bin_volume * LVN_THRESHOLD_MULTIPLIER
    hvns = volume_by_price[volume_by_price > hvn_threshold]
    lvns = volume_by_price[volume_by_price < lvn_threshold]
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
    
    # Ensure lookback periods are sorted from longest to shortest
    sorted_lookbacks = sorted(LOOKBACK_PERIODS_DAYS, reverse=True)
    
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        logging.info(f"--- Analyzing Volume Profile for {safe_symbol} ---")
        results[safe_symbol] = {}
        
        # 1. Fetch data for the LONGEST period to establish a master price grid
        longest_lookback = sorted_lookbacks[0]
        logging.info(f"  Fetching full {longest_lookback}d dataset (approx 3 Years)...")
        
        full_df = fetch_ohlcv_for_profile(symbol, TIMEFRAME_FOR_PROFILE, lookback_days=longest_lookback)
        
        if full_df is None or full_df.empty:
            logging.warning(f"  Could not fetch base data for {symbol}. Skipping symbol.")
            continue
            
        # 2. Create the MASTER price bins from the full range
        overall_min_price = full_df['Low'].min()
        overall_max_price = full_df['High'].max()
        
        # Increased bins dynamically based on range might be better, but fixed is fine for now
        master_price_bins = np.linspace(overall_min_price, overall_max_price, NUM_BINS + 1)
        logging.info(f"  Master grid created: ${overall_min_price:,.2f} to ${overall_max_price:,.2f}")

        # 3. Iterate through all lookbacks, using slices of the full dataset
        for days in sorted_lookbacks:
            label = f'{days}d'
            # Add friendly labels for years
            if days == 365: label = '1y'
            if days == 730: label = '2y'
            if days == 1095: label = '3y'

            logging.info(f"  ... processing {label} ({days} days)")
            
            # Slice the DataFrame to the desired lookback period
            try:
                # Use pandas' `last` method for time-based slicing
                df_slice = full_df.last(f'{days}D')
                if df_slice.empty:
                    logging.warning(f"  Slice for {label} resulted in empty DataFrame. Skipping.")
                    continue
            except Exception as e:
                logging.error(f"  Error slicing DataFrame for {label}: {e}")
                continue

            # Calculate profile using the slice but with the MASTER bins
            profile_data = calculate_volume_profile(df_slice, master_price_bins)
            
            if profile_data:
                results[safe_symbol][label] = profile_data
            else:
                logging.warning(f"  Could not generate profile for {symbol} {label}.")
        
        time.sleep(1) # Be nice to the API between symbols

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
