import pandas as pd
import json
import os
import logging
import requests
import mplfinance as mpf
import matplotlib

# Use a non-GUI backend, essential for running in GitHub Actions
matplotlib.use('Agg')

# --- Configuration ---
SYMBOLS_TO_CHART = ['BTC-USDT', 'ETH-USDT']
SR_DATA_FILE = 'sr_levels_analysis.json'
LOOKBACK_TO_CHART = '14d'  # Use S/R levels from this specific analysis period
TIMEFRAME = '1h'           # Timeframe for the candle chart
CANDLES_TO_PLOT = 240      # How many recent candles to display (240 1h candles = 10 days)
OUTPUT_DIR = 'charts'      # A folder to save the chart images
API_ENDPOINT = "https://api.binance.com/api/v3/klines"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def fetch_ohlcv(symbol, interval, limit):
    """Fetches a limited number of candles for plotting."""
    # Convert safe symbol back to API format
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
    
    # 1. Create the output directory if it doesn't exist
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        logging.info(f"Created output directory: {OUTPUT_DIR}")

    # 2. Load the S/R analysis data
    try:
        with open(SR_DATA_FILE, 'r') as f:
            sr_data = json.load(f)
        logging.info(f"Successfully loaded data from {SR_DATA_FILE}")
    except FileNotFoundError:
        logging.error(f"FATAL: S/R data file not found at '{SR_DATA_FILE}'. Make sure sr_levels_analysis.py runs first.")
        return
    except json.JSONDecodeError:
        logging.error(f"FATAL: Could not decode JSON from {SR_DATA_FILE}.")
        return

    # 3. Loop through each symbol and generate a chart
    for symbol in SYMBOLS_TO_CHART:
        logging.info(f"--- Generating chart for {symbol} ---")

        # Fetch candle data for the chart
        df = fetch_ohlcv(symbol, TIMEFRAME, CANDLES_TO_PLOT)
        if df is None or df.empty:
            logging.warning(f"Could not fetch OHLCV data for {symbol}. Skipping chart.")
            continue

        # Extract the specific S/R levels to plot
        levels = sr_data.get('data', {}).get(symbol, {}).get(LOOKBACK_TO_CHART, {})
        support_levels = levels.get('support', [])
        resistance_levels = levels.get('resistance', [])

        if not support_levels and not resistance_levels:
            logging.warning(f"No S/R levels found for {symbol} with lookback {LOOKBACK_TO_CHART}. Skipping chart.")
            continue

        # Prepare horizontal lines for mplfinance
        hlines = []
        colors = []
        for level in support_levels:
            # We draw a line at the average price of the zone
            hlines.append((level['Price Start'] + level['Price End']) / 2)
            colors.append('green')
        for level in resistance_levels:
            hlines.append((level['Price Start'] + level['Price End']) / 2)
            colors.append('red')
            
        # Define chart style and title
        chart_style = 'nightclouds'
        title = f"\n{symbol} - {TIMEFRAME} Chart with {LOOKBACK_TO_CHART} S/R Zones\nLast Updated: {sr_data.get('metadata', {}).get('last_updated_utc', 'N/A').split('T')[0]}"

        # Define the output path for the image
        output_path = os.path.join(OUTPUT_DIR, f"{symbol}_chart.png")

        # Plot the chart and save it to a file
        try:
            mpf.plot(df,
                     type='candle',
                     style=chart_style,
                     title=title,
                     ylabel='Price (USDT)',
                     hlines=dict(hlines=hlines, colors=colors, linestyle='--', linewidths=0.7),
                     savefig=dict(fname=output_path, dpi=150, pad_inches=0.25) # Save the figure
                    )
            logging.info(f"SUCCESS: Chart saved to {output_path}")
        except Exception as e:
            logging.error(f"Failed to plot or save chart for {symbol}: {e}")

    logging.info("--- Chart Generation Complete ---")

if __name__ == "__main__":
    main()
