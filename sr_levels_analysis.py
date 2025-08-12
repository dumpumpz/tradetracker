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
import random

# ### NEW ### Import new libraries for proxy fetching
from bs4 import BeautifulSoup
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

CLUSTER_THRESHOLD_PERCENT = 0.12

# ### MODIFIED ### We will try a different Binance API cluster first. This is often enough to bypass simple blocks.
API_ENDPOINT = "https://api3.binance.com/api/v3/klines"

# --- Weighting Systems ---
TIMEFRAME_WEIGHTS = {'15m': 1.0, '30m': 1.2, '1h': 1.5, '2h': 2.0, '4h': 2.5}
PIVOT_SOURCE_WEIGHTS = {'Wick': 1.0, 'Close': 1.5}
STRENGTH_CONFIG = {'VOLUME_STRENGTH_FACTOR': 1.0, 'RECENCY_HALFLIFE_DAYS': 45.0}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# ### NEW PROXY LOGIC ###
def get_working_proxy():
    """
    Fetches a list of free proxies and returns the first one that works.
    This is a resilient way to bypass geo-blocking.
    """
    url = "https://free-proxy-list.net/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'lxml')
        proxy_list = []
        for row in soup.find("table", attrs={"class": "table"}).find_all("tr")[1:]:
            tds = row.find_all("td")
            if tds[6].text.strip() == "yes": # Only use HTTPS proxies
                ip = tds[0].text.strip()
                port = tds[1].text.strip()
                proxy_list.append(f"http://{ip}:{port}")
        
        random.shuffle(proxy_list)
        logging.info(f"Found {len(proxy_list)} potential proxies. Testing...")

        for proxy_url in proxy_list:
            proxies = {"http": proxy_url, "https": proxy_url}
            try:
                # Test the proxy by trying to connect to a reliable service
                test_response = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
                if test_response.status_code == 200:
                    logging.info(f"SUCCESS: Found working proxy: {proxy_url}")
                    return proxies
            except requests.exceptions.RequestException:
                continue # Try the next proxy
    except Exception as e:
        logging.warning(f"Could not fetch or validate proxies: {e}")
    
    logging.error("FATAL: No working proxies found. Analysis may fail.")
    return None

def get_safe_symbol(symbol):
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol

# (The rest of your script remains the same, but the fetch function is modified)

def get_minutes_from_timeframe(tf_string):
    # ... (no changes needed in this function)
    num = int(re.findall(r'\d+', tf_string)[0])
    unit = re.findall(r'[a-zA-Z]', tf_string)[0].lower()
    if unit == 'm': return num
    elif unit == 'h': return num * 60
    elif unit == 'd': return num * 60 * 24
    elif unit == 'w': return num * 60 * 24 * 7
    elif unit.upper() == 'M': return num * 60 * 24 * 30
    return 0

# ### MODIFIED ### This function now accepts and uses a proxy
def fetch_ohlcv_paginated(symbol, interval, lookback_days=None, limit=1000, proxies=None):
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
                # Use the provided proxy for the request
                response = requests.get(url, timeout=20, proxies=proxies)
                response.raise_for_status()
                data_chunk = response.json()
                if not data_chunk:
                    logging.info(f"No more historical data for {symbol}, stopping.")
                    break
                all_data = data_chunk + all_data
                end_time_ms = data_chunk[0][0] - 1
                if len(data_chunk) < limit: break
                time.sleep(0.5) # Increased sleep time to be kind to proxies
            except requests.exceptions.RequestException as e:
                logging.error(f"Could not fetch data for {symbol} on {interval}: {e}")
                return None
        
        if not all_data: return None
        df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
        df = df.tail(total_candles_needed)
    else: # Simple fetch for a few candles
        url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
        try:
            response = requests.get(url, timeout=10, proxies=proxies)
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
    if lookback_days: logging.info(f"SUCCESS: Fetched {len(df)} candles for {symbol} on {interval}.")
    return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)

# ### MODIFIED ### This function now passes the proxy to the fetcher
def generate_pivots_for_timeframe(symbol, timeframe, lookback_days, proxies):
    df_ohlcv = fetch_ohlcv_paginated(symbol, timeframe, lookback_days=lookback_days, proxies=proxies)
    # ... (rest of this function is unchanged)
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

# ### MODIFIED ### This function now passes the proxy to its child functions
def run_analysis_for_lookback(symbol, lookback_days, proxies):
    logging.info(f"--- Running S/R Analysis for {symbol} with {lookback_days}-Day Lookback ---")
    all_pivots_dfs = [df for tf in TIMEFRAMES_TO_ANALYZE if not (df := generate_pivots_for_timeframe(symbol, tf, lookback_days, proxies)).empty]
    # ... (rest of this function is unchanged)
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

# ### MODIFIED ### This function now passes the proxy to its child functions
def get_open_prices(proxies):
    logging.info("\n--- Fetching Key Market Open Prices ---")
    timeframes = {'daily': '1d', 'weekly': '1w', 'monthly': '1M'}
    all_opens = {}
    for symbol in SYMBOLS:
        symbol_opens = {}
        logging.info(f"Fetching opens for {symbol}...")
        for tf_name, tf_code in timeframes.items():
            try:
                df = fetch_ohlcv_paginated(symbol, tf_code, limit=2, proxies=proxies)
                if df is not None and not df.empty:
                    symbol_opens[tf_name] = df['Open'].iloc[-1]
                    logging.info(f"  - {symbol} {tf_name.capitalize()} Open: {df['Open'].iloc[-1]}")
                else:
                    symbol_opens[tf_name] = 0
            except Exception as e:
                symbol_opens[tf_name] = 0
        safe_symbol = get_safe_symbol(symbol)
        all_opens[safe_symbol] = symbol_opens
    output_data = {"last_updated": datetime.now(timezone.utc).isoformat(), "opens": all_opens}
    try:
        with open(OPENS_OUTPUT_FILENAME, 'w') as f:
            json.dump(output_data, f, indent=4)
        logging.info(f"SUCCESS: Market open data saved to {OPENS_OUTPUT_FILENAME}.")
    except IOError as e:
        logging.error(f"FATAL: Could not write to file {OPENS_OUTPUT_FILENAME}. Error: {e}")

# ### MODIFIED ### The main function now finds a proxy ONCE and passes it to all other functions.
def main():
    # Find a working proxy at the start of the script.
    # If none are found, it will try to run without one.
    proxies = get_working_proxy()

    # --- Part 1: S/R Analysis ---
    analysis_payload = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}
        for days in LOOKBACK_PERIODS_DAYS:
            analysis_result = run_analysis_for_lookback(symbol, days, proxies)
            if analysis_result:
                analysis_payload[safe_symbol][f'{days}d'] = analysis_result
            time.sleep(1)
    
    if analysis_payload:
        full_payload = {'metadata': {'description': "...", 'last_updated_utc': datetime.now(timezone.utc).isoformat()}, 'data': analysis_payload}
        try:
            with open(SR_OUTPUT_FILENAME, 'w') as f:
                json.dump(full_payload, f, indent=4)
            logging.info(f"SUCCESS: S/R level data saved to {SR_OUTPUT_FILENAME}.")
        except IOError as e:
            logging.error(f"FATAL: Could not write file. Error: {e}")
            sys.exit(1)
    else:
        logging.warning("No S/R data was generated.")
    
    # --- Part 2: Market Opens Analysis ---
    get_open_prices(proxies)

    logging.info("\n--- All Analyses Complete ---")

# (find_pivots_scipy and find_clusters_dbscan are unchanged)
def find_pivots_scipy(data_series: pd.Series, window: int, is_high: bool):
    if window == 0 or len(data_series) <= 2 * window: return []
    comparator = np.greater if is_high else np.less
    pivot_indices = argrelextrema(data_series.values, comparator, order=window)[0]
    return [(data_series.index[i], data_series.iloc[i]) for i in pivot_indices]

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

if __name__ == "__main__":
    main()
