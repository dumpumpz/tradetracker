#!/usr/bin/env python3
import requests
import json
import os
import logging
import time
import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from math import inf
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple, Set

# --- Default Configuration ---
TARGET_CURRENCIES = ['BTC', 'ETH']
DEFAULT_OUTPUT_TEMPLATE = "deribit_options_{currency}_analysis.json"
DEFAULT_HISTORICAL_TEMPLATE = "historical_market_data_{currency}.json"

# --- Constants ---
END_DATE = datetime(2025, 12, 31)
DERIBIT_API_URL = "https://www.deribit.com/api/v2/public/"
MAX_WORKERS = 8
TOP_N_OI_WALLS = 5
MAX_HISTORY_POINTS = 288
STATIC_STRIKES_BY_CURRENCY = {
    'BTC': {80000, 90000, 100000, 110000, 120000, 130000, 140000, 150000},
    'ETH': {3000, 3500, 4000, 4500, 5000, 5500, 6000}
}

# --- API Client Configuration ---
API_TIMEOUT = 15
API_RETRY_ATTEMPTS = 5
API_RETRY_DELAY = 2

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')


class DeribitAPIClient:
    def __init__(self, base_url: str, session: Optional[requests.Session] = None):
        self.base_url = base_url
        self.session = session or requests.Session()

    def make_request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = self.base_url + endpoint
        delay = API_RETRY_DELAY
        for attempt in range(API_RETRY_ATTEMPTS):
            try:
                response = self.session.get(url, params=params, timeout=API_TIMEOUT)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logging.warning(
                        f"Rate limit on '{endpoint}'. Attempt {attempt + 1}/{API_RETRY_ATTEMPTS}. Retrying in {delay}s...")
                else:
                    logging.error(f"HTTP Error on '{endpoint}'. Attempt {attempt + 1}/{API_RETRY_ATTEMPTS}: {e}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed for '{endpoint}'. Attempt {attempt + 1}/{API_RETRY_ATTEMPTS}: {e}")
            if attempt < API_RETRY_ATTEMPTS - 1:
                time.sleep(delay)
                delay *= 2
        logging.critical(f"API request to '{endpoint}' failed after {API_RETRY_ATTEMPTS} attempts.")
        return None


class DeribitMarketAnalyzer:
    def __init__(self, currency: str, output_file: str, historical_file: str):
        self.currency = currency.upper()
        self.cur_lower = currency.lower()
        self.output_file = output_file
        self.historical_file = historical_file
        self.api_client = DeribitAPIClient(DERIBIT_API_URL)
        self.spot_price: Optional[float] = None
        self.statically_tracked_strikes = STATIC_STRIKES_BY_CURRENCY.get(self.currency, set())
        self.all_tickers: List[Dict[str, Any]] = []

    def run_analysis(self):
        logging.info(f"--- Starting Deribit Market Analysis for {self.currency} ---")
        start_time = time.time()
        if not self._fetch_initial_market_state():
            raise SystemExit(f"Fatal: Could not fetch initial market state for {self.currency}.")
        instrument_names = self._fetch_instrument_names()
        if not instrument_names:
            raise SystemExit(f"Fatal: No active {self.currency} instruments found.")
        self.all_tickers = self._get_all_tickers_in_parallel(instrument_names)
        if not self.all_tickers:
            raise SystemExit(f"Fatal: Could not fetch any ticker data for {self.currency}.")
        grouped_options, total_greeks = self._aggregate_market_data()
        if not grouped_options:
            raise SystemExit(f"Fatal: No valid options data after processing for {self.currency}.")
        self._process_and_save_data(grouped_options, total_greeks)
        end_time = time.time()
        logging.info(
            f"--- Analysis for {self.currency} finished successfully in {end_time - start_time:.2f} seconds! ---")

    def _fetch_initial_market_state(self) -> bool:
        logging.info(f"Fetching initial market state for {self.currency} (Index Price)...")
        self.spot_price = self._get_index_price()
        return self.spot_price is not None

    def _get_index_price(self) -> Optional[float]:
        index_name = f"{self.cur_lower}_usd"
        data = self.api_client.make_request("get_index_price", {'index_name': index_name})
        if data and 'result' in data and 'index_price' in data['result']:
            price = float(data['result']['index_price'])
            logging.info(f"Current {self.currency} Index Price: ${price:,.2f}")
            return price
        logging.error(f"Could not extract {self.currency} index price from API response.")
        return None

    def _fetch_instrument_names(self) -> List[str]:
        logging.info(f"Fetching instrument names for {self.currency} options...")
        params = {'currency': self.currency, 'kind': 'option', 'expired': 'false'}
        data = self.api_client.make_request("get_instruments", params)
        if data and 'result' in data:
            names = [inst['instrument_name'] for inst in data['result']]
            logging.info(f"Found {len(names)} active {self.currency} option instruments.")
            return names
        return []

    def _fetch_ticker_data(self, instrument_name: str) -> Optional[Dict[str, Any]]:
        data = self.api_client.make_request("ticker", {'instrument_name': instrument_name})
        return data.get('result') if data else None

    def _get_all_tickers_in_parallel(self, instrument_names: List[str]) -> List[Dict[str, Any]]:
        all_tickers, total = [], len(instrument_names)
        logging.info(
            f"Fetching full ticker data for {total} {self.currency} instruments using {MAX_WORKERS} parallel workers...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_name = {executor.submit(self._fetch_ticker_data, name): name for name in instrument_names}
            for i, future in enumerate(as_completed(future_to_name), 1):
                try:
                    data = future.result()
                    if data: all_tickers.append(data)
                except Exception as e:
                    logging.error(f"Error fetching ticker for {future_to_name[future]}: {e}")
                if i % 100 == 0 or i == total:
                    logging.info(f"  ... fetched {i}/{total}")
        logging.info(f"Successfully fetched data for {len(all_tickers)}/{total} instruments.")
        return all_tickers

    def _aggregate_market_data(self) -> Tuple[Dict, Dict]:
        grouped_options, total_greeks = defaultdict(list), defaultdict(lambda: defaultdict(float))
        logging.info(f"Processing {len(self.all_tickers)} {self.currency} tickers...")
        for tk in self.all_tickers:
            if (oi := float(tk.get('open_interest', 0.0))) == 0: continue
            parsed = self._parse_instrument(tk.get('instrument_name', ''))
            if not parsed: continue
            _, expiry_dt, strike, opt_type = parsed
            if expiry_dt.date() > END_DATE.date(): continue
            greeks = tk.get('greeks')
            if not greeks: continue

            gamma, delta = -float(greeks.get('gamma', 0.0)), -float(greeks.get('delta', 0.0))
            vega, theta = -float(greeks.get('vega', 0.0)), -float(greeks.get('theta', 0.0))

            contributions = {'gamma': gamma * oi, 'delta': delta * oi, 'vega': vega * oi, 'theta': theta * oi}
            grouped_options[expiry_dt].append({
                'strike': strike, 'type': opt_type, 'oi': oi,
                'iv': float(tk.get('mark_iv', 0.0)) / 100.0,
                'volume_24h': float(tk.get('stats', {}).get('volume', 0.0)),
                'contributions': contributions
            })
            for key in contributions:
                total_greeks[key][strike] += contributions[key]
        logging.info("Finished processing tickers.")
        return grouped_options, total_greeks

    def _process_and_save_data(self, grouped_options: Dict, total_greeks: Dict):
        logging.info("Calculating final metrics and preparing JSON files...")
        now_timestamp = datetime.now(timezone.utc).isoformat()
        expirations_list, market_totals = self._build_expirations_list(grouped_options)
        market_summary = self._build_market_summary(market_totals, total_greeks)
        output_data = {
            "metadata": {"calculation_timestamp_utc": now_timestamp, "spot_price_usd": self.spot_price,
                         "currency": self.currency},
            "definitions": self._get_definitions(),
            "market_summary": market_summary,
            "expirations": expirations_list
        }
        self._save_json_file(self.output_file, output_data)
        self._update_historical_data(now_timestamp, market_summary, total_greeks['gamma'])

    def _build_expirations_list(self, grouped_options: Dict) -> Tuple[List[Dict], Dict]:
        expirations_list, market_totals = [], defaultdict(float)
        for expiry_dt, options_list in sorted(grouped_options.items()):
            expiry_call_oi = sum(o['oi'] for o in options_list if o['type'] == 'call')
            expiry_put_oi = sum(o['oi'] for o in options_list if o['type'] == 'put')
            expiry_total_oi, expiry_volume = expiry_call_oi + expiry_put_oi, sum(o['volume_24h'] for o in options_list)

            market_totals['total_call_oi'] += expiry_call_oi
            market_totals['total_put_oi'] += expiry_put_oi
            market_totals['total_oi'] += expiry_total_oi
            market_totals['total_volume_24h'] += expiry_volume
            for opt in options_list:
                # ### THIS IS THE FIX ###
                if opt['type'] == 'call':
                    market_totals['total_call_volume_24h'] += opt['volume_24h']
                else:
                    market_totals['total_put_volume_24h'] += opt['volume_24h']

            otype = self._get_option_type(expiry_dt)
            max_pain = self._calculate_max_pain(options_list) if otype in ["Monthly", "Quarterly"] else None

            gex_by_strike = defaultdict(float)
            for opt in options_list: gex_by_strike[opt['strike']] += opt['contributions']['gamma']

            expirations_list.append({
                "expiration_date": expiry_dt.strftime('%Y-%m-%d'), "option_type": otype,
                f"open_interest_{self.cur_lower}": round(expiry_total_oi, 2),
                "notional_value_usd": round(expiry_total_oi * self.spot_price, 2),
                f"total_volume_24h_{self.cur_lower}": round(expiry_volume, 2),
                "pcr_by_oi": round(expiry_put_oi / expiry_call_oi, 4) if expiry_call_oi > 0 else 0,
                "max_pain_strike": max_pain,
                "greeks_summary": self._summarize_greeks_for_expiry(options_list),
                "open_interest_walls": self._find_oi_walls(options_list),
                "dealer_gamma_by_strike": sorted([{'strike': s, 'dealer_gamma': g} for s, g in gex_by_strike.items()],
                                                 key=lambda x: x['strike']),
                "volatility_surface": self._build_volatility_surface(options_list)
            })
        return expirations_list, market_totals

    def _build_market_summary(self, market_totals: Dict, total_greeks: Dict) -> Dict:
        pcr_by_oi = market_totals['total_put_oi'] / market_totals['total_call_oi'] if market_totals[
                                                                                          'total_call_oi'] > 0 else 0
        call_vol, put_vol = market_totals['total_call_volume_24h'], market_totals['total_put_volume_24h']
        pcr_by_vol_ratio = put_vol / call_vol if call_vol > 0 else 0.0
        pcr_by_24h_volume = {"ratio": round(pcr_by_vol_ratio, 4),
                             f"call_volume_24h_{self.cur_lower}": round(call_vol, 2),
                             f"put_volume_24h_{self.cur_lower}": round(put_vol, 2)}
        return {
            f"total_open_interest_{self.cur_lower}": round(market_totals['total_oi'], 2),
            "total_notional_oi_usd": round(market_totals['total_oi'] * self.spot_price, 2),
            f"total_volume_24h_{self.cur_lower}": round(market_totals['total_volume_24h'], 2),
            "pcr_by_open_interest": round(pcr_by_oi, 4), "pcr_by_24h_volume": pcr_by_24h_volume,
            "total_dealer_gamma_exposure": round(sum(total_greeks['gamma'].values()), 4),
            f"total_dealer_delta_exposure_{self.cur_lower}": round(sum(total_greeks['delta'].values()), 2),
            "total_dealer_vega_exposure_usd": round(sum(total_greeks['vega'].values()), 2),
            "total_dealer_theta_exposure_usd": round(sum(total_greeks['theta'].values()), 2),
            "gamma_flip_level_usd": self._calculate_gamma_flip(total_greeks['gamma'], self.spot_price)
        }

    def _update_historical_data(self, timestamp: str, market_summary: Dict, total_gamma_by_strike: Dict):
        key_gamma_data = self._get_key_gamma_strikes_for_history(total_gamma_by_strike)
        new_entry = {
            "timestamp": timestamp, "spot_price": self.spot_price,
            f"total_open_interest_{self.cur_lower}": market_summary[f"total_open_interest_{self.cur_lower}"],
            f"total_volume_24h_{self.cur_lower}": market_summary[f"total_volume_24h_{self.cur_lower}"],
            "pcr_by_oi": market_summary["pcr_by_open_interest"],
            "pcr_by_volume": market_summary["pcr_by_24h_volume"].get("ratio"),
            "total_gex": market_summary["total_dealer_gamma_exposure"],
            "total_dex": market_summary[f"total_dealer_delta_exposure_{self.cur_lower}"],
            "total_vex": market_summary["total_dealer_vega_exposure_usd"],
            "total_thex": market_summary["total_dealer_theta_exposure_usd"],
            "gamma_flip_level": market_summary["gamma_flip_level_usd"], "per_strike_gamma": key_gamma_data
        }
        history = []
        if os.path.exists(self.historical_file):
            try:
                with open(self.historical_file, 'r') as f:
                    history = json.load(f)
                if not isinstance(history, list): history = []
            except (json.JSONDecodeError, IOError):
                history = []
        history.append(new_entry)
        self._save_json_file(self.historical_file, history[-MAX_HISTORY_POINTS:])

    def _save_json_file(self, filename: str, data: Any):
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"✅ Data successfully saved to {filename}")
        except IOError as e:
            logging.error(f"Could not write to file {filename}. Error: {e}")

    def _find_oi_walls(self, options_list: List[Dict]) -> Dict[str, List[Dict]]:
        calls, puts = defaultdict(float), defaultdict(float)
        for opt in options_list: (calls if opt['type'] == 'call' else puts)[opt['strike']] += opt['oi']
        sorted_calls = sorted(calls.items(), key=lambda i: i[1], reverse=True)
        sorted_puts = sorted(puts.items(), key=lambda i: i[1], reverse=True)
        return {"top_call_strikes": [{"strike": k, f"open_interest_{self.cur_lower}": round(v, 2)} for k, v in
                                     sorted_calls[:TOP_N_OI_WALLS]],
                "top_put_strikes": [{"strike": k, f"open_interest_{self.cur_lower}": round(v, 2)} for k, v in
                                    sorted_puts[:TOP_N_OI_WALLS]]}

    @staticmethod
    def _get_definitions() -> Dict[str, str]:
        return {
            "total_dealer_gamma_exposure": "Total Gamma Exposure for dealers. Negative values amplify volatility. Positive values suppress volatility.",
            "total_dealer_delta_exposure": "Total Delta Exposure for dealers, in the base currency (e.g., BTC/ETH).",
            "gamma_flip_level_usd": "The estimated asset price where total dealer gamma exposure flips sign. A key pivot point for the market's volatility regime.",
        }

    def _summarize_greeks_for_expiry(self, options_list: List[Dict]) -> Dict:
        return {
            f"total_delta_exposure_{self.cur_lower}": round(sum(o['contributions']['delta'] for o in options_list), 2),
            "total_gamma_exposure": round(sum(o['contributions']['gamma'] for o in options_list), 4),
            "total_vega_exposure_usd": round(sum(o['contributions']['vega'] for o in options_list), 2),
            "total_theta_exposure_usd": round(sum(o['contributions']['theta'] for o in options_list), 2),
        }

    @staticmethod
    def _parse_instrument(instrument_name: str) -> Optional[Tuple[str, datetime, float, str]]:
        try:
            parts = instrument_name.split('-');
            return parts[0], datetime.strptime(parts[1], "%d%b%y"), float(parts[2]), 'call' if parts[
                                                                                                   3] == 'C' else 'put'
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _get_option_type(expiration_date: datetime) -> str:
        is_friday, is_last_friday = (expiration_date.weekday() == 4), (expiration_date.weekday() == 4) and (
                    expiration_date + timedelta(days=7)).month != expiration_date.month
        if is_last_friday and expiration_date.month in [3, 6, 9, 12]: return "Quarterly"
        if is_last_friday: return "Monthly"
        if is_friday: return "Weekly"
        return "Daily"

    @staticmethod
    def _calculate_max_pain(options_list: List[Dict]) -> Optional[float]:
        if not options_list: return None
        strikes, (min_pain, max_pain_strike) = sorted(list(set(opt['strike'] for opt in options_list))), (inf, None)
        for test_price in strikes:
            pain = sum((test_price - opt['strike']) * opt['oi'] for opt in options_list if
                       opt['type'] == 'call' and test_price > opt['strike']) + sum(
                (opt['strike'] - test_price) * opt['oi'] for opt in options_list if
                opt['type'] == 'put' and test_price < opt['strike'])
            if pain < min_pain: min_pain, max_pain_strike = pain, test_price
        return max_pain_strike

    def _calculate_gamma_flip(self, total_gamma_by_strike: Dict[float, float], spot_price: float) -> Optional[float]:
        if not total_gamma_by_strike: return None
        cumulative_gamma = sum(total_gamma_by_strike.values())
        if cumulative_gamma > 0:
            for strike in sorted(total_gamma_by_strike.keys(), reverse=True):
                if strike >= spot_price: continue
                cumulative_gamma -= total_gamma_by_strike[strike]
                if cumulative_gamma < 0: return strike
        else:
            for strike in sorted(total_gamma_by_strike.keys()):
                if strike <= spot_price: continue
                cumulative_gamma += total_gamma_by_strike[strike]
                if cumulative_gamma > 0: return strike
        return None

    @staticmethod
    def _build_volatility_surface(options_list: List[Dict]) -> List[Dict]:
        surface = defaultdict(lambda: {'call_iv': None, 'put_iv': None})
        for opt in options_list: surface[opt['strike']][f"{opt['type']}_iv"] = round(opt['iv'], 4)
        return [{"strike": s, **ivs} for s, ivs in sorted(surface.items())]

    def _get_key_gamma_strikes_for_history(self, total_gamma_by_strike: Dict) -> Dict[str, float]:
        short_gamma = [{'s': s, 'dist': abs(s - self.spot_price)} for s, g in total_gamma_by_strike.items() if g < 0]
        short_gamma.sort(key=lambda x: x['dist'])
        dynamic_strikes = {item['s'] for item in short_gamma[:5]}
        key_strikes = sorted(list(self.statically_tracked_strikes | dynamic_strikes))
        return {str(int(s)): round(total_gamma_by_strike.get(s, 0.0), 4) for s in key_strikes}


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and analyze Deribit options market data for multiple currencies.")
    parser.add_argument('-c', '--currencies', nargs='+', default=TARGET_CURRENCIES,
                        help=f"Space-separated list of currencies to analyze (e.g., BTC ETH). Default: {' '.join(TARGET_CURRENCIES)}")
    args = parser.parse_args()
    for currency in args.currencies:
        try:
            output_file = DEFAULT_OUTPUT_TEMPLATE.format(currency=currency.lower())
            historical_file = DEFAULT_HISTORICAL_TEMPLATE.format(currency=currency.lower())
            analyzer = DeribitMarketAnalyzer(currency, output_file, historical_file)
            analyzer.run_analysis()
        except SystemExit as e:
            logging.critical(f"Execution halted for {currency}: {e}")
        except Exception as e:
            logging.exception(f"An unexpected error occurred during analysis for {currency}: {e}")


if __name__ == "__main__":
    main()
