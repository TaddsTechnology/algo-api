#!/usr/bin/env python3
"""
Enhanced FastAPI Market Data Endpoint for Algo Trading
High-performance market data serving with specialized futures endpoints and calculation engine
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import json
import os
from datetime import datetime
import threading
import time

# Import our specialized futures fetchers
from kite_current_futures import KiteCurrentFutures
from kite_near_futures import KiteNearFutures
from kite_far_futures import KiteFarFutures
from kite_fast_futures import KiteFastFutures
from formula_calculator import FormulaCalculator, process_formula

app = FastAPI(
    title="Enhanced Algo Trading Market Data API",
    description="High-performance futures data API with specialized category endpoints and calculation engine",
    version="2.0.0"
)

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for API requests/responses
class FormulaRequest(BaseModel):
    formula: str
    variables: Optional[Dict[str, Any]] = None

class FormulaResponse(BaseModel):
    success: bool
    result: float
    formula: str
    timestamp: str
    message: str
    error: Optional[str] = None

# Global data stores
class CategoryDataStore:
    def __init__(self, category):
        self.category = category
        self.data = {}
        self.timestamp = time.time()
        self.lock = threading.Lock()
    
    def update_data(self, new_data):
        with self.lock:
            self.data = new_data
            self.timestamp = time.time()
    
    def get_data(self):
        with self.lock:
            return self.data.copy(), self.timestamp

# Initialize data stores for each category
current_futures_store = CategoryDataStore("current")
near_futures_store = CategoryDataStore("near")
far_futures_store = CategoryDataStore("far")
all_futures_store = CategoryDataStore("all")

# Initialize formula calculator
formula_calculator = FormulaCalculator()

# Initialize API Key and Access Token from config or environment
def get_api_credentials():
    """Get API credentials from config or environment variables"""
    # Try to get from environment variables first
    api_key = os.getenv('KITE_API_KEY')
    access_token = os.getenv('KITE_ACCESS_TOKEN')
    
    # If not found in environment, try to import from config file
    if not api_key or not access_token:
        try:
            # Try multiple config files to be flexible
            for config_file in ["kite_config_hf.py", "kite_config.py", "supabase_config_hf.py"]:
                if os.path.exists(config_file):
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("config", config_file)
                    config = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(config)
                    
                    api_key = getattr(config, "API_KEY", api_key)
                    access_token = getattr(config, "ACCESS_TOKEN", access_token)
                    
                    if api_key and access_token:
                        break
        except Exception as e:
            print(f"⚠️ Error loading config file: {e}")
    
    if not api_key or not access_token:
        raise ValueError("API Key and Access Token must be provided in environment or config file")
    
    return api_key, access_token

# Initialize all fetchers with same credentials
try:
    api_key, access_token = get_api_credentials()
    
    print(f"🔑 Using API Key: {api_key[:8]}...")
    
    # Initialize all specialized fetchers
    current_futures = KiteCurrentFutures(api_key, access_token)
    near_futures = KiteNearFutures(api_key, access_token)
    far_futures = KiteFarFutures(api_key, access_token)
    all_futures = KiteFastFutures(api_key, access_token)
    
except Exception as e:
    print(f"❌ Error initializing API fetchers: {e}")
    import traceback
    traceback.print_exc()

# Background data updaters for each category
async def update_current_futures():
    """Background task to update current futures data"""
    while True:
        try:
            data = current_futures.fetch_live_data(use_ltp_only=True, limit_contracts=50)
            current_futures_store.update_data(data)
            await asyncio.sleep(0.5)  # Fast 0.5s refresh for current futures
        except Exception as e:
            print(f"⚠️ Error updating current futures: {e}")
            await asyncio.sleep(2)

async def update_near_futures():
    """Background task to update near futures data"""
    while True:
        try:
            data = near_futures.fetch_live_data(use_ltp_only=True, limit_contracts=40)
            near_futures_store.update_data(data)
            await asyncio.sleep(1.0)  # 1s refresh for near futures
        except Exception as e:
            print(f"⚠️ Error updating near futures: {e}")
            await asyncio.sleep(3)

async def update_far_futures():
    """Background task to update far futures data"""
    while True:
        try:
            data = far_futures.fetch_live_data(use_ltp_only=True, limit_contracts=30)
            far_futures_store.update_data(data)
            await asyncio.sleep(1.5)  # 1.5s refresh for far futures
        except Exception as e:
            print(f"⚠️ Error updating far futures: {e}")
            await asyncio.sleep(3)

async def update_all_futures():
    """Background task to update combined futures data"""
    while True:
        try:
            data = all_futures.fetch_live_data(use_ltp_only=True, limit_contracts=None)
            all_futures_store.update_data(data)
            await asyncio.sleep(2.0)  # 2s refresh for all futures
        except Exception as e:
            print(f"⚠️ Error updating all futures: {e}")
            await asyncio.sleep(3)

# Start background tasks on app startup
@app.on_event("startup")
async def startup_event():
    """Start background data updaters on startup"""
    asyncio.create_task(update_current_futures())
    asyncio.create_task(update_near_futures())
    asyncio.create_task(update_far_futures())
    asyncio.create_task(update_all_futures())
    print("🚀 Started all background data fetchers")

# API endpoints for each futures category
@app.get("/api/current-futures")
async def get_current_futures():
    """Get current futures data (0-35 days expiry)"""
    data, timestamp = current_futures_store.get_data()
    return {
        "category": "current",
        "description": "Current month futures (0-35 days expiry)",
        "data": data,
        "timestamp": timestamp,
        "count": len(data),
        "server_time": time.time()
    }

@app.get("/api/near-futures")
async def get_near_futures():
    """Get near futures data (36-70 days expiry)"""
    data, timestamp = near_futures_store.get_data()
    return {
        "category": "near",
        "description": "Near month futures (36-70 days expiry)",
        "data": data,
        "timestamp": timestamp,
        "count": len(data),
        "server_time": time.time()
    }

@app.get("/api/far-futures")
async def get_far_futures():
    """Get far futures data (71-105 days expiry)"""
    data, timestamp = far_futures_store.get_data()
    return {
        "category": "far",
        "description": "Far month futures (71-105 days expiry)",
        "data": data,
        "timestamp": timestamp,
        "count": len(data),
        "server_time": time.time()
    }

@app.get("/api/all-futures")
async def get_all_futures():
    """Get all futures data (combined)"""
    data, timestamp = all_futures_store.get_data()
    return {
        "category": "all",
        "description": "All futures contracts combined",
        "data": data,
        "timestamp": timestamp,
        "count": len(data),
        "server_time": time.time()
    }

@app.get("/api/futures/{symbol}")
async def get_specific_future(symbol: str):
    """Get data for a specific futures symbol"""
    # Check each store for the symbol
    for store in [current_futures_store, near_futures_store, far_futures_store]:
        data, _ = store.get_data()
        if symbol in data:
            return {
                "symbol": symbol,
                "data": data[symbol],
                "timestamp": time.time()
            }
    
    # If not found
    raise HTTPException(status_code=404, detail=f"Futures contract {symbol} not found")

@app.get("/api/popular-contracts/{category}")
async def get_popular_contracts(category: str = "all", limit: int = 20):
    """Get popular contracts for a specific category"""
    if category == "current":
        data, _ = current_futures_store.get_data()
    elif category == "near":
        data, _ = near_futures_store.get_data()
    elif category == "far":
        data, _ = far_futures_store.get_data()
    elif category == "all":
        # Combine data from all categories
        current_data, _ = current_futures_store.get_data()
        near_data, _ = near_futures_store.get_data()
        far_data, _ = far_futures_store.get_data()
        
        data = {**current_data, **near_data, **far_data}
    else:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}. Must be current, near, far, or all")
    
    # Extract and filter only popular contracts
    popular_contracts = []
    for symbol, contract_data in data.items():
        contract_info = contract_data.get('contract_info', {})
        if contract_info.get('is_popular', False):
            popular_contracts.append(contract_data)
    
    # Sort by popularity first, then by symbol
    popular_contracts = sorted(popular_contracts, 
                               key=lambda x: (not x.get('contract_info', {}).get('is_popular', False), 
                                              x.get('contract_info', {}).get('symbol', '')))
    
    # Apply limit
    limited_contracts = popular_contracts[:limit]
    
    return {
        "category": category,
        "popular_contracts": limited_contracts,
        "count": len(limited_contracts),
        "timestamp": time.time()
    }

# Formula calculation endpoint
@app.post("/api/calculate", response_model=FormulaResponse)
async def calculate_formula(request: FormulaRequest):
    """Calculate a formula using current market data"""
    # Get latest combined data
    all_data, _ = all_futures_store.get_data()
    
    # Process formula
    result = process_formula(request.formula, all_data, request.variables)
    
    return result

# Function list endpoint
@app.get("/api/functions")
async def get_available_functions():
    """Get list of supported functions for formula calculations"""
    return formula_calculator.get_supported_functions()

# Formula validation endpoint
@app.post("/api/validate-formula")
async def validate_formula(request: FormulaRequest):
    """Validate a formula without executing it"""
    return formula_calculator.validate_formula(request.formula)

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    current_data, current_ts = current_futures_store.get_data()
    near_data, near_ts = near_futures_store.get_data()
    far_data, far_ts = far_futures_store.get_data()
    all_data, all_ts = all_futures_store.get_data()
    
    return {
        "status": "healthy",
        "data_count": {
            "current_futures": len(current_data),
            "near_futures": len(near_data),
            "far_futures": len(far_data),
            "all_futures": len(all_data)
        },
        "last_updates": {
            "current_futures": current_ts,
            "near_futures": near_ts,
            "far_futures": far_ts,
            "all_futures": all_ts
        },
        "server_time": time.time()
    }

# Root endpoint with API documentation link
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Enhanced Algo Trading Market Data API",
        "version": "2.0.0",
        "documentation": "/docs",
        "endpoints": {
            "futures_data": [
                "/api/current-futures",
                "/api/near-futures", 
                "/api/far-futures",
                "/api/all-futures",
                "/api/futures/{symbol}",
                "/api/popular-contracts/{category}"
            ],
            "formula_calculation": [
                "/api/calculate",
                "/api/functions",
                "/api/validate-formula"
            ],
            "system": [
                "/api/health"
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Enhanced FastAPI Market Data Server")
    print("📊 API Documentation available at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)