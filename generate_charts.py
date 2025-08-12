import pandas as pd
import json
import os
import logging
import requests
import mplfinance as mpf
import matplotlib

# Use a non-GUI backend
matplotlib.use('Agg')

# --- Configuration ---
SYMBOLS_TO_CHART = ['BTC-USDT', 'ETH-USDT']
SR_DATA_FILE = 'sr_levels_analysis.json'
LOOKBACK_TO_CHART = '14d'
TIMEFRAME = '1h'
CANDLES_TO_PLOT = 240
OUTPUT_DIR = 'charts'
# Use the global endpoint, as you are running locally
API_ENDPOINT = "https://api.binance.com/api/v3/klines"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def fetch_ohlcv(symbol, interval, limit):
    """Fetches a limited number of candles for plotting via a direct connection."""
    api_symbol = symbol.replace('-', '')
    url = f'{API_ENDPOINT}?symbol={api_symbol}&interval={interval}&limit={limit}'
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
        df['Date'] = pd.to_datetime(df['Open time'], unit='ms')
        df.set_index('Date', inplace=True)
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
    except requests.exceptions.RequestException as e:
        logging.error(f"Could not fetch chart data for {api_symbol}: {e}")
        return None

def main():
    logging.info("--- Starting Chart Generation Script ---")
    
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    try:
        with open(SR_DATA_FILE, 'r') as f:
            sr_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"FATAL: Could not read S/R data file '{SR_DATA_FILE}'. Error: {e}")
        return

    for symbol in SYMBOLS_TO_CHART:
        logging.info(f"--- Generating chart for {symbol} ---")

        # Fetch data directly, no proxy needed
        df = fetch_ohlcv(symbol, TIMEFRAME, CANDLES_TO_PLOT)
        if df is None or df.empty:
            logging.warning(f"Could not fetch OHLCV data for {symbol}. Skipping chart.")
            continue

        levels = sr_data.get('data', {}).get(symbol, {}).get(LOOKBACK_TO_CHART, {})
        support_levels = levels.get('support', [])
        resistance_levels = levels.get('resistance', [])

        if not support_levels and not resistance_levels:
            logging.warning(f"No S/R levels found for {symbol}. Skipping chart.")
            continue

        hlines, colors = [], []
        for level in support_levels:
            hlines.append((level['Price Start'] + level['Price End']) / 2)
            colors.append('green')
        for level in resistance_levels:
            hlines.append((level['Price Start'] + level['Price End']) / 2)
            colors.append('red')
            
        chart_style = 'nightclouds'
        title = f"\n{symbol} - {TIMEFRAME} Chart with {LOOKBACK_TO_CHART} S/R Zones\nLast Updated: {sr_data.get('metadata', {}).get('last_updated_utc', 'N/A').split('T')[0]}"
        output_path = os.path.join(OUTPUT_DIR, f"{symbol}_chart.png")

        try:
            mpf.plot(df, type='candle', style=chart_style, title=title,
                     ylabel='Price (USDT)',
                     hlines=dict(hlines=hlines, colors=colors, linestyle='--', linewidths=0.7),
                     savefig=dict(fname=output_path, dpi=150, pad_inches=0.25))
            logging.info(f"SUCCESS: Chart saved to {output_path}")
        except Exception as e:
            logging.error(f"Failed to plot or save chart for {symbol}: {e}")

    logging.info("--- Chart Generation Complete ---")

if __name__ == "__main__":
    main()