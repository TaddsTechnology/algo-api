#!/usr/bin/env python3
"""
OPTIMIZED Streaming API for Real-Time Market Data
✅ Connection pooling - reuses data across all users
✅ Rate limiting - prevents overload
✅ Pre-serialized cache - sends same JSON to all users
✅ Connection tracking - monitors active users
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, Set
import asyncio
import json
import os
import time
from datetime import datetime
from collections import defaultdict

# Import our specialized futures fetchers
from kite_current_futures import KiteCurrentFutures
from kite_near_futures import KiteNearFutures
from kite_far_futures import KiteFarFutures
from kite_live_data import KiteLiveData
from kite_websocket_manager import KiteWebSocketManager

app = FastAPI(
    title="Optimized Real-Time Futures Streaming API",
    description="High-performance streaming API with connection pooling",
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

# ====================
# OPTIMIZATION 1: Pre-serialized cache
# ====================
class OptimizedMarketDataCache:
    def __init__(self):
        self.current_data = {}
        self.near_data = {}
        self.next_data = {}
        self.far_data = {}
        self.last_update = time.time()
        
        # Pre-serialized JSON (avoids re-serialization for each user)
        self._cached_json = "{}"
        self._cache_dirty = True
        
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
        self._cache_dirty = True
    
    def get_all(self):
        return {
            "current": self.current_data,
            "near": self.near_data,
            "next": self.next_data,
            "far": self.far_data,
            "timestamp": self.last_update
        }
    
    def get_cached_json(self):
        """Return pre-serialized JSON - computed once, sent to all users"""
        if self._cache_dirty:
            self._cached_json = json.dumps({
                "current": self.current_data,
                "near": self.near_data,
                "next": self.next_data,
                "far": self.far_data,
                "timestamp": self.last_update
            })
            self._cache_dirty = False
        return self._cached_json

cache = OptimizedMarketDataCache()

# ====================
# OPTIMIZATION 2: Connection tracking & limits
# ====================
class ConnectionManager:
    def __init__(self, max_connections=50):
        self.active_connections: Set[str] = set()
        self.max_connections = max_connections
        self.ip_connections: Dict[str, int] = defaultdict(int)
        self.max_per_ip = 5
    
    def can_connect(self, client_ip: str) -> tuple[bool, str]:
        """Check if new connection is allowed"""
        if len(self.active_connections) >= self.max_connections:
            return False, f"Server at capacity ({self.max_connections} connections)"
        
        if self.ip_connections[client_ip] >= self.max_per_ip:
            return False, f"Too many connections from your IP (max {self.max_per_ip})"
        
        return True, "OK"
    
    def add_connection(self, connection_id: str, client_ip: str):
        self.active_connections.add(connection_id)
        self.ip_connections[client_ip] += 1
        print(f"✅ New connection {connection_id[:8]} from {client_ip} - Total: {len(self.active_connections)}")
    
    def remove_connection(self, connection_id: str, client_ip: str):
        self.active_connections.discard(connection_id)
        self.ip_connections[client_ip] = max(0, self.ip_connections[client_ip] - 1)
        print(f"❌ Closed connection {connection_id[:8]} from {client_ip} - Total: {len(self.active_connections)}")
    
    def get_stats(self):
        return {
            "active_connections": len(self.active_connections),
            "max_connections": self.max_connections,
            "unique_ips": len([ip for ip, count in self.ip_connections.items() if count > 0])
        }

connection_manager = ConnectionManager(max_connections=50)

# Initialize API fetchers (same as before)
def get_api_credentials():
    api_key = os.getenv('KITE_API_KEY')
    access_token = os.getenv('KITE_ACCESS_TOKEN')
    
    if not api_key or not access_token:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("config", "kite_config_hf.py")
            config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(config)
            api_key = config.API_KEY
            access_token = config.ACCESS_TOKEN
        except:
            pass
    
    return api_key, access_token

# Initialize fetchers
live_data_fetcher = None
near_futures = None
next_futures = None
far_futures = None
ws_manager = None

token_to_contract = {}
token_to_symbol = {}

try:
    api_key, access_token = get_api_credentials()
    if api_key and access_token:
        ws_manager = KiteWebSocketManager(api_key, access_token)
        live_data_fetcher = KiteLiveData(api_key, access_token, ws_manager)
        near_futures = KiteCurrentFutures(api_key, access_token, ws_manager)
        next_futures = KiteNearFutures(api_key, access_token, ws_manager)
        far_futures = KiteFarFutures(api_key, access_token, ws_manager)
        print("✅ API fetchers initialized successfully")
    else:
        print("⚠️ Missing API credentials")
except Exception as e:
    print(f"❌ Error initializing fetchers: {e}")

# Background tasks (same as before)
async def setup_websocket_subscriptions():
    """Setup WebSocket subscriptions for all instruments"""
    global token_to_contract, token_to_symbol
    
    if not ws_manager or not live_data_fetcher or not near_futures or not next_futures or not far_futures:
        print("❌ Fetchers not initialized - skipping WebSocket setup")
        return
    
    try:
        print("🔍 Fetching all instrument metadata...")
        
        live_instruments = await asyncio.to_thread(live_data_fetcher.get_equity_instruments)
        near_contracts = await asyncio.to_thread(near_futures.get_current_futures_contracts)
        next_contracts = await asyncio.to_thread(next_futures.get_near_futures_contracts)
        far_contracts = await asyncio.to_thread(far_futures.get_far_futures_contracts)
        
        all_tokens = []
        
        for instrument in live_instruments:
            token = instrument.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = instrument.get('symbol')
                token_to_contract[int(token)] = {'category': 'current', 'data': instrument}
        
        for contract in near_contracts:
            token = contract.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = contract.get('symbol')
                token_to_contract[int(token)] = {'category': 'near', 'data': contract}
        
        for contract in next_contracts:
            token = contract.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = contract.get('symbol')
                token_to_contract[int(token)] = {'category': 'next', 'data': contract}
        
        for contract in far_contracts:
            token = contract.get('instrument_token')
            if token:
                all_tokens.append(int(token))
                token_to_symbol[int(token)] = contract.get('symbol')
                token_to_contract[int(token)] = {'category': 'far', 'data': contract}
        
        print(f"📊 Collected {len(all_tokens)} instrument tokens")
        
        ws_manager.start()
        await asyncio.sleep(2)
        
        print(f"📡 Subscribing to {len(all_tokens)} instruments via WebSocket...")
        ws_manager.subscribe(all_tokens)
        
        print("✅ WebSocket subscriptions active")
        
    except Exception as e:
        print(f"❌ Error setting up WebSocket: {e}")

async def update_cache_from_websocket():
    """Continuously update cache from WebSocket tick data"""
    if not ws_manager:
        return
    
    update_counter = 0  # Track updates for periodic logging
    while True:
        try:
            tick_data = ws_manager.get_tick_data()
            
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
                
                formatted_tick = {
                    'symbol': symbol,
                    'ltp': tick.get('last_price', 0),
                    'volume': tick.get('volume_traded', 0),
                    'change': tick.get('change', 0),
                    'ohlc': tick.get('ohlc', {}),
                    'bid': tick.get('depth', {}).get('buy', [{}])[0].get('price', 0) if tick.get('depth') else 0,
                    'ask': tick.get('depth', {}).get('sell', [{}])[0].get('price', 0) if tick.get('depth') else 0,
                    'timestamp': tick.get('updated_at'),
                    'contract_info': contract_info['data']
                }
                
                if category == 'current':
                    current_data[symbol] = formatted_tick
                elif category == 'near':
                    near_data[symbol] = formatted_tick
                elif category == 'next':
                    next_data[symbol] = formatted_tick
                elif category == 'far':
                    far_data[symbol] = formatted_tick
            
            cache.update("current", current_data)
            cache.update("near", near_data)
            cache.update("next", next_data)
            cache.update("far", far_data)
            
            # Only log every 30 seconds instead of every second
            update_counter += 1
            if len(tick_data) > 0 and update_counter % 30 == 0:
                print(f"📊 Updated at {datetime.now().strftime('%H:%M:%S')} - {len(current_data)}/{len(near_data)}/{len(next_data)}/{len(far_data)} (checked {update_counter} times)")
            
            await asyncio.sleep(1)  # Update every 1 second (reduced from 0.5s)
            
        except Exception as e:
            print(f"⚠️ Error updating cache: {e}")
            await asyncio.sleep(1)

async def update_equity_depth_http():
    """Periodically fetch equity bid/ask via HTTP"""
    if not live_data_fetcher:
        return
    
    await asyncio.sleep(5)
    
    while True:
        try:
            equity_data = await asyncio.to_thread(
                live_data_fetcher.fetch_live_data_http,
                use_ltp_only=False,
                limit_symbols=None
            )
            
            if equity_data:
                for symbol, data in equity_data.items():
                    if symbol in cache.current_data:
                        cache.current_data[symbol]['bid'] = data.get('bid', 0)
                        cache.current_data[symbol]['ask'] = data.get('ask', 0)
                    else:
                        cache.current_data[symbol] = data
            
            await asyncio.sleep(15)  # Reduced frequency to 15s
            
        except Exception as e:
            print(f"⚠️ Error updating equity depth: {e}")
            await asyncio.sleep(15)

@app.on_event("startup")
async def startup_event():
    """Start WebSocket and background tasks"""
    print("🚀 Starting Optimized API...")
    try:
        asyncio.create_task(setup_websocket_subscriptions())
        await asyncio.sleep(3)
        asyncio.create_task(update_cache_from_websocket())
        asyncio.create_task(update_equity_depth_http())
        print("✅ API ready - Optimized streaming active")
    except Exception as e:
        print(f"⚠️ Error starting: {e}")

# ====================
# OPTIMIZATION 3: Efficient SSE with connection tracking
# ====================
@app.get("/api/stream")
async def stream_futures(request: Request):
    """
    Optimized SSE endpoint:
    - Connection limits per IP
    - Pre-serialized JSON (no repeated serialization)
    - Longer intervals (2s instead of 0.5s)
    """
    client_ip = request.client.host
    connection_id = f"{client_ip}_{time.time()}"
    
    # Check connection limits
    can_connect, message = connection_manager.can_connect(client_ip)
    if not can_connect:
        return JSONResponse(
            status_code=429,
            content={"error": message}
        )
    
    async def event_generator():
        connection_manager.add_connection(connection_id, client_ip)
        try:
            while True:
                # Use pre-serialized JSON (computed once, sent to all)
                data_json = cache.get_cached_json()
                yield f"data: {data_json}\n\n"
                await asyncio.sleep(2)  # Send every 2 seconds (not 0.5s)
        except Exception as e:
            print(f"⚠️ Stream error for {connection_id[:8]}: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            connection_manager.remove_connection(connection_id, client_ip)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

# REST endpoints (same as before but with optimized cache)
@app.get("/api/all-futures-combined")
async def get_all_futures():
    """Get all futures data (optimized single endpoint)"""
    try:
        all_data = cache.get_all()
        timestamp = all_data.get("timestamp", time.time())
        current_data = all_data.get("current", {})
        near_data = all_data.get("near", {})
        next_data = all_data.get("next", {})
        far_data = all_data.get("far", {})
        
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
        return {
            "success": False,
            "error": str(e),
            "data": {"current": {}, "near": {}, "next": {}, "far": {}, "timestamp": time.time()},
            "status": "error"
        }

@app.get("/api/live-data")
async def get_live_data():
    return {
        "category": "current",
        "description": "Live spot market data",
        "data": cache.current_data,
        "timestamp": cache.last_update,
        "count": len(cache.current_data)
    }

@app.get("/api/near-futures")
async def get_near_futures():
    return {
        "category": "near",
        "description": "Current month futures (0-35 days)",
        "data": cache.near_data,
        "timestamp": cache.last_update,
        "count": len(cache.near_data)
    }

@app.get("/api/next-futures")
async def get_next_futures():
    return {
        "category": "next",
        "description": "Next month futures (36-70 days)",
        "data": cache.next_data,
        "timestamp": cache.last_update,
        "count": len(cache.next_data)
    }

@app.get("/api/far-futures")
async def get_far_futures():
    return {
        "category": "far",
        "description": "Far month futures (71-105 days)",
        "data": cache.far_data,
        "timestamp": cache.last_update,
        "count": len(cache.far_data)
    }

@app.get("/api/health")
async def health_check():
    """Health check with connection stats"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "data_age": time.time() - cache.last_update,
        "contracts": {
            "current": len(cache.current_data),
            "near": len(cache.near_data),
            "next": len(cache.next_data),
            "far": len(cache.far_data)
        },
        "connections": connection_manager.get_stats()
    }

@app.get("/")
async def root():
    return {
        "api": "Optimized Real-Time Futures Streaming API",
        "version": "4.0.0",
        "optimizations": [
            "Pre-serialized JSON cache",
            "Connection limits (50 max, 5 per IP)",
            "Reduced SSE frequency (2s)",
            "Connection tracking"
        ],
        "endpoints": {
            "all_futures": "/api/all-futures-combined",
            "current": "/api/live-data",
            "near": "/api/near-futures",
            "next": "/api/next-futures",
            "far": "/api/far-futures",
            "stream": "/api/stream (SSE)",
            "health": "/api/health"
        },
        "status": "running",
        "connections": connection_manager.get_stats()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
