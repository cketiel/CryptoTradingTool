# Module to interact with the KuCoin API

import ccxt
import sys

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