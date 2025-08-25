import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import json


# --- [1] FULL ANALYSIS LOGIC ---

def get_historical_data(symbol, interval, limit):
    """Fetches historical candlestick data, ignoring the current unclosed candle."""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()[:-1]
    except requests.RequestException as e:
        print(f"Error fetching data for {symbol} on {interval}: {e}")
        return None


# S-signal helper functions remain unchanged
def find_s1_signal(df, crossover_iloc, signal_type, initial_level):
    df_after_crossover = df.iloc[crossover_iloc + 1:]
    effective_level = initial_level
    for index, candle in df_after_crossover.iterrows():
        if signal_type == "Bullish Confirmation":
            if candle['Open'] > initial_level and candle['Close'] > effective_level:
                return {"raw_date": index}
            elif candle['High'] > effective_level:
                effective_level = candle['High']
        elif signal_type == "Bearish Confirmation":
            if candle['Open'] < initial_level and candle['Close'] < effective_level:
                return {"raw_date": index}
            elif candle['Low'] < effective_level:
                effective_level = candle['Low']
    return None


def find_s2_signal(df, s1_signal_info, signal_type):
    s1_iloc = df.index.get_loc(s1_signal_info['raw_date'])
    s1_candle = df.iloc[s1_iloc]
    s1_open_level = s1_candle['Open']
    effective_level = s1_candle['High'] if signal_type == "Bullish Confirmation" else s1_candle['Low']
    for index, candle in df.iloc[s1_iloc + 1:].iterrows():
        if signal_type == "Bullish Confirmation":
            if candle['Open'] > s1_open_level and candle['Close'] > effective_level:
                return {"raw_date": index}
            elif candle['High'] > effective_level:
                effective_level = candle['High']
        elif signal_type == "Bearish Confirmation":
            if candle['Open'] < s1_open_level and candle['Close'] < effective_level:
                return {"raw_date": index}
            elif candle['Low'] < effective_level:
                effective_level = candle['Low']
    return None


def find_s3_signal(df, s2_signal_info, signal_type):
    s2_iloc = df.index.get_loc(s2_signal_info['raw_date'])
    s2_candle = df.iloc[s2_iloc]
    open_req = s2_candle['High'] if signal_type == "Bullish Confirmation" else s2_candle['Low']
    effective_level = open_req
    for index, candle in df.iloc[s2_iloc + 1:].iterrows():
        if signal_type == "Bullish Confirmation":
            if candle['Open'] > open_req and candle['Close'] > effective_level and candle['Close'] > candle['Open']:
                return {"raw_date": index}
            elif candle['High'] > effective_level:
                effective_level = candle['High']
        elif signal_type == "Bearish Confirmation":
            if candle['Open'] < open_req and candle['Close'] < effective_level and candle['Close'] < candle['Open']:
                return {"raw_date": index}
            elif candle['Low'] < effective_level:
                effective_level = candle['Low']
    return None


def find_s4_signal(df, s3_signal_info, signal_type):
    s3_iloc = df.index.get_loc(s3_signal_info['raw_date'])
    s3_candle = df.iloc[s3_iloc]
    open_req = s3_candle['High'] if signal_type == "Bullish Confirmation" else s3_candle['Low']
    effective_level = open_req
    for index, candle in df.iloc[s3_iloc + 1:].iterrows():
        if signal_type == "Bullish Confirmation":
            if candle['Open'] > open_req and candle['Close'] > effective_level and candle['Close'] > candle['Open']:
                return {"raw_date": index}
            elif candle['High'] > effective_level:
                effective_level = candle['High']
        elif signal_type == "Bearish Confirmation":
            if candle['Open'] < open_req and candle['Close'] < effective_level and candle['Close'] < candle['Open']:
                return {"raw_date": index}
            elif candle['Low'] < effective_level:
                effective_level = candle['Low']
    return None


def find_latest_combined_signal(data):
    if not data or len(data) < 49: return None
    columns = ["Open_time", "Open", "High", "Low", "Close", "Volume", "Close_time", "Quote_asset_volume",
               "Number_of_trades", "Taker_buy_base_asset_volume", "Taker_buy_quote_asset_volume", "Ignore"]
    df = pd.DataFrame(data, columns=columns)
    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['DateTime'] = pd.to_datetime(df['Close_time'], unit='ms')
    df.set_index('DateTime', inplace=True)
    df['SMA_13'] = df['Close'].rolling(window=13).mean()
    df['EMA_13'] = df['Close'].ewm(span=13, adjust=False).mean()
    df['SMA_49'] = df['Close'].rolling(window=49).mean()
    df['EMA_49'] = df['Close'].ewm(span=49, adjust=False).mean()
    df.dropna(inplace=True)
    if df.empty: return None

    df['bullish_state'] = (df[['EMA_13', 'SMA_13']].min(axis=1)) > (df[['EMA_49', 'SMA_49']].max(axis=1))
    df['bearish_state'] = (df[['EMA_13', 'SMA_13']].max(axis=1)) < (df[['EMA_49', 'SMA_49']].min(axis=1))
    df['grey_state'] = ~(df['bullish_state'] | df['bearish_state'])

    if df.iloc[-1]['grey_state']:
        return {"type": "Grey Crossover", "support_value": None}

    df['bullish_crossover_event'] = (df['bullish_state'] == True) & (df['bullish_state'].shift(1) == False)
    df['bearish_crossover_event'] = (df['bearish_state'] == True) & (df['bearish_state'].shift(1) == False)
    last_bull_event = df[df['bullish_crossover_event']].index.max()
    last_bear_event = df[df['bearish_crossover_event']].index.max()

    if pd.isna(last_bull_event) and pd.isna(last_bear_event): return None
    if pd.isna(last_bear_event) or (pd.notna(last_bull_event) and last_bull_event > last_bear_event):
        event_date, signal_type = last_bull_event, "Bullish Confirmation"
    else:
        event_date, signal_type = last_bear_event, "Bearish Confirmation"

    crossover_iloc = df.index.get_loc(event_date)
    df_before_crossover = df.iloc[:crossover_iloc]
    last_colored_candle = df_before_crossover[~df_before_crossover['grey_state']].index.max()
    start_grey_iloc = df.index.get_loc(last_colored_candle) + 1 if pd.notna(last_colored_candle) else 0
    search_range_df = df.iloc[start_grey_iloc: crossover_iloc + 1]

    s1_test_level = None
    support_value = None
    if not search_range_df.empty:
        period_low = search_range_df['Low'].min()
        period_high = search_range_df['High'].max()
        if signal_type == "Bullish Confirmation":
            s1_test_level = period_high
            support_value = period_low
        else:  # Bearish Confirmation
            s1_test_level = period_low
            support_value = period_high

    s1, s2, s3, s4 = None, None, None, None
    if s1_test_level is not None:
        s1 = find_s1_signal(df, crossover_iloc, signal_type, s1_test_level)
        if s1:
            s2 = find_s2_signal(df, s1, signal_type)
            if s2:
                s3 = find_s3_signal(df, s2, signal_type)
                if s3: s4 = find_s4_signal(df, s3, signal_type)

    return {"type": signal_type, "s1": s1, "s2": s2, "s3": s3, "s4": s4, "support_value": support_value}


# --- [2] MAIN EXPORTING LOOP ---

def main():
    """Main function to run analysis and save results to JSON."""
    symbols = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["1h", "2h", "4h", "1d", "1w", "1M"]
    output_filename = "crypto_signals.json"

    while True:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting analysis for {', '.join(symbols)}...")
        all_results = {}
        for symbol in symbols:
            print(f"--- Analyzing {symbol} ---")
            symbol_results = {}
            for tf in timeframes:
                klines = get_historical_data(symbol, tf, 1000)
                signal = find_latest_combined_signal(klines)

                stage = "No Signal"
                colour = "Grey"
                support_str = "N/A"
                if signal:
                    support_val = signal.get("support_value")
                    if support_val is not None:
                        support_str = f"{support_val:,.2f}"

                    base_type = signal["type"]
                    if base_type == "Grey Crossover":
                        stage = "Grey Crossover"
                        colour = "Grey"
                    else:
                        colour = "Green" if "Bullish" in base_type else "Red"
                        # <<< MODIFIED SECTION: Changed stage names to S0, S1, etc. >>>
                        if signal.get("s4"):
                            stage = "S4"
                        elif signal.get("s3"):
                            stage = "S3"
                        elif signal.get("s2"):
                            stage = "S2"
                        elif signal.get("s1"):
                            stage = "S1"
                        else:
                            stage = "S0" # S0 represents the initial crossover event

                symbol_results[tf] = {"stage": stage, "colour": colour, "support": support_str}
            all_results[symbol] = symbol_results

        try:
            with open(output_filename, 'w') as f:
                json.dump(all_results, f, indent=4)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully saved data to {output_filename}")
        except IOError as e:
            print(f"Error: Could not write to file {output_filename}. Reason: {e}")

        now = datetime.now()
        next_run = (now + timedelta(hours=1)).replace(minute=2, second=0,
                                                      microsecond=0) if now.minute >= 2 else now.replace(minute=2,
                                                                                                         second=0,
                                                                                                         microsecond=0)
        sleep_duration = (next_run - now).total_seconds()

        print(f"--- Analysis complete. Next update at {next_run.strftime('%Y-%m-%d %H:%M:%S')} ---")
        if sleep_duration > 0:
            time.sleep(sleep_duration)


# --- [3] SCRIPT ENTRY POINT ---
if __name__ == "__main__":
    main()