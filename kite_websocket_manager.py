#!/usr/bin/env python3
"""
Kite WebSocket Manager
Handles real-time market data streaming via WebSocket
"""

from kiteconnect import KiteTicker
import threading
import time
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KiteWebSocketManager:
    """Manages WebSocket connection for real-time tick data"""
    
    def __init__(self, api_key, access_token):
        self.api_key = api_key
        self.access_token = access_token
        self.kws = None
        
        # Data cache - thread-safe
        self.tick_data = {}
        self.data_lock = threading.Lock()
        
        # Connection state
        self.is_connected = False
        self.subscribed_tokens = set()
        
        logger.info(f"🔑 Initialized WebSocket Manager with key: {api_key[:10]}...")
    
    def start(self):
        """Start WebSocket connection"""
        try:
            # Initialize KiteTicker
            self.kws = KiteTicker(self.api_key, self.access_token)
            
            # Set callbacks
            self.kws.on_ticks = self.on_ticks
            self.kws.on_connect = self.on_connect
            self.kws.on_close = self.on_close
            self.kws.on_error = self.on_error
            self.kws.on_reconnect = self.on_reconnect
            self.kws.on_noreconnect = self.on_noreconnect
            
            # Start connection in separate thread
            ws_thread = threading.Thread(target=self.kws.connect, daemon=True)
            ws_thread.start()
            
            logger.info("🚀 WebSocket connection initiated...")
            
        except Exception as e:
            logger.error(f"❌ Error starting WebSocket: {e}")
            raise
    
    def on_connect(self, ws, response):
        """Callback when WebSocket connects"""
        self.is_connected = True
        logger.info("✅ WebSocket connected successfully")
        
        # Subscribe to tokens if any are pending
        if self.subscribed_tokens:
            tokens = list(self.subscribed_tokens)
            logger.info(f"📡 Subscribing to {len(tokens)} instruments...")
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_QUOTE, tokens)  # Use QUOTE mode for OHLC, volume, etc.
    
    def on_ticks(self, ws, ticks):
        """Callback when ticks are received"""
        with self.data_lock:
            for tick in ticks:
                instrument_token = tick.get('instrument_token')
                if instrument_token:
                    # Store complete tick data
                    self.tick_data[instrument_token] = {
                        'instrument_token': instrument_token,
                        'tradeable': tick.get('tradeable', True),
                        'mode': tick.get('mode', 'quote'),
                        'last_price': tick.get('last_price', 0),
                        'last_traded_quantity': tick.get('last_traded_quantity', 0),
                        'average_traded_price': tick.get('average_traded_price', 0),
                        'volume_traded': tick.get('volume_traded', 0),
                        'total_buy_quantity': tick.get('total_buy_quantity', 0),
                        'total_sell_quantity': tick.get('total_sell_quantity', 0),
                        'ohlc': tick.get('ohlc', {}),
                        'change': tick.get('change', 0),
                        'last_trade_time': tick.get('last_trade_time'),
                        'timestamp': tick.get('timestamp'),
                        'oi': tick.get('oi', 0),
                        'oi_day_high': tick.get('oi_day_high', 0),
                        'oi_day_low': tick.get('oi_day_low', 0),
                        'depth': tick.get('depth', {}),
                        'updated_at': datetime.now().isoformat()
                    }
        
        # Log every 100 ticks to avoid spam
        if len(ticks) > 0 and len(self.tick_data) % 100 == 0:
            logger.info(f"📊 Received ticks, total instruments: {len(self.tick_data)}")
    
    def on_close(self, ws, code, reason):
        """Callback when WebSocket closes"""
        self.is_connected = False
        logger.warning(f"⚠️ WebSocket closed: {code} - {reason}")
    
    def on_error(self, ws, code, reason):
        """Callback on WebSocket error"""
        logger.error(f"❌ WebSocket error: {code} - {reason}")
    
    def on_reconnect(self, ws, attempts_count):
        """Callback on reconnection attempt"""
        logger.info(f"🔄 Reconnecting... (Attempt {attempts_count})")
    
    def on_noreconnect(self, ws):
        """Callback when max reconnection attempts reached"""
        self.is_connected = False
        logger.error("❌ Max reconnection attempts reached. WebSocket stopped.")
    
    def subscribe(self, instrument_tokens):
        """Subscribe to instruments"""
        if not isinstance(instrument_tokens, list):
            instrument_tokens = [instrument_tokens]
        
        # Add to subscribed set
        for token in instrument_tokens:
            self.subscribed_tokens.add(int(token))
        
        # If connected, subscribe immediately
        if self.is_connected and self.kws:
            logger.info(f"📡 Subscribing to {len(instrument_tokens)} new instruments...")
            self.kws.subscribe(instrument_tokens)
            self.kws.set_mode(self.kws.MODE_QUOTE, instrument_tokens)
        else:
            logger.info(f"📝 Queued {len(instrument_tokens)} instruments for subscription")
    
    def unsubscribe(self, instrument_tokens):
        """Unsubscribe from instruments"""
        if not isinstance(instrument_tokens, list):
            instrument_tokens = [instrument_tokens]
        
        # Remove from subscribed set
        for token in instrument_tokens:
            self.subscribed_tokens.discard(int(token))
        
        # If connected, unsubscribe immediately
        if self.is_connected and self.kws:
            self.kws.unsubscribe(instrument_tokens)
    
    def get_tick_data(self, instrument_token=None):
        """Get tick data for specific token or all tokens"""
        with self.data_lock:
            if instrument_token:
                return self.tick_data.get(instrument_token, None)
            return dict(self.tick_data)
    
    def stop(self):
        """Stop WebSocket connection"""
        if self.kws:
            logger.info("🛑 Stopping WebSocket connection...")
            self.kws.close()
            self.is_connected = False

def main():
    """Test WebSocket manager"""
    import os
    
    try:
        # Load credentials
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
        
        # Create WebSocket manager
        ws_manager = KiteWebSocketManager(api_key, access_token)
        ws_manager.start()
        
        # Wait for connection
        time.sleep(3)
        
        # Subscribe to some instruments (example tokens)
        # These are sample tokens - replace with actual instrument tokens
        sample_tokens = [738561, 779521, 492033]  # NIFTY, BANKNIFTY, RELIANCE (example)
        ws_manager.subscribe(sample_tokens)
        
        print("✅ WebSocket running. Receiving ticks...")
        print("Press Ctrl+C to stop\n")
        
        # Monitor ticks
        while True:
            time.sleep(5)
            tick_data = ws_manager.get_tick_data()
            print(f"\n📊 Receiving data for {len(tick_data)} instruments")
            
            # Show sample data
            for token, data in list(tick_data.items())[:3]:
                print(f"Token {token}: LTP={data.get('last_price')}, Vol={data.get('volume_traded')}")
    
    except KeyboardInterrupt:
        print("\n👋 Stopping WebSocket...")
        ws_manager.stop()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
