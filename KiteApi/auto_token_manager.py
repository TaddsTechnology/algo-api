#!/usr/bin/env python3
"""
Lightweight Automated Kite Token Manager
Works without Supabase dependencies - uses file storage instead
"""

import os
import json
import time
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional
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

class LightweightKiteTokenManager:
    """Lightweight automated Kite token manager with file storage"""
    
    def __init__(self, api_key: str, api_secret: str, user_id: str, password: str, 
                 pin: str = None, totp_secret: str = None):
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.user_id = user_id
        self.password = password
        self.pin = pin
        self.totp_secret = totp_secret
        
        # State management
        self.current_token = None
        self.token_expiry = None
        self.token_file = os.path.join(os.path.dirname(__file__), '..', 'kite_token_cache.json')
        
        # Initialize
        self._load_token_from_file()
    
    def _load_token_from_file(self):
        """Load current token from file"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, 'r') as f:
                    token_data = json.load(f)
                
                self.current_token = token_data['access_token']
                self.token_expiry = datetime.fromisoformat(token_data['expires_at'])
                logger.info(f"Token loaded from file: {self.current_token[:20]}...")
            else:
                logger.info("No token file found")
                
        except Exception as e:
            logger.error(f"Failed to load token from file: {e}")
    
    def _save_token_to_file(self, access_token: str, expires_at: datetime):
        """Save token to file"""
        try:
            token_data = {
                'access_token': access_token,
                'api_key': self.api_key,
                'expires_at': expires_at.isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            
            logger.info("Token saved to file successfully")
            
        except Exception as e:
            logger.error(f"Failed to save token to file: {e}")
    
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
                logger.warning(f"Token validation failed: {response.status_code}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Token API test failed: {e}")
            return False
    
    def _generate_token_automatically(self):
        """Generate access token automatically using Selenium with Firefox"""
        logger.info("Starting automated token generation...")
        
        try:
            # Use Firefox instead of Chrome for better HF Space compatibility
            from selenium import webdriver
            from selenium.webdriver.firefox.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.firefox import GeckoDriverManager
            import time
            
            # Setup Firefox options
            firefox_options = Options()
            firefox_options.add_argument("--headless")  # Run in background
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-dev-shm-usage")
            
            # Initialize Firefox driver
            logger.info("Initializing Firefox WebDriver...")
            driver = webdriver.Firefox(
                executable_path=GeckoDriverManager().install(),
                options=firefox_options
            )
            
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
                
                # Calculate expiry (typically valid until 9 AM next day)
                now = datetime.now()
                expiry = now + timedelta(hours=23)  # ~24 hours
                
                # Update state
                self.current_token = access_token
                self.token_expiry = expiry
                
                # Save to file
                self._save_token_to_file(access_token, expiry)
                
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
                r'ACCESS_TOKEN = [^\n]*',
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
        
        new_token = self._generate_token_automatically()
        
        if new_token:
            logger.info("✅ Token refreshed automatically!")
            return new_token
        else:
            logger.error("❌ Automated token refresh failed")
            return None

def setup_lightweight_kite_manager():
    """Setup function to initialize lightweight token manager"""
    
    try:
        # Add parent directory to path
        import sys
        import os
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        # Import configuration
        from kite_config import API_KEY, API_SECRET, USER_ID, PASSWORD, TOTP_SECRET
        PIN = None  # PIN is optional since we're using TOTP
        
        manager = LightweightKiteTokenManager(
            api_key=API_KEY,
            api_secret=API_SECRET, 
            user_id=USER_ID,
            password=PASSWORD,
            pin=PIN,
            totp_secret=TOTP_SECRET
        )
        
        return manager
        
    except ImportError as e:
        logger.error(f"Missing configuration: {e}")
        return None

def main():
    """Main function to run automated token manager"""
    
    print("🤖 Lightweight Automated Kite Token Manager")
    print("=" * 40)
    
    manager = setup_lightweight_kite_manager()
    
    if not manager:
        print("❌ Setup failed - check configuration")
        return
    
    # Get valid token (refresh if needed)
    token = manager.get_valid_token()
    
    if token:
        print(f"✅ Valid token available: {token[:20]}...")
        print("\n🔄 Your system is now fully automated!")
        print("🎯 Tokens will be automatically refreshed")
        print("📊 Tokens stored in local file cache")
        print("⏰ No manual intervention required")
    else:
        print("❌ Could not get valid token")

if __name__ == "__main__":
    main()