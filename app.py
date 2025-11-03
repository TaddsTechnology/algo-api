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
    
    print("🚀 Starting Enhanced Algo Trading API")
    print(f"🌐 Server: http://{host}:{port}")
    print("📊 API Documentation: http://localhost:7860/docs")
    print("=" * 60)
    print("🎯 Available Endpoints:")
    print("   GET  /api/current-futures    - Current futures (0-35 days)")
    print("   GET  /api/near-futures       - Near futures (36-70 days)")
    print("   GET  /api/far-futures        - Far futures (71-105 days)")
    print("   GET  /api/all-futures        - All futures combined")
    print("   GET  /api/futures/{symbol}   - Specific futures contract")
    print("   GET  /api/popular-contracts/{category} - Popular contracts")
    print("   POST /api/calculate          - Formula calculations")
    print("   GET  /api/functions          - Available functions list")
    print("   POST /api/validate-formula   - Validate formulas")
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
