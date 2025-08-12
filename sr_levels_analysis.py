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

# --- Adaptive Clustering and Filtering Parameters ---
BASE_EPS_PERCENTAGE_RANGE = 0.0007   # Base epsilon for clustering (0.07%)
MIN_SAMPLES_FOR_CLUSTER = 3         # Minimum number of pivots to form a valid cluster
ATR_LOOKBACK = 14
ATR_VOLATILITY_MULTIPLIER = 1.5     # Multiplier for epsilon during high volatility
LIQUIDITY_VOLUME_MULTIPLIER = 1.2     # A pivot is considered 'high liquidity' if its volume is this much times the average

# --- Weighting Systems ---
TIMEFRAME_WEIGHTS = {'15m': 1.0, '30m': 1.2, '1h': 1.5, '2h': 2.0, '4h': 2.5}
PIVOT_SOURCE_WEIGHTS = {'Wick': 1.0, 'Close': 1.5}
STRENGTH_CONFIG = {'VOLUME_STRENGTH_FACTOR': 1.0, 'RECENCY_HALFLIFE_DAYS': 45.0}

# --- API and Session Setup ---
API_ENDPOINT = "https://api.binance.com/api/v3/klines"
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'})


def get_safe_symbol(symbol):
    return symbol.replace('USDT', '-USDT') if 'USDT' in symbol else symbol

def get_minutes_from_timeframe(tf_string):
    num_match = re.search(r'\d+', tf_string)
    unit_match = re.search(r'[a-zA-Z]', tf_string)
    if not num_match or not unit_match: return 0
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
    try:
        if lookback_days:
            minutes_per_tf = get_minutes_from_timeframe(interval)
            total_candles_needed = (lookback_days * 1440) // minutes_per_tf
            while len(all_data) < total_candles_needed:
                url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
                if end_time_ms: url += f'&endTime={end_time_ms}'
                response = SESSION.get(url, timeout=20)
                response.raise_for_status()
                data_chunk = response.json()
                if not data_chunk: break
                all_data = data_chunk + all_data
                end_time_ms = data_chunk[0][0] - 1
                if len(data_chunk) < limit: break
                time.sleep(0.3)
            df = pd.DataFrame(all_data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
            df = df.tail(total_candles_needed)
        else: # Simple fetch, not used in main analysis but kept for utility
            url = f'{API_ENDPOINT}?symbol={symbol}&interval={interval}&limit={limit}'
            response = SESSION.get(url, timeout=10)
            response.raise_for_status()
            df = pd.DataFrame(response.json(), columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])

        df['Date'] = pd.to_datetime(df['Open time'], unit='ms', utc=True)
        df.set_index('Date', inplace=True)
        df.drop_duplicates(inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    except requests.exceptions.RequestException as e:
        logging.error(f"API Request Failed for {symbol} on {interval}: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred during data fetching for {symbol} on {interval}: {e}")
        return None

def calc_atr(df, period=ATR_LOOKBACK):
    high_low = df['High'] - df['Low']
    high_close = abs(df['High'] - df['Close'].shift(1))
    low_close = abs(df['Low'] - df['Close'].shift(1))
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(window=period, min_periods=period).mean()

def find_pivots_scipy(series, window, is_high):
    if window == 0 or len(series) <= 2 * window: return []
    comparator = np.greater if is_high else np.less
    indices = argrelextrema(series.values, comparator, order=window)[0]
    return [(series.index[i], series.iloc[i]) for i in indices]

def generate_pivots_for_timeframe(df_ohlcv, timeframe, atr_percent):
    if df_ohlcv is None or df_ohlcv.empty: return pd.DataFrame()

    vol_min, vol_max = df_ohlcv['Volume'].min(), df_ohlcv['Volume'].max()
    df_ohlcv['Volume_Norm'] = (df_ohlcv['Volume'] - vol_min) / (vol_max - vol_min) if vol_max > vol_min else 0.5
    
    recency_lambda = np.log(2) / STRENGTH_CONFIG['RECENCY_HALFLIFE_DAYS']
    all_pivots = []
    
    # Adaptive pivot windows based on volatility
    pivot_windows = BASE_PIVOT_WINDOWS
    if atr_percent > 0.03: # Arbitrary threshold for "high volatility"
        pivot_windows = [int(w * ATR_VOLATILITY_MULTIPLIER) for w in BASE_PIVOT_WINDOWS]
        logging.info(f"High volatility detected on {timeframe} (ATR: {atr_percent:.2%}). Using expanded pivot windows.")

    pivot_defs = {
        'High_Wick': (df_ohlcv['High'], True, 'Resistance', 'Wick'),
        'Low_Wick': (df_ohlcv['Low'], False, 'Support', 'Wick'),
        'Close_High': (df_ohlcv['Close'], True, 'Resistance', 'Close'),
        'Close_Low': (df_ohlcv['Close'], False, 'Support', 'Close')
    }
    
    tf_weight = TIMEFRAME_WEIGHTS.get(timeframe, 1.0)
    now = datetime.now(timezone.utc)

    for window in pivot_windows:
        for name, (series, is_high, ptype, source) in pivot_defs.items():
            source_weight = PIVOT_SOURCE_WEIGHTS.get(source, 1.0)
            pivots = find_pivots_scipy(series, window, is_high)
            for ts, price in pivots:
                base_strength = window * tf_weight * source_weight
                days_ago = (now - ts).total_seconds() / 86400
                recency_weight = np.exp(-recency_lambda * days_ago)
                volume_weight = 1 + (df_ohlcv.loc[ts, 'Volume_Norm'] * STRENGTH_CONFIG['VOLUME_STRENGTH_FACTOR'])
                final_strength = base_strength * recency_weight * volume_weight
                all_pivots.append({
                    'Timestamp': ts, 'Price': price, 'Strength': final_strength,
                    'Type': ptype, 'Source': source, 'Timeframe': timeframe,
                    'Volume': df_ohlcv.loc[ts, 'Volume'], 'Close': df_ohlcv.loc[ts, 'Close'], 'Open': df_ohlcv.loc[ts, 'Open']
                })
    return pd.DataFrame(all_pivots)

def find_clusters_dbscan(pivots_df, symbol, atr_percent):
    if pivots_df.empty or len(pivots_df) < MIN_SAMPLES_FOR_CLUSTER: return []
    
    # Make a copy to avoid SettingWithCopyWarning
    pivots_df = pivots_df.copy()

    # Adaptive epsilon based on volatility
    epsilon_multiplier = 1 + (atr_percent * 10) # Simple way to slightly expand epsilon in high vol
    adaptive_eps_percentage = BASE_EPS_PERCENTAGE_RANGE * epsilon_multiplier
    
    avg_price = np.mean(pivots_df['Price'])
    epsilon = avg_price * adaptive_eps_percentage

    db = DBSCAN(eps=epsilon, min_samples=MIN_SAMPLES_FOR_CLUSTER).fit(pivots_df['Price'].values.reshape(-1, 1))
    
    # Use .loc to safely add the new column and avoid warnings
    pivots_df.loc[:, 'cluster_id'] = db.labels_

    clusters = []
    for cid in sorted(pivots_df['cluster_id'].unique()):
        if cid == -1: continue # Skip noise points

        cdf = pivots_df[pivots_df['cluster_id'] == cid].copy()

        # Filter 1: Liquidity Check (must have at least one high-volume pivot)
        avg_vol = pivots_df['Volume'].mean()
        if not cdf['Volume'].max() > avg_vol * LIQUIDITY_VOLUME_MULTIPLIER:
            continue
            
        # Filter 2: Reversal Check (must have at least one reversal candle)
        is_resistance_reversal = (cdf['Type'] == 'Resistance') & (cdf['Close'] < cdf['Open'])
        is_support_reversal = (cdf['Type'] == 'Support') & (cdf['Close'] > cdf['Open'])
        if not (is_resistance_reversal.any() or is_support_reversal.any()):
            continue
            
        weighted_avg_price = np.average(cdf['Price'], weights=cdf['Strength'])
        clusters.append({
            'Type': cdf['Type'].iloc[0],
            'Price Start': float(cdf['Price'].min()),
            'Price End': float(cdf['Price'].max()),
            'Center Price': float(round(weighted_avg_price, 2)),
            'Strength Score': int(cdf['Strength'].sum()),
            'Pivot Count': len(cdf)
        })
    return clusters

def run_analysis_for_lookback(symbol, days):
    logging.info(f"--- Running Analysis for {symbol} with {days}-day lookback ---")
    all_pivots_dfs = []

    # Fetch data once per timeframe and pass it down
    timeframe_data = {tf: fetch_ohlcv_paginated(symbol, tf, lookback_days=days) for tf in TIMEFRAMES_TO_ANALYZE}
    
    # Use 1h ATR as the reference for volatility for this lookback period
    df_1h = timeframe_data.get('1h')
    if df_1h is None or df_1h.empty:
        logging.warning(f"Cannot calculate ATR for {symbol}, 1h data is missing.")
        return None
    
    atr_val = calc_atr(df_1h).iloc[-1]
    atr_percent = atr_val / df_1h['Close'].iloc[-1] if df_1h['Close'].iloc[-1] > 0 else 0

    for tf, df in timeframe_data.items():
        if df is not None and not df.empty:
            pivots = generate_pivots_for_timeframe(df, tf, atr_percent)
            if not pivots.empty:
                all_pivots_dfs.append(pivots)

    if not all_pivots_dfs:
        logging.warning(f"No pivots generated for {symbol} at {days} days.")
        return None
        
    pivots_df = pd.concat(all_pivots_dfs, ignore_index=True)

    # Normalize strength across the entire dataset for this lookback, AFTER concatenation
    max_strength = pivots_df['Strength'].max()
    if max_strength > 0:
        pivots_df['Strength'] = pivots_df['Strength'] / max_strength

    support_clusters = sorted(find_clusters_dbscan(pivots_df[pivots_df['Type'] == 'Support'], symbol, atr_percent),
                               key=lambda x: x['Strength Score'], reverse=True)
    resistance_clusters = sorted(find_clusters_dbscan(pivots_df[pivots_df['Type'] == 'Resistance'], symbol, atr_percent),
                                  key=lambda x: x['Strength Score'], reverse=True)

    return {
        'support': support_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'resistance': resistance_clusters[:TOP_N_CLUSTERS_TO_SEND],
        'analysis_params': {
            'timeframes_analyzed': TIMEFRAMES_TO_ANALYZE,
            'lookback_days': days,
            'atr_percent': round(atr_percent, 4)
        }
    }

def main():
    logging.info("===== STARTING ADAPTIVE S/R ANALYSIS =====")
    results = {}
    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        results[safe_symbol] = {}
        for days in LOOKBACK_PERIODS_DAYS:
            res = run_analysis_for_lookback(symbol, days)
            if res:
                results[safe_symbol][f'{days}d'] = res
            time.sleep(1) # Be respectful to API

    if results:
        payload = {
            'metadata': {'last_updated_utc': datetime.now(timezone.utc).isoformat()},
            'data': results
        }
        with open(SR_OUTPUT_FILENAME, 'w') as f:
            json.dump(payload, f, indent=4)
        logging.info(f"SUCCESS: Analysis data saved to {SR_OUTPUT_FILENAME}")
    else:
        logging.warning("No data was generated for any symbol.")

    logging.info("--- Analysis complete. ---")

if __name__ == "__main__":
    main()
