#!/usr/bin/env python3
"""
API Wrapper for Far Futures Data
Outputs JSON data for frontend consumption
"""

import json
import sys
import os
from kite_far_futures import KiteFarFutures

def main():
    try:
        # Get credentials from environment variables
        API_KEY = os.getenv('KITE_API_KEY')
        ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN')
        
        if not API_KEY or not ACCESS_TOKEN:
            print(json.dumps({
                "error": "KITE_API_KEY and KITE_ACCESS_TOKEN environment variables required"
            }))
            sys.exit(1)
        
        # Initialize the futures fetcher
        fetcher = KiteFarFutures(API_KEY, ACCESS_TOKEN)
        
        # Get live data
        live_data = fetcher.fetch_live_data(use_ltp_only=False, limit_contracts=50)
        
        # Convert to frontend-compatible format
        contracts = []
        for symbol, data in live_data.items():
            contract_info = data.get('contract_info', {})
            
            # Calculate change percentage if not available
            ltp = data.get('ltp', 0)
            change = data.get('change', 0)
            change_percent = data.get('change_percent', 0)
            
            if ltp > 0 and change != 0 and change_percent == 0:
                change_percent = (change / (ltp - change)) * 100
            
            contract = {
                'symbol': symbol,
                'ltp': float(ltp),
                'change': float(change),
                'change_percent': float(change_percent),
                'volume': int(data.get('volume', 0)),
                'lot_size': int(contract_info.get('lot_size', 1)),
                'category': 'far',
                'days_to_expiry': contract_info.get('days_to_expiry', 0),
                'timestamp': data.get('timestamp', '')
            }
            contracts.append(contract)
        
        # Output as JSON
        print(json.dumps(contracts, indent=2))
        
    except Exception as e:
        error_data = {
            "error": str(e),
            "type": "far_futures_error"
        }
        print(json.dumps(error_data))
        sys.exit(1)

if __name__ == "__main__":
    main()