#!/usr/bin/env python3
"""
Scheduled Token Refresh
Refreshes Kite access token daily at 8:00 AM
"""

import schedule
import time
import logging
from datetime import datetime

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from KiteApi.auto_token_manager import setup_lightweight_kite_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def refresh_token_job():
    """Scheduled job to refresh token"""
    logger.info(f"⏰ Scheduled token refresh started at {datetime.now()}")
    
    try:
        # Setup token manager
        manager = setup_lightweight_kite_manager()
        if not manager:
            logger.error("❌ Failed to setup token manager")
            return
            
        # Generate new token
        new_token = manager._generate_token_automatically()
        if new_token:
            logger.info("✅ Scheduled token refresh completed successfully")
        else:
            logger.error("❌ Scheduled token refresh failed")
            
    except Exception as e:
        logger.error(f"❌ Scheduled token refresh failed with error: {e}")

def main():
    """Main scheduler loop"""
    logger.info("🚀 Starting scheduled token refresh service...")
    logger.info("📅 Token will be refreshed daily at 8:00 AM")
    
    # Schedule daily job at 8:00 AM
    schedule.every().day.at("08:00").do(refresh_token_job)
    
    # Also run once immediately if needed
    logger.info("🔍 Checking if immediate refresh is needed...")
    refresh_token_job()
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()