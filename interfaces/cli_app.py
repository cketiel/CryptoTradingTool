# Command-line application to test the core functionality

from core.kucoin_client import KuCoinClient

def run_cli():
    """
    Main function to run the console app.
    """
    print("Starting the trading tool in console mode...")
    
    # 1. Create an instance of our KuCoin client.
    # This will automatically connect and authenticate.
    kucoin = KuCoinClient()
    
    # 2. Call the method to get the top assets by volume.
    print("\nFetching the top 20 assets by volume...")
    top_assets = kucoin.fetch_top_volumes(limit=20)
    
    # 3. Display the results.
    if top_assets:
        print("\n--- Top 20 Assets by Volume ---")
        for i, asset in enumerate(top_assets, 1):
            print(f"{i:2}. {asset}")
        print("---------------------------------")
    else:
        print("Could not retrieve the assets.")
        
if __name__ == "__main__":
    run_cli()