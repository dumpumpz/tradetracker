import pandas as pd
import os
import logging
import sys
import requests
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any, Dict

# --- Configuration ---
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME_CONFIG = {
    '15m': {'name': '15min'},
    '30m': {'name': '30min'},
    '1h': {'name': '1hour'},
    '2h': {'name': '2hour'},
    '4h': {'name': '4hour'},
    '1d': {'name': 'daily'}
}
MA_PERIODS = [13, 49, 100, 200, 500, 1000]
OUTPUT_FILENAME = "ma_analysis.json"
CACHE_DATA_DIR = "warmup_ohlc_data_fixed"
MAX_ROWS_TO_KEEP_IN_CACHE = 20000

# --- API Configuration ---
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 5
API_KLINE_LIMIT = 1000

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# --- Helper Function ---
def get_safe_symbol(symbol):
    """Converts a symbol like 'BTC/USDT' to 'BTC-USDT'."""
    return symbol.replace('/', '-')

# --- DataHandler Class ---
class DataHandler:
    # ### THIS IS THE FIX ###
    # Use the global Binance endpoint for local execution
    BASE_URL = "https://api.binance.com/api/v3"

    @staticmethod
    def _make_api_request(params: Dict) -> Optional[List[Any]]:
        url = f"{DataHandler.BASE_URL}/klines"
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, params=params, timeout=15)
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                logging.warning(f"API request failed (attempt {attempt + 1}): {e}")
                time.sleep(API_RETRY_DELAY)
        return None

    @staticmethod
    def load_ohlc_from_cache(symbol: str, interval: str) -> Optional[pd.DataFrame]:
        logging.info(f"[{symbol}/{interval}] Searching for cache file...")
        if not os.path.exists(CACHE_DATA_DIR):
            logging.warning(f"Cache directory '{CACHE_DATA_DIR}' not found. Creating it.")
            os.makedirs(CACHE_DATA_DIR)
            return None
        
        cache_filename = f"{symbol.upper()}_{interval}_mastercache.parquet"
        file_path = os.path.join(CACHE_DATA_DIR, cache_filename)

        if not os.path.exists(file_path):
            logging.info(f"[{symbol}/{interval}] No cache file found at {file_path}.")
            return None
            
        try:
            logging.info(f"[{symbol}/{interval}] Loading data from: {file_path}")
            df = pd.read_parquet(file_path)
            if df.empty: return None
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            df = df[[col for col in required_cols if col in df.columns]]
            if not isinstance(df.index, pd.DatetimeIndex): raise TypeError("Cache data has no DatetimeIndex.")
            if df.index.tz is None: df.index = df.index.tz_localize('UTC')
            logging.info(f"[{symbol}/{interval}] Loaded {len(df)} candles from cache.")
            return df
        except Exception as e:
            logging.error(f"[{symbol}/{interval}] CRITICAL: Failed to load or parse cache file: {e}")
            return None

    @staticmethod
    def save_ohlc_to_cache(df: pd.DataFrame, symbol: str, interval: str):
        if df.empty:
            logging.warning(f"[{symbol}/{interval}] DataFrame is empty, skipping cache save.")
            return
            
        cache_filename = f"{symbol.upper()}_{interval}_mastercache.parquet"
        file_path = os.path.join(CACHE_DATA_DIR, cache_filename)
        try:
            columns_to_save = ['open', 'high', 'low', 'close', 'volume']
            df_to_save = df[columns_to_save].tail(MAX_ROWS_TO_KEEP_IN_CACHE)
            df_to_save.to_parquet(file_path)
            logging.info(f"[{symbol}/{interval}] Successfully saved {len(df_to_save)} clean candles to cache: {file_path}")
        except Exception as e:
            logging.error(f"[{symbol}/{interval}] CRITICAL: Could not save cache to {file_path}. Error: {e}")

    @staticmethod
    def fetch_new_data(symbol: str, interval: str, start_dt: pd.Timestamp) -> Optional[pd.DataFrame]:
        api_symbol = symbol.replace('/', '').upper()
        all_klines = []
        current_start_ms = int(start_dt.timestamp() * 1000)
        logging.info(f"[{symbol}/{interval}] Fetching new data from API since {start_dt.strftime('%Y-%m-%d %H:%M:%S')} UTC...")
        
        while True:
            params = {"symbol": api_symbol, "interval": interval, "limit": API_KLINE_LIMIT, "startTime": current_start_ms}
            klines_batch = DataHandler._make_api_request(params)
            if klines_batch is None: return None
            if not klines_batch: break
            all_klines.extend(klines_batch)
            last_candle_ts = int(klines_batch[-1][0])
            current_start_ms = last_candle_ts + 1
            if len(klines_batch) < API_KLINE_LIMIT: break
            time.sleep(0.1)

        if not all_klines: return pd.DataFrame()
        
        df = pd.DataFrame(all_klines, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols: df[col] = pd.to_numeric(df[col], errors='coerce')
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
        df = df.set_index('open_time')
        df = df[numeric_cols].dropna()
        return df

# --- Indicator Calculation ---
def add_indicators(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    if df.empty: return df
    df_res = df[['open', 'high', 'low', 'close', 'volume']].copy()
    logging.info(f"Calculating indicators for {len(df_res)} candles...")
    for period in periods:
        df_res[f'SMA_{period}'] = df_res['close'].rolling(window=period).mean()
        df_res[f'EMA_{period}'] = df_res['close'].ewm(span=period, adjust=False).mean()
    return df_res


if __name__ == "__main__":
    logging.info(f"--- Starting Accurate Market Snapshot Script ---")
    analysis_payload = {}

    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}

        for tf_api, tf_config in TIMEFRAME_CONFIG.items():
            print("-" * 50)
            logging.info(f"Processing {symbol} on the {tf_api} timeframe")

            df_cache = DataHandler.load_ohlc_from_cache(symbol.replace('/',''), tf_api)
            
            if df_cache is not None and not df_cache.empty:
                start_fetch_dt = df_cache.index[-1] + timedelta(milliseconds=1)
            else:
                start_fetch_dt = datetime.now(timezone.utc) - timedelta(days=365 * 4)
                logging.warning(f"[{symbol}/{tf_api}] No valid cache found. Performing a large historical fetch. This may take a moment.")

            df_new = DataHandler.fetch_new_data(symbol, tf_api, start_dt=start_fetch_dt)

            df_list = [df for df in [df_cache, df_new] if df is not None and not df.empty]
            if not df_list:
                logging.error(f"[{symbol}/{tf_api}] No data available from cache or API. Skipping.")
                continue

            df_combined = pd.concat(df_list)
            df_combined = df_combined[~df_combined.index.duplicated(keep='last')].sort_index()
            
            DataHandler.save_ohlc_to_cache(df_combined, symbol.replace('/',''), tf_api)
            data_with_indicators = add_indicators(df_combined, MA_PERIODS)
            
            latest_row = data_with_indicators.iloc[-1]
            indicator_values = {}
            indicator_values['price'] = float(round(latest_row['close'], 4))
            for period in MA_PERIODS:
                ema_val = latest_row.get(f'EMA_{period}')
                sma_val = latest_row.get(f'SMA_{period}')
                indicator_values[f'EMA_{period}'] = float(round(ema_val, 4)) if pd.notna(ema_val) else None
                indicator_values[f'SMA_{period}'] = float(round(sma_val, 4)) if pd.notna(sma_val) else None

            website_tf_name = tf_config['name']
            analysis_payload[safe_symbol][website_tf_name] = indicator_values
            logging.info(f"[{symbol}/{tf_api}] Prepared latest values.")

    if analysis_payload:
        full_payload = {
            'data': analysis_payload,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
        logging.info(f"\nWriting final payload to {OUTPUT_FILENAME}...")
        try:
            with open(OUTPUT_FILENAME, 'w') as json_file:
                json.dump(full_payload, json_file, indent=4)
            logging.info(f"SUCCESS: Analysis data saved to {OUTPUT_FILENAME}.")
        except IOError as e:
            logging.error(f"FATAL: Could not write to file {OUTPUT_FILENAME}. Error: {e}")
            sys.exit(1)
    else:
        logging.warning("No data was processed, JSON file not created.")

    print("-" * 80 + "\nScript finished.")