#!/usr/bin/env python3
"""
Automatic Token Manager for Kite Connect API

This module handles automatic token refresh and management.
Kite Connect tokens are valid for a single trading day only.
"""

import os
import json
import time
import requests
import hashlib
import webbrowser
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import schedule
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KiteTokenManager:
    def __init__(self, api_key: str, api_secret: str, config_path: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), '..', 'kite_config.py')
        self.token_file = os.path.join(os.path.dirname(__file__), 'token_data.json')
        self.current_token = None
        self.token_expiry = None
        self.refresh_thread = None
        self.is_running = False
        
    def load_token_data(self) -> Dict[str, Any]:
        """Load token data from file"""
        if os.path.exists(self.token_file):
            try:
                with open(self.token_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_token_data(self, data: Dict[str, Any]):
        """Save token data to file"""
        try:
            with open(self.token_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save token data: {e}")
    
    def update_config_file(self, access_token: str):
        """Update the access token in kite_config.py"""
        try:
            import re
            
            with open(self.config_path, 'r') as f:
                content = f.read()
            
            # Replace ACCESS_TOKEN line
            updated_content = re.sub(
                r'ACCESS_TOKEN = ".*?"',
                f'ACCESS_TOKEN = "{access_token}"',
                content
            )
            
            with open(self.config_path, 'w') as f:
                f.write(updated_content)
                
            logger.info("Config file updated with new token")
            
        except Exception as e:
            logger.error(f"Failed to update config file: {e}")
    
    def is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.current_token:
            return False
            
        # Kite tokens expire at end of trading day (3:30 PM IST)
        now = datetime.now()
        if self.token_expiry and now > self.token_expiry:
            return False
            
        # Test token with API call
        return self.test_token(self.current_token)
    
    def test_token(self, token: str) -> bool:
        """Test if a token is working"""
        try:
            headers = {
                'Authorization': f'token {self.api_key}:{token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                'https://api.kite.trade/user/profile',
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Token test failed: {e}")
            return False
    
    def generate_login_url(self) -> str:
        """Generate login URL for manual token generation"""
        from urllib.parse import urlencode
        
        params = {
            "api_key": self.api_key,
            "v": "3"
        }
        return f"https://kite.trade/connect/login?{urlencode(params)}"
    
    def get_access_token_from_request_token(self, request_token: str) -> Optional[str]:
        """Convert request token to access token"""
        try:
            # Create checksum
            checksum_data = self.api_key + request_token + self.api_secret
            checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
            
            # Make request
            url = "https://api.kite.trade/session/token"
            data = {
                "api_key": self.api_key,
                "request_token": request_token,
                "checksum": checksum
            }
            
            response = requests.post(url, data=data)
            result = response.json()
            
            if response.status_code == 200 and "data" in result:
                access_token = result["data"]["access_token"]
                
                # Calculate expiry (end of trading day - 3:30 PM IST)
                now = datetime.now()
                expiry = now.replace(hour=15, minute=30, second=0, microsecond=0)
                if now.hour >= 15 and now.minute >= 30:
                    expiry += timedelta(days=1)
                
                # Save token data
                token_data = {
                    'access_token': access_token,
                    'created_at': now.isoformat(),
                    'expires_at': expiry.isoformat()
                }
                self.save_token_data(token_data)
                
                # Update instance variables
                self.current_token = access_token
                self.token_expiry = expiry
                
                # Update config file
                self.update_config_file(access_token)
                
                logger.info(f"New access token generated: {access_token[:20]}...")
                return access_token
                
            else:
                logger.error(f"Failed to generate access token: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating access token: {e}")
            return None
    
    def interactive_token_refresh(self) -> Optional[str]:
        """Interactive token generation (opens browser)"""
        print("\n🔄 Token Refresh Required")
        print("=" * 50)
        
        # Generate login URL
        login_url = self.generate_login_url()
        print(f"🌐 Login URL: {login_url}")
        
        # Open browser
        try:
            print("📱 Opening browser for login...")
            webbrowser.open(login_url)
        except:
            print("⚠️ Could not open browser automatically")
        
        print("\n" + "="*60)
        print("📋 STEPS:")
        print("1. Complete login in browser")
        print("2. Copy request_token from redirect URL")
        print("="*60)
        
        # Get request token
        request_token = input("\n🔤 Paste request_token: ").strip()
        
        if request_token:
            return self.get_access_token_from_request_token(request_token)
        
        return None
    
    def get_valid_token(self, interactive: bool = True) -> Optional[str]:
        """Get a valid access token (refresh if needed)"""
        # Load existing token
        token_data = self.load_token_data()
        
        if token_data:
            self.current_token = token_data.get('access_token')
            expires_at = token_data.get('expires_at')
            if expires_at:
                self.token_expiry = datetime.fromisoformat(expires_at)
        
        # Check if current token is valid
        if self.is_token_valid():
            logger.info("Current token is valid")
            return self.current_token
        
        # Token invalid/expired, need refresh
        logger.info("Token refresh required")
        
        if interactive:
            return self.interactive_token_refresh()
        else:
            logger.warning("Token expired and interactive mode disabled")
            return None
    
    def schedule_daily_refresh(self):
        """Schedule daily token refresh"""
        # Schedule refresh at 8:00 AM (before market opens)
        schedule.every().day.at("08:00").do(self._daily_refresh_job)
        
        # Start scheduler in background thread
        self.is_running = True
        self.refresh_thread = threading.Thread(target=self._run_scheduler)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
        
        logger.info("Daily token refresh scheduled for 8:00 AM")
    
    def _daily_refresh_job(self):
        """Daily refresh job (non-interactive)"""
        logger.info("Running scheduled token refresh...")
        
        # For automated refresh, you'd need to implement one of:
        # 1. Store refresh token (if API supports it)
        # 2. Use headless browser automation
        # 3. Use alternative authentication method
        
        # For now, just log that manual refresh is needed
        logger.warning("Manual token refresh required - run token manager interactively")
        
        # You could also send notification, email, etc.
        self._send_refresh_notification()
    
    def _send_refresh_notification(self):
        """Send notification that token refresh is needed"""
        # You can implement email, slack, etc. notifications here
        print("\n⚠️ TOKEN REFRESH NEEDED ⚠️")
        print("Your Kite access token has expired.")
        print("Run: python KiteApi/token_manager.py")
        print("=" * 50)
    
    def _run_scheduler(self):
        """Run the scheduler in background"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def stop_scheduler(self):
        """Stop the background scheduler"""
        self.is_running = False
        if self.refresh_thread:
            self.refresh_thread.join()

def main():
    """Interactive token management"""
    try:
        from kite_config import API_KEY, API_SECRET
    except ImportError:
        print("❌ Could not import API credentials from kite_config.py")
        return
    
    manager = KiteTokenManager(API_KEY, API_SECRET)
    
    print("🔑 Kite Token Manager")
    print("=" * 30)
    
    # Get valid token
    token = manager.get_valid_token(interactive=True)
    
    if token:
        print(f"✅ Valid token: {token[:20]}...")
        
        # Ask about scheduling
        schedule_refresh = input("\n📅 Schedule daily refresh checks? (y/n): ").strip().lower()
        if schedule_refresh == 'y':
            manager.schedule_daily_refresh()
            print("✅ Daily refresh scheduled!")
            
            # Keep running to maintain scheduler
            try:
                print("🔄 Scheduler running... Press Ctrl+C to stop")
                while True:
                    time.sleep(10)
            except KeyboardInterrupt:
                print("\n⏹️ Stopping scheduler...")
                manager.stop_scheduler()
    else:
        print("❌ Could not get valid token")

if __name__ == "__main__":
    main()