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

# --- Unified Configuration ---
SYMBOLS = ['BTCUSDT', 'ETHUSDT']
TIMEFRAMES_TO_ANALYZE = ['15m', '30m', '1h', '2h', '4h']
LOOKBACK_PERIODS_DAYS = [60, 30, 21, 14, 7, 3, 2]
PIVOT_WINDOWS = [1, 2, 3, 5, 8, 10, 13, 21]
CLUSTER_THRESHOLD_PERCENT = 0.5
TOP_N_CLUSTERS_TO_SEND = 10
OUTPUT_FILENAME = "sr_levels_analysis.json"

# --- Timeframe Weighting System ---
TIMEFRAME_WEIGHTS = {
    '15m': 1.0,
    '30m': 1.2,
    '1h': 1.5,
    '2h': 2.0,
    '4h': 2.5
}

# --- PIVOT SOURCE WEIGHTING SYSTEM ---
PIVOT_SOURCE_WEIGHTS = {
    'Wick': 1.0,
    'Close': 1.5
}

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')


def get_safe_symbol(symbol):
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol


def get_minutes_from_timeframe(tf_string):
    num = int(re.findall(r'\d+', tf_string)[0])
    unit = re.findall(r'[a-zA-Z]', tf_string)[0].lower()
    if unit == 'm':
        return num
    elif unit == 'h':
        return num * 60
    elif unit == 'd':
        return num * 60 * 24
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

    logging.info(
        f"Fetching data for {symbol} on {interval}. Need ~"
        f"{total_candles_needed} candles for {lookback_days} days.")

    while len(all_data) < total_candles_needed:
        url = f'https://api.binance.us/api/v3/klines?symbol=' \
              f'{symbol}&interval={interval}&limit={limit_per_req}'
        if end_time_ms:
            url += f'&endTime={end_time_ms}'

        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data_chunk = response.json()

            if not data_chunk:
                logging.info(f"No more historical data for {symbol}, stopping pagination.")
                break

            all_data = data_chunk + all_data
            end_time_ms = data_chunk[0][0] - 1

            if len(data_chunk) < limit_per_req:
                break
            time.sleep(0.2)
        except requests.exceptions.RequestException as e:
            logging.error(f"Could not fetch paginated data for {symbol} on {interval}: {e}")
            if e.response is not None:
                logging.error(f"API Error Details: Status Code = {e.response.status_code}, Response = {e.response.text}")
            return None

    if not all_data:
        return None

    df = pd.DataFrame(all_data,
                      columns=['Open time', 'Open', 'High', 'Low', 'Close',
                               'Volume', 'Close time', 'Quote asset volume',
                               'Number of trades',
                               'Taker buy base asset volume',
                               'Taker buy quote asset volume', 'Ignore'])
    df['Date'] = pd.to_datetime(df['Open time'], unit='ms')
    df.set_index('Date', inplace=True)
    df.drop_duplicates(inplace=True)

    final_df = df.tail(total_candles_needed)
    logging.info(
        f"SUCCESS: Fetched a total of {len(final_df)} candles for {symbol} "
        f"on {interval}.")
    return final_df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)


def find_pivots_from_series(data_series, window, is_high):
    if window == 0 or len(data_series) <= 2 * window: return []
    pivots = []
    for i in range(window, len(data_series) - window):
        window_slice = data_series.iloc[i - window: i + window + 1]
        current_candle_price = data_series.iloc[i]
        is_pivot = (is_high and current_candle_price >= window_slice.max()) \
                   or \
                   (not is_high and current_candle_price <= window_slice.min())
        if is_pivot and (not pivots or pivots[-1][1] != current_candle_price):
            pivots.append((data_series.index[i], current_candle_price))
    return pivots


def generate_pivots_for_timeframe(symbol, timeframe, lookback_days):
    df_ohlcv = fetch_ohlcv_paginated(symbol, timeframe, lookback_days)
    if df_ohlcv is None or df_ohlcv.empty: return pd.DataFrame()

    all_pivots_list = []
    pivot_definitions = {
        'High_Wick': (df_ohlcv['High'], True, 'Resistance', 'Wick'),
        'Low_Wick': (df_ohlcv['Low'], False, 'Support', 'Wick'),
        'Close_High': (df_ohlcv['Close'], True, 'Resistance', 'Close'),
        'Close_Low': (df_ohlcv['Close'], False, 'Support', 'Close')
    }

    timeframe_weight = TIMEFRAME_WEIGHTS.get(timeframe, 1.0)

    for window in PIVOT_WINDOWS:
        for pivot_name, (series, is_high, type_str, source) in pivot_definitions.items():
            source_weight = PIVOT_SOURCE_WEIGHTS.get(source, 1.0)
            for timestamp, price in find_pivots_from_series(series, window, is_high):
                weighted_strength = window * timeframe_weight * source_weight
                all_pivots_list.append({
                    'Timestamp': timestamp,
                    'Price': price,
                    'Strength': weighted_strength,
                    'Type': type_str,
                    'Source': source,
                    'Timeframe': timeframe
                })
    return pd.DataFrame(all_pivots_list)


def find_clusters(pivots_df, threshold_percent):
    if pivots_df.empty: return []
    clusters, current_cluster_pivots = [], []
    pivots_df.sort_values(by='Price', inplace=True)
    for _, pivot in pivots_df.iterrows():
        if not current_cluster_pivots:
            current_cluster_pivots.append(pivot)
            continue
        cluster_start_price = current_cluster_pivots[0]['Price']
        price_diff_percent = (pivot['Price'] - cluster_start_price) / cluster_start_price * 100
        if abs(price_diff_percent) <= threshold_percent:
            current_cluster_pivots.append(pivot)
        else:
            if current_cluster_pivots:
                cluster_df = pd.DataFrame(current_cluster_pivots)
                # <<< MODIFIED: Ensure all numeric types are standard Python types >>>
                cluster_data = {
                    'Type': str(cluster_df['Type'].iloc[0]),
                    'Price Start': float(cluster_df['Price'].min()),
                    'Price End': float(cluster_df['Price'].max()),
                    'Strength Score': int(cluster_df['Strength'].sum()),
                    'Pivot Count': int(len(cluster_df))
                }
                clusters.append(cluster_data)
                # <<< END MODIFICATION >>>
            current_cluster_pivots = [pivot]
    if current_cluster_pivots:
        cluster_df = pd.DataFrame(current_cluster_pivots)
        # <<< MODIFIED: Ensure all numeric types are standard Python types >>>
        cluster_data = {
            'Type': str(cluster_df['Type'].iloc[0]),
            'Price Start': float(cluster_df['Price'].min()),
            'Price End': float(cluster_df['Price'].max()),
            'Strength Score': int(cluster_df['Strength'].sum()),
            'Pivot Count': int(len(cluster_df))
        }
        clusters.append(cluster_data)
        # <<< END MODIFICATION >>>
    return clusters


def run_analysis_for_lookback(symbol, lookback_days):
    logging.info(
        f"--- Running Analysis for {symbol} with {lookback_days}-Day "
        f"Lookback ---")
    all_pivots_dfs = []
    for tf in TIMEFRAMES_TO_ANALYZE:
        pivots_df = generate_pivots_for_timeframe(symbol, tf, lookback_days)
        if not pivots_df.empty:
            all_pivots_dfs.append(pivots_df)
        time.sleep(0.5)

    if not all_pivots_dfs:
        logging.warning(f"No pivot data for {symbol} at {lookback_days} days.")
        return None

    pivots_data = pd.concat(all_pivots_dfs, ignore_index=True)

    support_clusters = find_clusters(
        pivots_data[pivots_data['Type'] == 'Support'],
        CLUSTER_THRESHOLD_PERCENT)
    resistance_clusters = find_clusters(
        pivots_data[pivots_data['Type'] == 'Resistance'],
        CLUSTER_THRESHOLD_PERCENT)
    support_clusters.sort(key=lambda x: x['Strength Score'], reverse=True)
    resistance_clusters.sort(key=lambda x: x['Strength Score'], reverse=True)

    return {
        'support': support_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'resistance': resistance_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'analysis_params': {
            'timeframes_analyzed': TIMEFRAMES_TO_ANALYZE,
            'pivot_windows': PIVOT_WINDOWS,
            'lookback_days': lookback_days,
            'oldest_pivot_date': pivots_data['Timestamp'].min().strftime(
                '%Y-%m-%d'),
            'newest_pivot_date': pivots_data['Timestamp'].max().strftime(
                '%Y-%m-%d')
        }
    }


def main():
    analysis_payload = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}
        for days in LOOKBACK_PERIODS_DAYS:
            analysis_result = run_analysis_for_lookback(symbol, days)
            if analysis_result:
                analysis_payload[safe_symbol][f'{days}d'] = analysis_result

    if analysis_payload:
        full_payload = {
            'data': analysis_payload,
            'last_updated': datetime.now(timezone.utc).isoformat()
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
