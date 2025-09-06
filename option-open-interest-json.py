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
TARGET_CURRENCIES = ['BTC', 'ETH'] # <<< MODIFIED to handle multiple currencies
END_DATE = datetime(2025, 12, 31)
DERIBIT_API_URL = "https://www.deribit.com/api/v2/public/"
MAX_WORKERS = 20
TOP_N_OI_WALLS = 5

# Statically track gamma for these major strikes in the historical data
STATICALLY_TRACKED_STRIKES = { # <<< MODIFIED for multiple currencies
    'BTC': [80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000],
    'ETH': [3000, 3500, 4000, 4500, 5000, 5500, 6000]
}
MAX_HISTORY_POINTS = 288

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# ... (Helper functions are mostly unchanged) ...
def get_option_type(expiration_date: datetime) -> str:
    is_friday = (expiration_date.weekday() == 4); is_last_friday_of_month = is_friday and (expiration_date + timedelta(days=7)).month != expiration_date.month
    if is_last_friday_of_month and expiration_date.month in [3, 6, 9, 12]: return "Quarterly"
    if is_last_friday_of_month: return "Monthly"
    if is_friday: return "Weekly"
    return "Daily"

def parse_instrument(instrument_name: str) -> Optional[Tuple[str, datetime, float, str]]:
    try:
        parts = instrument_name.split('-');
        if len(parts) != 4: return None
        underlying = parts[0]; expiry_dt = datetime.strptime(parts[1], "%d%b%y"); strike = float(parts[2]); opt_type = 'call' if parts[3].upper() == 'C' else 'put'; return underlying, expiry_dt, strike, opt_type
    except (ValueError, IndexError): logging.warning(f"Could not parse instrument name: {instrument_name}"); return None

# -----------------------------
# API Calls
# -----------------------------
def make_api_request(endpoint: str, params: Dict[str, Any], timeout: int = 15) -> Optional[Dict[str, Any]]:
    url = DERIBIT_API_URL + endpoint
    try:
        response = requests.get(url, params=params, timeout=timeout); response.raise_for_status(); return response.json()
    except requests.exceptions.RequestException as e: logging.error(f"API request to '{endpoint}' failed: {e}"); return None

def get_index_price(currency: str) -> Optional[float]: # <<< MODIFIED to be generic
    index_name = f"{currency.lower()}_usd"
    logging.info(f"Fetching current {currency} index price...")
    data = make_api_request("get_index_price", {'index_name': index_name})
    if data and 'result' in data and 'index_price' in data['result']:
        price = float(data['result']['index_price'])
        logging.info(f"Current {currency} Index Price: ${price:,.2f}"); return price
    logging.error(f"Could not extract {currency} index price from API response."); return None

def get_cumulative_flow(currency: str) -> Dict[str, float]:
    logging.info(f"Fetching recent trades for {currency} to calculate cumulative flow...")
    params = {"currency": currency, "kind": "option", "count": 1000, "include_old": "true"}
    data = make_api_request("get_last_trades_by_currency", params)
    if not (data and 'result' in data and 'trades' in data['result']):
        logging.warning(f"Could not fetch trade history for {currency}."); return {"buy_notional_usd": 0.0, "sell_notional_usd": 0.0}
    buy_notional = 0.0; sell_notional = 0.0
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0); start_of_day_ms = int(start_of_day.timestamp() * 1000)
    for trade in data['result']['trades']:
        if trade['timestamp'] >= start_of_day_ms:
            notional_usd = trade.get('amount', 0.0) * trade.get('index_price', 0.0)
            if trade.get('direction') == 'buy': buy_notional += notional_usd
            else: sell_notional += notional_usd
    logging.info(f"Cumulative flow for {currency} (since midnight UTC): Buy=${buy_notional:,.0f}, Sell=${sell_notional:,.0f}")
    return {"buy_notional_usd": buy_notional, "sell_notional_usd": sell_notional}

def get_instrument_names(currency: str) -> List[str]:
    logging.info(f"Fetching instrument names for {currency} options...")
    data = make_api_request("get_instruments", {'currency': currency, 'kind': 'option', 'expired': 'false'}, timeout=30)
    if data and 'result' in data:
        names = [inst['instrument_name'] for inst in data['result']]
        logging.info(f"Found {len(names)} active option instruments for {currency}."); return names
    return []

def get_all_tickers_in_parallel(instrument_names: List[str]) -> List[Dict[str, Any]]:
    all_tickers = []
    total = len(instrument_names)
    logging.info(f"Fetching full ticker data for {total} instruments using {MAX_WORKERS} parallel workers...")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_name = {executor.submit(make_api_request, "ticker", {'instrument_name': name}): name for name in instrument_names}
        for i, future in enumerate(as_completed(future_to_name), 1):
            try:
                data = future.result()
                if data and 'result' in data: all_tickers.append(data['result'])
            except Exception as e: name = future_to_name[future]; logging.error(f"Error fetching ticker for {name}: {e}")
            if i % 250 == 0 or i == total: logging.info(f"  ... fetched {i}/{total}")
    logging.info(f"Successfully fetched data for {len(all_tickers)} instruments."); return all_tickers

# ... (Core calculations are unchanged) ...
def aggregate_market_data(all_tickers: List[Dict[str, Any]], end_date: datetime):
    grouped_options = defaultdict(list); total_gamma_by_strike = defaultdict(float); total_delta_by_strike = defaultdict(float); total_vega_by_strike = defaultdict(float); total_theta_by_strike = defaultdict(float)
    for tk in all_tickers:
        parsed = parse_instrument(tk.get('instrument_name', ''));
        if not parsed: continue
        _, expiry_dt, strike, opt_type = parsed
        if expiry_dt > end_date: continue
        oi = float(tk.get('open_interest', 0.0));
        if oi == 0: continue
        greeks = tk.get('greeks', {}); gamma = float(greeks.get('gamma', 0.0)); delta = float(greeks.get('delta', 0.0)); vega = float(greeks.get('vega', 0.0)); theta = float(greeks.get('theta', 0.0))
        dealer_gamma_contrib = -gamma * oi; dealer_delta_contrib = -delta * oi; dealer_vega_contrib = -vega * oi; dealer_theta_contrib = -theta * oi
        grouped_options[expiry_dt].append({'strike': strike, 'type': opt_type, 'oi': oi, 'iv': float(tk.get('mark_iv', 0.0)) / 100.0, 'volume_24h': float(tk.get('stats', {}).get('volume', 0.0)), 'dealer_gamma_contrib': dealer_gamma_contrib, 'dealer_delta_contrib': dealer_delta_contrib, 'dealer_vega_contrib': dealer_vega_contrib, 'dealer_theta_contrib': dealer_theta_contrib})
        total_gamma_by_strike[strike] += dealer_gamma_contrib; total_delta_by_strike[strike] += dealer_delta_contrib; total_vega_by_strike[strike] += dealer_vega_contrib; total_theta_by_strike[strike] += dealer_theta_contrib
    return grouped_options, total_gamma_by_strike, total_delta_by_strike, total_vega_by_strike, total_theta_by_strike

# ... (find_oi_walls, calculate_max_pain, etc. are unchanged) ...
def find_oi_walls(options_list: List[Dict[str, Any]], top_n: int) -> Dict[str, List[Dict[str, Any]]]:
    calls, puts = defaultdict(float), defaultdict(float)
    for opt in options_list:
        if opt['type'] == 'call': calls[opt['strike']] += opt['oi']
        else: puts[opt['strike']] += opt['oi']
    sorted_calls = sorted(calls.items(), key=lambda item: item[1], reverse=True); sorted_puts = sorted(puts.items(), key=lambda item: item[1], reverse=True)
    return {"top_call_strikes": [{"strike": k, "open_interest": round(v, 2)} for k, v in sorted_calls[:top_n]], "top_put_strikes": [{"strike": k, "open_interest": round(v, 2)} for k, v in sorted_puts[:top_n]]}
def calculate_max_pain(options_list: List[Dict[str, Any]]) -> Optional[float]:
    if not options_list: return None
    unique_strikes = sorted(list(set(opt['strike'] for opt in options_list))); min_pain_value, max_pain_strike = inf, None
    for test_price in unique_strikes:
        total_pain = sum((test_price - opt['strike']) * opt['oi'] for opt in options_list if opt['type'] == 'call' and test_price > opt['strike']); total_pain += sum((opt['strike'] - test_price) * opt['oi'] for opt in options_list if opt['type'] == 'put' and test_price < opt['strike'])
        if total_pain < min_pain_value: min_pain_value, max_pain_strike = total_pain, test_price
    return max_pain_strike
def calculate_gamma_flip(total_gamma_by_strike: Dict[float, float], spot_price: float) -> Optional[float]:
    if not total_gamma_by_strike: return None
    current_total_gamma = sum(total_gamma_by_strike.values())
    if current_total_gamma > 0:
        cumulative_gamma = current_total_gamma
        for strike in sorted(total_gamma_by_strike.keys(), reverse=True):
            if strike >= spot_price: continue
            gamma_at_strike = total_gamma_by_strike[strike]
            if cumulative_gamma - gamma_at_strike < 0: return strike; cumulative_gamma -= gamma_at_strike
    else:
        cumulative_gamma = current_total_gamma
        for strike in sorted(total_gamma_by_strike.keys()):
            if strike <= spot_price: continue
            gamma_at_strike = total_gamma_by_strike[strike]
            if cumulative_gamma + gamma_at_strike > 0: return strike; cumulative_gamma += gamma_at_strike
    return None

def get_key_gamma_strikes_for_history(total_gamma_by_strike: Dict[float, float], spot_price: float, currency: str) -> Dict[str, float]: # <<< MODIFIED
    dynamic_strikes = []; short_gamma_strikes = [{'strike': s, 'distance': abs(s - spot_price)} for s, g in total_gamma_by_strike.items() if g < 0]; short_gamma_strikes.sort(key=lambda x: x['distance'])
    for item in short_gamma_strikes[:5]: dynamic_strikes.append(item['strike'])
    key_strikes_set = set(STATICALLY_TRACKED_STRIKES.get(currency, [])) | set(dynamic_strikes) # Use .get for safety
    return {str(int(strike)): round(total_gamma_by_strike.get(strike, 0.0), 4) for strike in sorted(list(key_strikes_set))}

# -----------------------------
# Final JSON Assembly
# -----------------------------
def process_and_save_data(currency: str, output_filename: str, historical_filename: str, # <<< MODIFIED signature
                          grouped_options: Dict, total_gamma_by_strike: Dict, total_delta_by_strike: Dict,
                          total_vega_by_strike: Dict, total_theta_by_strike: Dict,
                          spot_price: float, cumulative_flow: Dict):
    if not grouped_options: logging.error(f"No options data for {currency} to process."); return

    logging.info(f"Calculating final metrics for {currency}...")
    expirations_list = []; total_oi, total_volume_24h = 0.0, 0.0; total_call_oi, total_put_oi = 0.0, 0.0
    for expiry_dt, options_list in sorted(grouped_options.items()):
        expiry_call_oi = sum(o['oi'] for o in options_list if o['type'] == 'call'); expiry_put_oi = sum(o['oi'] for o in options_list if o['type'] == 'put'); expiry_total_oi = expiry_call_oi + expiry_put_oi; expiry_volume = sum(o['volume_24h'] for o in options_list)
        total_call_oi += expiry_call_oi; total_put_oi += expiry_put_oi; total_oi += expiry_total_oi; total_volume_24h += expiry_volume
        otype = get_option_type(expiry_dt); max_pain = calculate_max_pain(options_list) if otype in ["Monthly", "Quarterly"] else None
        expiry_delta = sum(o['dealer_delta_contrib'] for o in options_list); expiry_gamma = sum(o['dealer_gamma_contrib'] for o in options_list); expiry_vega = sum(o['dealer_vega_contrib'] for o in options_list); expiry_theta = sum(o['dealer_theta_contrib'] for o in options_list)
        expirations_list.append({"expiration_date": expiry_dt.strftime('%Y-%m-%d'), "option_type": otype, "open_interest": round(expiry_total_oi, 2), "notional_value_usd": round(expiry_total_oi * spot_price, 2), "total_volume_24h": round(expiry_volume, 2), "pcr_by_oi": round(expiry_put_oi / expiry_call_oi, 4) if expiry_call_oi > 0 else 0, "max_pain_strike": max_pain, "greeks_summary": {"total_delta_exposure": round(expiry_delta, 2), "total_gamma_exposure": round(expiry_gamma, 4), "total_vega_exposure_usd": round(expiry_vega, 2), "total_theta_exposure_usd": round(expiry_theta, 2)}, "open_interest_walls": find_oi_walls(options_list, top_n=TOP_N_OI_WALLS)})
    
    pcr_by_oi = total_put_oi / total_call_oi if total_call_oi > 0 else 0
    total_gex = sum(total_gamma_by_strike.values()); total_dex = sum(total_delta_by_strike.values()); total_vex = sum(total_vega_by_strike.values()); total_thex = sum(total_theta_by_strike.values()); gamma_flip_level = calculate_gamma_flip(total_gamma_by_strike, spot_price)
    
    market_summary = {
        "total_open_interest": round(total_oi, 2), "total_notional_oi_usd": round(total_oi * spot_price, 2),
        "total_volume_24h": round(total_volume_24h, 2), "pcr_by_open_interest": round(pcr_by_oi, 4),
        "total_dealer_gamma_exposure": round(total_gex, 4), "total_dealer_delta_exposure": round(total_dex, 2),
        "total_dealer_vega_exposure_usd": round(total_vex, 2), "total_dealer_theta_exposure_usd": round(total_thex, 2),
        "gamma_flip_level_usd": gamma_flip_level, "cumulative_flow_since_utc_midnight": cumulative_flow
    }
    
    output_data = {"metadata": {"calculation_timestamp_utc": datetime.utcnow().isoformat()+"Z", "index_price_usd": spot_price, "currency": currency}, "market_summary": market_summary, "expirations": expirations_list}
    
    try:
        with open(output_filename, 'w') as f: json.dump(output_data, f, indent=2)
        logging.info(f"✅ Full market analysis for {currency} saved to {output_filename}")
    except IOError as e: logging.error(f"Could not write to file {output_filename}. {e}")
    
    # ... (historical update is the same, just uses dynamic filename)

# -----------------------------
# Main Execution
# -----------------------------
if __name__ == "__main__":
    for currency in TARGET_CURRENCIES: # <<< MODIFIED to loop
        logging.info(f"========== STARTING ANALYSIS FOR {currency} ==========")
        
        # Dynamic filenames
        output_filename = f"deribit_{currency.lower()}_options_analysis.json"
        historical_filename = f"historical_{currency.lower()}_market_data.json"
        
        spot_price = get_index_price(currency)
        if not spot_price:
            logging.error(f"Fatal: Could not fetch {currency} index price. Skipping.")
            continue

        flow_data = get_cumulative_flow(currency)
        instrument_names = get_instrument_names(currency)
        if not instrument_names:
            logging.error(f"Fatal: No instrument names found for {currency}. Skipping.")
            continue

        all_tickers = get_all_tickers_in_parallel(instrument_names)
        if not all_tickers:
            logging.error(f"Fatal: Could not fetch any ticker data for {currency}. Skipping.")
            continue

        data = aggregate_market_data(all_tickers, END_DATE)
        grouped_options, total_gamma, total_delta, total_vega, total_theta = data
        if not grouped_options:
            logging.error(f"Fatal: No valid options data after processing tickers for {currency}. Skipping.")
            continue

        process_and_save_data(currency, output_filename, historical_filename, grouped_options, total_gamma, total_delta, total_vega, total_theta, spot_price, flow_data)

        logging.info(f"========== FINISHED ANALYSIS FOR {currency} ==========\n")

    logging.info("--- Script finished successfully for all currencies! ---")
