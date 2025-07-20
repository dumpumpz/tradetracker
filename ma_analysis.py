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
    '15m': {'name': '15min', 'minutes': 15},
    '30m': {'name': '30min', 'minutes': 30},
    '1h': {'name': '1hour', 'minutes': 60},
    '2h': {'name': '2hour', 'minutes': 120},
    '4h': {'name': '4hour', 'minutes': 240},
    '1d': {'name': 'daily', 'minutes': 1440}
}
MA_PERIODS = [13, 49, 100, 200, 500, 1000]
OUTPUT_FILENAME = "ma_analysis.json"
# <<< NEW: Increased lookback for better MA warmup >>>
DATA_LOOKBACK_DAYS = 200

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
    """Converts 'BTC/USDT' to 'BTC-USDT' for JSON keys."""
    return symbol.replace('/', '-')


# --- API Class ---
class BinanceAPI:
    # <<< MODIFIED: Using the binance.us API endpoint >>>
    BASE_URL = "https://api.binance.us/api/v3"

    @staticmethod
    def _make_request(url: str, params: Dict) -> Optional[List[Any]]:
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, params=params, timeout=20)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logging.warning(
                    f"API request failed (attempt {attempt + 1}/"
                    f"{API_RETRY_ATTEMPTS}): {e}")
                if e.response is not None:
                    logging.warning(f"API Error Details: Status Code = {e.response.status_code}, Response = {e.response.text}")
                time.sleep(API_RETRY_DELAY)
        logging.error(
            f"API request failed after {API_RETRY_ATTEMPTS} attempts.")
        return None

    @staticmethod
    def fetch_new_data(symbol: str, interval: str, start_dt: pd.Timestamp) -> Optional[pd.DataFrame]:
        api_symbol = symbol.replace('/', '').upper()
        all_klines_list = []
        current_start_ms = int(start_dt.timestamp() * 1000)
        logging.info(
            f"[{symbol}/{interval}] Fetching new data from API for "
            f"{api_symbol} starting from {start_dt.strftime('%Y-%m-%d')}...")
            
        while True:
            params = {"symbol": api_symbol, "interval": interval,
                      "limit": HISTORICAL_DATA_CHUNK_LIMIT,
                      "startTime": current_start_ms}
            klines_chunk_raw = BinanceAPI._make_request(
                f"{BinanceAPI.BASE_URL}/klines", params)
                
            if klines_chunk_raw is None: 
                return None
            if not klines_chunk_raw: 
                break
                
            all_klines_list.extend(klines_chunk_raw)
            last_candle_open_time_ms = int(klines_chunk_raw[-1][0])
            current_start_ms = last_candle_open_time_ms + 1
            if len(klines_chunk_raw) < HISTORICAL_DATA_CHUNK_LIMIT: 
                break
                
        if not all_klines_list:
            logging.info(f"[{symbol}/{interval}] No new data found on API.")
            return pd.DataFrame()
            
        columns = ['open_time', 'open', 'high', 'low', 'close', 'volume',
                   'close_time', 'quote_asset_volume', 'number_of_trades',
                   'taker_buy_base_asset_volume',
                   'taker_buy_quote_asset_volume', 'ignore']
        df = pd.DataFrame(all_klines_list, columns=columns)
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols: 
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
        df = df.set_index('open_time')
        df = df[['open', 'high', 'low', 'close', 'volume']].dropna()
        logging.info(
            f"[{symbol}/{interval}] Fetched {len(df)} new candles from API.")
        return df


# --- Calculation Function ---
def add_indicators(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    df_res = df.copy()
    for period in periods:
        df_res[f'SMA_{period}'] = df_res['close'].rolling(window=period).mean()
        df_res[f'EMA_{period}'] = df_res['close'].ewm(span=period, adjust=False).mean()
    return df_res


# --- Main Execution ---
if __name__ == "__main__":
    logging.info("--- Starting Market Snapshot Script ---")
    analysis_payload = {}

    for symbol in SYMBOLS:
        safe_symbol = get_safe_symbol(symbol)
        analysis_payload[safe_symbol] = {}

        for tf_api, tf_config in TIMEFRAME_CONFIG.items():
            print("-" * 50)
            logging.info(f"Processing {symbol} on the {tf_api} timeframe")
            
            # <<< MODIFIED: Simplified data fetching logic >>>
            # 1. Fetch all required historical data from the API
            start_date = datetime.now(timezone.utc) - timedelta(days=DATA_LOOKBACK_DAYS)
            
            df_full = BinanceAPI.fetch_new_data(symbol, tf_api, start_dt=start_date)

            if df_full is None or df_full.empty:
                logging.error(f"[{symbol}/{tf_api}] No data available from API. Skipping.")
                continue

            # 2. Calculate indicators
            data_with_indicators = add_indicators(df_full, MA_PERIODS)

            # 3. Get the latest row and prepare the payload
            latest_row = data_with_indicators.iloc[-1]
            indicator_values = {}

                        # Add the latest price
            # Wrap in float() to convert from numpy type to standard python type
            indicator_values['price'] = float(round(latest_row['close'], 4))

            # Add EMAs and SMAs
            for period in MA_PERIODS:
                # Wrap each value in float()
                ema_val = latest_row.get(f'EMA_{period}')
                sma_val = latest_row.get(f'SMA_{period}')

                indicator_values[f'EMA_{period}'] = float(round(ema_val, 4)) if pd.notna(ema_val) else None
                indicator_values[f'SMA_{period}'] = float(round(sma_val, 4)) if pd.notna(sma_val) else None

            website_tf_name = tf_config['name']
            analysis_payload[safe_symbol][website_tf_name] = indicator_values
            logging.info(f"[{symbol}/{tf_api}] Prepared latest values: {indicator_values}")

    # After processing all symbols and timeframes, save to JSON file
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
            logging.error(f"FATAL: Could not write to file {OUTPUT_FILENAME}. "
                          f"Error: {e}")
            sys.exit(1)
    else:
        logging.warning("No data was processed, JSON file not created.")

    print("-" * 80 + "\nScript finished.")
