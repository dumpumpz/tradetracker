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

# ### NEW ### Import necessary libraries for performance and advanced analysis
from scipy.signal import argrelextrema
from sklearn.cluster import DBSCAN

# --- Unified Configuration ---
SYMBOLS = ['BTCUSDT', 'ETHUSDT']
TIMEFRAMES_TO_ANALYZE = ['15m', '30m', '1h', '2h', '4h']
# ### FIX ### Adjusted lookback periods to match the dropdown in your HTML
LOOKBACK_PERIODS_DAYS = [60, 30, 21, 14, 7, 3, 2]
CLUSTER_THRESHOLD_PERCENT = 0.5
TOP_N_CLUSTERS_TO_SEND = 10
# ### FIX ### Changed filename to match what the JavaScript fetches
OUTPUT_FILENAME = "sr_levels_analysis.json"

# ### MODIFIED ### Using an extended Fibonacci sequence for a wider range of market structures
PIVOT_WINDOWS = [5, 8, 13, 21, 34, 55, 89, 144]

# --- Timeframe Weighting System ---
TIMEFRAME_WEIGHTS = {
    '15m': 1.0, '30m': 1.2, '1h': 1.5, '2h': 2.0, '4h': 2.5
}

# --- PIVOT SOURCE WEIGHTING SYSTEM ---
PIVOT_SOURCE_WEIGHTS = {
    'Wick': 1.0, 'Close': 1.5
}

# ### NEW ### Configuration for advanced strength scoring
STRENGTH_CONFIG = {
    # How much more strength a pivot on high volume gets. 1.0 means volume can double the score.
    'VOLUME_STRENGTH_FACTOR': 1.0,
    # The "half-life" of a pivot's relevance in days. A pivot from 45 days ago will have half the recency score.
    'RECENCY_HALFLIFE_DAYS': 45.0
}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


# ### FIX ### Added this function to create JS-friendly keys like "BTC-USDT"
def get_safe_symbol(symbol):
    """Converts an API symbol like BTCUSDT to a JS-friendly one like BTC-USDT."""
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol


def get_minutes_from_timeframe(tf_string):
    num = int(re.findall(r'\d+', tf_string)[0])
    unit = re.findall(r'[a-zA-Z]', tf_string)[0].lower()
    if unit == 'm': return num
    elif unit == 'h': return num * 60
    elif unit == 'd': return num * 60 * 24
    return 0

def fetch_ohlcv_paginated(symbol, interval, lookback_days):
    minutes_per_tf = get_minutes_from_timeframe(interval)
    if minutes_per_tf == 0:
        logging.error(f"Invalid timeframe provided: {interval}")
        return None
    total_candles_needed = (lookback_days * 1440) // minutes_per_tf
    all_data = []
    end_time_ms = None
    limit_per_req = 1000
    logging.info(f"Fetching data for {symbol} on {interval}. Need ~{total_candles_needed} candles for {lookback_days} days.")
    while len(all_data) < total_candles_needed:
        url = f'https://api.binance.us/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit_per_req}'
        if end_time_ms: url += f'&endTime={end_time_ms}'
        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data_chunk = response.json()
            if not data_chunk:
                logging.info(f"No more historical data for {symbol}, stopping pagination.")
                break
            all_data = data_chunk + all_data
            end_time_ms = data_chunk[0][0] - 1
            if len(data_chunk) < limit_per_req: break
            time.sleep(0.2)
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not fetch data for {symbol} on {interval}: {e}")
            return None
    if not all_data: return None
    df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
    df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
    df.set_index('Date', inplace=True)
    df.drop_duplicates(inplace=True)
    final_df = df.tail(total_candles_needed)
    logging.info(f"SUCCESS: Fetched {len(final_df)} candles for {symbol} on {interval}.")
    return final_df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)


def find_pivots_scipy(data_series: pd.Series, window: int, is_high: bool):
    """
    Finds pivot points (local maxima/minima) using scipy.signal.argrelextrema
    for significantly better performance than a Python loop.
    """
    if window == 0 or len(data_series) <= 2 * window: return []
    comparator = np.greater if is_high else np.less
    pivot_indices = argrelextrema(data_series.values, comparator, order=window)[0]
    return [(data_series.index[i], data_series.iloc[i]) for i in pivot_indices]


def generate_pivots_for_timeframe(symbol, timeframe, lookback_days):
    df_ohlcv = fetch_ohlcv_paginated(symbol, timeframe, lookback_days)
    if df_ohlcv is None or df_ohlcv.empty: return pd.DataFrame()

    vol_min = df_ohlcv['Volume'].min()
    vol_max = df_ohlcv['Volume'].max()
    if vol_max > vol_min:
        df_ohlcv['Volume_Norm'] = (df_ohlcv['Volume'] - vol_min) / (vol_max - vol_min)
    else:
        df_ohlcv['Volume_Norm'] = 0.5

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
        for pivot_name, (series, is_high, type_str, source) in pivot_definitions.items():
            source_weight = PIVOT_SOURCE_WEIGHTS.get(source, 1.0)
            for timestamp, price in find_pivots_scipy(series, window, is_high):
                base_strength = window * timeframe_weight * source_weight
                days_ago = (current_time_utc - timestamp).total_seconds() / 86400
                recency_weight = np.exp(-recency_lambda * days_ago)
                volume_at_pivot = df_ohlcv.loc[timestamp]['Volume_Norm']
                volume_weight = 1 + (volume_at_pivot * STRENGTH_CONFIG['VOLUME_STRENGTH_FACTOR'])
                final_strength = base_strength * recency_weight * volume_weight
                
                all_pivots_list.append({
                    'Timestamp': timestamp, 'Price': price, 'Strength': final_strength,
                    'Type': type_str, 'Source': source, 'Timeframe': timeframe
                })
    return pd.DataFrame(all_pivots_list)


def find_clusters_dbscan(pivots_df: pd.DataFrame, threshold_percent: float):
    """
    Groups pivots into dense clusters (zones) using the DBSCAN algorithm.
    """
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
    logging.info(f"--- Running Analysis for {symbol} with {lookback_days}-Day Lookback ---")
    all_pivots_dfs = []
    for tf in TIMEFRAMES_TO_ANALYZE:
        pivots_df = generate_pivots_for_timeframe(symbol, tf, lookback_days)
        if not pivots_df.empty: all_pivots_dfs.append(pivots_df)
        time.sleep(0.5)

    if not all_pivots_dfs:
        logging.warning(f"No pivot data for {symbol} at {lookback_days} days.")
        return None

    pivots_data = pd.concat(all_pivots_dfs, ignore_index=True)
    support_clusters = find_clusters_dbscan(pivots_data[pivots_data['Type'] == 'Support'].copy(), CLUSTER_THRESHOLD_PERCENT)
    resistance_clusters = find_clusters_dbscan(pivots_data[pivots_data['Type'] == 'Resistance'].copy(), CLUSTER_THRESHOLD_PERCENT)
    support_clusters.sort(key=lambda x: x['Strength Score'], reverse=True)
    resistance_clusters.sort(key=lambda x: x['Strength Score'], reverse=True)

    return {
        'support': support_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'resistance': resistance_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'analysis_params': {
            'timeframes_analyzed': TIMEFRAMES_TO_ANALYZE,
            'pivot_windows': PIVOT_WINDOWS,
            'lookback_days': lookback_days,
            'oldest_pivot_date': pivots_data['Timestamp'].min().strftime('%Y-%m-%d'),
            'newest_pivot_date': pivots_data['Timestamp'].max().strftime('%Y-%m-%d')
        }
    }


def main():
    analysis_payload = {}
    for symbol in SYMBOLS:
        # ### FIX ### Use the safe symbol for the JSON key to match JavaScript's expectation
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}
        
        for days in LOOKBACK_PERIODS_DAYS:
            # Fetch data using the original API symbol (e.g., "BTCUSDT")
            analysis_result = run_analysis_for_lookback(symbol, days)
            if analysis_result:
                # Store the result under the safe key (e.g., "BTC-USDT")
                analysis_payload[safe_symbol][f'{days}d'] = analysis_result
            time.sleep(1)

    if analysis_payload:
        full_payload = {
            'metadata': {
                'description': "Support/Resistance analysis using multi-timeframe pivots, advanced strength scoring (recency, volume), and DBSCAN clustering.",
                'last_updated_utc': datetime.now(timezone.utc).isoformat()
            },
            'data': analysis_payload
        }

        logging.info(f"\nWriting S/R level payload to {OUTPUT_FILENAME}...")
        try:
            with open(OUTPUT_FILENAME, 'w') as json_file:
                json.dump(full_payload, json_file, indent=4)
            logging.info(f"SUCCESS: S/R level data has been saved to {OUTPUT_FILENAME}.")
        except IOError as e:
            logging.error(f"FATAL: Could not write to file {OUTPUT_FILENAME}. Error: {e}")
            sys.exit(1)
    else:
        logging.warning("No S/R data was generated to save.")
    logging.info("\n--- All Analyses Complete ---")


if __name__ == "__main__":
    main()
