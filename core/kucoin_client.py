import ccxt
import sys
import os
import requests
import time
import pickle
from datetime import datetime, timezone, timedelta

try:
    from config.api_key import API_KEY, API_SECRET, API_PASSWORD
except ImportError:
    print("Error: 'config/api_key.py' not found or is missing required variables.")
    sys.exit(1)

ASSET_CACHE_DIR = 'cache'
ICON_CACHE_DIR = os.path.join(ASSET_CACHE_DIR, 'icons')
ASSET_DETAILS_FILE = os.path.join(ASSET_CACHE_DIR, 'asset_details.pkl')
COINGECKO_MAP_FILE = os.path.join(ASSET_CACHE_DIR, 'coingecko_map.pkl')

class KuCoinClient:
    def __init__(self):
        self.client = None
        self.asset_details = self._load_local_asset_cache()
        self.coingecko_map = {}
        if not all([API_KEY, API_SECRET, API_PASSWORD]) or "HERE" in API_KEY:
            sys.exit("Error: Credentials in 'config/api_key.py' are incomplete.")
        try:
            self.client = ccxt.kucoinfutures({
                'apiKey': API_KEY, 'secret': API_SECRET, 'password': API_PASSWORD,
            })
            print("Successfully connected to the KuCoin Futures API.")
        except Exception as e:
            sys.exit(f"An error occurred during KuCoin client initialization: {e}")

    def _load_local_asset_cache(self):
        if os.path.exists(ASSET_DETAILS_FILE):
            try:
                with open(ASSET_DETAILS_FILE, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"Warning: Could not load asset cache: {e}.")
        return {}

    def get_asset_details(self, symbol_string):
        try:
            base_currency = symbol_string.split('/')[0]
            return self.asset_details.get(base_currency, {'name': base_currency, 'icon_path': None})
        except Exception:
            return {'name': symbol_string, 'icon_path': None}
    
    def ensure_asset_details_are_loaded(self, top_symbols: list, log_callback=None):
        def _log(message):
            if log_callback: log_callback(message)
        base_currencies_to_check = {s.split('/')[0] for s in top_symbols}
        missing_currencies = [
            c for c in base_currencies_to_check 
            if not self.asset_details.get(c) or not self.asset_details[c].get('icon_path') or not os.path.exists(self.asset_details[c]['icon_path'])
        ]
        if not missing_currencies:
            return
        _log(f"Found {len(missing_currencies)} new or missing assets. Fetching details...")
        if not self.coingecko_map:
            if os.path.exists(COINGECKO_MAP_FILE):
                with open(COINGECKO_MAP_FILE, 'rb') as f:
                    self.coingecko_map = pickle.load(f)
            else:
                _log("Fetching CoinGecko ID map (one-time operation)...")
                try:
                    os.makedirs(ASSET_CACHE_DIR, exist_ok=True)
                    response = requests.get("https://api.coingecko.com/api/v3/coins/list", timeout=30)
                    response.raise_for_status()
                    for coin in response.json():
                        self.coingecko_map[coin['symbol']] = coin['id']
                    with open(COINGECKO_MAP_FILE, 'wb') as f:
                        pickle.dump(self.coingecko_map, f)
                except Exception as e:
                    _log(f"Fatal Error: Could not fetch CoinGecko ID map: {e}")
                    return
        os.makedirs(ICON_CACHE_DIR, exist_ok=True)
        for i, code in enumerate(missing_currencies):
            _log(f"  -> Fetching Icon & Name [{i+1}/{len(missing_currencies)}]: {code}")
            coingecko_id = self.coingecko_map.get(code.lower())
            if not coingecko_id:
                self.asset_details[code] = {'name': code, 'icon_path': None}
                continue
            max_retries = 3
            success = False
            for attempt in range(max_retries):
                try:
                    time.sleep(1.2)
                    coin_url = f"https://api.coingecko.com/api/v3/coins/{coingecko_id}"
                    coin_response = requests.get(coin_url, timeout=10)
                    if coin_response.status_code == 429:
                        _log(f"    Rate limit hit for {code}. Waiting 61 seconds...")
                        time.sleep(61)
                        continue
                    coin_response.raise_for_status()
                    coin_data = coin_response.json()
                    name = coin_data.get('name', code)
                    icon_url = coin_data.get('image', {}).get('small')
                    icon_path = None
                    if icon_url:
                        icon_response = requests.get(icon_url, stream=True, timeout=10)
                        icon_response.raise_for_status()
                        filename = f"{code}.png"
                        icon_path = os.path.join(ICON_CACHE_DIR, filename)
                        with open(icon_path, 'wb') as f:
                            for chunk in icon_response.iter_content(chunk_size=8192): f.write(chunk)
                    self.asset_details[code] = {'name': name, 'icon_path': icon_path}
                    success = True
                    break
                except requests.exceptions.RequestException as e:
                    _log(f"    Attempt {attempt+1}/{max_retries} failed for {code}: {e}. Retrying...")
                    time.sleep(5 * (attempt + 1))
            if not success:
                _log(f"    All attempts failed for {code}. Using fallback data.")
                self.asset_details[code] = {'name': code, 'icon_path': None}
        with open(ASSET_DETAILS_FILE, 'wb') as f:
            pickle.dump(self.asset_details, f)
        _log("Asset details cache has been updated.")

    def fetch_top_volumes(self, limit=50):
        try:
            tickers = self.client.fetch_tickers()
            symbols = [(s, d['quoteVolume']) for s, d in tickers.items() if d.get('quoteVolume') and ':USDT' in s]
            return [s[0] for s in sorted(symbols, key=lambda x: x[1], reverse=True)[:limit]]
        except Exception as e:
            print(f"Error fetching tickers from KuCoin: {e}")
            return []

    def count_consecutive_candles(self, symbol, timeframe, num_candles=20):
        """Counts consecutive candles and returns count, color, and last close price."""
        try:
            since = self.client.milliseconds() - (num_candles * self.client.parse_timeframe(timeframe) * 1000)
            ohlcv = self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=num_candles)
            if not ohlcv: 
                return 0, None, None
            
            completed = ohlcv[:-1]
            if not completed:
                return 0, None, None

            count = 0
            last_color = None
            last_close_price = None
          
            for i, candle in enumerate(reversed(completed)):
                # candle format: [timestamp, open, high, low, close, volume]
                if i == 0:
                    last_close_price = candle[4] 

                color = "green" if candle[4] >= candle[1] else "red"
                if last_color is None or color == last_color:
                    count += 1
                    last_color = color
                else: 
                    break
            
            return count, last_color, last_close_price
        except Exception: 
            return 0, None, None
            
    def scan_for_candle_streaks(self, timeframes, top_n_volume=50, min_streak_count=3, progress_callback=None, log_callback=None):
        """Scans top volume assets for streaks and ensures their metadata is loaded."""
        def _log(message):
            if log_callback: log_callback(message)
        _log("Fetching top volume symbols from KuCoin...")
        symbols = self.fetch_top_volumes(limit=top_n_volume)
        if not symbols:
            _log("Could not fetch top volume symbols. Aborting scan.")
            return []
        self.ensure_asset_details_are_loaded(symbols, log_callback)
        _log(f"Scanning {len(symbols)} symbols for candle streaks...")
        report_data = []
        total_scans = len(symbols) * len(timeframes)
        current_scan = 0
        for i, symbol in enumerate(symbols):
            print(f"  -> [{i+1}/{len(symbols)}] Analyzing {symbol}...")
            _log(f"  -> [{i+1}/{len(symbols)}] Analyzing {symbol}...")
            for timeframe in timeframes:
                current_scan += 1
                if progress_callback: progress_callback(current_scan, total_scans)
                
                count, color, last_price = self.count_consecutive_candles(symbol, timeframe)
                
                if count >= min_streak_count:                   
                    report_data.append((symbol, count, timeframe, color, last_price))
        
        if progress_callback: progress_callback(total_scans, total_scans)
        _log("Scan complete.")
        return report_data