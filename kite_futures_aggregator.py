#!/usr/bin/env python3
"""
Futures Data Aggregator
Dynamically fetches and categorizes futures by expiry rank (near/next/far)
"""

from KiteApi.kiteConnect import KiteConnect
import json
from datetime import datetime
import time
import os
import threading
from collections import defaultdict

class FuturesAggregator:
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key, access_token=access_token)
        
        self.all_futures = []
        self.cached = False
        
        self.last_request_time = 0
        self.min_request_interval = 0.1
        self.request_lock = threading.Lock()
    
    def _rate_limited_request(self, request_func, *args, **kwargs):
        with self.request_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
            
            try:
                result = request_func(*args, **kwargs)
                self.last_request_time = time.time()
                return result
            except Exception as e:
                self.last_request_time = time.time()
                raise e
    
    def fetch_all_futures_contracts(self, exchange="NFO"):
        """Fetch ALL futures contracts from NFO and organize by expiry rank"""
        if self.cached and self.all_futures:
            return self.all_futures
        
        print(f"[FETCHING] Getting all futures from {exchange}...")
        
        instruments_data = self._rate_limited_request(self.kite.instruments, exchange)
        
        if not instruments_data or 'data' not in instruments_data:
            print("[ERROR] No instruments data")
            return []
        
        instruments = instruments_data['data']
        print(f"[PROCESSING] {len(instruments)} instruments...")
        
        current_date = datetime.now()
        
        popular_symbols = [
            'NIFTY', 'BANKNIFTY', 'SENSEX', 'BANKEX', 'FINNIFTY',
            'RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK', 'SBIN',
            'LT', 'HCLTECH', 'WIPRO', 'ITC', 'BHARTIARTL', 'HINDUNILVR',
            'AXISBANK', 'KOTAKBANK', 'ASIANPAINT', 'MARUTI', 'TITAN'
        ]
        
        all_contracts = []
        
        for instrument in instruments:
            try:
                trading_symbol = instrument.get('tradingsymbol', '').upper()
                name = instrument.get('name', '').upper().replace('"', '').strip()
                instrument_type = instrument.get('instrument_type', '').upper()
                expiry_str = instrument.get('expiry', '')
                lot_size = instrument.get('lot_size', 1)
                instrument_token = instrument.get('instrument_token', '')
                
                if (instrument_type == 'FUT' and 
                    expiry_str and expiry_str != '0' and expiry_str.lower() != 'none' and
                    instrument_token):
                    
                    try:
                        expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d')
                        days_diff = (expiry_dt - current_date).days
                        
                        # Include all contracts (even if expired today)
                        # This ensures 24 Feb is included until market closes
                        is_popular = any(pop in name for pop in popular_symbols)
                        
                        contract = {
                            'symbol': trading_symbol,
                            'name': name,
                            'instrument_token': instrument_token,
                            'expiry': expiry_str,
                            'expiry_formatted': expiry_dt.strftime('%d/%m/%Y'),
                            'days_to_expiry': days_diff,
                            'lot_size': int(lot_size) if lot_size else 1,
                            'instrument_type': instrument_type,
                            'tick_size': float(instrument.get('tick_size', 0.05)),
                            'exchange': exchange,
                            'is_popular': is_popular
                        }
                        all_contracts.append(contract)
                    except:
                        continue
            except:
                continue
        
        print(f"[OK] Found {len(all_contracts)} futures contracts")
        
        # Group by underlying name
        by_name = defaultdict(list)
        for c in all_contracts:
            by_name[c['name']].append(c)
        
        # Sort each group by days_to_expiry
        for name in by_name:
            by_name[name].sort(key=lambda x: x['days_to_expiry'])
        
        # Create rank-based categories
        near_contracts = []
        next_contracts = []
        far_contracts = []
        
        for name, contracts in by_name.items():
            # Rank 1 = nearest (near)
            if len(contracts) >= 1:
                c = contracts[0].copy()
                c['category'] = 'near'
                near_contracts.append(c)
            
            # Rank 2 = next nearest (next)
            if len(contracts) >= 2:
                c = contracts[1].copy()
                c['category'] = 'next'
                next_contracts.append(c)
            
            # Rank 3 = third nearest (far)
            # If only 2 contracts exist, use the 2nd one as far (extended range)
            if len(contracts) >= 3:
                c = contracts[2].copy()
                c['category'] = 'far'
                far_contracts.append(c)
            elif len(contracts) == 2:
                # Use 2nd contract as far when no 3rd exists
                c = contracts[1].copy()
                c['category'] = 'far'
                far_contracts.append(c)
        
        # Sort by popularity then symbol
        for c_list in [near_contracts, next_contracts, far_contracts]:
            c_list.sort(key=lambda x: (not x['is_popular'], x['symbol']))
        
        self.all_futures = {
            'near': near_contracts,
            'next': next_contracts,
            'far': far_contracts
        }
        self.cached = True
        
        print(f"[OK] Near: {len(near_contracts)}, Next: {len(next_contracts)}, Far: {len(far_contracts)}")
        
        return self.all_futures
    
    def get_near_contracts(self):
        """Get nearest expiry contracts"""
        if not self.cached:
            self.fetch_all_futures_contracts()
        return self.all_futures.get('near', [])
    
    def get_next_contracts(self):
        """Get second nearest expiry contracts"""
        if not self.cached:
            self.fetch_all_futures_contracts()
        return self.all_futures.get('next', [])
    
    def get_far_contracts(self):
        """Get third nearest expiry contracts"""
        if not self.cached:
            self.fetch_all_futures_contracts()
        return self.all_futures.get('far', [])

def main():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    config_file = "kite_config_hf.py"
    if os.path.exists(config_file):
        import importlib.util
        spec = importlib.util.spec_from_file_location("config", config_file)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        api_key = config.API_KEY
        access_token = config.ACCESS_TOKEN
    else:
        api_key = os.getenv('KITE_API_KEY')
        access_token = os.getenv('KITE_ACCESS_TOKEN')
    
    if not api_key or not access_token:
        print("ERROR: Set KITE_API_KEY and KITE_ACCESS_TOKEN")
        return
    
    aggregator = FuturesAggregator(api_key, access_token)
    
    print("\n" + "="*60)
    print("TESTING FUTURES AGGREGATOR")
    print("="*60)
    
    result = aggregator.fetch_all_futures_contracts()
    
    print(f"\nNear (1st nearest): {len(result['near'])}")
    print(f"Next (2nd nearest): {len(result['next'])}")
    print(f"Far (3rd nearest): {len(result['far'])}")
    
    # Show sample
    print("\n--- Sample Near ---")
    for c in result['near'][:3]:
        print(f"  {c['name']}: {c['symbol']}, days={c['days_to_expiry']}, expiry={c['expiry_formatted']}")
    
    print("\n--- Sample Next ---")
    for c in result['next'][:3]:
        print(f"  {c['name']}: {c['symbol']}, days={c['days_to_expiry']}, expiry={c['expiry_formatted']}")
    
    print("\n--- Sample Far ---")
    for c in result['far'][:3]:
        print(f"  {c['name']}: {c['symbol']}, days={c['days_to_expiry']}, expiry={c['expiry_formatted']}")

if __name__ == "__main__":
    main()
