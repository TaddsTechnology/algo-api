#!/usr/bin/env python3
"""
Optimized Streaming API for Real-Time Market Data
Uses Server-Sent Events (SSE) for continuous data streaming
"""

import os
import sys

def _validate_token_via_api(api_key, access_token):
    """Validate access token by calling Kite profile API"""
    try:
        import requests
        headers = {
            'Authorization': f'token {api_key}:{access_token}',
            'Content-Type': 'application/json'
        }
        response = requests.get(
            'https://api.kite.trade/user/profile',
            headers=headers,
            timeout=10
        )
        return response.status_code == 200
    except Exception:
        return False


def _try_auto_refresh_token():
    """Attempt to auto-generate a new access token via HTTP login (no Selenium)"""
    try:
        project_root = os.path.dirname(os.path.abspath(__file__))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        from refresh_token import refresh_access_token
        new_token = refresh_access_token()
        if new_token:
            os.environ['KITE_ACCESS_TOKEN'] = new_token
            print("[OK] Auto token refresh successful (HTTP-based)")
            return new_token
        else:
            print("[ERROR] HTTP-based token refresh returned no token")
    except Exception as e:
        print(f"[ERROR] Auto token refresh failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Fallback: try old Selenium-based manager
    try:
        kiteapi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'KiteApi')
        if kiteapi_path not in sys.path:
            sys.path.insert(0, kiteapi_path)
        
        from auto_token_manager import setup_lightweight_kite_manager
        manager = setup_lightweight_kite_manager()
        if manager:
            token = manager.get_valid_token()
            if token:
                os.environ['KITE_ACCESS_TOKEN'] = token
                print("[OK] Auto token refresh successful (Selenium fallback)")
                return token
    except Exception as e2:
        print(f"[ERROR] Selenium fallback also failed: {e2}")
    
    return None


def initialize_kite_credentials():
    """Initialize and validate Kite credentials, auto-refresh if expired"""
    api_key = os.environ.get('KITE_API_KEY', '')
    access_token = os.environ.get('KITE_ACCESS_TOKEN', '')
    
    # Case 1: Token is missing entirely
    if not access_token:
        print("[WARNING] KITE_ACCESS_TOKEN missing, triggering auto-generation...")
        new_token = _try_auto_refresh_token()
        return bool(new_token)
    
    # Case 2: Token exists - validate it
    if api_key and access_token:
        print("[INFO] Validating existing access token...")
        if _validate_token_via_api(api_key, access_token):
            print("[OK] Access token is valid")
            return True
        else:
            print("[WARNING] Access token is EXPIRED or INVALID, attempting auto-refresh...")
            new_token = _try_auto_refresh_token()
            return bool(new_token)
    
    return False

# Try to initialize credentials before importing other modules
credentials_initialized = initialize_kite_credentials()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import asyncio
import json
import time
import requests
from datetime import datetime

# Import our specialized futures fetchers
from kite_current_futures import KiteCurrentFutures
from kite_near_futures import KiteNearFutures
from kite_far_futures import KiteFarFutures
from kite_futures_aggregator import FuturesAggregator
from kite_live_data import KiteLiveData
from kite_websocket_manager import KiteWebSocketManager

app = FastAPI(
    title="Real-Time Futures Streaming API",
    description="Dynamic rank-based futures API for arbitrage trading",
    version="4.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global cache for market data
class MarketDataCache:
    def __init__(self):
        self.current_data = {}  # Live market data (spot prices)
        self.near_data = {}     # Current month futures (0-35 days)
        self.next_data = {}     # Next month futures (36-70 days)
        self.far_data = {}      # Far month futures (71-105 days)
        self.last_update = time.time()
        
    def update(self, category, data):
        if category == "current":
            self.current_data = data
        elif category == "near":
            self.near_data = data
        elif category == "next":
            self.next_data = data
        elif category == "far":
            self.far_data = data
        self.last_update = time.time()
    
    def get_all(self):
        return {
            "current": self.current_data,
            "near": self.near_data,
            "next": self.next_data,
            "far": self.far_data,
            "timestamp": self.last_update
        }

cache = MarketDataCache()

# Initialize API fetchers
def get_api_credentials():
    api_key = os.getenv('KITE_API_KEY')
    access_token = os.getenv('KITE_ACCESS_TOKEN')
    
    print(f"[CREDENTIALS] KITE_API_KEY: {'SET' if api_key else 'NOT SET'}")
    print(f"[CREDENTIALS] KITE_ACCESS_TOKEN: {'SET' if access_token else 'NOT SET'}")
    
    if not api_key or not access_token:
        # Try config file
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", "kite_config_hf.py")
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
            api_key = config.API_KEY
            access_token = config.ACCESS_TOKEN
            print(f"[CREDENTIALS] Loaded from kite_config_hf.py: API_KEY={api_key[:8] if api_key else 'NONE'}...")
        except Exception as e:
            print(f"[CREDENTIALS] Error loading kite_config_hf.py: {e}")
            # Try kite_config.py as fallback
            try:
                import kite_config
                api_key = kite_config.API_KEY
                access_token = kite_config.ACCESS_TOKEN
                print(f"[CREDENTIALS] Loaded from kite_config.py: API_KEY={api_key[:8] if api_key else 'NONE'}...")
            except Exception as e2:
                print(f"[CREDENTIALS] Error loading kite_config.py: {e2}")
    
    return api_key, access_token

# Initialize fetchers with error handling
# Note: "near_futures" now fetches current month (0-35 days)
# "next_futures" now fetches next month (36-70 days)
live_data_fetcher = None  # Live spot prices
near_futures = None       # Current month futures (was "current")
next_futures = None       # Next month futures (was "near")
far_futures = None        # Far month futures
futures_aggregator = None  # NEW: Dynamic rank-based futures aggregator
ws_manager = None         # WebSocket manager for real-time data

# Instrument token mappings
token_to_contract = {}    # Maps instrument_token -> contract info
token_to_symbol = {}      # Maps instrument_token -> symbol

try:
    api_key, access_token = get_api_credentials()
    if api_key and access_token:
        # Check if WebSocket should be disabled
        # Disable on HuggingFace Spaces as outbound WS may be blocked
        enable_ws = os.getenv('ENABLE_WEBSOCKET', 'true').lower() == 'true'
        
        # HuggingFace Spaces: Try WebSocket first, fall back to HTTP if needed
        if os.getenv('SPACE_ID') or os.getenv('HF_SPACE'):
            enable_ws = True  # Try WebSocket first
            print("INFO: HuggingFace detected - trying WebSocket, will use HTTP fallback if needed")
        
        # Force WebSocket ON for Render.com (allows outbound WebSocket)
        if os.getenv('RENDER'):
            enable_ws = True
            print("INFO: Running on Render.com - WebSocket enabled")
        
        # Initialize WebSocket manager
        ws_manager = KiteWebSocketManager(api_key, access_token, enable_websocket=enable_ws)
        
        if not enable_ws:
            print("WARNING: WebSocket disabled via ENABLE_WEBSOCKET=false")
        
        # Initialize contract fetchers WITH WebSocket manager for real-time data
        live_data_fetcher = KiteLiveData(api_key, access_token, ws_manager)      # Live spot data
        
        # Initialize NEW aggregator for dynamic rank-based futures (near/next/far)
        futures_aggregator = FuturesAggregator(api_key, access_token)
        
        # Also keep old fetchers for backward compatibility
        near_futures = KiteCurrentFutures(api_key, access_token, ws_manager)     # 0-35 days
        next_futures = KiteNearFutures(api_key, access_token, ws_manager)        # 36-70 days
        far_futures = KiteFarFutures(api_key, access_token, ws_manager)          # 71-105 days
        
        print("OK: API fetchers initialized successfully")
        print("OK: Futures Aggregator (dynamic rank-based) enabled")
        print("OK: WebSocket mode enabled for real-time data")
    else:
        print("WARNING: Missing API credentials - will return empty data")
except Exception as e:
    print(f"ERROR: Error initializing fetchers: {e}")
    print("WARNING: API will start but data fetching may fail")

# Background task to setup WebSocket subscriptions
async def setup_websocket_subscriptions():
    """Setup WebSocket subscriptions for all instruments"""
    global token_to_contract, token_to_symbol
    
    # Check if fetchers are initialized
    if not ws_manager or not live_data_fetcher:
        print("ERROR: Fetchers not initialized - skipping WebSocket setup")
        return
    
    try:
        print("[SETUP] Fetching all instrument metadata...")
        
        # Get live instruments
        live_instruments = await asyncio.to_thread(live_data_fetcher.get_equity_instruments)
        
        # Get futures from aggregator (dynamic rank-based)
        if futures_aggregator:
            agg_result = await asyncio.to_thread(futures_aggregator.fetch_all_futures_contracts)
            near_contracts = agg_result.get('near', [])
            next_contracts = agg_result.get('next', [])
            far_contracts = agg_result.get('far', [])
            print(f"[SETUP] Aggregator - Near: {len(near_contracts)}, Next: {len(next_contracts)}, Far: {len(far_contracts)}")
        else:
            # Fallback to old fetchers
            near_contracts = await asyncio.to_thread(near_futures.get_current_futures_contracts)
            next_contracts = await asyncio.to_thread(next_futures.get_near_futures_contracts)
            far_contracts = await asyncio.to_thread(far_futures.get_far_futures_contracts)
        
        # Collect all instrument tokens to subscribe
        all_tokens = []
        
        # Live data instruments
        for instrument in live_instruments:
            token = instrument.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = instrument.get('symbol')
                token_to_contract[int(token)] = {'category': 'current', 'data': instrument}
        
        # Near futures
        for contract in near_contracts:
            token = contract.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = contract.get('symbol')
                token_to_contract[int(token)] = {'category': 'near', 'data': contract}
        
        # Next futures
        for contract in next_contracts:
            token = contract.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = contract.get('symbol')
                token_to_contract[int(token)] = {'category': 'next', 'data': contract}
        
        # Far futures
        for contract in far_contracts:
            token = contract.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = contract.get('symbol')
                token_to_contract[int(token)] = {'category': 'far', 'data': contract}
        
        print(f"[SETUP] Collected {len(all_tokens)} instrument tokens")
        print(f"   - Live: {len(live_instruments)}")
        print(f"   - Near: {len(near_contracts)}")
        print(f"   - Next: {len(next_contracts)}")
        print(f"   - Far: {len(far_contracts)}")
        
        # Start WebSocket
        ws_manager.start()

        # Log warning if on HF and WebSocket failed
        if (os.getenv('SPACE_ID') or os.getenv('HF_SPACE')) and ws_manager and not ws_manager.is_connected:
            print("[WARNING] WebSocket failed on HF Space - Kite likely blocking HF IP range - using HTTP fallback (15s polling)")
            print("[TIP] For real-time data, use Render.com or a VPS with dedicated IP")

        
        # Wait for WebSocket to actually connect (with timeout)
        print("[WS] Waiting for WebSocket connection...")
        for _ in range(30):  # Wait up to 30 seconds
            await asyncio.sleep(1)
            if ws_manager.is_connected:
                print("[OK] WebSocket connected")
                break
        
        if not ws_manager.is_connected:
            print("[ERROR] WebSocket failed to connect")
            return
        
        # Subscribe to all tokens in batches
        print(f"[WS] Subscribing to {len(all_tokens)} instruments via WebSocket (batched)...")
        ws_manager.subscribe_batched(all_tokens)
        
        print("[OK] WebSocket subscriptions active - receiving real-time ticks")
        
    except Exception as e:
        print(f"[ERROR] Error setting up WebSocket: {e}")
        import traceback
        traceback.print_exc()

# Background task to update cache from WebSocket data
async def update_cache_from_websocket():
    """Continuously update cache from WebSocket tick data"""
    if not ws_manager:
        return
    
    while True:
        try:
            # Get all tick data from WebSocket
            tick_data = ws_manager.get_tick_data()
            
            # Organize by category
            current_data = {}
            near_data = {}
            next_data = {}
            far_data = {}
            
            for token, tick in tick_data.items():
                contract_info = token_to_contract.get(token)
                if not contract_info:
                    continue
                
                category = contract_info['category']
                symbol = token_to_symbol.get(token, f"TOKEN_{token}")
                
                # Format tick data
                futures_bid = tick.get('depth', {}).get('buy', [{}])[0].get('price', 0) if tick.get('depth') else 0
                futures_ask = tick.get('depth', {}).get('sell', [{}])[0].get('price', 0) if tick.get('depth') else 0
                
                # Calculate profit %: (futures_bid - spot_ask) / spot_ask * 100
                # Only for futures (near/next/far), not for live-data
                profit = None
                if category != 'current' and contract_info and 'data' in contract_info:
                    underlying_name = contract_info['data'].get('name', '')
                    if underlying_name:
                        # Remove quotes from name
                        underlying_name = underlying_name.replace('"', '').strip()
                        # Look up spot data
                        spot_data = cache.current_data.get(underlying_name)
                        if spot_data:
                            spot_ask = spot_data.get('ask', 0)
                            if spot_ask and futures_bid:
                                # Profit % = (futures_bid - spot_ask) / spot_ask * 100
                                profit = round(((futures_bid - spot_ask) / spot_ask) * 100, 2)
                
                # Build tick data - profit only for futures (near/next/far)
                formatted_tick = {
                    'symbol': symbol,
                    'ltp': tick.get('last_price', 0),
                    'volume': tick.get('volume_traded', 0),
                    'change': tick.get('change', 0),
                    'ohlc': tick.get('ohlc', {}),
                    'bid': futures_bid,
                    'ask': futures_ask,
                    'timestamp': tick.get('updated_at'),
                    'contract_info': contract_info['data']
                }
                
                # Add profit only for futures (near/next/far), not for live-data
                if category != 'current':
                    formatted_tick['profit'] = profit
                
                # Assign to category
                if category == 'current':
                    current_data[symbol] = formatted_tick
                elif category == 'near':
                    near_data[symbol] = formatted_tick
                elif category == 'next':
                    next_data[symbol] = formatted_tick
                elif category == 'far':
                    far_data[symbol] = formatted_tick
            
            # Update cache
            cache.update("current", current_data)
            cache.update("near", near_data)
            cache.update("next", next_data)
            cache.update("far", far_data)
            
            if len(tick_data) > 0:
                print(f"[STATS] Updated cache at {datetime.now().strftime('%H:%M:%S')} - Live: {len(current_data)}, Near: {len(near_data)}, Next: {len(next_data)}, Far: {len(far_data)}")
            
            await asyncio.sleep(0.1)  # Update cache every 100ms for algo trading
            
        except Exception as e:
            print(f"[WARN] Error updating cache: {e}")
            await asyncio.sleep(1)

# Background task to update equity bid/ask via HTTP
async def update_equity_depth_http():
    """Periodically fetch equity bid/ask via HTTP (WebSocket doesn't provide depth for equity)"""
    if not live_data_fetcher:
        return
    
    await asyncio.sleep(5)  # Wait for initial WebSocket data
    
    while True:
        try:
            # Fetch equity data with depth via HTTP
            print("[SEARCH] Fetching equity bid/ask via HTTP...")
            equity_data = await asyncio.to_thread(
                live_data_fetcher.fetch_live_data_http, 
                use_ltp_only=False,  # Get full quote with depth
                limit_symbols=None
            )
            
            if equity_data:
                # Update only bid/ask in cache while keeping WebSocket LTP/volume
                for symbol, data in equity_data.items():
                    if symbol in cache.current_data:
                        # Merge: keep WebSocket LTP but use HTTP bid/ask
                        cache.current_data[symbol]['bid'] = data.get('bid', 0)
                        cache.current_data[symbol]['ask'] = data.get('ask', 0)
                    else:
                        # New entry from HTTP
                        cache.current_data[symbol] = data
                
                print(f"[OK] Updated bid/ask for {len(equity_data)} equity instruments")
            
            await asyncio.sleep(10)  # Update depth every 10 seconds
            
        except Exception as e:
            print(f"[WARN] Error updating equity depth: {e}")
            await asyncio.sleep(10)

# HTTP Fallback - fetches data via HTTP if WebSocket fails
async def http_fallback_fetcher():
    """Fallback HTTP fetcher when WebSocket is not connected"""
    await asyncio.sleep(10)  # Wait for initial WebSocket attempt
    
    http_fetch_count = 0
    while True:
        try:
            # Check if WebSocket is connected
            ws_connected = ws_manager and ws_manager.is_connected and len(ws_manager.get_tick_data()) > 0
            
            if not ws_connected:
                http_fetch_count += 1
                print(f"[INFO] HTTP Fallback fetch #{http_fetch_count} (WebSocket not connected)...")
                
                # Fetch live data via HTTP
                if live_data_fetcher:
                    live_data = await asyncio.to_thread(live_data_fetcher.fetch_live_data_http, use_ltp_only=False)
                    if live_data:
                        for symbol, data in live_data.items():
                            cache.current_data[symbol] = data
                        print(f"[OK] HTTP fallback updated {len(live_data)} instruments")
                
                # Fetch futures via HTTP
                if futures_aggregator:
                    agg_result = await asyncio.to_thread(futures_aggregator.fetch_all_futures_contracts)
                    for category, contracts in [('near', agg_result.get('near', [])), 
                                                 ('next', agg_result.get('next', [])), 
                                                 ('far', agg_result.get('far', []))]:
                        category_data = {}
                        for contract in contracts:
                            symbol = contract.get('symbol', '')
                            category_data[symbol] = {
                                'symbol': symbol,
                                'ltp': contract.get('last_price', 0),
                                'volume': contract.get('volume_traded', 0),
                                'change': contract.get('change', 0),
                                'ohlc': contract.get('ohlc', {}),
                                'bid': contract.get('bid', 0),
                                'ask': contract.get('ask', 0),
                                'timestamp': contract.get('timestamp'),
                                'contract_info': contract
                            }
                        cache.update(category, category_data)
                        print(f"[OK] HTTP fallback updated {len(category_data)} {category} contracts")
                
                print(f"[STATS] Cache status: Live={len(cache.current_data)}, Near={len(cache.near_data)}, Next={len(cache.next_data)}, Far={len(cache.far_data)}")
            
            await asyncio.sleep(15)  # Check every 15 seconds
            
        except Exception as e:
            print(f"[WARN] Error in HTTP fallback: {e}")
            await asyncio.sleep(15)


# Token refresh and WebSocket reconnection task
async def token_refresh_and_reconnect():
    """Background task to validate token periodically and reconnect WebSocket if needed"""
    await asyncio.sleep(60)  # Wait 1 minute before first check
    
    refresh_interval = int(os.getenv('TOKEN_REFRESH_INTERVAL', '3600'))  # Default: 1 hour
    print(f"[TOKEN] Token refresh scheduler started (interval: {refresh_interval}s)")
    
    while True:
        try:
            api_key = os.getenv('KITE_API_KEY', '')
            access_token = os.getenv('KITE_ACCESS_TOKEN', '')
            
            if not api_key or not access_token:
                print("[TOKEN] No credentials to validate")
                await asyncio.sleep(refresh_interval)
                continue
            
            # Validate current token
            is_valid = _validate_token_via_api(api_key, access_token)
            
            if not is_valid:
                print("[TOKEN] Token expired, attempting auto-refresh...")
                new_token = _try_auto_refresh_token()
                
                if new_token:
                    print("[TOKEN] Token refreshed successfully, reconnecting WebSocket...")
                    
                    # Update WebSocket manager with new token
                    if ws_manager:
                        ws_manager.update_token(new_token)
                        
                        # Stop current WebSocket if connected
                        if ws_manager.is_connected:
                            ws_manager.stop()
                            await asyncio.sleep(2)
                        
                        # Restart WebSocket with new token
                        ws_manager.start()
                        await asyncio.sleep(5)
                        
                        # Re-subscribe to instruments
                        if token_to_contract:
                            all_tokens = list(token_to_contract.keys())
                            ws_manager.subscribe_batched(all_tokens)
                            print(f"[TOKEN] WebSocket reconnected with {len(all_tokens)} subscriptions")
                    
                    print("[TOKEN] Token refresh and WebSocket reconnection complete")
                else:
                    print("[TOKEN] Token refresh failed! Will retry in next cycle")
            else:
                print(f"[TOKEN] Token valid, next check in {refresh_interval}s")
            
            await asyncio.sleep(refresh_interval)
            
        except Exception as e:
            print(f"[TOKEN] Error in token refresh task: {e}")
            await asyncio.sleep(refresh_interval)

@app.on_event("startup")
async def startup_event():
    """Start WebSocket and background tasks"""
    print("[STARTUP] Starting API...")
    try:
        # Log credential status
        api_key, access_token = get_api_credentials()
        if api_key and access_token:
            print(f"[OK] Credentials loaded - API_KEY: {api_key[:8]}... ACCESS_TOKEN: {access_token[:8]}...")
        else:
            print("[ERROR] WARNING: Missing credentials!")
        
        # Setup WebSocket subscriptions
        asyncio.create_task(setup_websocket_subscriptions())
        
        # Start cache updater
        await asyncio.sleep(3)  # Wait for WebSocket to connect
        asyncio.create_task(update_cache_from_websocket())
        
        # Start equity depth updater (HTTP fallback for bid/ask)
        asyncio.create_task(update_equity_depth_http())
        
        # Start HTTP fallback data fetcher if WebSocket fails
        asyncio.create_task(http_fallback_fetcher())
        
        # Start token refresh and WebSocket reconnection scheduler
        asyncio.create_task(token_refresh_and_reconnect())
        
        print("[OK] API ready - WebSocket streaming active")
        print("[FAST] Real-time data streaming started")
        print("[STATS] Equity bid/ask will update via HTTP every 10 seconds")
    except Exception as e:
        print(f"[WARN] Error starting WebSocket: {e}")
        print("[ALERT] API will still respond but data may be empty initially")

# REST API endpoints
@app.get("/api/all-futures-combined")
async def get_all_futures():
    """Get all futures data (optimized single endpoint)"""
    try:
        all_data = cache.get_all()
        timestamp = all_data.get("timestamp", time.time())
        current_data = all_data.get("current", {})  # Live spot prices
        near_data = all_data.get("near", {})        # Current month futures (0-35 days)
        next_data = all_data.get("next", {})        # Next month futures (36-70 days)
        far_data = all_data.get("far", {})          # Far month futures (71-105 days)
        
        return {
            "success": True,
            "data": {
                "current": current_data,
                "near": near_data,
                "next": next_data,
                "far": far_data,
                "timestamp": timestamp
            },
            "timestamp": timestamp,
            "data_age_seconds": time.time() - timestamp,
            "counts": {
                "current": len(current_data),
                "near": len(near_data),
                "next": len(next_data),
                "far": len(far_data)
            },
            "status": "ready" if len(near_data) > 0 else "loading"
        }
    except Exception as e:
        print(f"[ERROR] Error in get_all_futures: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "data": {"current": {}, "near": {}, "next": {}, "far": {}, "timestamp": time.time()},
            "timestamp": time.time(),
            "counts": {"current": 0, "near": 0, "next": 0, "far": 0},
            "status": "error"
        }

@app.get("/api/live-data")
async def get_live_data():
    """Get live market data (spot prices)"""
    return {
        "category": "current",
        "description": "Live spot market data",
        "data": cache.current_data,
        "timestamp": cache.last_update,
        "count": len(cache.current_data)
    }

@app.get("/api/near-futures")
async def get_near_futures():
    """Get near futures (nearest expiry: 0-40 days)"""
    return {
        "category": "near",
        "description": "Near futures (0-40 days)",
        "data": cache.near_data,
        "timestamp": cache.last_update,
        "count": len(cache.near_data)
    }

@app.get("/api/next-futures")
async def get_next_futures():
    """Get next futures (second nearest: 40-75 days)"""
    return {
        "category": "next",
        "description": "Next futures (40-75 days)",
        "data": cache.next_data,
        "timestamp": cache.last_update,
        "count": len(cache.next_data)
    }

@app.get("/api/far-futures")
async def get_far_futures():
    """Get far futures (third nearest: 75-120 days)"""
    return {
        "category": "far",
        "description": "Far futures (75-120 days)",
        "data": cache.far_data,
        "timestamp": cache.last_update,
        "count": len(cache.far_data)
    }

# Server-Sent Events endpoint for real-time streaming
@app.get("/api/stream")
async def stream_futures():
    """Stream real-time futures data using Server-Sent Events"""
    async def event_generator():
        while True:
            try:
                all_data = cache.get_all()
                data_json = json.dumps({
                    "current": all_data["current"],
                    "near": all_data["near"],
                    "next": all_data["next"],
                    "far": all_data["far"],
                    "timestamp": all_data["timestamp"]
                })
                yield f"data: {data_json}\n\n"
                await asyncio.sleep(0.1)  # Stream every 100ms for algo trading
            except Exception as e:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(2)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    ws_status = "connected" if (ws_manager and ws_manager.is_connected) else "disconnected"
    ws_error = ws_manager.get_last_error() if ws_manager else "N/A"
    
    # Check data availability
    total_contracts = len(cache.current_data) + len(cache.near_data) + len(cache.next_data) + len(cache.far_data)
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "data_age": time.time() - cache.last_update,
        "websocket": {
            "status": ws_status,
            "error": ws_error,
            "can_reconnect": ws_manager.is_websocket_available() if ws_manager else False
        },
        "contracts": {
            "current": len(cache.current_data),
            "near": len(cache.near_data),
            "next": len(cache.next_data),
            "far": len(cache.far_data)
        }
    }

@app.get("/api/diagnostics")
async def get_diagnostics():
    """Diagnostic endpoint to check configuration"""
    api_key = os.getenv('KITE_API_KEY', '')
    access_token = os.getenv('KITE_ACCESS_TOKEN', '')
    
    diagnostics = {
        "environment": {
            "KITE_API_KEY": f"SET ({api_key[:8]}...)" if api_key else "NOT SET",
            "KITE_ACCESS_TOKEN": f"SET ({access_token[:10]}...)" if access_token else "NOT SET",
            "KITE_API_SECRET": "SET" if os.getenv('KITE_API_SECRET') else "NOT SET",
            "KITE_USER_ID": "SET" if os.getenv('KITE_USER_ID') else "NOT SET",
            "KITE_PASSWORD": "SET" if os.getenv('KITE_PASSWORD') else "NOT SET",
            "KITE_TOTP_SECRET": "SET" if os.getenv('KITE_TOTP_SECRET') else "NOT SET",
        },
        "websocket": {
            "enabled": ws_manager is not None,
            "connected": ws_manager.is_connected if ws_manager else False,
            "last_error": ws_manager.get_last_error() if ws_manager else "N/A",
            "ticks_received": len(ws_manager.get_tick_data()) if ws_manager else 0
        },
        "data": {
            "current": len(cache.current_data),
            "near": len(cache.near_data),
            "next": len(cache.next_data),
            "far": len(cache.far_data),
            "last_update": cache.last_update
        }
    }
    return diagnostics

@app.post("/api/websocket/retry")
async def retry_websocket():
    """Manually retry WebSocket connection"""
    if not ws_manager:
        return {"success": False, "error": "WebSocket manager not initialized"}
    
    try:
        # Stop existing connection if any
        if ws_manager.is_connected:
            ws_manager.stop()
            await asyncio.sleep(2)
        
        ws_manager.retry_connection()
        await asyncio.sleep(5)  # Wait for connection attempt
        
        if ws_manager.is_connected:
            # Also setup subscriptions after reconnect
            await setup_websocket_subscriptions()
            return {"success": True, "message": "WebSocket reconnected and subscriptions restored"}
        else:
            return {
                "success": False, 
                "message": "Connection attempt started",
                "last_error": ws_manager.get_last_error()
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

n@app.get("/api/ip")
async def get_outbound_ip():
    """Get the outbound IP address of this server (for whitelisting)"""
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip = response.json().get("ip", "unknown")
        return {"ip": ip, "message": "This is the IP your HF Space uses for outbound requests. IP may change over time.", "note": "Kite may block shared IP ranges used by cloud platforms. Consider using Render.com for stable IP."}
    except Exception as e:
        return {"error": str(e), "ip": "unknown"}
@app.get("/")
async def root():
    """Root endpoint with API info"""
    ws_status = "connected" if (ws_manager and ws_manager.is_connected) else "disconnected"
    
    return {
        "api": "Real-Time Futures Streaming API",
        "version": "4.0.0",
        "description": "Dynamic rank-based futures with spot-futures arbitrage support",
        "websocket_status": ws_status,
        "endpoints": {
            "all_futures": "/api/all-futures-combined",
            "current": "/api/live-data (Live spot prices)",
            "near": "/api/near-futures (1st nearest expiry)",
            "next": "/api/next-futures (2nd nearest expiry)",
            "far": "/api/far-futures (3rd nearest expiry)",
            "stream": "/api/stream (SSE)",
            "health": "/api/health",
            "ws_retry": "POST /api/websocket/retry"
        },
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
