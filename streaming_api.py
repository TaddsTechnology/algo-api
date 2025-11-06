#!/usr/bin/env python3
"""
Optimized Streaming API for Real-Time Market Data
Uses Server-Sent Events (SSE) for continuous data streaming
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import Dict, Any
import asyncio
import json
import os
import time
from datetime import datetime

# Import our specialized futures fetchers
from kite_current_futures import KiteCurrentFutures
from kite_near_futures import KiteNearFutures
from kite_far_futures import KiteFarFutures
from kite_live_data import KiteLiveData

app = FastAPI(
    title="Real-Time Futures Streaming API",
    description="High-performance streaming API for live futures market data",
    version="3.0.0"
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
    
    if not api_key or not access_token:
        # Try config file
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

# Initialize fetchers with error handling
# Note: "near_futures" now fetches current month (0-35 days)
# "next_futures" now fetches next month (36-70 days)
live_data_fetcher = None  # Live spot prices
near_futures = None       # Current month futures (was "current")
next_futures = None       # Next month futures (was "near")
far_futures = None        # Far month futures

try:
    api_key, access_token = get_api_credentials()
    if api_key and access_token:
        live_data_fetcher = KiteLiveData(api_key, access_token)      # Live spot data
        near_futures = KiteCurrentFutures(api_key, access_token)     # 0-35 days
        next_futures = KiteNearFutures(api_key, access_token)        # 36-70 days
        far_futures = KiteFarFutures(api_key, access_token)          # 71-105 days
        print("✅ API fetchers initialized successfully")
    else:
        print("⚠️ Missing API credentials - will return empty data")
except Exception as e:
    print(f"❌ Error initializing fetchers: {e}")
    print("⚠️ API will start but data fetching may fail")

# Background task to continuously fetch data
async def continuous_data_fetcher():
    """Continuously fetch market data in background"""
    # Check if fetchers are initialized
    if not live_data_fetcher or not near_futures or not next_futures or not far_futures:
        print("❌ Fetchers not initialized - skipping data fetch")
        return
    
    # Start with lighter load - only popular contracts initially
    first_fetch = True
    
    while True:
        try:
            # Use limit on first fetch to start faster, then fetch all
            limit = 50 if first_fetch else None
            
            # Fetch all categories in parallel
            live_task = asyncio.create_task(
                asyncio.to_thread(live_data_fetcher.fetch_live_data, use_ltp_only=False, limit_symbols=limit)
            )
            near_task = asyncio.create_task(
                asyncio.to_thread(near_futures.fetch_live_data, use_ltp_only=False, limit_contracts=limit)
            )
            next_task = asyncio.create_task(
                asyncio.to_thread(next_futures.fetch_live_data, use_ltp_only=False, limit_contracts=limit)
            )
            far_task = asyncio.create_task(
                asyncio.to_thread(far_futures.fetch_live_data, use_ltp_only=False, limit_contracts=limit)
            )
            
            # Wait for all to complete
            live_data, near_data, next_data, far_data = await asyncio.gather(
                live_task, near_task, next_task, far_task, return_exceptions=True
            )
            
            # Update cache
            if not isinstance(live_data, Exception):
                cache.update("current", live_data)
            if not isinstance(near_data, Exception):
                cache.update("near", near_data)
            if not isinstance(next_data, Exception):
                cache.update("next", next_data)
            if not isinstance(far_data, Exception):
                cache.update("far", far_data)
            
            print(f"✅ Updated at {datetime.now().strftime('%H:%M:%S')} - Live: {len(live_data) if not isinstance(live_data, Exception) else 0}, Near: {len(near_data) if not isinstance(near_data, Exception) else 0}, Next: {len(next_data) if not isinstance(next_data, Exception) else 0}, Far: {len(far_data) if not isinstance(far_data, Exception) else 0}")
            
            # After first fetch, fetch all contracts
            if first_fetch:
                first_fetch = False
                await asyncio.sleep(0.5)  # Quick refresh to get all contracts
            else:
                await asyncio.sleep(2)  # Update every 2 seconds for all contracts
            
        except Exception as e:
            print(f"⚠️ Error in fetcher: {e}")
            await asyncio.sleep(2)

@app.on_event("startup")
async def startup_event():
    """Start background data fetcher"""
    print("🚀 Starting API...")
    try:
        # Start fetcher without blocking startup
        asyncio.create_task(continuous_data_fetcher())
        print("✅ API ready - data fetcher running in background")
        print("⚡ First data will be available in ~5-10 seconds")
    except Exception as e:
        print(f"⚠️ Error starting data fetcher: {e}")
        print("🚨 API will still respond but data may be empty initially")

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
        print(f"❌ Error in get_all_futures: {e}")
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
    """Get near futures (current month: 0-35 days expiry)"""
    return {
        "category": "near",
        "description": "Current month futures (0-35 days)",
        "data": cache.near_data,
        "timestamp": cache.last_update,
        "count": len(cache.near_data)
    }

@app.get("/api/next-futures")
async def get_next_futures():
    """Get next futures (next month: 36-70 days expiry)"""
    return {
        "category": "next",
        "description": "Next month futures (36-70 days)",
        "data": cache.next_data,
        "timestamp": cache.last_update,
        "count": len(cache.next_data)
    }

@app.get("/api/far-futures")
async def get_far_futures():
    """Get far futures (far month: 71-105 days expiry)"""
    return {
        "category": "far",
        "description": "Far month futures (71-105 days)",
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
                await asyncio.sleep(1)  # Stream every 1 second
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
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "data_age": time.time() - cache.last_update,
        "contracts": {
            "current": len(cache.current_data),
            "near": len(cache.near_data),
            "next": len(cache.next_data),
            "far": len(cache.far_data)
        }
    }

@app.get("/")
async def root():
    """Root endpoint with API info"""
    return {
        "api": "Real-Time Futures Streaming API",
        "version": "3.0.0",
        "endpoints": {
            "all_futures": "/api/all-futures-combined",
            "current": "/api/live-data (Live spot prices)",
            "near": "/api/near-futures (0-35 days)",
            "next": "/api/next-futures (36-70 days)",
            "far": "/api/far-futures (71-105 days)",
            "stream": "/api/stream (SSE)",
            "health": "/api/health"
        },
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
