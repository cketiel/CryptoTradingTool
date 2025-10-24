# Module to interact with the KuCoin API

import ccxt
import sys
from datetime import datetime, timezone, timedelta

# Import credentials from our secure config file
try:
    from config.api_key import API_KEY, API_SECRET, API_PASSWORD
except ImportError:
    print("Error: 'config/api_key.py' not found or is missing the required variables.")
    print("Please create the file and define API_KEY, API_SECRET, and API_PASSWORD.")
    sys.exit(1) # Exit the script if credentials are not found

class KuCoinClient:
    """
    A class to interact with the KuCoin Futures API.
    It encapsulates the ccxt exchange instance.
    """

    def __init__(self):
        """
        Initializes the KuCoin client and handles authentication.
        """
        self.client = None
        # Validate that the keys are not empty or still have placeholder text
        if not all([API_KEY, API_SECRET, API_PASSWORD]) or "HERE" in API_KEY:
            print("Error: Credentials in 'config/api_key.py' are incomplete.")
            sys.exit(1)
        
        try:
            # Setup for KuCoin Futures API
            self.client = ccxt.kucoinfutures({
                'apiKey': API_KEY,
                'secret': API_SECRET,
                'password': API_PASSWORD,               
            })
            # Test the connection to verify credentials
            #self.client.fetch_balance()
            print("Successfully connected to the KuCoin Futures API.")
        except ccxt.AuthenticationError as e:
            print(f"KuCoin Authentication Error: {e}")
            print("Please check your credentials in 'config/api_key.py'.")
            sys.exit(1)
        except Exception as e:
            print(f"An error occurred while connecting to KuCoin: {e}")
            sys.exit(1)

    def fetch_top_volumes(self, limit=70):
        """
        Fetches the future pairs with the highest 24h volume.

        Args:
            limit (int): The number of pairs to retrieve. Defaults to 70.

        Returns:
            list: A list of symbols for the highest volume pairs (e.g., ['BTC/USDT:USDT']).
        """
        if not self.client:
            print("Client is not initialized. Cannot fetch data.")
            return []

        try:
            # Fetch tickers for all futures markets
            tickers = self.client.fetch_tickers()

            # Filter for USDT-margined markets only and sort by quote volume
            symbols_with_volume = [
                (symbol, data['quoteVolume']) for symbol, data in tickers.items()
                if data.get('quoteVolume') is not None and ':USDT' in symbol
            ]
            
            # Sort from highest to lowest volume and apply the limit
            top_symbols = sorted(symbols_with_volume, key=lambda x: x[1], reverse=True)[:limit]

            print(f"Found {len(top_symbols)} high-volume pairs.")
            return [symbol[0] for symbol in top_symbols]

        except Exception as e:
            print(f"Error fetching tickers from KuCoin: {e}")
            return []

    def count_consecutive_candles(self, symbol, timeframe, num_candles=20):
        """
        Counts the number of consecutive green or red candles for a given symbol.

        Args:
            symbol (str): The trading symbol (e.g., 'BTC/USDT:USDT').
            timeframe (str): The timeframe to analyze (e.g., '1h', '4h').
            num_candles (int): The number of recent candles to fetch for analysis.

        Returns:
            int: The number of consecutive candles of the same color from the most recent completed candle.
                 Returns 0 if an error occurs.
        """
        if not self.client:
            print("Client is not initialized. Cannot fetch candle data.")
            return 0
        
        try:
            # Calculate the starting time to fetch the last `num_candles`
            timeframe_in_ms = self.client.parse_timeframe(timeframe) * 1000
            since = self.client.milliseconds() - (num_candles * timeframe_in_ms)

            # Fetch the OHLCV data
            ohlcv = self.client.fetch_ohlcv(symbol, timeframe, since=since, limit=num_candles)

            if not ohlcv:
                print(f"Warning: No OHLCV data returned for {symbol} on {timeframe}.")
                return 0

            # Exclude the current, incomplete candle from the analysis
            completed_candles = ohlcv[:-1]

            # Count consecutive candles of the same color, starting from the most recent
            consecutive_count = 0
            last_color = None

            for candle in reversed(completed_candles):
                # ohlcv format: [timestamp, open, high, low, close, volume]
                open_price = candle[1]
                close_price = candle[4]
                
                current_color = "green" if close_price >= open_price else "red"

                if last_color is None or current_color == last_color:
                    consecutive_count += 1
                    last_color = current_color
                else:
                    # The streak is broken
                    break
            
            return consecutive_count

        except Exception as e:
            print(f"Error counting candles for {symbol} on {timeframe}: {e}")
            return 0

    def scan_for_candle_streaks(self, timeframes, top_n_volume=70, min_streak_count=3):
        """
        Scans top volume assets across multiple timeframes for consecutive candle streaks.

        Args:
            timeframes (list): A list of timeframes to scan (e.g., ['1h', '4h']).
            top_n_volume (int): The number of top volume symbols to scan.
            min_streak_count (int): The minimum number of consecutive candles to be considered a valid streak.

        Returns:
            list: A sorted list of tuples, where each tuple is (symbol, streak_count, timeframe).
                  The list is sorted by streak_count in descending order.
        """
        print(f"Scanning {top_n_volume} top volume symbols for streaks of at least {min_streak_count} candles...")
        
        # 1. Get the symbols with the highest volume
        symbols = self.fetch_top_volumes(limit=top_n_volume)
        if not symbols:
            print("Could not fetch top volume symbols. Aborting scan.")
            return []

        # 2. Iterate through symbols and timeframes to find streaks
        report_data = []
        for i, symbol in enumerate(symbols):
            # Print progress to the console
            print(f"  -> [{i+1}/{len(symbols)}] Analyzing {symbol}...")
            for timeframe in timeframes:
                count = self.count_consecutive_candles(symbol, timeframe)
                
                # Only add to the report if the streak is significant
                if count >= min_streak_count:
                    report_data.append((symbol, count, timeframe))

        # 3. Sort the final data by the streak count (descending)
        sorted_data = sorted(report_data, key=lambda x: x[1], reverse=True)
        
        print(f"Scan complete. Found {len(sorted_data)} significant streaks.")
        return sorted_data