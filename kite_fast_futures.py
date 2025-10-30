#!/usr/bin/env python3
"""
Kite Fast Futures Data Fetcher
Optimized version that fetches current, near, and far futures data in parallel for faster performance
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

class KiteFastFutures:
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key, access_token=access_token)
        
        # Data storage
        self.categorized_contracts = {}
        self.live_data = {}
        self.data_lock = threading.Lock()
        
        # Rate limiting variables
        self.last_request_time = 0
        self.min_request_interval = 0.1  # Minimum 100ms between requests
        self.request_lock = threading.Lock()
        
        print(f"🔑 Initialized Kite API with key: {api_key[:10]}...")
    
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
    
    def get_all_futures_by_category(self, exchange="NFO"):
        """Get all futures contracts categorized by expiry periods"""
        try:
            if self.categorized_contracts:
                return self.categorized_contracts
            
            print(f"🔍 Fetching futures contracts from exchange: {exchange}")
            instruments_data = self._rate_limited_request(self.kite.instruments, exchange)
            
            if not instruments_data or 'data' not in instruments_data:
                print("❌ No instruments data available")
                return {"current": [], "near": [], "far": []}
            
            instruments = instruments_data['data']
            print(f"📊 Processing {len(instruments)} instruments...")
            
            current_date = datetime.now()
            
            categorized_contracts = {
                "current": [],
                "near": [], 
                "far": []
            }
            
            # Focus on popular underlying symbols for faster loading
            popular_symbols = ['NIFTY', 'BANKNIFTY', 'SENSEX', 'BANKEX', 'FINNIFTY', 'RELIANCE', 'TCS', 'INFY', 'HDFC', 'ICICIBANK', 'SBIN', 'LT', 'HCLTECH', 'WIPRO']
            
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
                            
                            # Skip expired contracts
                            if days_diff < 0:
                                continue
                            
                            # Better categorization aligned with futures expiry cycles
                            if days_diff <= 35:  # Current month expiry (0-35 days)
                                category = "current"
                            elif days_diff <= 70:  # Next month expiry (36-70 days) 
                                category = "near"
                            elif days_diff <= 105:  # Far month expiry (71-105 days)
                                category = "far"
                            else:
                                continue
                            
                            # Add contract
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
                                'category': category,
                                'exchange': exchange,
                                'is_popular': is_popular
                            }
                            
                            categorized_contracts[category].append(contract)
                            
                        except Exception:
                            continue
                            
                except Exception:
                    continue
            
            # Sort by popularity first, then by symbol
            for category in categorized_contracts:
                categorized_contracts[category].sort(key=lambda x: (not x['is_popular'], x['symbol']))
            
            total = sum(len(contracts) for contracts in categorized_contracts.values())
            print(f"✅ Found {total} futures contracts")
            print(f"   Current (0-35 days): {len(categorized_contracts['current'])}")
            print(f"   Near (36-70 days): {len(categorized_contracts['near'])}")
            print(f"   Far (71-105 days): {len(categorized_contracts['far'])}")
            
            self.categorized_contracts = categorized_contracts
            return categorized_contracts
            
        except Exception as e:
            print(f"❌ Error fetching futures contracts: {e}")
            import traceback
            traceback.print_exc()
            return {"current": [], "near": [], "far": []}
    
    def _rate_limited_request(self, request_func, *args, **kwargs):
        """Make a rate-limited API request"""
        with self.request_lock:
            # Ensure minimum interval between requests
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
    
    def fetch_category_quotes(self, category, contracts, use_ltp_only=False):
        """Fetch quotes for a specific category of contracts with rate limiting"""
        if not contracts:
            return category, {}
        
        live_data = {}
        successful_fetches = 0
        
        try:
            # Prepare symbols
            symbols = []
            symbol_to_contract = {}
            
            for contract in contracts:
                symbol_key = f"{contract['exchange']}:{contract['symbol']}"
                symbols.append(symbol_key)
                symbol_to_contract[contract['symbol']] = contract
            
            # Adjust batch size based on number of contracts to balance speed and rate limits
            batch_size = 15 if len(contracts) > 100 else 10
            
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]
                
                try:
                    if use_ltp_only:
                        response = self._rate_limited_request(self.kite.ltp, batch)
                    else:
                        response = self._rate_limited_request(self.kite.quote, batch)
                    
                    if response and 'data' in response and response['data']:
                        for instrument_id, quote_data in response['data'].items():
                            try:
                                symbol = instrument_id.split(':')[-1]
                                contract = symbol_to_contract.get(symbol)
                                
                                if contract and quote_data:
                                    token = contract['instrument_token']
                                    
                                    if use_ltp_only:
                                        ltp = quote_data.get('last_price', 0)
                                        if ltp and ltp > 0:
                                            live_data[token] = {
                                                'symbol': symbol,
                                                'ltp': ltp,
                                                'open': 0,
                                                'high': 0,
                                                'low': 0,
                                                'close': 0,
                                                'volume': 0,
                                                'change': 0,
                                                'change_percent': 0,
                                                'bid': 0,
                                                'ask': 0,
                                                'timestamp': datetime.now().strftime('%H:%M:%S')
                                            }
                                            successful_fetches += 1
                                    else:
                                        ltp = quote_data.get('last_price', 0)
                                        ohlc = quote_data.get('ohlc', {})
                                        prev_close = ohlc.get('close', 0) if ohlc else 0
                                        net_change = quote_data.get('net_change', 0)
                                        volume = quote_data.get('volume', 0)
                                        
                                        if ltp is not None:
                                            # Use net_change from API if available, otherwise calculate
                                            if net_change != 0:
                                                change = net_change
                                                change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                                            elif prev_close and prev_close > 0 and ltp > 0:
                                                change = ltp - prev_close
                                                change_percent = (change / prev_close) * 100
                                            else:
                                                change = 0
                                                change_percent = 0
                                            
                                            # Get bid/ask from depth
                                            depth = quote_data.get('depth', {})
                                            buy_orders = depth.get('buy', []) if depth else []
                                            sell_orders = depth.get('sell', []) if depth else []
                                            
                                            bid = buy_orders[0].get('price', 0) if buy_orders else 0
                                            ask = sell_orders[0].get('price', 0) if sell_orders else 0
                                            
                                            live_data[token] = {
                                                'symbol': symbol,
                                                'ltp': ltp if ltp else 0,
                                                'open': ohlc.get('open', 0) if ohlc else 0,
                                                'high': ohlc.get('high', 0) if ohlc else 0,
                                                'low': ohlc.get('low', 0) if ohlc else 0,
                                                'close': prev_close,
                                                'volume': volume,
                                                'change': change,
                                                'change_percent': change_percent,
                                                'bid': bid,
                                                'ask': ask,
                                                'timestamp': datetime.now().strftime('%H:%M:%S')
                                            }
                                            successful_fetches += 1
                                            
                            except Exception as item_error:
                                continue
                            
                except Exception as e:
                    print(f"⚠️ Error fetching batch for {category}: {e}")
                    continue
                
                # Adjust delay based on batch size to respect rate limits
                if i + batch_size < len(symbols):
                    time.sleep(0.15 if len(contracts) <= 50 else 0.25)
            
            print(f"📊 {category.upper()} - Successfully fetched data for {successful_fetches}/{len(contracts)} contracts")
            return category, live_data
            
        except Exception as e:
            print(f"❌ Error getting {category} quotes: {e}")
            return category, {}
    
    def get_all_live_quotes_parallel(self, categorized_contracts, use_ltp_only=False):
        """Get live quotes for all categories in parallel"""
        all_live_data = {}
        
        # Use ThreadPoolExecutor for parallel processing with fewer workers to avoid rate limits
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Submit tasks for each category
            future_to_category = {
                executor.submit(self.fetch_category_quotes, category, contracts, use_ltp_only): category
                for category, contracts in categorized_contracts.items()
            }
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_category):
                category, live_data = future.result()
                all_live_data.update(live_data)
        
        return all_live_data
    
    def display_live_data(self, categorized_contracts, live_data, refresh_count, refresh_interval):
        """Display live data with better formatting"""
        
        self.clear_screen()
        
        market_status = "🟢 MARKET OPEN" if self.is_market_open() else "🔴 MARKET CLOSED"
        
        print("=" * 140)
        print(f"⚡ KITE FAST FUTURES - LIVE MODE - {datetime.now().strftime('%d-%m-%Y %H:%M:%S')} | {market_status}")
        print(f"🔄 Refresh #{refresh_count} | ⏱️ Auto-refresh every {refresh_interval} seconds | Press Ctrl+C to stop")
        print(f"📊 Live data available for {len(live_data)} contracts")
        print("=" * 140)
        
        total_displayed = 0
    
    def fetch_live_data(self, use_ltp_only=True, limit_contracts=None):
        """Fetch live data for all futures - compatible with specialized futures classes"""
        try:
            categorized_contracts = self.get_all_futures_by_category()
            
            # Apply contract limit if specified
            if limit_contracts:
                for category in categorized_contracts:
                    if len(categorized_contracts[category]) > limit_contracts:
                        categorized_contracts[category] = categorized_contracts[category][:limit_contracts]
            
            live_data = self.get_all_live_quotes_parallel(categorized_contracts, use_ltp_only)
            
            with self.data_lock:
                self.live_data = live_data
            
            # Transform data to match expected format
            transformed_data = {}
            for token, data in live_data.items():
                # Find the contract info for this token
                contract_info = None
                for category in categorized_contracts.values():
                    for contract in category:
                        if contract['instrument_token'] == token:
                            contract_info = contract
                            break
                    if contract_info:
                        break
                
                symbol = data.get('symbol', '')
                if symbol and contract_info:
                    transformed_data[symbol] = {
                        'symbol': symbol,
                        'ltp': data.get('ltp', 0),
                        'open': data.get('open', 0),
                        'high': data.get('high', 0),
                        'low': data.get('low', 0),
                        'close': data.get('close', 0),
                        'volume': data.get('volume', 0),
                        'oi': 0,  # Not available in this version
                        'bid': data.get('bid', 0),
                        'ask': data.get('ask', 0),
                        'contract_info': contract_info,
                        'timestamp': datetime.now().isoformat()
                    }
            
            return transformed_data
            
        except Exception as e:
            print(f"❌ Error fetching live data: {e}")
            import traceback
            traceback.print_exc()
            return {}
        
        for category in ['current', 'near', 'far']:
            contracts = categorized_contracts.get(category, [])
            if not contracts:
                continue
            
            # Display ALL contracts as requested
            category_name = category.upper()
            print(f"\n📅 {category_name} CATEGORY ({len(contracts)} contracts)")
            print("-" * 140)
            print(f"{'Symbol':<22} {'LTP':<10} {'Change':<10} {'Change%':<10} {'Lot':<8} {'Expiry':<12} {'Time':<10}")
            print("-" * 140)
            
            for contract in contracts:
                symbol = contract['symbol'][:20]
                lot_size = contract['lot_size']
                expiry = contract['expiry_formatted']
                
                # Get live data
                token = contract['instrument_token']
                live = live_data.get(token, {})
                
                ltp = live.get('ltp', 0)
                change = live.get('change', 0)
                change_pct = live.get('change_percent', 0)
                timestamp = live.get('timestamp', '')
                
                # Color indicators
                if change_pct > 0:
                    change_str = f"▲ {change:.2f}"
                    pct_str = f"▲ {change_pct:.2f}%"
                elif change_pct < 0:
                    change_str = f"▼ {change:.2f}"
                    pct_str = f"▼ {change_pct:.2f}%"
                else:
                    change_str = f"  {change:.2f}"
                    pct_str = f"  {change_pct:.2f}%"
                
                star = "⭐" if contract['is_popular'] else "  "
                print(f"{star}{symbol:<21} {ltp:<10.2f} {change_str:<10} {pct_str:<10} {lot_size:<8} {expiry:<12} {timestamp:<10}")
                total_displayed += 1
        
        if not self.is_market_open():
            print(f"\n⚠️ Market is currently closed. Data may be from previous trading session.")
        
        print("\n" + "=" * 140)
        print(f"📊 Live contracts tracked: {len(live_data)} | 💡 Press Ctrl+C to stop live updates")
        print("=" * 140)
    
    def start_fast_monitoring(self, refresh_interval=3, max_contracts_per_category=0):
        """Start fast continuous live monitoring with parallel processing - 0 means no limit"""
        print("🚀 Starting Kite Fast Futures LIVE Monitoring")
        print("=" * 70)
        
        # Test connection
        if not self.kite.test_connection():
            print("❌ Failed to connect to Kite API")
            return
        
        # Check market status
        if self.is_market_open():
            print("🟢 Market is currently OPEN")
        else:
            print("🔴 Market is currently CLOSED")
            print("💡 You'll see data from the last trading session")
        
        # Get contracts
        print("\n📥 Loading futures contracts...")
        categorized_contracts = self.get_all_futures_by_category()
        
        total_contracts = sum(len(contracts) for contracts in categorized_contracts.values())
        if total_contracts == 0:
            print("❌ No futures contracts found!")
            return
        
        print(f"✅ Loaded {total_contracts} contracts")
        
        # Limit contracts per category ONLY if user specified a limit (> 0)
        contracts_limited = False
        if max_contracts_per_category > 0:
            for category in categorized_contracts:
                if len(categorized_contracts[category]) > max_contracts_per_category:
                    categorized_contracts[category] = categorized_contracts[category][:max_contracts_per_category]
                    print(f"📋 Limited {category} contracts to {max_contracts_per_category} for performance")
                    contracts_limited = True
        
        if not contracts_limited:
            print("📋 Showing ALL contracts (no limit)")
        
        # Test data access
        print("\n🧪 Testing market data access...")
        test_contracts = []
        # Get a mix of popular contracts for testing
        for category in ['current', 'near']:
            test_contracts.extend(categorized_contracts[category][:3])
        
        if not test_contracts:
            print("❌ No test contracts available")
            return
        
        test_data = self.fetch_category_quotes('test', test_contracts[:5], use_ltp_only=True)  # Use LTP for faster testing
        use_ltp = True
        
        if test_data[1]:
            print(f"✅ Market data access working! Got data for {len(test_data[1])} contracts")
        else:
            print("⚠️ Limited market data access. Will show available data.")
        
        print(f"\n🎯 Monitoring contracts:")
        for category, contracts in categorized_contracts.items():
            print(f"   {category.upper()}: {len(contracts)} contracts")
        
        print(f"⏱️ Refresh interval: {refresh_interval} seconds")
        print("🔄 Starting live updates in 2 seconds...")
        time.sleep(2)
        
        # Start continuous monitoring
        refresh_count = 0
        
        try:
            while True:
                refresh_count += 1
                start_time = time.time()
                
                # Fetch live data in parallel
                live_data = self.get_all_live_quotes_parallel(categorized_contracts, use_ltp_only=use_ltp)
                
                # Calculate fetch time
                fetch_time = time.time() - start_time
                print(f"⏱️ Data fetch completed in {fetch_time:.2f} seconds")
                
                # Display
                self.display_live_data(categorized_contracts, live_data, refresh_count, refresh_interval)
                
                # Wait for next refresh
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print("\n\n⏹️ Live monitoring stopped by user")
            print("👋 Goodbye!")
        except Exception as e:
            print(f"\n❌ Error during live monitoring: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main function"""
    print("🔍 Kite Fast Futures - LIVE CONTINUOUS MODE")
    print("=" * 60)
    
    # Load credentials
    try:
        from kite_config import API_KEY, ACCESS_TOKEN
        
        if not API_KEY or API_KEY == "your_api_key_here":
            print("❌ Please update kite_config.py with your API key")
            return
        
        if not ACCESS_TOKEN:
            print("❌ Please update kite_config.py with your access token")
            return
        
        print(f"✅ API Key: {API_KEY[:10]}...")
        print(f"✅ Access Token: {ACCESS_TOKEN[:20]}...")
        
    except ImportError:
        print("❌ kite_config.py not found")
        return
    
    # Get user preferences
    print("\n⚙️ Configuration:")
    refresh_input = input("Refresh interval in seconds [default: 2]: ").strip()
    refresh_interval = int(refresh_input) if refresh_input.isdigit() else 2
    
    max_input = input("Max contracts per category [default: 0 for all]: ").strip()
    max_contracts = int(max_input) if max_input.isdigit() else 0
    
    # Initialize and start
    fast_monitor = KiteFastFutures(API_KEY, ACCESS_TOKEN)
    
    try:
        fast_monitor.start_fast_monitoring(refresh_interval=refresh_interval, max_contracts_per_category=max_contracts)
    except KeyboardInterrupt:
        print("\n⏹️ Stopped by user")

if __name__ == "__main__":
    main()