# Entry point to run the different interfaces

# This file would be the entry point. It could accept command line arguments to decide which interface to launch. For example: python main.py --interface telegram.

# Main entry point for the entire application.

import sys

# We will import the different application interfaces here
from interfaces.cli_app import run_cli
# from interfaces.telegram_bot import run_bot # Example for the future
# from interfaces.web_app import run_web # Example for the future

def main():
    """
    Determines which interface to run.
    For now, it will default to the command-line interface (CLI).
    """
    print("--- Crypto Trading Tool ---")
    
    # In the future, you could check command-line arguments here
    # to decide which interface to launch.
    # For example: python main.py --interface telegram
    
    # For now, we will run the CLI by default.
    run_cli()

if __name__ == "__main__":
    main()