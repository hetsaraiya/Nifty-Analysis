#!/usr/bin/env python3
"""
Standalone Enhanced NIFTY Options Greeks Calculator
Run this script independently to get comprehensive options analysis with live Angel One data
"""

import sys
import os
from datetime import datetime
import json

# Add the current directory to the path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nifty_greeks_calculator import EnhancedAngelSmartAPI, EnhancedNiftyDataFetcher

def get_user_input():
    """Get user input for credentials and parameters"""
    print("=" * 60)
    print("ENHANCED NIFTY OPTIONS GREEKS CALCULATOR")
    print("=" * 60)
    print()
    
    # Get credentials
    print("Please enter your Angel One credentials:")
    client_code = input("Client Code: ").strip()
    password = input("Password: ").strip()
    totp = input("Current TOTP (6-digit code): ").strip()
    
    if not all([client_code, password, totp]):
        print("Error: All credentials are required!")
        return None
    
    # Get analysis parameters
    print("\nAnalysis Parameters:")
    try:
        volatility_input = input("Implied Volatility (default 20%): ").strip()
        volatility = float(volatility_input) / 100 if volatility_input else 0.20
    except ValueError:
        volatility = 0.20
        print("Using default volatility: 20%")
    
    expiry_input = input("Days to expiry (default: next Thursday): ").strip()
    days_to_expiry = int(expiry_input) if expiry_input.isdigit() else None
    
    return {
        'client_code': client_code,
        'password': password,
        'totp': totp,
        'volatility': volatility,
        'days_to_expiry': days_to_expiry
    }

def save_results(result, suffix=""):
    """Save results to files"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save main data to CSV
    if isinstance(result, dict) and 'data' in result:
        df = result['data']
        csv_filename = f"enhanced_nifty_greeks{suffix}_{timestamp}.csv"
        df.to_csv(csv_filename, index=False)
        print(f"✓ Data saved to: {csv_filename}")
        
        # Save analytics and metadata to JSON
        analytics_data = {
            'analytics': result.get('analytics', {}),
            'metadata': result.get('metadata', {}),
            'timestamp': timestamp
        }
        
        json_filename = f"nifty_analytics{suffix}_{timestamp}.json"
        with open(json_filename, 'w') as f:
            json.dump(analytics_data, f, indent=2)
        print(f"✓ Analytics saved to: {json_filename}")
        
    else:
        # Simple DataFrame
        csv_filename = f"nifty_greeks{suffix}_{timestamp}.csv"
        result.to_csv(csv_filename, index=False)
        print(f"✓ Data saved to: {csv_filename}")

def run_continuous_analysis(fetcher, volatility, update_interval=30):
    """Run continuous analysis with periodic updates"""
    print(f"\n{'='*60}")
    print("CONTINUOUS MONITORING MODE")
    print(f"Updates every {update_interval} seconds (Ctrl+C to stop)")
    print(f"{'='*60}")
    
    try:
        iteration = 1
        while True:
            print(f"\n--- Update #{iteration} at {datetime.now().strftime('%H:%M:%S')} ---")
            
            result = fetcher.get_live_nifty_data_with_greeks(
                volatility=volatility,
                include_analytics=True
            )
            
            if result:
                # Quick summary display
                metadata = result.get('metadata', {})
                analytics = result.get('analytics', {})
                
                spot_price = metadata.get('spot_price', 'N/A')
                print(f"Spot Price: {spot_price}")
                
                if 'portfolio_greeks' in analytics:
                    pg = analytics['portfolio_greeks']
                    print(f"Portfolio Delta: {pg.get('delta', 'N/A')}")
                    print(f"Portfolio Gamma: {pg.get('gamma', 'N/A')}")
                    print(f"Portfolio Theta: {pg.get('theta', 'N/A')}")
                
                # Save every 10th iteration
                if iteration % 10 == 0:
                    save_results(result, f"_update_{iteration}")
                    print(f"✓ Saved update #{iteration} data")
            
            else:
                print("⚠ Failed to fetch data in this iteration")
            
            iteration += 1
            time.sleep(update_interval)
            
    except KeyboardInterrupt:
        print(f"\n{'='*60}")
        print("CONTINUOUS MONITORING STOPPED")
        print(f"Total iterations completed: {iteration - 1}")
        print(f"{'='*60}")

def main():
    """Main execution function"""
    # Get user input
    user_input = get_user_input()
    if not user_input:
        return
    
    # Initialize API
    print(f"\n{'='*60}")
    print("INITIALIZING CONNECTION")
    print(f"{'='*60}")
    
    api = EnhancedAngelSmartAPI()
    
    # Login
    print("Logging into Angel One SmartAPI...")
    login_success = api.login(
        user_input['client_code'],
        user_input['password'],
        user_input['totp']
    )
    
    if not login_success:
        print("❌ Login failed. Please check your credentials and try again.")
        return
    
    print("✅ Login successful!")
    
    # Initialize data fetcher
    fetcher = EnhancedNiftyDataFetcher(api)
    
    # Fetch initial comprehensive data
    print(f"\n{'='*60}")
    print("FETCHING COMPREHENSIVE DATA")
    print(f"{'='*60}")
    
    result = fetcher.get_live_nifty_data_with_greeks(
        volatility=user_input['volatility'],
        include_analytics=True
    )
    
    if not result:
        print("❌ Failed to fetch initial data.")
        return
    
    # Display results
    fetcher.display_enhanced_greeks_data(result)
    
    # Save results
    print(f"\n{'='*60}")
    print("SAVING RESULTS")
    print(f"{'='*60}")
    
    save_results(result)
    
    # Ask for continuous monitoring
    print(f"\n{'='*60}")
    print("OPTIONS")
    print(f"{'='*60}")
    
    choice = input("Start continuous monitoring? (y/N): ").strip().lower()
    
    if choice in ['y', 'yes']:
        try:
            interval_input = input("Update interval in seconds (default 30): ").strip()
            interval = int(interval_input) if interval_input.isdigit() else 30
            
            run_continuous_analysis(fetcher, user_input['volatility'], interval)
            
        except ValueError:
            print("Invalid interval. Using default 30 seconds.")
            run_continuous_analysis(fetcher, user_input['volatility'])
    
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print("Thank you for using Enhanced NIFTY Options Greeks Calculator!")
    print(f"{'='*60}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {str(e)}")
        print("Please check your credentials and try again.")
