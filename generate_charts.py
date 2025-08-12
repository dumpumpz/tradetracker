import pandas as pd
import json
import os
import logging
import requests
import mplfinance as mpf
import matplotlib
import random

# ### NEW ### Import BeautifulSoup for proxy scraping
from bs4 import BeautifulSoup

# Use a non-GUI backend, essential for running in GitHub Actions
matplotlib.use('Agg')

# --- Configuration ---
SYMBOLS_TO_CHART = ['BTC-USDT', 'ETH-USDT']
SR_DATA_FILE = 'sr_levels_analysis.json'
LOOKBACK_TO_CHART = '14d'
TIMEFRAME = '1h'
CANDLES_TO_PLOT = 240
OUTPUT_DIR = 'charts'
API_ENDPOINT = "https://api3.binance.com/api/v3/klines" # Use a resilient endpoint

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# ### NEW ### Copied the proxy-finding logic from the main script
def get_working_proxy():
    """
    Fetches a list of free proxies and returns the first one that works.
    """
    url = "https://free-proxy-list.net/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser') # Use html.parser, no lxml needed
        proxy_list = []
        for row in soup.find("table", attrs={"class": "table"}).find_all("tr")[1:]:
            tds = row.find_all("td")
            if tds[6].text.strip() == "yes":
                ip = tds[0].text.strip()
                port = tds[1].text.strip()
                proxy_list.append(f"http://{ip}:{port}")
        
        random.shuffle(proxy_list)
        logging.info(f"Found {len(proxy_list)} potential proxies for charting. Testing...")

        for proxy_url in proxy_list:
            proxies = {"http": proxy_url, "https": proxy_url}
            try:
                test_response = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
                if test_response.status_code == 200:
                    logging.info(f"SUCCESS: Charting will use proxy: {proxy_url}")
                    return proxies
            except requests.exceptions.RequestException:
                continue
    except Exception as e:
        logging.warning(f"Could not fetch or validate proxies for charting: {e}")
    
    logging.error("No working proxies found for charting. Trying direct connection.")
    return None

# ### MODIFIED ### Updated to accept and use the proxy
def fetch_ohlcv(symbol, interval, limit, proxies):
    """Fetches a limited number of candles for plotting, using a proxy."""
    api_symbol = symbol.replace('-', '')
    url = f'{API_ENDPOINT}?symbol={api_symbol}&interval={interval}&limit={limit}'
    try:
        response = requests.get(url, timeout=20, proxies=proxies)
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
        logging.info(f"Created output directory: {OUTPUT_DIR}")

    try:
        with open(SR_DATA_FILE, 'r') as f:
            sr_data = json.load(f)
        logging.info(f"Successfully loaded data from {SR_DATA_FILE}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"FATAL: Could not read or parse '{SR_DATA_FILE}'. Error: {e}")
        return

    # ### NEW ### Get a proxy before starting the loop
    proxies = get_working_proxy()

    for symbol in SYMBOLS_TO_CHART:
        logging.info(f"--- Generating chart for {symbol} ---")

        # ### MODIFIED ### Pass the proxy to the fetch function
        df = fetch_ohlcv(symbol, TIMEFRAME, CANDLES_TO_PLOT, proxies)
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
