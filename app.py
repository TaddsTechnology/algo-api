#!/usr/bin/env python3
"""
Main Application Entry Point for Hugging Face Spaces
Enhanced Algo Trading Market Data API with specialized futures endpoints
"""

import os
import sys
import uvicorn
from streaming_api import app

# Ensure proper path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main function to run the enhanced API"""
    # Get port from environment (Hugging Face Spaces uses port 7860)
    port = int(os.getenv("PORT", 7860))
    host = os.getenv("HOST", "0.0.0.0")
    
    print("Starting Enhanced Algo Trading API v4.0.0")
    print(f"Server: http://{host}:{port}")
    print("API Docs: http://localhost:7860/docs")
    print("=" * 60)
    print("Available Endpoints:")
    print("   GET  /api/all-futures-combined - All futures (FAST)")
    print("   GET  /api/live-data           - Live spot prices")
    print("   GET  /api/near-futures       - Nearest expiry futures")
    print("   GET  /api/next-futures       - 2nd nearest expiry futures")
    print("   GET  /api/far-futures        - 3rd nearest expiry futures")
    print("   GET  /api/stream             - Real-time SSE stream")
    print("   GET  /api/health             - Health check")
    print("=" * 60)
    
    # Check for required environment variables
    required_vars = ['KITE_API_KEY', 'KITE_ACCESS_TOKEN']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("⚠️ WARNING: Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please set these in your Hugging Face Space settings")
        print("   or in your kite_config_hf.py file")
    else:
        print("✅ All required environment variables found")
    
    print("\n🔄 Starting background data fetchers...")
    
    # Run the FastAPI application
    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=1,  # Single worker for Hugging Face Spaces
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
