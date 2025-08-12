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
OPENS_OUTPUT_FILENAME = "market_opens.json"

# DYNAMIC CLUSTER MERGE RANGE (percentage)
EPS_PERCENTAGE_RANGE = 0.0025

# Use the primary, global Binance API endpoint. The VPN will handle access.
API_ENDPOINT = "https://api.binance.com/api/v3/klines"

# --- Weighting Systems ---
TIMEFRAME_WEIGHTS = {'15m': 1.0, '30m': 1.2, '1h': 1.5, '2h': 2.0, '4h': 2.5}
PIVOT_SOURCE_WEIGHTS = {'Wick': 1.0, 'Close': 1.5}
STRENGTH_CONFIG = {'VOLUME_STRENGTH_FACTOR': 1.0, 'RECENCY_HALFLIFE_DAYS': 45.0}

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# --- Session Setup for API Requests ---
# Use a session for connection pooling and to set a user-agent
SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})


def get_safe_symbol(symbol):
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol

def get_minutes_from_timeframe(tf_string):
    num_match = re.search(r'\d+', tf_string)
    unit_match = re.search(r'[a-zA-Z]', tf_string)
    if not num_match or not unit_match:
        return 0
    num = int(num_match.group(0))
    unit = unit_match.group(0).lower()
    if unit == 'm': return num
    elif unit == 'h': return num * 60
    elif unit == 'd': return num * 60 * 24
    elif unit == 'w': return num * 60 * 24 * 7
    return 0

def fetch_ohlcv_paginated(symbol, interval, lookback_days=None, limit=1000):
    all_data = []
    end_time_ms = None
    df = pd.DataFrame() # Initialize empty dataframe

    try:
        if lookback_days:
            minutes_per_tf = get_minutes_from_timeframe(interval)
            if minutes_per_tf == 0:
                logging.error(f"Invalid timeframe string: {interval}")
                return None
            total_candles_needed = (lookback_days * 1440) // minutes_per_tf
            logging.info(f"Fetching data for {symbol} on {interval}. Need ~{total_candles_needed} candles for {lookback_days} days.")

            while len(all_data) < total_candles_needed:
                url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
                if end_time_ms:
                    url += f'&endTime={end_time_ms}'
                
                response = SESSION.get(url, timeout=20)
                response.raise_for_status() # Will raise HTTPError for bad responses (4XX or 5XX)
                data_chunk = response.json()
                
                if not data_chunk:
                    logging.info(f"No more historical data for {symbol} on {interval} from Binance. Stopping pagination.")
                    break
                
                all_data = data_chunk + all_data
                end_time_ms = data_chunk[0][0] - 1
                if len(data_chunk) < limit:
                    break
                time.sleep(0.3)

            if not all_data:
                 logging.warning(f"No data was returned from API for {symbol} on {interval} with lookback.")
                 return None

            df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
            df = df.tail(total_candles_needed) # Trim to the exact lookback
        
        else:  # Simple fetch (for market opens)
            url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
            response = SESSION.get(url, timeout=10)
            response.raise_for_status()
            all_data = response.json()
            if not all_data:
                logging.warning(f"No limited data returned for {symbol} on {interval}.")
                return None
            df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])

        df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        df.set_index('Date', inplace=True)
        df.drop_duplicates(inplace=True)
        if lookback_days:
            logging.info(f"SUCCESS: Fetched and processed {len(df)} candles for {symbol} on {interval}.")
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)

    except requests.exceptions.RequestException as e:
        logging.error(f"API REQUEST FAILED for {symbol} on {interval}. Error: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during data fetching for {symbol} on {interval}: {e}")
        return None


def find_pivots_scipy(data_series: pd.Series, window: int, is_high: bool):
    if window == 0 or len(data_series) <= 2 * window:
        return []
    comparator = np.greater if is_high else np.less
    pivot_indices = argrelextrema(data_series.values, comparator, order=window)[0]
    return [(data_series.index[i], data_series.iloc[i]) for i in pivot_indices]

def generate_pivots_for_timeframe(symbol, timeframe, lookback_days):
    df_ohlcv = fetch_ohlcv_paginated(symbol, timeframe, lookback_days=lookback_days)
    if df_ohlcv is None or df_ohlcv.empty:
        # The fetch function now logs the specific reason for failure, so no extra log here is needed.
        return pd.DataFrame()

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
            pivots = find_pivots_scipy(series, window, is_high)
            for timestamp, price in pivots:
                base_strength = window * timeframe_weight * source_weight
                days_ago = (current_time_utc - timestamp).total_seconds() / 86400
                recency_weight = np.exp(-recency_lambda * days_ago)
                volume_weight = 1 + (df_ohlcv.loc[timestamp]['Volume_Norm'] * STRENGTH_CONFIG['VOLUME_STRENGTH_FACTOR'])
                final_strength = base_strength * recency_weight * volume_weight
                all_pivots_list.append({
                    'Timestamp': timestamp,
                    'Price': price,
                    'Strength': final_strength,
                    'Type': type_str,
                    'Source': source,
                    'Timeframe': timeframe
                })
    
    if not all_pivots_list:
        logging.warning(f"No pivots were generated for {symbol} on {timeframe} with {lookback_days}-day lookback, despite receiving data.")
        return pd.DataFrame()
        
    logging.info(f"Generated {len(all_pivots_list)} pivots for {symbol} on {timeframe} ({lookback_days} days).")
    return pd.DataFrame(all_pivots_list)

def find_clusters_dbscan(pivots_df: pd.DataFrame, symbol: str):
    if pivots_df.empty or len(pivots_df) < 2:
        return []
    
    prices = pivots_df['Price'].values.reshape(-1, 1)
    average_price = np.mean(prices)
    if average_price <= 0:
        logging.warning(f"Could not calculate average price for clustering on {symbol}. Skipping.")
        return []
        
    epsilon = average_price * EPS_PERCENTAGE_RANGE
    cluster_type = pivots_df['Type'].iloc[0]
    logging.info(f"DBSCAN for {symbol} {cluster_type}: Avg Price=${average_price:,.2f}, Epsilon (merge range)=${epsilon:.2f} ({EPS_PERCENTAGE_RANGE:.2%})")

    db = DBSCAN(eps=epsilon, min_samples=1).fit(prices)
    pivots_df['cluster_id'] = db.labels_
    clusters = []
    
    for cluster_id in sorted(pivots_df['cluster_id'].unique()):
        cluster_df = pivots_df[pivots_df['cluster_id'] == cluster_id]
        if cluster_df.empty:
            continue
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
    
    all_pivots_dfs = []
    # Using a standard loop instead of list comprehension for better logging
    for tf in TIMEFRAMES_TO_ANALYZE:
        df = generate_pivots_for_timeframe(symbol, tf, lookback_days)
        if not df.empty:
            all_pivots_dfs.append(df)
        # Failure to generate pivots is now logged inside generate_pivots_for_timeframe

    if not all_pivots_dfs:
        logging.warning(f"No pivot data was generated for ANY timeframe for {symbol} at {lookback_days} days. Aborting this lookback.")
        return None
        
    pivots_data = pd.concat(all_pivots_dfs, ignore_index=True)
    if pivots_data.empty:
        logging.error(f"Concatenated pivot data is empty for {symbol} at {lookback_days} days. This should not happen if all_pivots_dfs was not empty.")
        return None

    logging.info(f"Total pivots collected for {symbol} ({lookback_days} days) across all timeframes: {len(pivots_data)}")
    
    support_clusters = sorted(find_clusters_dbscan(pivots_data[pivots_data['Type'] == 'Support'].copy(), symbol), key=lambda x: x['Strength Score'], reverse=True)
    resistance_clusters = sorted(find_clusters_dbscan(pivots_data[pivots_data['Type'] == 'Resistance'].copy(), symbol), key=lambda x: x['Strength Score'], reverse=True)
    
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

def get_open_prices():
    logging.info("\n--- Fetching Key Market Open Prices ---")
    timeframes = {'daily': '1d', 'weekly': '1w', 'monthly': '1M'}
    all_opens = {}
    for symbol in SYMBOLS:
        symbol_opens = {}
        logging.info(f"Fetching opens for {symbol}...")
        for tf_name, tf_code in timeframes.items():
            # Binance API uses '1M' for month, not '1m' which is minute.
            df = fetch_ohlcv_paginated(symbol, tf_code, limit=2)
            if df is not None and not df.empty and len(df) > 0:
                # .iloc[-1] gets the open of the current, forming candle
                current_open = df['Open'].iloc[-1]
                symbol_opens[tf_name] = current_open
                logging.info(f"  - {symbol} {tf_name.capitalize()} Open: {current_open}")
            else:
                symbol_opens[tf_name] = 0
                logging.warning(f"  - Could not fetch {tf_name.capitalize()} open for {symbol}.")
        safe_symbol = get_safe_symbol(symbol)
        all_opens[safe_symbol] = symbol_opens
        
    output_data = {"last_updated": datetime.now(timezone.utc).isoformat(), "opens": all_opens}
    try:
        with open(OPENS_OUTPUT_FILENAME, 'w') as f:
            json.dump(output_data, f, indent=4)
        logging.info(f"SUCCESS: Market open data saved to {OPENS_OUTPUT_FILENAME}.")
    except IOError as e:
        logging.error(f"FATAL: Could not write file '{OPENS_OUTPUT_FILENAME}'. Error: {e}")

def main():
    logging.info("===== STARTING S/R AND MARKET OPENS ANALYSIS =====")
    # --- Part 1: S/R Analysis ---
    analysis_payload = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        symbol_has_data = False
        for days in LOOKBACK_PERIODS_DAYS:
            analysis_result = run_analysis_for_lookback(symbol, days)
            if analysis_result:
                if safe_symbol not in analysis_payload:
                    analysis_payload[safe_symbol] = {}
                analysis_payload[safe_symbol][f'{days}d'] = analysis_result
                symbol_has_data = True
            time.sleep(1) # Be respectful to the API
        
        if not symbol_has_data:
            logging.warning(f"Completed all lookbacks for {symbol}, but NO DATA was successfully generated.")

    if analysis_payload:
        full_payload = {
            'metadata': {
                'description': "Support/Resistance analysis using multi-timeframe pivots, advanced strength scoring (recency, volume), and DBSCAN clustering with a dynamic percentage-based merge range.",
                'last_updated_utc': datetime.now(timezone.utc).isoformat()
            },
            'data': analysis_payload
        }
        try:
            with open(SR_OUTPUT_FILENAME, 'w') as f:
                json.dump(full_payload, f, indent=4)
            logging.info(f"\nSUCCESS: S/R level data saved to {SR_OUTPUT_FILENAME}.")
        except IOError as e:
            logging.error(f"FATAL: Could not write S/R file '{SR_OUTPUT_FILENAME}'. Error: {e}")
            sys.exit(1)
    else:
        logging.warning("\nNo S/R data was generated for ANY symbol. The output file will not be created.")

    # --- Part 2: Market Opens Analysis ---
    get_open_prices()
    logging.info("\n--- All Analyses Complete ---")

if __name__ == "__main__":
    main()
