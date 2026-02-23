#!/usr/bin/env python3
"""
Kite Near Futures Data Fetcher
Specialized for near month futures (36-70 days expiry) with ultra-fast performance
"""

from KiteApi.kiteConnect import KiteConnect
import json
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import sys
import concurrent.futures
import threading

class KiteNearFutures:
    def __init__(self, api_key, access_token, ws_manager=None):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key, access_token=access_token)
        self.ws_manager = ws_manager  # WebSocket manager for real-time data
        
        # Data storage
        self.near_contracts = []
        self.live_data = {}
        self.data_lock = threading.Lock()
        
        # Rate limiting variables (for fallback HTTP calls only)
        self.last_request_time = 0
        self.min_request_interval = 0.1
        self.request_lock = threading.Lock()
        
        print(f"🔑 Initialized Near Futures API with key: {api_key[:10]}...")
        if ws_manager:
            print("🔌 WebSocket mode enabled - will use real-time tick data")
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def is_market_open(self):
        """Check if market is currently open"""
        now = datetime.now()
        
        # Check if it's a weekday (Monday=0, Sunday=6)
        if now.weekday() > 4:  # Saturday or Sunday
            return False
        
        # Market hours: 9:15 AM to 3:30 PM IST
        market_start = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_start <= now <= market_end
    
    def get_near_futures_contracts(self, exchange="NFO"):
        """Get near month futures contracts (36-70 days expiry)"""
        try:
            if self.near_contracts:
                return self.near_contracts
            
            print(f"🔍 Fetching NEAR futures contracts from exchange: {exchange}")
            instruments_data = self._rate_limited_request(self.kite.instruments, exchange)
            
            if not instruments_data or 'data' not in instruments_data:
                print("❌ No instruments data available")
                return []
            
            instruments = instruments_data['data']
            print(f"📊 Processing {len(instruments)} instruments for near futures...")
            
            current_date = datetime.now()
            near_contracts = []
            
            # Popular symbols for faster loading
            popular_symbols = [
                'NIFTY', 'BANKNIFTY', 'SENSEX', 'BANKEX', 'FINNIFTY', 
                'RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK', 'SBIN', 
                'LT', 'HCLTECH', 'WIPRO', 'ITC', 'BHARTIARTL', 'HINDUNILVR',
                'AXISBANK', 'KOTAKBANK', 'ASIANPAINT', 'MARUTI', 'TITAN'
            ]
            
            for instrument in instruments:
                try:
                    trading_symbol = instrument.get('tradingsymbol', '').upper()
                    name = instrument.get('name', '').upper()
                    instrument_type = instrument.get('instrument_type', '').upper()
                    expiry_str = instrument.get('expiry', '')
                    lot_size = instrument.get('lot_size', 1)
                    instrument_token = instrument.get('instrument_token', '')
                    
                    # Filter for futures only
                    if (instrument_type == 'FUT' and 
                        expiry_str and expiry_str != '0' and expiry_str.lower() != 'none' and
                        instrument_token):
                        
                        # Check if it's a popular symbol
                        is_popular = any(pop_symbol in name for pop_symbol in popular_symbols)
                        
                        try:
                            expiry_dt = datetime.strptime(expiry_str, '%Y-%m-%d')
                            days_diff = (expiry_dt - current_date).days
                            
                            # Only next month futures (30-65 days)
                            # Adjusted to catch actual next month expiry (March)
                            if 30 <= days_diff <= 65:
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
                                    'category': 'near',
                                    'exchange': exchange,
                                    'is_popular': is_popular
                                }
                                
                                near_contracts.append(contract)
                                
                        except Exception:
                            continue
                            
                except Exception:
                    continue
            
            # Sort by popularity first, then by symbol
            near_contracts.sort(key=lambda x: (not x['is_popular'], x['symbol']))
            
            print(f"✅ Found {len(near_contracts)} near futures contracts")
            
            self.near_contracts = near_contracts
            return near_contracts
            
        except Exception as e:
            print(f"❌ Error fetching near futures contracts: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _rate_limited_request(self, request_func, *args, **kwargs):
        """Make a rate-limited API request"""
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
    
    def fetch_live_data_from_websocket(self):
        """Get live data from WebSocket manager (real-time ticks)"""
        if not self.ws_manager:
            print("⚠️ WebSocket manager not available - use HTTP fallback")
            return self.fetch_live_data_http()
        
        try:
            contracts = self.get_near_futures_contracts()
            if not contracts:
                return {}
            
            # Get all tick data from WebSocket
            all_ticks = self.ws_manager.get_tick_data()
            
            live_data = {}
            for contract in contracts:
                token = int(contract['instrument_token'])
                tick = all_ticks.get(token)
                
                if tick:
                    symbol = contract['symbol']
                    ltp = tick.get('last_price', 0)
                    ohlc = tick.get('ohlc', {})
                    close = ohlc.get('close', 0)
                    change = ltp - close if close else 0
                    change_pct = (change / close * 100) if close else 0
                    
                    live_data[symbol] = {
                        'symbol': symbol,
                        'ltp': ltp,
                        'change': change,
                        'change_pct': change_pct,
                        'volume': tick.get('volume_traded', 0),
                        'oi': tick.get('oi', 0),
                        'bid': tick.get('depth', {}).get('buy', [{}])[0].get('price', 0) if tick.get('depth') else 0,
                        'ask': tick.get('depth', {}).get('sell', [{}])[0].get('price', 0) if tick.get('depth') else 0,
                        'contract_info': contract,
                        'timestamp': tick.get('updated_at', datetime.now().isoformat())
                    }
            
            with self.data_lock:
                self.live_data = live_data
            
            return live_data
            
        except Exception as e:
            print(f"❌ Error getting WebSocket data: {e}")
            return {}
    
    def fetch_live_data_http(self, use_ltp_only=True, limit_contracts=None):
        """Fetch live data via HTTP (fallback method)"""
        try:
            contracts = self.get_near_futures_contracts()
            
            if limit_contracts and len(contracts) > limit_contracts:
                contracts = contracts[:limit_contracts]
            
            if not contracts:
                print("❌ No near futures contracts available")
                return {}
            
            print(f"📈 Fetching live data for {len(contracts)} near futures via HTTP...")
            
            symbols = []
            symbol_to_contract = {}
            
            for contract in contracts:
                symbol_key = f"{contract['exchange']}:{contract['symbol']}"
                symbols.append(symbol_key)
                symbol_to_contract[contract['symbol']] = contract
            
            live_data = {}
            batch_size = 20
            
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                
                try:
                    if use_ltp_only:
                        response = self._rate_limited_request(self.kite.ltp, batch)
                    else:
                        response = self._rate_limited_request(self.kite.quote, batch)
                    
                    if response and 'data' in response:
                        for symbol_key, data in response['data'].items():
                            symbol = symbol_key.split(':')[1]
                            contract = symbol_to_contract.get(symbol)
                            
                            if contract:
                                if use_ltp_only:
                                    live_data[symbol] = {
                                        'symbol': symbol,
                                        'ltp': data.get('last_price', 0),
                                        'contract_info': contract,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                else:
                                    ltp = data.get('last_price', 0)
                                    close = data.get('ohlc', {}).get('close', 0)
                                    change = ltp - close if close else 0
                                    change_pct = (change / close * 100) if close else 0
                                    
                                    live_data[symbol] = {
                                        'symbol': symbol,
                                        'ltp': ltp,
                                        'change': change,
                                        'change_pct': change_pct,
                                        'volume': data.get('volume', 0),
                                        'bid': data.get('depth', {}).get('buy', [{}])[0].get('price', 0) if data.get('depth') else 0,
                                        'ask': data.get('depth', {}).get('sell', [{}])[0].get('price', 0) if data.get('depth') else 0,
                                        'contract_info': contract,
                                        'timestamp': datetime.now().isoformat()
                                    }
                
                except Exception as e:
                    print(f"⚠️ Error fetching batch {i//batch_size + 1}: {e}")
                    continue
            
            with self.data_lock:
                self.live_data = live_data
            
            print(f"✅ Successfully fetched data for {len(live_data)} near futures")
            return live_data
            
        except Exception as e:
            print(f"❌ Error fetching live data: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def fetch_live_data(self, use_ltp_only=True, limit_contracts=None):
        """Fetch live data - uses WebSocket if available, otherwise HTTP"""
        if self.ws_manager:
            return self.fetch_live_data_from_websocket()
        else:
            return self.fetch_live_data_http(use_ltp_only, limit_contracts)
    
    def get_data_as_json(self):
        """Get near live data as JSON"""
        with self.data_lock:
            return json.dumps(self.live_data, indent=2)
    
    def display_live_data(self, limit=20):
        """Display live data in terminal"""
        if not self.live_data:
            print("❌ No live data available")
            return
        
        self.clear_screen()
        print("=" * 120)
        print(f"🔄 NEAR FUTURES LIVE DATA - {datetime.now().strftime('%H:%M:%S')}")
        print(f"📊 Market Status: {'🟢 OPEN' if self.is_market_open() else '🔴 CLOSED'}")
        print("=" * 120)
        
        # Header with all fields
        print(f"{'Symbol':<20} {'LTP':<10} {'Change':<10} {'Change%':<10} {'Volume':<12} {'Bid':<10} {'Ask':<10} {'Expiry':<12} {'Days':<6}")
        print("-" * 120)
        
        count = 0
        for symbol, data in list(self.live_data.items())[:limit]:
            contract = data.get('contract_info', {})
            change = data.get('change', 0)
            change_pct = data.get('change_pct', 0)
            
            # Color coding for change
            change_color = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
            
            print(f"{symbol:<20} {data.get('ltp', 0):<10.2f} "
                  f"{change_color} {change:<8.2f} "
                  f"{change_pct:<9.2f}% "
                  f"{data.get('volume', 0):<12} "
                  f"{data.get('bid', 0):<10.2f} "
                  f"{data.get('ask', 0):<10.2f} "
                  f"{contract.get('expiry_formatted', 'N/A'):<12} "
                  f"{contract.get('days_to_expiry', 'N/A'):<6}")
            
            count += 1
        
        print("-" * 120)
        print(f"📈 Showing {count} of {len(self.live_data)} near futures contracts")
        print("=" * 120)

def main():
    """Main function to run near futures fetcher"""
    try:
        # Load configuration
        config_file = "kite_config_hf.py"
        if os.path.exists(config_file):
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", config_file)
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
            
            api_key = config.API_KEY
            access_token = config.ACCESS_TOKEN
        else:
            # Fallback to environment variables
            api_key = os.getenv('KITE_API_KEY')
            access_token = os.getenv('KITE_ACCESS_TOKEN')
        
        if not api_key or not access_token:
            print("❌ Please set KITE_API_KEY and KITE_ACCESS_TOKEN")
            return
        
        # Initialize near futures fetcher
        near_futures = KiteNearFutures(api_key, access_token)
        
        print("🚀 Starting Near Futures Live Data Feed...")
        print("Press Ctrl+C to stop")
        
        while True:
            try:
                start_time = time.time()
                near_futures.fetch_live_data(use_ltp_only=False, limit_contracts=None)
                near_futures.display_live_data(limit=None)
                
                fetch_time = time.time() - start_time
                print(f"⏱️ Fetch time: {fetch_time:.2f} seconds")
                
                time.sleep(2)  # Refresh every 2 seconds
                
            except KeyboardInterrupt:
                print("\n👋 Stopping near futures feed...")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                time.sleep(5)
    
    except Exception as e:
        print(f"❌ Failed to start near futures fetcher: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()