import requests
from datetime import datetime, timedelta
import json

# --- Configuration ---
TARGET_CURRENCY = 'BTC'
END_DATE = datetime(2025, 12, 31)
OUTPUT_FILENAME = "deribit_open_interest_classified.json"
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


def get_open_interest_data(currency, end_date):
    """
    Fetches and aggregates the open interest for all option instruments,
    grouped by expiration date.
    """
    print("Fetching open interest data for all option instruments...")
    url = DERIBIT_API_URL + "get_book_summary_by_currency"
    params = {'currency': currency, 'kind': 'option'}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        summaries = response.json().get('result', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching summary data from Deribit API: {e}")
        return {}

    print(f"Found {len(summaries)} instruments. Aggregating open interest...")
    grouped_oi = {}
    for summary in summaries:
        try:
            instrument_name = summary['instrument_name']
            expiration_date = datetime.strptime(instrument_name.split('-')[1], '%d%b%y')
            if expiration_date <= end_date:
                oi = summary['open_interest']
                if expiration_date not in grouped_oi:
                    grouped_oi[expiration_date] = 0
                grouped_oi[expiration_date] += oi
        except (ValueError, IndexError):
            continue
    return grouped_oi


def process_and_save_json(grouped_oi, btc_price, filename):
    """
    Processes the aggregated data, adds classification, and saves it to a JSON file.
    """
    if not grouped_oi:
        print("No open interest data to save.")
        return

    print(f"Processing and classifying data to be saved in {filename}...")

    expirations_list = []
    for expiration_date in sorted(grouped_oi.keys()):
        total_oi_btc = grouped_oi[expiration_date]
        notional_oi_usd = total_oi_btc * btc_price

        # Get the classification for the date
        option_type = get_option_type(expiration_date)

        expirations_list.append({
            "expiration_date": expiration_date.strftime('%Y-%m-%d'),
            "day_of_week": expiration_date.strftime('%A'),
            "option_type": option_type,  # <-- Our new field
            "open_interest_btc": round(total_oi_btc, 4),
            "notional_value_usd": round(notional_oi_usd, 2)
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
        print(f"✅ Data successfully saved to {filename}")
    except IOError as e:
        print(f"Error: Could not write to file {filename}. {e}")


if __name__ == "__main__":
    current_btc_price = get_btc_index_price()

    if current_btc_price:
        open_interest_data = get_open_interest_data(TARGET_CURRENCY, END_DATE)
        if open_interest_data:
            process_and_save_json(open_interest_data, current_btc_price, OUTPUT_FILENAME)
