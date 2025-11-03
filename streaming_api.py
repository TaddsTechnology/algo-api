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
        self.current_data = {}
        self.near_data = {}
        self.far_data = {}
        self.last_update = time.time()
        
    def update(self, category, data):
        if category == "current":
            self.current_data = data
        elif category == "near":
            self.near_data = data
        elif category == "far":
            self.far_data = data
        self.last_update = time.time()
    
    def get_all(self):
        return {
            "current": self.current_data,
            "near": self.near_data,
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
current_futures = None
near_futures = None
far_futures = None

try:
    api_key, access_token = get_api_credentials()
    if api_key and access_token:
        current_futures = KiteCurrentFutures(api_key, access_token)
        near_futures = KiteNearFutures(api_key, access_token)
        far_futures = KiteFarFutures(api_key, access_token)
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
    if not current_futures or not near_futures or not far_futures:
        print("❌ Fetchers not initialized - skipping data fetch")
        return
    
    # Start with lighter load - only popular contracts initially
    first_fetch = True
    
    while True:
        try:
            # Use limit on first fetch to start faster, then fetch all
            limit = 50 if first_fetch else None
            
            # Fetch all categories in parallel
            current_task = asyncio.create_task(
                asyncio.to_thread(current_futures.fetch_live_data, use_ltp_only=False, limit_contracts=limit)
            )
            near_task = asyncio.create_task(
                asyncio.to_thread(near_futures.fetch_live_data, use_ltp_only=False, limit_contracts=limit)
            )
            far_task = asyncio.create_task(
                asyncio.to_thread(far_futures.fetch_live_data, use_ltp_only=False, limit_contracts=limit)
            )
            
            # Wait for all to complete
            current_data, near_data, far_data = await asyncio.gather(
                current_task, near_task, far_task, return_exceptions=True
            )
            
            # Update cache
            if not isinstance(current_data, Exception):
                cache.update("current", current_data)
            if not isinstance(near_data, Exception):
                cache.update("near", near_data)
            if not isinstance(far_data, Exception):
                cache.update("far", far_data)
            
            print(f"✅ Updated at {datetime.now().strftime('%H:%M:%S')} - Current: {len(current_data) if not isinstance(current_data, Exception) else 0}, Near: {len(near_data) if not isinstance(near_data, Exception) else 0}, Far: {len(far_data) if not isinstance(far_data, Exception) else 0}")
            
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
    all_data = cache.get_all()
    return {
        "success": True,
        "data": all_data,
        "timestamp": all_data["timestamp"],
        "data_age_seconds": time.time() - all_data["timestamp"],
        "counts": {
            "current": len(all_data["current"]),
            "near": len(all_data["near"]),
            "far": len(all_data["far"])
        },
        "status": "ready" if len(all_data["current"]) > 0 else "loading"
    }

@app.get("/api/current-futures")
async def get_current_futures():
    """Get current futures only"""
    return {
        "category": "current",
        "data": cache.current_data,
        "timestamp": cache.last_update,
        "count": len(cache.current_data)
    }

@app.get("/api/near-futures")
async def get_near_futures():
    """Get near futures only"""
    return {
        "category": "near",
        "data": cache.near_data,
        "timestamp": cache.last_update,
        "count": len(cache.near_data)
    }

@app.get("/api/far-futures")
async def get_far_futures():
    """Get far futures only"""
    return {
        "category": "far",
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
            "current": "/api/current-futures",
            "near": "/api/near-futures",
            "far": "/api/far-futures",
            "stream": "/api/stream (SSE)",
            "health": "/api/health"
        },
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
