# Entry point to run the different interfaces

# This file would be the entry point. It could accept command line arguments to decide which interface to launch. For example: python main.py --interface telegram.

# Main entry point for the entire application.

import sys

# We will import the different application interfaces here
from interfaces.cli_app import run_cli
from interfaces.desktop_app import run_desktop
# from interfaces.telegram_bot import run_bot # Example for the future
# from interfaces.web_app import run_web # Example for the future

def main():
    """
    Determines which interface to run based on command-line arguments.
    """
    print("--- Crypto Trading Tool ---")
    
    # Check for command-line arguments
    if len(sys.argv) > 1 and sys.argv[1] == '--interface':
        try:
            interface = sys.argv[2]
            if interface == 'desktop':
                run_desktop()
            elif interface == 'cli':
                run_cli()
            else:
                print(f"Error: Unknown interface '{interface}'. Defaulting to CLI.")
                run_cli()
        except IndexError:
            print("Error: Missing interface name. Use '--interface [cli|desktop]'. Defaulting to CLI.")
            run_cli()
    else:
        # Default behavior: run the CLI
        run_cli()

if __name__ == "__main__":
    main()