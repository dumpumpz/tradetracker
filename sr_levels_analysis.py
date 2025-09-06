import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, timezone
import re
import time
import logging
import sys
from typing import Optional, List, Any, Dict
from scipy.signal import argrelextrema
from sklearn.cluster import DBSCAN

# --- Unified Configuration ---
SYMBOLS = ['BTCUSDT', 'ETHUSDT']
TIMEFRAMES_TO_ANALYZE = ['15m', '30m', '1h', '2h', '4h']
LOOKBACK_PERIODS_DAYS = [60, 30, 21, 14, 7, 3, 2]
BASE_PIVOT_WINDOWS = [5, 8, 13, 21, 34]
TOP_N_CLUSTERS_TO_SEND = 10
SR_OUTPUT_FILENAME = "sr_levels_analysis.json"
OPENS_OUTPUT_FILENAME = "market_opens.json"

# --- NEW PARAMETERS ---
BASE_EPS_PERCENTAGE_RANGE = 0.0007   # Base epsilon (0.07%)
MIN_SAMPLES_FOR_CLUSTER = 3
ATR_LOOKBACK = 14
ATR_VOL_MULTIPLIER = 1.5  # Expand pivots when ATR is high
LIQUIDITY_VOLUME_MULTIPLIER = 1.2  # Above-average volume filter

# Weighting Systems
TIMEFRAME_WEIGHTS = {'15m': 1.0, '30m': 1.2, '1h': 1.5, '2h': 2.0, '4h': 2.5}
PIVOT_SOURCE_WEIGHTS = {'Wick': 1.0, 'Close': 1.5}
STRENGTH_CONFIG = {'VOLUME_STRENGTH_FACTOR': 1.0, 'RECENCY_HALFLIFE_DAYS': 45.0}

API_ENDPOINT = "https://api.binance.com/api/v3/klines"

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0'
})
DEFAULT_TIMEOUT = 20


def get_safe_symbol(symbol):
    # For display/keys only
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol


def get_minutes_from_timeframe(tf_string):
    num_match = re.search(r'\d+', tf_string)
    unit_match = re.search(r'[a-zA-Z]', tf_string)
    if not num_match or not unit_match:
        return 0
    num = int(num_match.group(0))
    unit = unit_match.group(0).lower()
    return num if unit == 'm' else num * 60 if unit == 'h' else num * 60 * 24 if unit == 'd' else num * 60 * 24 * 7


def fetch_ohlcv_paginated(symbol, interval, lookback_days=None, limit=1000):
    all_data = []
    end_time_ms = None
    df = pd.DataFrame()
    try:
        if lookback_days:
            minutes_per_tf = get_minutes_from_timeframe(interval)
            total_candles_needed = (lookback_days * 1440) // minutes_per_tf
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
            # Ensure we don't have more data than needed, which can happen with pagination logic
            df = df.tail(int(total_candles_needed))
        else:
            url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
            r = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
            r.raise_for_status()
            df = pd.DataFrame(r.json(), columns=[
                'Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time',
                'Quote asset volume', 'Number of trades', 'Taker buy base asset volume',
                'Taker buy quote asset volume', 'Ignore'
            ])
        if df.empty:
            return None

        df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        df.set_index('Date', inplace=True)
        # Ensure numeric
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'], inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        logging.error(f'Error fetching {symbol} {interval}: {e}')
        return None


def get_market_opens(symbols_list: List[str]) -> Dict[str, Dict[str, float]]:
    """
    Fetches the current daily, weekly, and monthly open prices for a list of symbols.
    """
    opens_data = {}
    timeframes_map = {'daily': '1d', 'weekly': '1w', 'monthly': '1M'}

    for symbol in symbols_list:
        logging.info(f"Fetching D/W/M opens for {symbol}...")
        symbol_opens = {}
        safe_symbol = get_safe_symbol(symbol)
        
        for name, tf in timeframes_map.items():
            # We only need the most recent candle to get the open price
            df = fetch_ohlcv_paginated(symbol, tf, limit=2) 
            if df is not None and not df.empty:
                # The last row is the current, forming candle. Its 'Open' is what we need.
                current_open = df['Open'].iloc[-1]
                symbol_opens[name] = float(current_open)
                logging.info(f"  {symbol} {name} ({tf}) open: {current_open}")
            else:
                logging.warning(f"  Could not fetch {name} open for {symbol}")
                symbol_opens[name] = None # Or handle as an error
            time.sleep(0.5) # Be nice to the API

        if symbol_opens:
            opens_data[safe_symbol] = symbol_opens
            
    return opens_data


def calc_atr(df, period=ATR_LOOKBACK):
    if df is None or df.empty:
        return pd.Series(dtype=float)
    hl = df['High'] - df['Low']
    hc = (df['High'] - df['Close'].shift(1)).abs()
    lc = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=max(2, period // 2)).mean()


def find_pivots_scipy(series, window, is_high):
    if len(series) < (2 * window + 1):
        return []
    comp = np.greater if is_high else np.less
    idxs = argrelextrema(series.values, comp, order=window)[0]
    return [(series.index[i], series.iloc[i]) for i in idxs]


def generate_pivots_for_timeframe(symbol, timeframe, lookback_days, atr_percent):
    df = fetch_ohlcv_paginated(symbol, timeframe, lookback_days=lookback_days)
    if df is None or df.empty:
        return pd.DataFrame()

    # Normalized volume (guard zero division)
    vol_min, vol_max = df['Volume'].min(), df['Volume'].max()
    if vol_max > vol_min:
        df['Volume_Norm'] = (df['Volume'] - vol_min) / (vol_max - vol_min)
    else:
        df['Volume_Norm'] = 0.5

    recency_lambda = np.log(2) / max(1e-9, STRENGTH_CONFIG['RECENCY_HALFLIFE_DAYS'])
    all_pivots = []

    # Adaptive windows
    if atr_percent > 0.03:  # high volatility
        pivot_windows = [max(2, int(round(w * ATR_VOL_MULTIPLIER))) for w in BASE_PIVOT_WINDOWS]
    else:
        pivot_windows = BASE_PIVOT_WINDOWS

    pivot_defs = {
        'High_Wick': (df['High'], True, 'Resistance', 'Wick'),
        'Low_Wick': (df['Low'], False, 'Support', 'Wick'),
        'Close_High': (df['Close'], True, 'Resistance', 'Close'),
        'Close_Low': (df['Close'], False, 'Support', 'Close')
    }
    tf_weight = TIMEFRAME_WEIGHTS.get(timeframe, 1.0)
    now = datetime.now(timezone.utc)

    for window in pivot_windows:
        for name, (series, is_high, ptype, source) in pivot_defs.items():
            s_weight = PIVOT_SOURCE_WEIGHTS.get(source, 1.0)
            pivots = find_pivots_scipy(series, window, is_high)
            for ts, price in pivots:
                base_strength = window * tf_weight * s_weight
                days_ago = (now - ts).total_seconds() / 86400.0
                recency_weight = float(np.exp(-recency_lambda * days_ago))
                volume_weight = 1.0 + (float(df.loc[ts, 'Volume_Norm']) * STRENGTH_CONFIG['VOLUME_STRENGTH_FACTOR'])
                final_strength = base_strength * recency_weight * volume_weight
                all_pivots.append({
                    'Timestamp': ts, 'Price': float(price), 'Strength': float(final_strength),
                    'Type': ptype, 'Source': source, 'Timeframe': timeframe,
                    'Volume': float(df.loc[ts, 'Volume']),
                    'Close': float(df.loc[ts, 'Close']),
                    'Open': float(df.loc[ts, 'Open'])
                })
    return pd.DataFrame(all_pivots)


def is_reversal(pivot_row):
    return ((pivot_row['Type'] == 'Resistance' and pivot_row['Close'] < pivot_row['Open']) or
            (pivot_row['Type'] == 'Support' and pivot_row['Close'] > pivot_row['Open']))


def find_clusters_dbscan(pivots_df, symbol, atr_percent):
    if pivots_df.empty or len(pivots_df) < MIN_SAMPLES_FOR_CLUSTER:
        return []

    avg_price = float(np.mean(pivots_df['Price']))
    # Adaptive epsilon; keep a reasonable floor to avoid epsilon=0
    eps_pct = BASE_EPS_PERCENTAGE_RANGE * max(0.25, (atr_percent / 0.01))  # floor at 0.25x base
    epsilon = max(1e-6, avg_price * eps_pct)
    
    pivots_df = pivots_df.copy()
    db = DBSCAN(eps=epsilon, min_samples=MIN_SAMPLES_FOR_CLUSTER).fit(
        pivots_df['Price'].values.reshape(-1, 1)
    )
    pivots_df['cluster_id'] = db.labels_

    clusters = []
    for cid in sorted(pivots_df['cluster_id'].unique()):
        if cid == -1:
            continue
        cdf = pivots_df[pivots_df['cluster_id'] == cid]

        avg_vol = pivots_df['Volume'].mean()
        if not any(cdf['Volume'] > avg_vol * LIQUIDITY_VOLUME_MULTIPLIER):
            continue
        if not any(cdf.apply(is_reversal, axis=1)):
            continue

        weighted_avg_price = float(np.average(cdf['Price'], weights=np.maximum(cdf['Strength'], 1e-9)))
        clusters.append({
            'Type': cdf['Type'].iloc[0],
            'Price Start': float(cdf['Price'].min()),
            'Price End': float(cdf['Price'].max()),
            'Center Price': float(round(weighted_avg_price, 2)),
            'Strength Score': float(cdf['Strength'].sum()),
            'Pivot Count': int(len(cdf))
        })
    return clusters


def run_analysis_for_lookback(symbol, days):
    df_for_atr = fetch_ohlcv_paginated(symbol, '1h', lookback_days=days)
    if df_for_atr is None or df_for_atr.empty:
        logging.warning(f'No ATR data for {symbol} lookback {days}d')
        return None

    atr_series = calc_atr(df_for_atr)
    if atr_series.empty:
        logging.warning(f'ATR series empty for {symbol} {days}d; skipping.')
        return None
        
    atr_val = atr_series.iloc[-1] if not atr_series.empty else np.nan
    if np.isnan(atr_val) or df_for_atr['Close'].iloc[-1] == 0:
        logging.warning(f'ATR NaN/invalid for {symbol} {days}d; skipping.')
        return None

    atr_percent = float(atr_val / df_for_atr['Close'].iloc[-1])

    all_pivots = []
    for tf in TIMEFRAMES_TO_ANALYZE:
        pivots = generate_pivots_for_timeframe(symbol, tf, days, atr_percent)
        if not pivots.empty:
            max_s = pivots['Strength'].max()
            if max_s and max_s > 0:
                pivots['Strength'] = pivots['Strength'] / max_s
            all_pivots.append(pivots)

    if not all_pivots:
        return None

    pivots_df = pd.concat(all_pivots, ignore_index=True)

    support_clusters = sorted(
        find_clusters_dbscan(pivots_df[pivots_df['Type'] == 'Support'], symbol, atr_percent),
        key=lambda x: x['Strength Score'], reverse=True
    )
    resistance_clusters = sorted(
        find_clusters_dbscan(pivots_df[pivots_df['Type'] == 'Resistance'], symbol, atr_percent),
        key=lambda x: x['Strength Score'], reverse=True
    )

    return {
        'support': support_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'resistance': resistance_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'analysis_params': {
            'timeframes_analyzed': TIMEFRAMES_TO_ANALYZE,
            'lookback_days': days,
            'atr_percent': atr_percent
        }
    }


def main():
    # --- Part 1: S/R Level Analysis ---
    logging.info("===== STARTING ADAPTIVE S/R ANALYSIS =====")
    results = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        logging.info(f"--- Analyzing S/R for {safe_symbol} ---")
        for days in LOOKBACK_PERIODS_DAYS:
            logging.info(f"  ... using {days}d lookback period.")
            res = run_analysis_for_lookback(symbol, days)
            if res:
                if safe_symbol not in results:
                    results[safe_symbol] = {}
                results[safe_symbol][f'{days}d'] = res
            time.sleep(1) # Be nice to the API

    try:
        sr_payload = {'data': results, 'last_updated': datetime.now(timezone.utc).isoformat()}
        with open(SR_OUTPUT_FILENAME, 'w') as f:
            json.dump(sr_payload, f, indent=4)
        logging.info(f"S/R analysis complete. Saved to {SR_OUTPUT_FILENAME}")
    except IOError as e:
        logging.error(f"Could not write to file {SR_OUTPUT_FILENAME}: {e}")

    # --- Part 2: Market Opens Analysis ---
    logging.info("===== STARTING MARKET OPENS ANALYSIS =====")
    market_opens_data = get_market_opens(SYMBOLS)
    
    if market_opens_data:
        try:
            opens_payload = {
                'last_updated': datetime.now(timezone.utc).isoformat(),
                'opens': market_opens_data
            }
            with open(OPENS_OUTPUT_FILENAME, 'w') as f:
                json.dump(opens_payload, f, indent=4)
            logging.info(f"Market opens data saved to {OPENS_OUTPUT_FILENAME}")
        except IOError as e:
            logging.error(f"Could not write to file {OPENS_OUTPUT_FILENAME}: {e}")
    else:
        logging.error("Failed to fetch any market open data. File not written.")

    logging.info("===== ALL ANALYSIS COMPLETE =====")

    ### THIS IS THE FIX ###
    # This line explicitly closes all connections in the session pool,
    # allowing the Python process to terminate cleanly and immediately.
    logging.info("Closing network session...")
    SESSION.close()


if __name__ == "__main__":
    main()
