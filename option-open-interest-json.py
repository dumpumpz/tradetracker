import requests
import json
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from math import inf
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple

# --- Configuration ---
TARGET_CURRENCY = 'BTC'
END_DATE = datetime(2025, 12, 31)
OUTPUT_FILENAME = "deribit_options_market_analysis.json"
DERIBIT_API_URL = "https://www.deribit.com/api/v2/public/"
MAX_WORKERS = 20
TOP_N_OI_WALLS = 5

# --- Historical Data Configuration ---
HISTORICAL_DATA_FILENAME = "historical_market_data.json"
# Number of data points to keep. Running every 15 mins = 4 points/hr * 24 hrs * 3 days = 288 points.
MAX_HISTORY_POINTS = 288
# Statically track gamma for these major strikes in the historical data
STATICALLY_TRACKED_STRIKES = [50000, 60000, 70000, 80000, 90000, 100000, 120000, 150000]

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


# -----------------------------
# Helpers / Classification
# -----------------------------
def get_option_type(expiration_date: datetime) -> str:
    """Classifies an option expiry date as Daily, Weekly, Monthly, or Quarterly."""
    is_friday = (expiration_date.weekday() == 4)
    is_last_friday_of_month = is_friday and (expiration_date + timedelta(days=7)).month != expiration_date.month
    if is_last_friday_of_month and expiration_date.month in [3, 6, 9, 12]:
        return "Quarterly"
    if is_last_friday_of_month:
        return "Monthly"
    if is_friday:
        return "Weekly"
    return "Daily"


def parse_instrument(instrument_name: str) -> Optional[Tuple[str, datetime, float, str]]:
    """Parses a Deribit instrument name into its components."""
    try:
        parts = instrument_name.split('-')
        if len(parts) != 4: return None
        underlying = parts[0]
        expiry_dt = datetime.strptime(parts[1], "%d%b%y")
        strike = float(parts[2])
        opt_type = 'call' if parts[3].upper() == 'C' else 'put'
        return underlying, expiry_dt, strike, opt_type
    except (ValueError, IndexError):
        logging.warning(f"Could not parse instrument name: {instrument_name}")
        return None


# -----------------------------
# API Calls
# -----------------------------
def make_api_request(endpoint: str, params: Dict[str, Any], timeout: int = 15) -> Optional[Dict[str, Any]]:
    """Generic function to make a GET request to the Deribit API."""
    url = DERIBIT_API_URL + endpoint
    try:
        response = requests.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"API request to '{endpoint}' failed: {e}")
        return None


def get_btc_index_price() -> Optional[float]:
    logging.info("Fetching current BTC index price...")
    data = make_api_request("get_index_price", {'index_name': 'btc_usd'})
    if data and 'result' in data and 'index_price' in data['result']:
        price = float(data['result']['index_price'])
        logging.info(f"Current BTC Index Price: ${price:,.2f}")
        return price
    logging.error("Could not extract BTC index price from API response.")
    return None


def get_24h_put_call_ratio_by_volume(currency: str) -> Optional[Dict[str, float]]:
    logging.info("Fetching 24h Put/Call Ratio by Volume...")
    data = make_api_request("get_book_summary_by_currency", {'currency': currency, 'kind': 'option'})
    if data and 'result' in data and data['result']:
        summary = data['result'][0]
        call_volume = float(summary.get('call_volume', 0.0))
        put_volume = float(summary.get('put_volume', 0.0))
        ratio = put_volume / call_volume if call_volume > 0 else 0.0
        pcr_data = {
            "ratio": round(ratio, 4),
            "call_volume_24h_btc": call_volume,
            "put_volume_24h_btc": put_volume
        }
        logging.info(f"24h Put/Call Ratio (Volume): {pcr_data['ratio']:.2f}")
        return pcr_data
    logging.warning("Could not fetch 24h put/call ratio by volume.")
    return None


def get_instrument_names(currency: str) -> List[str]:
    logging.info(f"Fetching instrument names for {currency} options...")
    data = make_api_request("get_instruments", {'currency': currency, 'kind': 'option', 'expired': 'false'}, timeout=30)
    if data and 'result' in data:
        names = [inst['instrument_name'] for inst in data['result']]
        logging.info(f"Found {len(names)} active option instruments.")
        return names
    return []


def fetch_ticker_data(instrument_name: str) -> Optional[Dict[str, Any]]:
    """Fetches full ticker data for a single instrument."""
    data = make_api_request("ticker", {'instrument_name': instrument_name})
    return data.get('result') if data else None


def get_all_tickers_in_parallel(instrument_names: List[str]) -> List[Dict[str, Any]]:
    """Fetches ticker data for all instruments using a thread pool."""
    all_tickers = []
    total = len(instrument_names)
    logging.info(f"Fetching full ticker data for {total} instruments using {MAX_WORKERS} parallel workers...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_name = {executor.submit(fetch_ticker_data, name): name for name in instrument_names}
        for i, future in enumerate(as_completed(future_to_name), 1):
            try:
                data = future.result()
                if data:
                    all_tickers.append(data)
            except Exception as e:
                name = future_to_name[future]
                logging.error(f"Error fetching ticker for {name}: {e}")
            if i % 250 == 0 or i == total:
                logging.info(f"  ... fetched {i}/{total}")
    logging.info(f"Successfully fetched data for {len(all_tickers)} instruments.")
    return all_tickers


# -----------------------------
# Core Calculations
# -----------------------------
def aggregate_market_data(all_tickers: List[Dict[str, Any]], end_date: datetime):
    """Aggregates raw ticker data into structured formats for analysis."""
    grouped_options = defaultdict(list)
    total_gamma_by_strike = defaultdict(float)
    logging.info(f"Processing {len(all_tickers)} tickers with full greeks data...")

    for tk in all_tickers:
        parsed = parse_instrument(tk.get('instrument_name', ''))
        if not parsed: continue
        _, expiry_dt, strike, opt_type = parsed

        if expiry_dt > end_date: continue

        oi = float(tk.get('open_interest', 0.0))
        if oi == 0: continue

        gamma = float(tk.get('greeks', {}).get('gamma', 0.0))
        # Dealer gamma is the opposite of customer gamma. If a customer is long an option (positive gamma),
        # the dealer who sold it is short the option (negative gamma). The dealer's exposure is what matters.
        # Open Interest is in contracts (BTC), so Gamma * OI gives the total gamma exposure in BTC per 1 USD move.
        dealer_gamma_contrib = -gamma * oi

        grouped_options[expiry_dt].append({
            'strike': strike,
            'type': opt_type,
            'oi': oi,
            'iv': float(tk.get('mark_iv', 0.0)) / 100.0,
            'volume_24h': float(tk.get('stats', {}).get('volume', 0.0)),
            'dealer_gamma_contrib': dealer_gamma_contrib
        })
        total_gamma_by_strike[strike] += dealer_gamma_contrib

    logging.info("Finished processing all tickers.")
    return grouped_options, total_gamma_by_strike


def find_oi_walls(options_list: List[Dict[str, Any]], top_n: int) -> Dict[str, List[Dict[str, Any]]]:
    """Finds the top N call and put strikes by Open Interest for a given expiry."""
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


def calculate_max_pain(options_list: List[Dict[str, Any]]) -> Optional[float]:
    """Calculates the Max Pain strike for a given expiry."""
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


def calculate_gamma_flip(total_gamma_by_strike: Dict[float, float], spot_price: float) -> Optional[float]:
    """Calculates the price level where cumulative dealer gamma exposure flips from negative to positive."""
    if not total_gamma_by_strike:
        return None

    sorted_strikes = sorted(total_gamma_by_strike.keys())
    cumulative_gamma = 0.0
    # Find the total negative gamma to start from
    total_negative_gamma = sum(g for g in total_gamma_by_strike.values() if g < 0)

    # Start from the lowest strike and accumulate gamma
    for strike in sorted_strikes:
        gamma_at_strike = total_gamma_by_strike[strike]
        # Check if crossing the zero line happens within this strike interval
        if cumulative_gamma + gamma_at_strike > 0 and cumulative_gamma <= 0:
            # Simple linear interpolation to find the crossover point
            prev_strike = sorted_strikes[sorted_strikes.index(strike) - 1] if sorted_strikes.index(
                strike) > 0 else strike
            return (prev_strike + strike) / 2
        cumulative_gamma += gamma_at_strike

    # If no flip point is found (e.g., gamma is all positive or all negative), return None
    return None


def get_key_gamma_strikes_for_history(total_gamma_by_strike: Dict[float, float], spot_price: float) -> Dict[str, float]:
    """Identifies and returns gamma values for a set of key strikes for historical tracking."""
    # Find the top 5 dynamic short gamma strikes closest to the spot price
    dynamic_strikes = []
    short_gamma_strikes = [{'strike': s, 'distance': abs(s - spot_price)} for s, g in total_gamma_by_strike.items() if
                           g < 0]
    short_gamma_strikes.sort(key=lambda x: x['distance'])
    for item in short_gamma_strikes[:5]:
        dynamic_strikes.append(item['strike'])

    key_strikes_set = set(STATICALLY_TRACKED_STRIKES) | set(dynamic_strikes)

    return {
        str(int(strike)): round(total_gamma_by_strike.get(strike, 0.0), 4)
        for strike in sorted(list(key_strikes_set))
    }


# -----------------------------
# Data Persistence
# -----------------------------
def update_historical_data(filename: str, new_entry: Dict[str, Any]):
    """Reads, appends, trims, and saves historical market data to a JSON file."""
    history = []
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                history = json.load(f)
            if not isinstance(history, list):
                logging.warning(f"Historical data file '{filename}' is not a list. Starting fresh.")
                history = []
        except (json.JSONDecodeError, IOError) as e:
            logging.warning(f"Could not read/parse '{filename}'. Starting fresh. Error: {e}")
            history = []

    history.append(new_entry)
    trimmed_history = history[-MAX_HISTORY_POINTS:]

    try:
        with open(filename, 'w') as f:
            json.dump(trimmed_history, f, indent=2)
        logging.info(f"✅ Historical data updated and saved to {filename}")
    except IOError as e:
        logging.error(f"Could not write to historical data file {filename}. {e}")


# -----------------------------
# Final JSON Assembly
# -----------------------------
def process_and_save_data(grouped_options: Dict, total_gamma_by_strike: Dict, btc_price: float, pcr_by_volume: Dict):
    """Orchestrates all final calculations and saves the output files."""
    if not grouped_options:
        logging.error("No options data to process and save.")
        return

    logging.info("Calculating final metrics and preparing JSON files...")
    expirations_list = []

    # --- Market-wide totals ---
    total_oi_btc, total_volume_24h_btc = 0.0, 0.0
    total_call_oi_btc, total_put_oi_btc = 0.0, 0.0

    for expiry_dt, options_list in sorted(grouped_options.items()):
        # Per-expiry calculations
        expiry_call_oi = sum(o['oi'] for o in options_list if o['type'] == 'call')
        expiry_put_oi = sum(o['oi'] for o in options_list if o['type'] == 'put')
        expiry_total_oi = expiry_call_oi + expiry_put_oi
        expiry_volume = sum(o['volume_24h'] for o in options_list)

        # Accumulate market-wide totals
        total_call_oi_btc += expiry_call_oi
        total_put_oi_btc += expiry_put_oi
        total_oi_btc += expiry_total_oi
        total_volume_24h_btc += expiry_volume

        # Other per-expiry metrics
        weighted_call_iv = sum(o['iv'] * o['oi'] for o in options_list if
                               o['type'] == 'call') / expiry_call_oi if expiry_call_oi > 0 else 0
        weighted_put_iv = sum(
            o['iv'] * o['oi'] for o in options_list if o['type'] == 'put') / expiry_put_oi if expiry_put_oi > 0 else 0

        otype = get_option_type(expiry_dt)
        max_pain = calculate_max_pain(options_list) if otype in ["Monthly", "Quarterly"] else None

        # Extract per-expiry gamma curve
        gex_by_strike = {opt['strike']: opt['dealer_gamma_contrib'] for opt in options_list}
        gex_curve = sorted([{'strike': s, 'dealer_gamma': g} for s, g in gex_by_strike.items()],
                           key=lambda x: x['strike'])

        expirations_list.append({
            "expiration_date": expiry_dt.strftime('%Y-%m-%d'),
            "option_type": otype,
            "open_interest_btc": round(expiry_total_oi, 2),
            "notional_value_usd": round(expiry_total_oi * btc_price, 2),
            "total_volume_24h_btc": round(expiry_volume, 2),
            "pcr_by_oi": round(expiry_put_oi / expiry_call_oi, 4) if expiry_call_oi > 0 else 0,
            "max_pain_strike": max_pain,
            "open_interest_walls": find_oi_walls(options_list, top_n=TOP_N_OI_WALLS),
            "average_iv_data": {
                "call_iv": round(weighted_call_iv, 4),
                "put_iv": round(weighted_put_iv, 4),
                "skew_proxy": round(weighted_call_iv - weighted_put_iv, 4)
            },
            "dealer_gamma_by_strike": gex_curve,
        })

    # --- Final Market-Wide Calculations ---
    pcr_by_oi = total_put_oi_btc / total_call_oi_btc if total_call_oi_btc > 0 else 0
    total_gex = sum(total_gamma_by_strike.values())
    gamma_flip_level = calculate_gamma_flip(total_gamma_by_strike, btc_price)

    # --- Assemble Final Output ---
    now_timestamp = datetime.utcnow().isoformat() + "Z"

    market_summary = {
        "total_open_interest_btc": round(total_oi_btc, 2),
        "total_notional_oi_usd": round(total_oi_btc * btc_price, 2),
        "total_volume_24h_btc": round(total_volume_24h_btc, 2),
        "pcr_by_open_interest": round(pcr_by_oi, 4),
        "pcr_by_24h_volume": pcr_by_volume,
        "total_dealer_gamma_exposure": round(total_gex, 4),
        "gamma_flip_level_usd": gamma_flip_level,
    }

    definitions = {
        # ... (definitions remain largely the same, but add new ones)
        "gamma_flip_level_usd": "The estimated BTC price where total dealer gamma exposure flips from negative to positive. Below this level, dealer hedging tends to suppress volatility (buy dips, sell rips). Above this level, hedging can amplify volatility (sell dips, buy rips). It's a key pivot point.",
        "total_dealer_gamma_exposure": "The sum of all dealer gamma positions across all strikes and expiries. A large negative value indicates the market is vulnerable to volatile moves as dealers are net short gamma.",
        "pcr_by_open_interest": "Put/Call Ratio calculated from total Open Interest. A more stable indicator of overall market sentiment and positioning than the volume-based ratio.",
        "pcr_by_24h_volume": "Put/Call Ratio from the last 24h of trading volume. More indicative of short-term hedging/speculative activity.",
        # Add other definitions as needed
    }

    output_data = {
        "metadata": {
            "calculation_timestamp_utc": now_timestamp,
            "btc_index_price_usd": btc_price,
            "currency": TARGET_CURRENCY,
        },
        "definitions": definitions,
        "market_summary": market_summary,
        "expirations": expirations_list
    }

    try:
        with open(OUTPUT_FILENAME, 'w') as f:
            json.dump(output_data, f, indent=2)
        logging.info(f"✅ Full market analysis saved to {OUTPUT_FILENAME}")
    except IOError as e:
        logging.error(f"Could not write to file {OUTPUT_FILENAME}. {e}")

    # --- Update Historical Data ---
    key_gamma_data_for_history = get_key_gamma_strikes_for_history(total_gamma_by_strike, btc_price)

    new_historical_entry = {
        "timestamp": now_timestamp,
        "btc_price": btc_price,
        "total_open_interest_btc": market_summary["total_open_interest_btc"],
        "total_volume_24h_btc": market_summary["total_volume_24h_btc"],
        "pcr_by_oi": market_summary["pcr_by_open_interest"],
        "pcr_by_volume": market_summary["pcr_by_24h_volume"]["ratio"] if market_summary["pcr_by_24h_volume"] else None,
        "total_gex": market_summary["total_dealer_gamma_exposure"],
        "gamma_flip_level": market_summary["gamma_flip_level_usd"],
        "per_strike_gamma": key_gamma_data_for_history
    }
    update_historical_data(HISTORICAL_DATA_FILENAME, new_historical_entry)


# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":
    spot_price = get_btc_index_price()
    if not spot_price:
        raise SystemExit("Fatal: Could not fetch BTC index price. Exiting.")

    pcr_volume_data = get_24h_put_call_ratio_by_volume(TARGET_CURRENCY)
    if not pcr_volume_data:
        logging.warning("Could not fetch 24h P/C Ratio by Volume. Proceeding without it.")
        pcr_volume_data = {}  # Ensure it's a dict to avoid errors

    instrument_names = get_instrument_names(TARGET_CURRENCY)
    if not instrument_names:
        raise SystemExit("Fatal: No instrument names found. Exiting.")

    all_tickers = get_all_tickers_in_parallel(instrument_names)
    if not all_tickers:
        raise SystemExit("Fatal: Could not fetch any ticker data. Exiting.")

    grouped_options, total_gamma_by_strike = aggregate_market_data(all_tickers, END_DATE)
    if not grouped_options:
        raise SystemExit("Fatal: No valid options data after processing tickers. Exiting.")

    process_and_save_data(grouped_options, total_gamma_by_strike, spot_price, pcr_volume_data)

    logging.info("--- Script finished successfully! ---")
