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

CANDLES_TO_FETCH = 5000

# --- API Configuration ---
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 5
HISTORICAL_DATA_CHUNK_LIMIT = 1000

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_safe_symbol(symbol):
    return symbol.replace('/', '-')


# --- API Class ---
class BinanceAPI:
    BASE_URL = "https://api.binance.us/api/v3"

    @staticmethod
    def _make_request(url: str, params: Dict) -> Optional[List[Any]]:
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logging.warning(f"API request failed (attempt {attempt + 1}/{API_RETRY_ATTEMPTS}): {e}")
                if e.response is not None:
                    logging.warning(f"API Error Details: Status Code = {e.response.status_code}, Response = {e.response.text}")
                time.sleep(API_RETRY_DELAY)
        logging.error(f"API request failed after {API_RETRY_ATTEMPTS} attempts.")
        return None

    @staticmethod
    def fetch_last_n_candles(symbol: str, interval: str, num_candles: int) -> Optional[pd.DataFrame]:
        api_symbol = symbol.replace('/', '').upper()
        all_data = []
        end_time_ms = None
        
        logging.info(
            f"[{symbol}/{interval}] Fetching last {num_candles} candles from API for {api_symbol}...")

        while len(all_data) < num_candles:
            params = {
                "symbol": api_symbol,
                "interval": interval,
                "limit": min(HISTORICAL_DATA_CHUNK_LIMIT, num_candles - len(all_data) + 1) # +1 buffer
            }
            if end_time_ms:
                params['endTime'] = end_time_ms
            
            url = f"{BinanceAPI.BASE_URL}/klines"
            klines_chunk_raw = BinanceAPI._make_request(url, params)

            if klines_chunk_raw is None: return None
            if not klines_chunk_raw: break

            all_data = klines_chunk_raw + all_data
            end_time_ms = klines_chunk_raw[0][0] - 1

            if len(klines_chunk_raw) < HISTORICAL_DATA_CHUNK_LIMIT: break
            time.sleep(0.1)

        if not all_data:
            logging.warning(f"[{symbol}/{interval}] No data found on API.")
            return pd.DataFrame()

        df = pd.DataFrame(all_data, columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        
        # <<< THIS IS THE FIX >>>
        # Use the actual column name 'open_time' for deduplication
        df = df.drop_duplicates(subset=['open_time'], keep='first')
        # <<< END OF FIX >>>
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
        df = df.set_index('open_time')
        df = df[['open', 'high', 'low', 'close', 'volume']].dropna()
        
        df = df.tail(num_candles)

        logging.info(
            f"[{symbol}/{interval}] SUCCESS: Fetched a total of {len(df)} candles.")
        return df


def add_indicators(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    if df.empty: return df
    df_res = df.copy()
    for period in periods:
        df_res[f'SMA_{period}'] = df_res['close'].rolling(window=period).mean()
        df_res[f'EMA_{period}'] = df_res['close'].ewm(span=period, adjust=False).mean()
    return df_res


if __name__ == "__main__":
    logging.info(f"--- Starting Market Snapshot Script (Fetching {CANDLES_TO_FETCH} candles) ---")
    analysis_payload = {}

    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}

        for tf_api, tf_config in TIMEFRAME_CONFIG.items():
            print("-" * 50)
            logging.info(f"Processing {symbol} on the {tf_api} timeframe")

            df_full = BinanceAPI.fetch_last_n_candles(symbol, tf_api, num_candles=CANDLES_TO_FETCH)

            if df_full is None or df_full.empty:
                logging.error(f"[{symbol}/{tf_api}] No data available from API. Skipping.")
                continue

            data_with_indicators = add_indicators(df_full, MA_PERIODS)

            if data_with_indicators.empty:
                logging.warning(f"[{symbol}/{tf_api}] Indicator calculation resulted in an empty DataFrame. Skipping.")
                continue
                
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
            logging.info(f"[{symbol}/{tf_api}] Prepared latest values: {indicator_values}")

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
