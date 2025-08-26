import requests
from datetime import datetime, timedelta
import json
from collections import defaultdict

# --- Configuration ---
TARGET_CURRENCY = 'BTC'
END_DATE = datetime(2025, 12, 31)
OUTPUT_FILENAME = "deribit_open_interest_classified.json" # The same output file your HTML uses
DERIBIT_API_URL = "https://www.deribit.com/api/v2/public/"

def get_option_type(expiration_date):
    """
    Determines if an option expiration is Quarterly, Monthly, Weekly, or Daily.
    """
    is_friday = (expiration_date.weekday() == 4)
    is_last_friday_of_month = is_friday and (expiration_date + timedelta(days=7)).month != expiration_date.month

    if is_last_friday_of_month and expiration_date.month in [3, 6, 9, 12]:
        return "Quarterly"
    if is_last_friday_of_month:
        return "Monthly"
    if is_friday:
        return "Weekly"
    return "Daily"

def get_btc_index_price():
    """Fetches the current BTC index price from Deribit."""
    print("Fetching current BTC index price...")
    url = DERIBIT_API_URL + "get_index_price"
    params = {'index_name': 'btc_usd'}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        price = response.json().get('result', {}).get('index_price')
        if price:
            print(f"Current BTC Index Price: ${price:,.2f}")
            return price
    except requests.exceptions.RequestException as e:
        print(f"Error fetching BTC index price: {e}")
    return None

def fetch_all_options_data(currency, end_date):
    """
    Fetches detailed data for all options (strike, type, oi) and groups by expiration date.
    This is the combined, efficient fetch function.
    """
    print(f"Fetching market summary for all {currency} options...")
    summary_url = DERIBIT_API_URL + "get_book_summary_by_currency"
    params = {'currency': currency, 'kind': 'option'}
    try:
        response = requests.get(summary_url, params=params)
        response.raise_for_status()
        summaries = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching summary data: {e}")
        return {}

    print(f"Found {len(summaries)} instruments. Parsing and grouping...")
    grouped_options = defaultdict(list)
    for summary in summaries:
        try:
            instrument_name = summary['instrument_name']
            name_parts = instrument_name.split('-')
            if len(name_parts) != 4:
                continue

            date_str = name_parts[1]
            expiration_date = datetime.strptime(date_str, '%d%b%y')

            if expiration_date <= end_date:
                strike_price = float(name_parts[2])
                option_type_char = name_parts[3]
                option_type_str = 'call' if option_type_char == 'C' else 'put'

                option_data = {
                    'strike': strike_price,
                    'type': option_type_str,
                    'oi': summary['open_interest']
                }
                grouped_options[expiration_date].append(option_data)
        except (ValueError, IndexError):
            continue
    return grouped_options

def calculate_max_pain(options_list):
    """
    Calculates the Max Pain strike price for a single list of options contracts.
    """
    if not options_list:
        return None
    unique_strikes = sorted(list(set(opt['strike'] for opt in options_list)))
    min_pain_value = float('inf')
    max_pain_strike = None
    for test_price in unique_strikes:
        total_pain = sum((test_price - opt['strike']) * opt['oi'] for opt in options_list if opt['type'] == 'call' and test_price > opt['strike'])
        total_pain += sum((opt['strike'] - test_price) * opt['oi'] for opt in options_list if opt['type'] == 'put' and test_price < opt['strike'])
        if total_pain < min_pain_value:
            min_pain_value = total_pain
            max_pain_strike = test_price
    return max_pain_strike

def process_and_save_json(grouped_options, btc_price, filename):
    """
    Processes the aggregated data, calculates all metrics, and saves to a JSON file.
    """
    if not grouped_options:
        print("No options data to save.")
        return

    print("Calculating final metrics and preparing JSON file...")
    expirations_list = []
    for expiration_date, options_list in sorted(grouped_options.items()):
        total_oi_btc = sum(opt['oi'] for opt in options_list)
        notional_oi_usd = total_oi_btc * btc_price
        option_type = get_option_type(expiration_date)
        
        # Calculate Max Pain only for significant expiries
        max_pain_strike = None
        if option_type in ["Monthly", "Quarterly"]:
            max_pain_strike = calculate_max_pain(options_list)

        expirations_list.append({
            "expiration_date": expiration_date.strftime('%Y-%m-%d'),
            "day_of_week": expiration_date.strftime('%A'),
            "option_type": option_type,
            "open_interest_btc": round(total_oi_btc, 4),
            "notional_value_usd": round(notional_oi_usd, 2),
            "max_pain_strike": max_pain_strike # <-- ADDED THE NEW DATA POINT
        })

    output_data = {
        "metadata": {
            "calculation_timestamp_utc": datetime.utcnow().isoformat() + "Z",
            "btc_index_price_usd": btc_price,
            "currency": TARGET_CURRENCY
        },
        "expirations": expirations_list
    }

    try:
        with open(filename, 'w') as f:
            json.dump(output_data, f, indent=4)
        print(f"✅ Combined options analysis successfully saved to {filename}")
    except IOError as e:
        print(f"Error: Could not write to file {filename}. {e}")

if __name__ == "__main__":
    current_btc_price = get_btc_index_price()
    if current_btc_price:
        # Fetch data once
        all_options_data = fetch_all_options_data(TARGET_CURRENCY, END_DATE)
        if all_options_data:
            # Process and save the combined data
            process_and_save_json(all_options_data, current_btc_price, OUTPUT_FILENAME)
