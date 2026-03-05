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
    def __init__(self, api_key, access_token, ws_manager=None):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key, access_token=access_token)
        self.ws_manager = ws_manager  # WebSocket manager for real-time data
        
        # Data storage
        self.instruments = []
        self.live_data = {}
        self.data_lock = threading.Lock()
        
        # Rate limiting variables (for fallback HTTP calls only)
        self.last_request_time = 0
        self.min_request_interval = 0.1
        self.request_lock = threading.Lock()
        
        print(f"[INFO] Initialized Live Data API with key: {api_key[:10]}...")
        if ws_manager:
            print("[WS] WebSocket mode enabled - will use real-time tick data")
        
        # Pre-fetch instruments at startup for instant access
        print("[INFO] Pre-loading instruments for instant access...")
        self.get_equity_instruments()
        print(f"[OK] Ready with {len(self.instruments)} instruments")
    
    def get_equity_instruments(self, exchange="NFO"):
        """Get equity instruments that have futures contracts"""
        try:
            if self.instruments:
                print(f"[OK] Using cached {len(self.instruments)} instruments with futures")
                return self.instruments
            
            print(f"[INFO] Fetching instruments with futures from exchange: {exchange}")
            
            # Get futures contracts from NFO
            instruments_data = self.kite.instruments(exchange)
            
            if not instruments_data or 'data' not in instruments_data:
                print("[ERROR] No instruments data available")
                return []
            
            all_instruments = instruments_data['data']
            print(f"[DATA] Processing {len(all_instruments)} instruments...")
            
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
            
            print(f"[DATA] Found {len(underlying_symbols)} unique underlying symbols with futures")
            
            # Now fetch NSE instruments (both equity and indices)
            print("[INFO] Fetching NSE instruments for instrument tokens...")
            nse_instruments_data = self.kite.instruments('NSE')
            
            # Map symbol to instrument token (both EQ and INDEX)
            symbol_to_token = {}
            if nse_instruments_data and 'data' in nse_instruments_data:
                for instrument in nse_instruments_data['data']:
                    try:
                        symbol = instrument.get('tradingsymbol', '').upper()
                        instrument_type = instrument.get('instrument_type', '').upper()
                        instrument_token = instrument.get('instrument_token')
                        
                        # Include equity (EQ) and indices (INDEX)
                        if instrument_type in ['EQ', 'INDEX'] and symbol and instrument_token:
                            symbol_to_token[symbol] = instrument_token
                    except Exception:
                        continue
            
            print(f"[OK] Mapped {len(symbol_to_token)} NSE instrument tokens (EQ + INDEX)")
            
            # Debug: Print index symbols found in NSE
            index_keys = [k for k in symbol_to_token.keys() if any(x in k for x in ['NIFTY', 'BANK', 'FIN', 'SENSEX', 'MID', 'NEXT'])]
            print(f"DEBUG: Index symbols in NSE: {index_keys}")
            
            # Special mapping for indices (NSE symbols differ from NFO underlying)
            # NFO uses: NIFTY, BANKNIFTY, FINNIFTY, MIDCPNIFTY, NIFTYNXT50
            # NSE uses: NIFTY 50, NIFTY BANK, NIFTY FIN SERVICE, NIFTY MID SELECT, NIFTY NEXT 50
            index_symbol_map = {
                'NIFTY': ['NIFTY 50'],
                'BANKNIFTY': ['NIFTY BANK'],
                'FINNIFTY': ['NIFTY FIN SERVICE'],
                'MIDCPNIFTY': ['NIFTY MID SELECT'],
                'NIFTYNXT50': ['NIFTY NEXT 50'],
                'SENSEX': ['SENSEX'],
                'BANKEX': ['BANKEX']
            }
            
            # Build instrument list with metadata (both equity and indices)
            equity_instruments = []
            for symbol in underlying_symbols.keys():
                is_popular = any(pop_symbol in symbol for pop_symbol in popular_symbols)
                
                # For indices, try multiple symbol variations
                instrument_token = symbol_to_token.get(symbol)
                if not instrument_token and symbol in index_symbol_map:
                    for possible_symbol in index_symbol_map[symbol]:
                        instrument_token = symbol_to_token.get(possible_symbol)
                        if instrument_token:
                            break
                
                # Determine instrument type
                inst_type = 'EQ'
                if symbol in ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY', 'NIFTYNXT50', 'SENSEX', 'BANKEX']:
                    inst_type = 'INDEX'
                
                equity_instruments.append({
                    'symbol': symbol,
                    'name': symbol,
                    'exchange': 'NSE',
                    'instrument_type': inst_type,
                    'instrument_token': instrument_token,
                    'is_popular': is_popular
                })
            
            # Sort by popularity first, then by symbol
            equity_instruments.sort(key=lambda x: (not x['is_popular'], x['symbol']))
            
            print(f"[OK] Ready with {len(equity_instruments)} instruments (stocks with futures)")
            self.instruments = equity_instruments
            return equity_instruments
            
        except Exception as e:
            print(f"[ERROR] Error fetching instruments: {e}")
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
            print("[WARN] WebSocket manager not available - use HTTP fallback")
            return self.fetch_live_data_http()
        
        try:
            instruments = self.get_equity_instruments()
            if not instruments:
                return {}
            
            # Get all tick data from WebSocket
            all_ticks = self.ws_manager.get_tick_data()
            
            live_data = {}
            for instrument in instruments:
                token = instrument.get('instrument_token')
                if not token:
                    continue
                    
                tick = all_ticks.get(int(token))
                
                if tick:
                    symbol = instrument['symbol']
                    ltp = tick.get('last_price', 0)
                    ohlc = tick.get('ohlc', {})
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
                        'volume': tick.get('volume_traded', 0),
                        'bid': tick.get('depth', {}).get('buy', [{}])[0].get('price', 0) if tick.get('depth') else 0,
                        'ask': tick.get('depth', {}).get('sell', [{}])[0].get('price', 0) if tick.get('depth') else 0,
                        'instrument_info': instrument,
                        'timestamp': tick.get('updated_at', datetime.now().isoformat())
                    }
            
            with self.data_lock:
                self.live_data = live_data
            
            return live_data
            
        except Exception as e:
            print(f"[ERROR] Error getting WebSocket data: {e}")
            return {}
    
    def fetch_live_data_http(self, use_ltp_only=True, limit_symbols=None):
        """Fetch live spot prices for all equity instruments via HTTP"""
        try:
            instruments = self.get_equity_instruments()
            
            if limit_symbols and len(instruments) > limit_symbols:
                instruments = instruments[:limit_symbols]
            
            if not instruments:
                print("[ERROR] No instruments available")
                return {}
            
            print(f"[INFO] Fetching live data for {len(instruments)} equity instruments via HTTP...")
            
            symbols = []
            symbol_to_instrument = {}
            
            for instrument in instruments:
                symbol_key = f"{instrument['exchange']}:{instrument['symbol']}"
                symbols.append(symbol_key)
                symbol_to_instrument[instrument['symbol']] = instrument
            
            # Debug: print first few symbols
            if symbols:
                print(f"[INFO] Sample symbols: {symbols[:5]}")
            
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
                                        'bid': 0,
                                        'ask': 0,
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
                                        'bid': data.get('depth', {}).get('buy', [{}])[0].get('price', 0) if data.get('depth') else 0,
                                        'ask': data.get('depth', {}).get('sell', [{}])[0].get('price', 0) if data.get('depth') else 0,
                                        'instrument_info': instrument,
                                        'timestamp': datetime.now().isoformat()
                                    }
                
                except Exception as e:
                    print(f"[WARN] Error fetching batch {i//batch_size + 1}: {e}")
                    continue
            
            with self.data_lock:
                self.live_data = live_data
            
            print(f"[OK] Successfully fetched data for {len(live_data)} equity instruments")
            return live_data
            
        except Exception as e:
            print(f"[ERROR] Error fetching live data: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def fetch_live_data(self, use_ltp_only=True, limit_symbols=None):
        """Fetch live data - uses WebSocket if available, otherwise HTTP"""
        if self.ws_manager:
            return self.fetch_live_data_from_websocket()
        else:
            return self.fetch_live_data_http(use_ltp_only, limit_symbols)
    
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
            print("[ERROR] Please set KITE_API_KEY and KITE_ACCESS_TOKEN")
            return
        
        live_data = KiteLiveData(api_key, access_token)
        data = live_data.fetch_live_data(use_ltp_only=False)
        
        print("\n" + "="*100)
        print("LIVE MARKET DATA")
        print("="*100)
        print(f"{'Symbol':<15} {'LTP':<10} {'Bid':<10} {'Ask':<10} {'Change':<10} {'Change%':<10} {'Volume':<12}")
        print("-"*100)
        
        for symbol, info in list(data.items())[:20]:
            change = info.get('change', 0)
            change_pct = info.get('change_pct', 0)
            color = "OPEN" if change > 0 else "CLOSED" if change < 0 else "-"
            
            print(f"{symbol:<15} {info.get('ltp', 0):<10.2f} {info.get('bid', 0):<10.2f} {info.get('ask', 0):<10.2f} {color} {change:<8.2f} {change_pct:<9.2f}% {info.get('volume', 0):<12}")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
