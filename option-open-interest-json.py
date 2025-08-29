import requests
from datetime import datetime, timedelta
import json
import os
from collections import defaultdict
from math import inf
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
TARGET_CURRENCY = 'BTC'
END_DATE = datetime(2025, 12, 31)
OUTPUT_FILENAME = "deribit_options_market_analysis.json"
DERIBIT_API_URL = "https://www.deribit.com/api/v2/public/"
MAX_WORKERS = 20
TOP_N_OI_WALLS = 5

# --- NEW: Historical Data Configuration ---
HISTORICAL_DATA_FILENAME = "historical_market_data.json"
# Number of data points to keep. Running every 15 mins = 4 points/hr * 24 hrs * 3 days = 288 points for 3 days of history.
MAX_HISTORY_POINTS = 288


# -----------------------------
# Helpers / classification
# (No changes in this section)
# -----------------------------
def get_option_type(expiration_date: datetime) -> str:
    is_friday = (expiration_date.weekday() == 4)
    is_last_friday_of_month = is_friday and (expiration_date + timedelta(days=7)).month != expiration_date.month
    if is_last_friday_of_month and expiration_date.month in [3, 6, 9, 12]:
        return "Quarterly"
    if is_last_friday_of_month:
        return "Monthly"
    if is_friday:
        return "Weekly"
    return "Daily"

def parse_instrument(instrument_name: str):
    try:
        parts = instrument_name.split('-')
        if len(parts) != 4: return None
        underlying = parts[0]
        expiry_dt = datetime.strptime(parts[1], "%d%b%y")
        strike = float(parts[2])
        opt_type = 'call' if parts[3].upper() == 'C' else 'put'
        return underlying, expiry_dt, strike, opt_type
    except Exception:
        return None

# -----------------------------
# API calls
# (No changes in this section)
# -----------------------------
def get_btc_index_price() -> float | None:
    print("Fetching current BTC index price...")
    url = DERIBIT_API_URL + "get_index_price"
    params = {'index_name': 'btc_usd'}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        price = response.json().get('result', {}).get('index_price')
        if price:
            print(f"Current BTC Index Price: ${price:,.2f}")
            return float(price)
    except requests.exceptions.RequestException as e:
        print(f"Error fetching BTC index price: {e}")
    return None

def get_put_call_ratio(currency: str) -> dict | None:
    print("Fetching 24h Put/Call Ratio...")
    url = DERIBIT_API_URL + "get_book_summary_by_currency"
    params = {'currency': currency, 'kind': 'option'}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        summary = response.json().get('result', [])
        if not summary: return None
        data = summary[0]
        call_volume = float(data.get('call_volume', 0.0))
        put_volume = float(data.get('put_volume', 0.0))
        ratio = put_volume / call_volume if call_volume > 0 else 0.0
        pcr_data = {
            "ratio_by_volume": round(ratio, 4),
            "call_volume_24h_btc": call_volume,
            "put_volume_24h_btc": put_volume
        }
        print(f"Put/Call Ratio (Volume): {pcr_data['ratio_by_volume']:.2f}")
        return pcr_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching put/call ratio: {e}")
    return None

def get_instrument_names(currency: str) -> list[str]:
    print(f"Fetching instrument names for {currency} options...")
    url = DERIBIT_API_URL + "get_instruments"
    params = {'currency': currency, 'kind': 'option', 'expired': 'false'}
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        instruments = r.json().get('result', []) or []
        names = [inst['instrument_name'] for inst in instruments]
        print(f"Found {len(names)} active option instruments.")
        return names
    except requests.exceptions.RequestException as e:
        print(f"Error listing instruments: {e}")
        return []

def fetch_ticker_data(instrument_name: str) -> dict | None:
    url = DERIBIT_API_URL + "ticker"
    params = {'instrument_name': instrument_name}
    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get('result', {})
    except requests.exceptions.RequestException:
        return None

def get_all_tickers_in_parallel(instrument_names: list[str]) -> list[dict]:
    all_tickers = []
    total = len(instrument_names)
    print(f"Fetching full ticker data for {total} instruments using {MAX_WORKERS} parallel workers...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_name = {executor.submit(fetch_ticker_data, name): name for name in instrument_names}
        for i, future in enumerate(as_completed(future_to_name), 1):
            try:
                data = future.result()
                if data: all_tickers.append(data)
            except Exception as e:
                name = future_to_name[future]
                print(f"Error fetching ticker for {name}: {e}")
            if i % 100 == 0 or i == total: print(f"  ... fetched {i}/{total}")
    print(f"Successfully fetched data for {len(all_tickers)} instruments.")
    return all_tickers


# -----------------------------
# Core Calculations
# (No changes in this section)
# -----------------------------
def aggregate_by_expiry_and_strike(all_tickers, end_date: datetime):
    grouped_options = defaultdict(list)
    gex_by_expiry_strike = defaultdict(lambda: defaultdict(float))
    total = len(all_tickers)
    print(f"Processing {total} tickers with full greeks data...")
    for tk in all_tickers:
        name = tk.get('instrument_name')
        parsed = parse_instrument(name)
        if not parsed: continue
        _, expiry_dt, strike, opt_type = parsed
        if expiry_dt > end_date: continue
        oi = tk.get('open_interest')
        if oi is None or float(oi) == 0: continue

        greeks = tk.get('greeks', {})
        gamma = greeks.get('gamma', 0.0)
        stats = tk.get('stats', {})
        volume_24h = stats.get('volume', 0.0)
        iv = tk.get('mark_iv', 0.0)
        oi, gamma, volume_24h = float(oi), float(gamma), float(volume_24h)
        iv = float(iv) / 100.0

        dealer_gamma_contrib = -gamma * oi
        grouped_options[expiry_dt].append({
            'strike': strike, 'type': opt_type, 'oi': oi, 'gamma': gamma,
            'iv': iv, 'volume_24h': volume_24h, 'dealer_gamma_contrib': dealer_gamma_contrib
        })
        gex_by_expiry_strike[expiry_dt][strike] += dealer_gamma_contrib
    print("Finished processing all tickers.")
    return grouped_options, gex_by_expiry_strike

def find_oi_walls(options_list, top_n):
    calls, puts = defaultdict(float), defaultdict(float)
    for opt in options_list:
        if opt['type'] == 'call':
            calls[opt['strike']] += opt['oi']
        else:
            puts[opt['strike']] += opt['oi']
    sorted_calls = sorted(calls.items(), key=lambda item: item[1], reverse=True)
    sorted_puts = sorted(puts.items(), key=lambda item: item[1], reverse=True)
    return {
        "top_call_strikes": [{"strike": k, "open_interest_btc": round(v, 2)} for k, v in sorted_calls[:top_n]],
        "top_put_strikes": [{"strike": k, "open_interest_btc": round(v, 2)} for k, v in sorted_puts[:top_n]]
    }

def calculate_max_pain(options_list):
    if not options_list: return None
    unique_strikes = sorted(list(set(opt['strike'] for opt in options_list)))
    min_pain_value, max_pain_strike = inf, None
    for test_price in unique_strikes:
        total_pain = sum((test_price - opt['strike']) * opt['oi'] for opt in options_list if
                         opt['type'] == 'call' and test_price > opt['strike'])
        total_pain += sum((opt['strike'] - test_price) * opt['oi'] for opt in options_list if
                          opt['type'] == 'put' and test_price < opt['strike'])
        if total_pain < min_pain_value:
            min_pain_value, max_pain_strike = total_pain, test_price
    return max_pain_strike

def summarize_short_gamma_zones(gex_by_expiry_strike, spot_price, top_n_per_expiry=10):
    results_by_expiry = {}
    for expiry_dt, strike_map in gex_by_expiry_strike.items():
        rows = [{'strike': s, 'dealer_gamma': g, 'distance_to_spot': abs(s - spot_price)} for s, g in strike_map.items()
                if g < 0]
        rows.sort(key=lambda r: r['distance_to_spot'])
        results_by_expiry[expiry_dt] = rows[:top_n_per_expiry]
    return results_by_expiry

# --- NEW: Function to update historical data file ---
def update_historical_data(filename: str, new_entry: dict):
    """Reads, updates, and saves the historical data JSON file."""
    history = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                history = json.load(f)
            if not isinstance(history, list): # Basic validation
                print(f"Warning: Historical data file '{filename}' is not a list. Starting fresh.")
                history = []
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read or parse '{filename}'. Starting fresh. Error: {e}")
            history = []

    history.append(new_entry)

    # Trim the history to the max number of points
    trimmed_history = history[-MAX_HISTORY_POINTS:]

    try:
        with open(filename, 'w') as f:
            json.dump(trimmed_history, f, indent=2)
        print(f"✅ Historical data updated and saved to {filename}")
    except IOError as e:
        print(f"Error: Could not write to historical data file {filename}. {e}")


# -----------------------------
# Final JSON Assembly
# (This section is modified to calculate totals and call the new function)
# -----------------------------
def process_and_save_json(grouped_options, gex_by_expiry_strike, btc_price, pcr_data, filename):
    if not grouped_options:
        print("No options data to save.")
        return
    print("Calculating final metrics and preparing JSON files...")
    expirations_list = []
    short_gamma_lookup = summarize_short_gamma_zones(gex_by_expiry_strike, btc_price)

    # --- NEW: Variables to store market-wide totals ---
    total_oi_all_expiries = 0
    total_volume_all_expiries = 0
    total_short_gamma_all_expiries = 0
    # ---

    for expiry_dt in sorted(grouped_options.keys()):
        options_list = grouped_options[expiry_dt]

        total_volume_24h_btc = sum(opt['volume_24h'] for opt in options_list)
        total_call_oi = sum(o['oi'] for o in options_list if o['type'] == 'call')
        total_put_oi = sum(o['oi'] for o in options_list if o['type'] == 'put')
        weighted_call_iv = sum(o['iv'] * o['oi'] for o in options_list if o['type'] == 'call') / total_call_oi if total_call_oi > 0 else 0
        weighted_put_iv = sum(o['iv'] * o['oi'] for o in options_list if o['type'] == 'put') / total_put_oi if total_put_oi > 0 else 0
        average_iv_data = {
            "call_iv": round(weighted_call_iv, 4),
            "put_iv": round(weighted_put_iv, 4),
            "skew_proxy": round(weighted_call_iv - weighted_put_iv, 4) if weighted_call_iv > 0 and weighted_put_iv > 0 else 0
        }
        oi_walls = find_oi_walls(options_list, top_n=TOP_N_OI_WALLS)
        total_oi_btc = total_call_oi + total_put_oi
        notional_oi_usd = total_oi_btc * btc_price
        otype = get_option_type(expiry_dt)
        max_pain_strike = calculate_max_pain(options_list) if otype in ["Monthly", "Quarterly"] else None
        gex_curve = sorted([{'strike': s, 'dealer_gamma': g} for s, g in gex_by_expiry_strike[expiry_dt].items()], key=lambda x: x['strike'])

        expirations_list.append({
            "expiration_date": expiry_dt.strftime('%Y-%m-%d'),
            "day_of_week": expiry_dt.strftime('%A'),
            "option_type": otype,
            "open_interest_btc": round(total_oi_btc, 4),
            "notional_value_usd": round(notional_oi_usd, 2),
            "total_volume_24h_btc": round(total_volume_24h_btc, 4),
            "max_pain_strike": max_pain_strike,
            "open_interest_walls": oi_walls,
            "average_iv_data": average_iv_data,
            "dealer_gamma_by_strike": gex_curve,
            "short_gamma_near_spot": short_gamma_lookup.get(expiry_dt, [])
        })

        # --- NEW: Accumulate totals for historical data ---
        total_oi_all_expiries += total_oi_btc
        total_volume_all_expiries += total_volume_24h_btc
        total_short_gamma_for_expiry = sum(item['dealer_gamma'] for item in gex_curve if item['dealer_gamma'] < 0)
        total_short_gamma_all_expiries += total_short_gamma_for_expiry
        # ---

    # --- NEW: Create and save the historical data point ---
    now_timestamp = datetime.utcnow().isoformat() + "Z"
    new_historical_entry = {
        "timestamp": now_timestamp,
        "btc_price": btc_price,
        "total_open_interest_btc": round(total_oi_all_expiries, 2),
        "total_volume_24h_btc": round(total_volume_all_expiries, 2),
        "pcr_by_volume": pcr_data.get("ratio_by_volume"),
        "total_short_gamma": round(total_short_gamma_all_expiries, 4)
    }
    update_historical_data(HISTORICAL_DATA_FILENAME, new_historical_entry)
    # ---

    definitions = { "..." } # Definitions are unchanged, snipped for brevity
    # (Copy the original definitions dictionary here)

    output_data = {
        "definitions": definitions,
        "metadata": {
            "calculation_timestamp_utc": now_timestamp,
            "btc_index_price_usd": btc_price,
            "currency": TARGET_CURRENCY,
            "put_call_ratio_24h_volume": pcr_data
        },
        "expirations": expirations_list
    }

    try:
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\n✅ Full market analysis saved to {filename}")
    except IOError as e:
        print(f"Error: Could not write to file {filename}. {e}")

# -----------------------------
# Main Execution
# (No changes in this section)
# -----------------------------
if __name__ == "__main__":
    spot = get_btc_index_price()
    if not spot: raise SystemExit("Could not fetch BTC index price.")

    pcr = get_put_call_ratio(TARGET_CURRENCY)
    if not pcr:
        print("Warning: Could not fetch Put/Call Ratio. Proceeding without it.")
        pcr = {}

    instrument_names = get_instrument_names(TARGET_CURRENCY)
    if not instrument_names: raise SystemExit("No instrument names retrieved.")

    all_tickers = get_all_tickers_in_parallel(instrument_names)
    if not all_tickers: raise SystemExit("Could not fetch ticker data.")

    grouped_options, gex_by_expiry_strike = aggregate_by_expiry_and_strike(all_tickers, END_DATE)
    if not grouped_options: raise SystemExit("No options data after processing.")

    process_and_save_json(grouped_options, gex_by_expiry_strike, spot, pcr, OUTPUT_FILENAME)
