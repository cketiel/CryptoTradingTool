# Command-line application to test the core functionality

from prettytable import PrettyTable
from core.kucoin_client import KuCoinClient
from config.intervals import all_interval, small_interval, big_interval

def display_report(report_data):
    """
    Displays the generated report data in a formatted table.
    """
    if not report_data:
        print("\nNo significant streaks found based on the current criteria.")
        return

    # Limit the output to the top 20 results for clarity
    display_data = report_data[:20]

    # Create and populate the table
    table = PrettyTable()
    table.field_names = ["Symbol", "Streak Count", "Timeframe"]
    table.align = "l" # Left align
    table.align["Streak Count"] = "r" # Right align the count

    for row in display_data:
        table.add_row(row)

    print("\n--- Consecutive Candle Streak Report ---")
    print(table)
    print("----------------------------------------")

def run_cli():
    """
    Main function to run the console app.
    """
    print("Starting the trading tool in console mode...")
    
    # 1. Initialize the KuCoin client
    kucoin = KuCoinClient()
    
    # 2. Run the scan
    # You can easily choose which intervals to scan by changing the parameter.
    # Options: all_interval, small_interval, big_interval
    print("\nScanning for assets with significant candle streaks...")
    interesting_assets = kucoin.scan_for_candle_streaks(
        timeframes=all_interval, 
        top_n_volume=50,      # Scan the top 50 coins by volume
        min_streak_count=4    # Report streaks of 4 or more candles
    )
    
    # 3. Display the results in a table
    display_report(interesting_assets)

def run_cli2():
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

        # Get consecutive candle count for the #1 asset
        top_asset = top_assets[0]
        test_timeframe = '1h'
        print(f"\nChecking consecutive candles for top asset: {top_asset} on {test_timeframe} timeframe...")
        
        consecutive_count = kucoin.count_consecutive_candles(top_asset, test_timeframe)
        
        if consecutive_count > 0:
            print(f"Result: Found a streak of {consecutive_count} consecutive candles.")
        else:
            print("Result: No consecutive candle streak found or an error occurred.")

    else:
        print("Could not retrieve the assets.")
        
if __name__ == "__main__":
    run_cli()