#!/usr/bin/env python3
"""
Kite Live Data Fetcher
Fetches real-time spot prices for all equity instruments
"""

from KiteApi.kiteConnect import KiteConnect
import json
from datetime import datetime
import time
import os
import threading

class KiteLiveData:
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key, access_token=access_token)
        
        # Data storage
        self.instruments = []
        self.live_data = {}
        self.data_lock = threading.Lock()
        
        # Rate limiting variables
        self.last_request_time = 0
        self.min_request_interval = 0.1
        self.request_lock = threading.Lock()
        
        print(f"🔑 Initialized Live Data API with key: {api_key[:10]}...")
        
        # Pre-fetch instruments at startup for instant access
        print("🚀 Pre-loading instruments for instant access...")
        self.get_equity_instruments()
        print(f"✅ Ready with {len(self.instruments)} instruments")
    
    def get_equity_instruments(self, exchange="NFO"):
        """Get equity instruments that have futures contracts"""
        try:
            if self.instruments:
                print(f"✅ Using cached {len(self.instruments)} instruments with futures")
                return self.instruments
            
            print(f"🔍 Fetching instruments with futures from exchange: {exchange}")
            
            # Get futures contracts from NFO
            instruments_data = self.kite.instruments(exchange)
            
            if not instruments_data or 'data' not in instruments_data:
                print("❌ No instruments data available")
                return []
            
            all_instruments = instruments_data['data']
            print(f"📊 Processing {len(all_instruments)} instruments...")
            
            # Popular symbols for prioritization
            popular_symbols = [
                'NIFTY', 'BANKNIFTY', 'SENSEX', 'FINNIFTY', 'MIDCPNIFTY',
                'RELIANCE', 'TCS', 'INFY', 'HDFC', 'HDFCBANK', 'ICICIBANK', 'SBIN',
                'LT', 'HCLTECH', 'WIPRO', 'ITC', 'BHARTIARTL', 'HINDUNILVR',
                'AXISBANK', 'KOTAKBANK', 'ASIANPAINT', 'MARUTI', 'TITAN'
            ]
            
            # Get unique underlying symbols from futures contracts
            underlying_symbols = {}
            for instrument in all_instruments:
                try:
                    instrument_type = instrument.get('instrument_type', '').upper()
                    name = instrument.get('name', '').upper().replace('"', '').strip()
                    
                    # Only futures contracts - store name as key
                    if instrument_type == 'FUT' and name:
                        underlying_symbols[name] = name
                        
                except Exception:
                    continue
            
            print(f"📊 Found {len(underlying_symbols)} unique underlying symbols with futures")
            
            # Build instrument list with metadata
            equity_instruments = []
            for symbol in underlying_symbols.keys():
                is_popular = any(pop_symbol in symbol for pop_symbol in popular_symbols)
                
                equity_instruments.append({
                    'symbol': symbol,
                    'name': symbol,
                    'exchange': 'NSE',  # Spot prices are on NSE
                    'instrument_type': 'EQ',
                    'is_popular': is_popular
                })
            
            # Sort by popularity first, then by symbol
            equity_instruments.sort(key=lambda x: (not x['is_popular'], x['symbol']))
            
            print(f"✅ Ready with {len(equity_instruments)} instruments (stocks with futures)")
            self.instruments = equity_instruments
            return equity_instruments
            
        except Exception as e:
            print(f"❌ Error fetching instruments: {e}")
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
    
    def fetch_live_data(self, use_ltp_only=True, limit_symbols=None):
        """Fetch live spot prices for all equity instruments"""
        try:
            instruments = self.get_equity_instruments()
            
            if limit_symbols and len(instruments) > limit_symbols:
                instruments = instruments[:limit_symbols]
            
            if not instruments:
                print("❌ No instruments available")
                return {}
            
            print(f"📈 Fetching live data for {len(instruments)} equity instruments...")
            
            symbols = []
            symbol_to_instrument = {}
            
            for instrument in instruments:
                symbol_key = f"{instrument['exchange']}:{instrument['symbol']}"
                symbols.append(symbol_key)
                symbol_to_instrument[instrument['symbol']] = instrument
            
            # Debug: print first few symbols
            if symbols:
                print(f"🔍 Sample symbols: {symbols[:5]}")
            
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
                            instrument = symbol_to_instrument.get(symbol)
                            
                            if instrument:
                                if use_ltp_only:
                                    live_data[symbol] = {
                                        'symbol': symbol,
                                        'ltp': data.get('last_price', 0),
                                        'instrument_info': instrument,
                                        'timestamp': datetime.now().isoformat()
                                    }
                                else:
                                    ltp = data.get('last_price', 0)
                                    ohlc = data.get('ohlc', {})
                                    close = ohlc.get('close', 0)
                                    change = ltp - close if close else 0
                                    change_pct = (change / close * 100) if close else 0
                                    
                                    live_data[symbol] = {
                                        'symbol': symbol,
                                        'ltp': ltp,
                                        'open': ohlc.get('open', 0),
                                        'high': ohlc.get('high', 0),
                                        'low': ohlc.get('low', 0),
                                        'close': close,
                                        'change': change,
                                        'change_pct': change_pct,
                                        'volume': data.get('volume', 0),
                                        'instrument_info': instrument,
                                        'timestamp': datetime.now().isoformat()
                                    }
                
                except Exception as e:
                    print(f"⚠️ Error fetching batch {i//batch_size + 1}: {e}")
                    continue
            
            with self.data_lock:
                self.live_data = live_data
            
            print(f"✅ Successfully fetched data for {len(live_data)} equity instruments")
            return live_data
            
        except Exception as e:
            print(f"❌ Error fetching live data: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def get_data_as_json(self):
        """Get live data as JSON"""
        return json.dumps(self.live_data, indent=2)

def main():
    """Test live data fetcher"""
    try:
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
            print("❌ Please set KITE_API_KEY and KITE_ACCESS_TOKEN")
            return
        
        live_data = KiteLiveData(api_key, access_token)
        data = live_data.fetch_live_data(use_ltp_only=False)
        
        print("\n" + "="*80)
        print("LIVE MARKET DATA")
        print("="*80)
        print(f"{'Symbol':<15} {'LTP':<10} {'Change':<10} {'Change%':<10} {'Volume':<12}")
        print("-"*80)
        
        for symbol, info in list(data.items())[:20]:
            change = info.get('change', 0)
            change_pct = info.get('change_pct', 0)
            color = "🟢" if change > 0 else "🔴" if change < 0 else "⚪"
            
            print(f"{symbol:<15} {info.get('ltp', 0):<10.2f} {color} {change:<8.2f} {change_pct:<9.2f}% {info.get('volume', 0):<12}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
