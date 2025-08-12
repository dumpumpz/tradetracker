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
PIVOT_WINDOWS = [5, 8, 13, 21, 34, 55, 89, 144]
TOP_N_CLUSTERS_TO_SEND = 10
SR_OUTPUT_FILENAME = "sr_levels_analysis.json"
OPENS_OUTPUT_FILENAME = "market_opens.json" # START: ADDED FOR MARKET OPENS

# ### FIX 1 ### Drastically tighten the cluster threshold for more precise zones
CLUSTER_THRESHOLD_PERCENT = 0.12

# ### FIX 2 ### Use the more reliable international Binance API endpoint
API_ENDPOINT = "https://api.binance.us/api/v3/klines" # Use the US endpoint for data-heavy requests


# --- Weighting Systems ---
TIMEFRAME_WEIGHTS = {'15m': 1.0, '30m': 1.2, '1h': 1.5, '2h': 2.0, '4h': 2.5}
PIVOT_SOURCE_WEIGHTS = {'Wick': 1.0, 'Close': 1.5}
STRENGTH_CONFIG = {'VOLUME_STRENGTH_FACTOR': 1.0, 'RECENCY_HALFLIFE_DAYS': 45.0}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def get_safe_symbol(symbol):
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol

def get_minutes_from_timeframe(tf_string):
    num = int(re.findall(r'\d+', tf_string)[0])
    unit = re.findall(r'[a-zA-Z]', tf_string)[0].lower()
    if unit == 'm': return num
    elif unit == 'h': return num * 60
    elif unit == 'd': return num * 60 * 24
    elif unit == 'w': return num * 60 * 24 * 7
    elif unit.upper() == 'M': return num * 60 * 24 * 30 # Approximation for month
    return 0

def fetch_ohlcv_paginated(symbol, interval, lookback_days=None, limit=1000):
    # Modified to handle both lookback days and simple limit fetching
    all_data = []
    end_time_ms = None
    
    if lookback_days:
        minutes_per_tf = get_minutes_from_timeframe(interval)
        if minutes_per_tf == 0: return None
        total_candles_needed = (lookback_days * 1440) // minutes_per_tf
        logging.info(f"Fetching data for {symbol} on {interval}. Need ~{total_candles_needed} candles for {lookback_days} days.")
        
        while len(all_data) < total_candles_needed:
            url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
            if end_time_ms: url += f'&endTime={end_time_ms}'
            try:
                response = requests.get(url, timeout=20)
                response.raise_for_status()
                data_chunk = response.json()
                if not data_chunk:
                    logging.info(f"No more historical data for {symbol}, stopping.")
                    break
                all_data = data_chunk + all_data
                end_time_ms = data_chunk[0][0] - 1
                if len(data_chunk) < limit: break
                time.sleep(0.2)
            except requests.exceptions.RequestException as e:
                logging.error(f"Could not fetch data for {symbol} on {interval}: {e}")
                return None
        
        if not all_data: return None
        df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
        df = df.tail(total_candles_needed)
    else: # Simple fetch for a few candles
        url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            all_data = response.json()
            if not all_data: return None
            df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not fetch limited data for {symbol} on {interval}: {e}")
            return None

    df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
    df.set_index('Date', inplace=True)
    df.drop_duplicates(inplace=True)
    
    if lookback_days:
        logging.info(f"SUCCESS: Fetched {len(df)} candles for {symbol} on {interval}.")
    
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)


def find_pivots_scipy(data_series: pd.Series, window: int, is_high: bool):
    if window == 0 or len(data_series) <= 2 * window: return []
    comparator = np.greater if is_high else np.less
    pivot_indices = argrelextrema(data_series.values, comparator, order=window)[0]
    return [(data_series.index[i], data_series.iloc[i]) for i in pivot_indices]

def generate_pivots_for_timeframe(symbol, timeframe, lookback_days):
    df_ohlcv = fetch_ohlcv_paginated(symbol, timeframe, lookback_days=lookback_days)
    if df_ohlcv is None or df_ohlcv.empty: return pd.DataFrame()

    vol_min, vol_max = df_ohlcv['Volume'].min(), df_ohlcv['Volume'].max()
    df_ohlcv['Volume_Norm'] = 0.5 if vol_max <= vol_min else (df_ohlcv['Volume'] - vol_min) / (vol_max - vol_min)
    
    recency_lambda = np.log(2) / STRENGTH_CONFIG['RECENCY_HALFLIFE_DAYS']
    all_pivots_list = []
    pivot_definitions = {
        'High_Wick': (df_ohlcv['High'], True, 'Resistance', 'Wick'),
        'Low_Wick': (df_ohlcv['Low'], False, 'Support', 'Wick'),
        'Close_High': (df_ohlcv['Close'], True, 'Resistance', 'Close'),
        'Close_Low': (df_ohlcv['Close'], False, 'Support', 'Close')
    }
    timeframe_weight = TIMEFRAME_WEIGHTS.get(timeframe, 1.0)
    current_time_utc = datetime.now(timezone.utc)

    for window in PIVOT_WINDOWS:
        for name, (series, is_high, type_str, source) in pivot_definitions.items():
            source_weight = PIVOT_SOURCE_WEIGHTS.get(source, 1.0)
            for timestamp, price in find_pivots_scipy(series, window, is_high):
                base_strength = window * timeframe_weight * source_weight
                days_ago = (current_time_utc - timestamp).total_seconds() / 86400
                recency_weight = np.exp(-recency_lambda * days_ago)
                volume_weight = 1 + (df_ohlcv.loc[timestamp]['Volume_Norm'] * STRENGTH_CONFIG['VOLUME_STRENGTH_FACTOR'])
                final_strength = base_strength * recency_weight * volume_weight
                all_pivots_list.append({'Timestamp': timestamp, 'Price': price, 'Strength': final_strength, 'Type': type_str, 'Source': source, 'Timeframe': timeframe})
    
    return pd.DataFrame(all_pivots_list)

def find_clusters_dbscan(pivots_df: pd.DataFrame, threshold_percent: float):
    if pivots_df.empty: return []
    prices = pivots_df['Price'].values.reshape(-1, 1)
    if len(prices) == 0: return []
    avg_price = np.mean(prices)
    epsilon = avg_price * (threshold_percent / 100.0)
    db = DBSCAN(eps=epsilon, min_samples=1).fit(prices)
    pivots_df['cluster_id'] = db.labels_
    
    clusters = []
    for cluster_id in sorted(pivots_df['cluster_id'].unique()):
        cluster_df = pivots_df[pivots_df['cluster_id'] == cluster_id]
        if cluster_df.empty: continue
        clusters.append({
            'Type': str(cluster_df['Type'].iloc[0]),
            'Price Start': float(cluster_df['Price'].min()),
            'Price End': float(cluster_df['Price'].max()),
            'Strength Score': int(cluster_df['Strength'].sum()),
            'Pivot Count': len(cluster_df)
        })
    return clusters

def run_analysis_for_lookback(symbol, lookback_days):
    logging.info(f"--- Running S/R Analysis for {symbol} with {lookback_days}-Day Lookback ---")
    all_pivots_dfs = [df for tf in TIMEFRAMES_TO_ANALYZE if not (df := generate_pivots_for_timeframe(symbol, tf, lookback_days)).empty]
    if not all_pivots_dfs:
        logging.warning(f"No pivot data for {symbol} at {lookback_days} days.")
        return None

    pivots_data = pd.concat(all_pivots_dfs, ignore_index=True)
    support_clusters = sorted(find_clusters_dbscan(pivots_data[pivots_data['Type'] == 'Support'].copy(), CLUSTER_THRESHOLD_PERCENT), key=lambda x: x['Strength Score'], reverse=True)
    resistance_clusters = sorted(find_clusters_dbscan(pivots_data[pivots_data['Type'] == 'Resistance'].copy(), CLUSTER_THRESHOLD_PERCENT), key=lambda x: x['Strength Score'], reverse=True)

    return {
        'support': support_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'resistance': resistance_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'analysis_params': {
            'timeframes_analyzed': TIMEFRAMES_TO_ANALYZE, 'pivot_windows': PIVOT_WINDOWS,
            'lookback_days': lookback_days,
            'oldest_pivot_date': pivots_data['Timestamp'].min().strftime('%Y-%m-%d'),
            'newest_pivot_date': pivots_data['Timestamp'].max().strftime('%Y-%m-%d')
        }
    }

# START: ADDED FOR MARKET OPENS
def get_open_prices():
    """
    Fetches the latest daily, weekly, and monthly open prices for configured symbols.
    """
    logging.info("\n--- Fetching Key Market Open Prices ---")
    timeframes = {'daily': '1d', 'weekly': '1w', 'monthly': '1M'}
    all_opens = {}

    for symbol in SYMBOLS:
        symbol_opens = {}
        logging.info(f"Fetching opens for {symbol}...")
        for tf_name, tf_code in timeframes.items():
            try:
                # Fetch just the last 2 candles to get the current open
                df = fetch_ohlcv_paginated(symbol, tf_code, limit=2)
                if df is not None and not df.empty:
                    # The latest (current) candle is the last row
                    open_price = df['Open'].iloc[-1]
                    symbol_opens[tf_name] = open_price
                    logging.info(f"  - {symbol} {tf_name.capitalize()} Open: {open_price}")
                else:
                    logging.warning(f"  - Could not fetch {tf_name} for {symbol}. Setting open to 0.")
                    symbol_opens[tf_name] = 0
            except Exception as e:
                logging.error(f"  - Error fetching {tf_name} for {symbol}: {e}")
                symbol_opens[tf_name] = 0
        
        safe_symbol = get_safe_symbol(symbol)
        all_opens[safe_symbol] = symbol_opens
            
    output_data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "opens": all_opens
    }
    
    try:
        with open(OPENS_OUTPUT_FILENAME, 'w') as f:
            json.dump(output_data, f, indent=4)
        logging.info(f"SUCCESS: Market open data has been saved to {OPENS_OUTPUT_FILENAME}.")
    except IOError as e:
        logging.error(f"FATAL: Could not write to file {OPENS_OUTPUT_FILENAME}. Error: {e}")

# END: ADDED FOR MARKET OPENS


def main():
    # --- Part 1: S/R Analysis ---
    analysis_payload = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}
        for days in LOOKBACK_PERIODS_DAYS:
            analysis_result = run_analysis_for_lookback(symbol, days)
            if analysis_result:
                analysis_payload[safe_symbol][f'{days}d'] = analysis_result
            time.sleep(1)
    
    if analysis_payload:
        full_payload = {
            'last_updated': datetime.now(timezone.utc).isoformat(), # Simplified metadata
            'data': analysis_payload
        }
        logging.info(f"\nWriting S/R level payload to {SR_OUTPUT_FILENAME}...")
        try:
            with open(SR_OUTPUT_FILENAME, 'w') as json_file:
                json.dump(full_payload, json_file, indent=4)
            logging.info(f"SUCCESS: S/R level data has been saved to {SR_OUTPUT_FILENAME}.")
        except IOError as e:
            logging.error(f"FATAL: Could not write to file {SR_OUTPUT_FILENAME}. Error: {e}")
            sys.exit(1)
    else:
        logging.warning("No S/R data was generated to save.")
    
    # --- Part 2: Market Opens Analysis ---
    get_open_prices()

    logging.info("\n--- All Analyses Complete ---")

if __name__ == "__main__":
    main()

