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
            # Force Firefox usage for HF Space compatibility
            from selenium import webdriver
            from selenium.webdriver.firefox.service import Service as FirefoxService
            from selenium.webdriver.firefox.options import Options as FirefoxOptions
            from selenium.webdriver.common.by import By
            from selenium.webdriver.common.keys import Keys
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, NoSuchElementException
            import geckodriver_autoinstaller
            import time
            import os
            
            # Setup Firefox options
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")  # Run in background
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-dev-shm-usage")
            firefox_options.add_argument("--disable-dev-tools")
            
            # Auto install geckodriver with error handling
            try:
                geckodriver_autoinstaller.install()
            except PermissionError:
                logger.warning("Permission denied for geckodriver installation, using system geckodriver...")
            except Exception as e:
                logger.warning(f"Geckodriver installation warning: {e}")
            
            # Initialize Firefox driver with explicit service
            logger.info("Initializing Firefox WebDriver...")
            try:
                service = FirefoxService()
                driver = webdriver.Firefox(service=service, options=firefox_options)
            except Exception as e:
                logger.warning(f"Failed to initialize Firefox with service: {e}")
                # Try without explicit service
                driver = webdriver.Firefox(options=firefox_options)
            
            # Set implicit wait
            driver.implicitly_wait(10)
            
            try:
                # Step 1: Go to Kite login
                logger.info("Navigating to Kite login page...")
                driver.get(f"https://kite.zerodha.com/connect/login?api_key={self.api_key}")
                
                # Wait for and fill user ID with robust waiting
                logger.info("Waiting for user ID field...")
                user_id_field = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@id='userid' or @placeholder='User ID (eg: AB1234)' or @type='text']"))
                )
                user_id_field.clear()
                user_id_field.send_keys(self.user_id)
                
                # Wait for and fill password with robust waiting
                logger.info("Waiting for password field...")
                password_field = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@id='password' or @placeholder='Password' or @type='password']"))
                )
                password_field.clear()
                password_field.send_keys(self.password)
                
                # Click login button
                logger.info("Clicking login button...")
                login_button = WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' or contains(text(), 'Login') or contains(@class, 'button')]"))
                )
                login_button.click()
                
                # Wait for PIN/TOTP field (could be either)
                logger.info("Waiting for PIN/TOTP field...")
                time.sleep(2)  # Brief pause for transition
                
                # Try multiple selectors for PIN/TOTP field
                pin_field = None
                totp_selectors = [
                    "//input[@id='pin' or @id='totp' or @id='twofa' or @placeholder='TWO FA' or @placeholder='PIN']",
                    "//input[@type='number' or @type='text' and contains(@placeholder, 'PIN')]",
                    "//input[contains(@class, 'pin') or contains(@class, 'totp')]"
                ]
                
                for selector in totp_selectors:
                    try:
                        pin_field = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if pin_field:
                            logger.info(f"Found PIN/TOTP field with selector: {selector}")
                            break
                    except TimeoutException:
                        continue
                
                if not pin_field:
                    raise TimeoutException("Could not find PIN/TOTP field")
                
                # Generate TOTP code
                logger.info("Generating TOTP code...")
                import pyotp
                totp = pyotp.TOTP(self.totp_secret)
                totp_code = totp.now()
                
                # Fill PIN/TOTP field
                pin_field.clear()
                pin_field.send_keys(totp_code)
                
                # Click continue/submit button
                logger.info("Submitting TOTP code...")
                submit_buttons = [
                    "//button[@type='submit' or contains(text(), 'Continue') or contains(text(), 'Submit') or contains(text(), 'Login')]",
                    "//button[contains(@class, 'button') or contains(@class, 'btn') or contains(@class, 'submit')]",
                    "//input[@type='submit']",
                    "//button",
                    "//input[@type='button' and contains(@value, 'Continue') or contains(@value, 'Submit') or contains(@value, 'Login')]"
                ]
                
                submit_button = None
                for selector in submit_buttons:
                    try:
                        submit_button = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if submit_button:
                            logger.info(f"Found submit button with selector: {selector}")
                            # Log button text for debugging
                            button_text = submit_button.text
                            button_value = submit_button.get_attribute("value")
                            logger.info(f"Button text: '{button_text}', value: '{button_value}'")
                            break
                    except TimeoutException:
                        continue
                
                if not submit_button:
                    logger.warning("Could not find submit button with explicit search, trying to find any clickable button...")
                    # Try to find any button and click the first one
                    try:
                        buttons = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.TAG_NAME, "button"))
                        )
                        if buttons:
                            submit_button = buttons[0]
                            logger.info(f"Found {len(buttons)} buttons, clicking the first one")
                            button_text = submit_button.text
                            button_value = submit_button.get_attribute("value")
                            logger.info(f"First button text: '{button_text}', value: '{button_value}'")
                        else:
                            raise TimeoutException("No buttons found on page")
                    except TimeoutException:
                        # Last resort: try pressing Enter in the TOTP field
                        logger.warning("No buttons found, trying to submit by pressing Enter in TOTP field...")
                        pin_field.send_keys(Keys.RETURN)
                        time.sleep(3)  # Wait for submission
                
                if submit_button:
                    # Scroll to button and click
                    driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                    time.sleep(1)  # Wait for scroll
                    submit_button.click()
                
                # Wait for redirect and extract request token
                logger.info("Waiting for redirect and request token...")
                time.sleep(5)  # Wait for redirect
                
                # Log current URL for debugging
                current_url = driver.current_url
                logger.info(f"Current URL: {current_url}")
                logger.info(f"Page title: {driver.title}")
                
                # Save page source for debugging if needed
                if "request_token" not in current_url:
                    logger.warning("Request token not found in URL, saving page source for debugging...")
                    with open("/tmp/kite_login_debug.html", "w") as f:
                        f.write(driver.page_source)
                    # Also save screenshot if possible
                    try:
                        driver.save_screenshot("/tmp/kite_login_debug.png")
                        logger.info("Saved debug screenshot to /tmp/kite_login_debug.png")
                    except Exception as screenshot_error:
                        logger.warning(f"Could not save screenshot: {screenshot_error}")
                
                # Extract request token from URL
                from urllib.parse import parse_qs, urlparse
                parsed_url = urlparse(current_url)
                query_params = parse_qs(parsed_url.query)
                
                request_token = query_params.get('request_token', [None])[0]
                if not request_token:
                    raise Exception(f"Request token not found in URL. Current URL: {current_url}")
                
                logger.info(f"Successfully extracted request token: {request_token[:10]}...")
                
                # Step 2: Exchange request token for access token
                logger.info("Exchanging request token for access token...")
                from kiteconnect import KiteConnect
                kite = KiteConnect(api_key=self.api_key)
                data = kite.generate_session(request_token, api_secret=self.api_secret)
                access_token = data["access_token"]
                
                logger.info("✅ Successfully generated access token!")
                return access_token
                
            finally:
                # Close driver
                try:
                    driver.quit()
                except Exception as e:
                    logger.warning(f"Error closing driver: {e}")
                    
        except Exception as e:
            logger.error(f"Automated token generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
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