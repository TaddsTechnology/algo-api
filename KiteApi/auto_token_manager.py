#!/usr/bin/env python3
"""
Fully Automated Kite Token Manager with Supabase Storage

This system automatically handles token refresh using headless browser automation
and stores tokens in Supabase for persistence across sessions.
"""

import os
import json
import time
import hashlib
import logging
import schedule
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from supabase import create_client, Client
import requests

# Try to import browser automation (install if needed)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium or webdriver-manager not installed. Run: pip install selenium webdriver-manager")

# Try to import TOTP library
try:
    import pyotp
    TOTP_AVAILABLE = True
except ImportError:
    TOTP_AVAILABLE = False
    print("⚠️ pyotp not installed. Run: pip install pyotp")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoKiteTokenManager:
    """Fully automated Kite token manager with Supabase storage"""
    
    def __init__(self, api_key: str, api_secret: str, user_id: str, password: str, 
                 supabase_url: str, supabase_key: str, pin: str = None, totp_secret: str = None,
                 app_name: str = "kite_trading"):
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = user_id
        self.password = password
        self.pin = pin
        self.totp_secret = totp_secret
        self.app_name = app_name
        
        # Supabase setup
        self.supabase: Client = create_client(supabase_url, supabase_key)
        
        # State management
        self.current_token = None
        self.token_expiry = None
        self.is_running = False
        self.refresh_thread = None
        
        # Initialize
        self._setup_supabase_table()
        self._load_token_from_supabase()
    
    def _setup_supabase_table(self):
        """Setup Supabase table for token storage"""
        try:
            # Check if table exists, create if not
            table_query = """
            CREATE TABLE IF NOT EXISTS kite_tokens (
                id SERIAL PRIMARY KEY,
                app_name TEXT UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                api_key TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
            
            # Use RPC to execute SQL (if you have permissions)
            # Otherwise, ensure table exists in your Supabase dashboard
            logger.info("Ensure 'kite_tokens' table exists in your Supabase dashboard")
            
        except Exception as e:
            logger.warning(f"Could not setup table automatically: {e}")
    
    def _load_token_from_supabase(self):
        """Load current token from Supabase"""
        try:
            result = self.supabase.table('kite_tokens').select('*').eq('app_name', self.app_name).execute()
            
            if result.data:
                token_data = result.data[0]
                self.current_token = token_data['access_token']
                self.token_expiry = datetime.fromisoformat(token_data['expires_at'].replace('Z', '+00:00'))
                logger.info(f"Token loaded from Supabase: {self.current_token[:20]}...")
            else:
                logger.info("No token found in Supabase")
                
        except Exception as e:
            logger.error(f"Failed to load token from Supabase: {e}")
    
    def _save_token_to_supabase(self, access_token: str, expires_at: datetime):
        """Save token to Supabase"""
        try:
            token_data = {
                'app_name': self.app_name,
                'access_token': access_token,
                'api_key': self.api_key,
                'expires_at': expires_at.isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Upsert (insert or update)
            self.supabase.table('kite_tokens').upsert(token_data, on_conflict='app_name').execute()
            logger.info("Token saved to Supabase successfully")
            
        except Exception as e:
            logger.error(f"Failed to save token to Supabase: {e}")
    
    def is_token_valid(self) -> bool:
        """Check if current token is still valid"""
        if not self.current_token:
            return False
            
        # Check expiry
        if self.token_expiry and datetime.now() > self.token_expiry:
            logger.info("Token expired by time")
            return False
            
        # Test with API
        return self._test_token_api(self.current_token)
    
    def _test_token_api(self, token: str) -> bool:
        """Test token with Kite API"""
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
            
            is_valid = response.status_code == 200
            if not is_valid:
                logger.warning(f"Token validation failed: {response.status_code} - {response.text}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Token API test failed: {e}")
            return False
    
    def _generate_new_token_automated(self) -> Optional[str]:
        """Generate new token using automated browser"""
        if not SELENIUM_AVAILABLE:
            logger.error("Selenium not available for automated token generation")
            return None
        
        try:
            logger.info("Starting automated token generation...")
            
            # Setup headless Chrome
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            
            # Initialize driver with webdriver-manager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            try:
                # Step 1: Go to Kite login
                login_url = f"https://kite.trade/connect/login?api_key={self.api_key}&v=3"
                driver.get(login_url)
                
                # Step 2: Login
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "userid"))
                )
                
                driver.find_element(By.ID, "userid").send_keys(self.user_id)
                driver.find_element(By.ID, "password").send_keys(self.password)
                driver.find_element(By.CLASS_NAME, "button-orange").click()
                
                # Step 3: Enter PIN/TOTP
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "pin"))
                )
                
                # Generate TOTP if secret is provided, otherwise use static PIN
                if self.totp_secret and TOTP_AVAILABLE:
                    totp = pyotp.TOTP(self.totp_secret)
                    pin_value = totp.now()
                    logger.info(f"Generated TOTP code: {pin_value}")
                elif self.pin:
                    pin_value = self.pin
                    logger.info("Using static PIN")
                else:
                    logger.error("No PIN or TOTP secret provided")
                    return None
                
                driver.find_element(By.ID, "pin").send_keys(pin_value)
                driver.find_element(By.CLASS_NAME, "button-orange").click()
                
                # Step 4: Wait for redirect and extract request_token
                WebDriverWait(driver, 15).until(
                    lambda d: "request_token=" in d.current_url
                )
                
                current_url = driver.current_url
                logger.info(f"Redirect URL: {current_url}")
                
                # Extract request_token
                if "request_token=" in current_url:
                    request_token = current_url.split("request_token=")[1].split("&")[0]
                    logger.info(f"Request token extracted: {request_token[:20]}...")
                    
                    # Convert to access token
                    access_token = self._convert_request_to_access_token(request_token)
                    return access_token
                
                logger.error("Could not extract request_token from URL")
                return None
                
            finally:
                driver.quit()
                
        except Exception as e:
            logger.error(f"Automated token generation failed: {e}")
            return None
    
    def _convert_request_to_access_token(self, request_token: str) -> Optional[str]:
        """Convert request token to access token"""
        try:
            # Create checksum
            checksum_data = self.api_key + request_token + self.api_secret
            checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
            
            # Make API call
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
                
                # Calculate expiry
                now = datetime.now()
                expiry = now.replace(hour=15, minute=30, second=0, microsecond=0)
                if now.hour >= 15 and now.minute >= 30:
                    expiry += timedelta(days=1)
                
                # Update state
                self.current_token = access_token
                self.token_expiry = expiry
                
                # Save to Supabase
                self._save_token_to_supabase(access_token, expiry)
                
                # Update config file
                self._update_config_file(access_token)
                
                logger.info(f"New access token generated: {access_token[:20]}...")
                return access_token
                
            else:
                logger.error(f"Failed to convert request token: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error converting request token: {e}")
            return None
    
    def _update_config_file(self, access_token: str):
        """Update kite_config.py with new token"""
        try:
            import re
            config_path = os.path.join(os.path.dirname(__file__), '..', 'kite_config.py')
            
            with open(config_path, 'r') as f:
                content = f.read()
            
            # Replace ACCESS_TOKEN
            updated_content = re.sub(
                r'ACCESS_TOKEN = ".*?"',
                f'ACCESS_TOKEN = "{access_token}"',
                content
            )
            
            with open(config_path, 'w') as f:
                f.write(updated_content)
                
            logger.info("Config file updated with new token")
            
        except Exception as e:
            logger.error(f"Failed to update config file: {e}")
    
    def get_valid_token(self) -> Optional[str]:
        """Get a valid token - refresh automatically if needed"""
        # Check if current token is valid
        if self.is_token_valid():
            logger.info("Current token is valid")
            return self.current_token
        
        # Need to refresh
        logger.info("Token refresh required - generating new token...")
        
        new_token = self._generate_new_token_automated()
        
        if new_token:
            logger.info("✅ Token refreshed automatically!")
            return new_token
        else:
            logger.error("❌ Automated token refresh failed")
            return None
    
    def start_automated_refresh_service(self):
        """Start background service for automated token refresh"""
        
        # Schedule refresh checks
        schedule.every().day.at("07:30").do(self._automated_refresh_job)  # Before market opens
        schedule.every().day.at("15:45").do(self._automated_refresh_job)  # After market closes
        
        # Start background thread
        self.is_running = True
        self.refresh_thread = threading.Thread(target=self._run_scheduler)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
        
        logger.info("🔄 Automated refresh service started")
        logger.info("📅 Scheduled: 7:30 AM and 3:45 PM daily")
    
    def _automated_refresh_job(self):
        """Automated refresh job"""
        logger.info("Running automated token refresh check...")
        
        if not self.is_token_valid():
            logger.info("Token invalid - refreshing automatically...")
            
            new_token = self.get_valid_token()
            
            if new_token:
                logger.info("✅ Token refreshed automatically")
                
                # Optionally restart your trading scripts here
                self._restart_trading_scripts()
                
            else:
                logger.error("❌ Automated refresh failed")
                self._send_alert("Token refresh failed - manual intervention needed")
        else:
            logger.info("✅ Token still valid")
    
    def _restart_trading_scripts(self):
        """Restart trading scripts with new token"""
        # Add your script restart logic here
        logger.info("🔄 Trading scripts would restart here")
        
        # Example:
        # os.system("python your_trading_script.py &")
    
    def _send_alert(self, message: str):
        """Send alert notification (email, telegram, etc.)"""
        logger.warning(f"ALERT: {message}")
        # Add your notification logic here
        # - Email
        # - Telegram bot
        # - Slack webhook
        # etc.
    
    def _run_scheduler(self):
        """Run scheduler in background"""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)
    
    def stop_service(self):
        """Stop the background service"""
        self.is_running = False
        if self.refresh_thread:
            self.refresh_thread.join()
        logger.info("Service stopped")

def setup_automated_kite_manager():
    """Setup function to initialize automated token manager"""
    
    try:
        # Try environment-aware configs first
        try:
            from kite_config_hf import API_KEY, API_SECRET, USER_ID, PASSWORD, PIN, TOTP_SECRET
        except ImportError:
            from kite_config import API_KEY, API_SECRET, USER_ID, PASSWORD, PIN, TOTP_SECRET
        
        try:
            from supabase_config_hf import SUPABASE_URL, SUPABASE_KEY
        except ImportError:
            from supabase_config import SUPABASE_URL, SUPABASE_KEY
        
        manager = AutoKiteTokenManager(
            api_key=API_KEY,
            api_secret=API_SECRET, 
            user_id=USER_ID,
            password=PASSWORD,
            pin=PIN if 'PIN' in locals() else None,
            totp_secret=TOTP_SECRET if 'TOTP_SECRET' in locals() else None,
            supabase_url=SUPABASE_URL,
            supabase_key=SUPABASE_KEY
        )
        
        return manager
        
    except ImportError as e:
        logger.error(f"Missing configuration: {e}")
        logger.error("Create supabase_config.py with SUPABASE_URL and SUPABASE_KEY")
        return None

def main():
    """Main function to run automated token manager"""
    
    print("🤖 Automated Kite Token Manager")
    print("=" * 40)
    
    manager = setup_automated_kite_manager()
    
    if not manager:
        print("❌ Setup failed - check configuration")
        return
    
    # Get valid token (refresh if needed)
    token = manager.get_valid_token()
    
    if token:
        print(f"✅ Valid token available: {token[:20]}...")
        
        # Start automated service
        manager.start_automated_refresh_service()
        
        print("\n🔄 Automated service started!")
        print("🎯 Your software will now auto-refresh tokens")
        print("📊 Tokens stored in Supabase")
        print("⏰ Checks scheduled: 7:30 AM & 3:45 PM")
        
        try:
            print("\n⌨️ Press Ctrl+C to stop service")
            while True:
                time.sleep(10)
                
        except KeyboardInterrupt:
            print("\n⏹️ Stopping service...")
            manager.stop_service()
            print("✅ Service stopped")
    
    else:
        print("❌ Could not get valid token")

if __name__ == "__main__":
    main()