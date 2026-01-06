#!/usr/bin/env python3
"""
Lightweight Automated Kite Token Manager
Works without Supabase dependencies - uses file storage instead

Handles CAPTCHA and other authentication challenges with multiple browser strategies
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
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
    import chromedriver_autoinstaller
    import geckodriver_autoinstaller
    SELENIUM_AVAILABLE = True
except ImportError as e:
    SELENIUM_AVAILABLE = False
    print(f"⚠️ Selenium components not available: {e}")
    print("Run: pip install selenium webdriver-manager chromedriver-autoinstaller geckodriver-autoinstaller")

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
            
            # Save to JSON cache file
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            
            logger.info("Token saved to cache file successfully")
            
            # ALSO update kite_config.py file
            try:
                config_path = os.path.join(os.path.dirname(__file__), '..', 'kite_config.py')
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config_content = f.read()
                    
                    # Update ACCESS_TOKEN line
                    import re
                    updated_content = re.sub(
                        r'ACCESS_TOKEN = ".*"', 
                        f'ACCESS_TOKEN = "{access_token}"', 
                        config_content
                    )
                    
                    with open(config_path, 'w') as f:
                        f.write(updated_content)
                    
                    logger.info("Token also saved to kite_config.py successfully")
                else:
                    logger.warning("kite_config.py not found, only saving to cache file")
            except Exception as config_error:
                logger.error(f"Failed to update kite_config.py: {config_error}")
            
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
    
    def _setup_chrome_driver(self):
        """Setup Chrome WebDriver with proper configuration"""
        try:
            logger.info("Setting up Chrome WebDriver...")
            
            # Auto-install ChromeDriver
            try:
                chromedriver_autoinstaller.install()
            except Exception as e:
                logger.warning(f"ChromeDriver auto-installation warning: {e}")
            
            chrome_options = ChromeOptions()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-dev-tools")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")
            chrome_options.add_argument("--disable-javascript")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Enable JavaScript only when needed
            chrome_options.add_argument("--enable-javascript")
            
            service = ChromeService()
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Chrome WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Chrome WebDriver setup failed: {e}")
            return None
    
    def _setup_firefox_driver(self):
        """Setup Firefox WebDriver with proper configuration"""
        try:
            logger.info("Setting up Firefox WebDriver...")
            
            # Auto-install GeckoDriver
            try:
                geckodriver_autoinstaller.install()
            except Exception as e:
                logger.warning(f"GeckoDriver auto-installation warning: {e}")
            
            firefox_options = FirefoxOptions()
            firefox_options.add_argument("--headless")
            firefox_options.add_argument("--no-sandbox")
            firefox_options.add_argument("--disable-dev-shm-usage")
            firefox_options.add_argument("--disable-dev-tools")
            
            service = FirefoxService()
            driver = webdriver.Firefox(service=service, options=firefox_options)
            
            logger.info("Firefox WebDriver initialized successfully")
            return driver
        except Exception as e:
            logger.error(f"Firefox WebDriver setup failed: {e}")
            return None
    
    def _generate_token_automatically(self):
        """Generate access token automatically using Selenium with multiple browser strategies"""
        logger.info("Starting automated token generation...")
        logger.info("⚠️  NOTE: If you encounter persistent CAPTCHA issues, consider using a dedicated authentication service")
        
        if not SELENIUM_AVAILABLE:
            logger.error("Selenium not available. Please install required packages:")
            logger.error("pip install selenium webdriver-manager chromedriver-autoinstaller geckodriver-autoinstaller")
            return None
            
        if not TOTP_AVAILABLE:
            logger.error("pyotp not available. Please install: pip install pyotp")
            return None
        
        # Try multiple browser strategies
        browsers = [
            ("Chrome", self._setup_chrome_driver),
            ("Firefox", self._setup_firefox_driver)
        ]
        
        driver = None
        for browser_name, setup_func in browsers:
            try:
                logger.info(f"Attempting authentication with {browser_name}...")
                driver = setup_func()
                if driver:
                    break
            except Exception as e:
                logger.warning(f"{browser_name} setup failed: {e}")
                continue
        
        if not driver:
            logger.error("Failed to initialize any WebDriver")
            return None
        
        try:
            # Set implicit wait
            driver.implicitly_wait(10)
            
            # Step 1: Go to Kite login
            logger.info("Navigating to Kite login page...")
            driver.get(f"https://kite.zerodha.com/connect/login?api_key={self.api_key}")
            
            # Check for CAPTCHA early
            if self._check_for_captcha(driver):
                logger.warning("CAPTCHA detected. Trying to proceed anyway...")
            
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
            
            # Wait for next page and check for login errors
            time.sleep(3)
            self._check_for_errors(driver, "after login attempt")
            
            # Wait for PIN/TOTP field (could be either) - this appears AFTER login
            logger.info("Waiting for PIN/TOTP field (after login)...")
            time.sleep(5)  # Increased wait time for page transition and dynamic loading
            
            # Check again for errors
            self._check_for_errors(driver, "after TOTP page load")
            
            # Check for CAPTCHA on TOTP page
            if self._check_for_captcha(driver):
                logger.warning("CAPTCHA detected on TOTP page. This may affect automation.")
            
            # Try multiple selectors for PIN/TOTP field with explicit waits
            pin_field = None
            totp_selectors = [
                "//input[@id='pin' or @id='totp' or @id='twofa']",
                "//input[@placeholder='TWO FA' or @placeholder='PIN']",
                "//input[@type='number' and @maxlength='6']",
                "//input[@type='text' and @maxlength='6']",
                "//input[@type='number']",
                "//input[@type='text' and contains(@placeholder, 'PIN')]",
                "//input[contains(@class, 'pin') or contains(@class, 'totp')]",
                "//input[@type='text']"  # Last resort - any text input
            ]
            
            # Try each selector with explicit wait
            for i, selector in enumerate(totp_selectors):
                try:
                    logger.info(f"Trying selector {i+1}/{len(totp_selectors)}: {selector}")
                    pin_field = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    if pin_field:
                        logger.info(f"Found PIN/TOTP field with selector: {selector}")
                        break
                except TimeoutException:
                    logger.debug(f"Selector {selector} timed out")
                    continue
            
            if not pin_field:
                # Take screenshot for debugging
                try:
                    driver.save_screenshot("login_page_debug.png")
                    logger.info("Saved debug screenshot as login_page_debug.png")
                    
                    # Print page source for debugging
                    with open("page_source_debug.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    logger.info("Saved page source as page_source_debug.html")
                    
                    # Try to find all input elements for debugging
                    try:
                        all_inputs = driver.find_elements(By.TAG_NAME, "input")
                        logger.info(f"Found {len(all_inputs)} input elements on page:")
                        for i, inp in enumerate(all_inputs):
                            inp_id = inp.get_attribute("id") or "no-id"
                            inp_type = inp.get_attribute("type") or "no-type"
                            inp_placeholder = inp.get_attribute("placeholder") or "no-placeholder"
                            inp_name = inp.get_attribute("name") or "no-name"
                            logger.info(f"  Input {i}: id='{inp_id}', type='{inp_type}', placeholder='{inp_placeholder}', name='{inp_name}'")
                    except Exception as input_debug_error:
                        logger.warning(f"Failed to list input elements: {input_debug_error}")
                except Exception as debug_error:
                    logger.warning(f"Failed to save debug info: {debug_error}")
                
                logger.error("❌ Could not find PIN/TOTP field after login")
                logger.error("This could be due to:")
                logger.error("  1. Incorrect credentials")
                logger.error("  2. CAPTCHA challenge")
                logger.error("  3. Network issues")
                logger.error("  4. Zerodha's anti-bot measures")
                return None
            
            # Generate TOTP code
            logger.info("Generating TOTP code...")
            import pyotp
            totp = pyotp.TOTP(self.totp_secret)
            totp_code = totp.now()
            
            # Fill PIN/TOTP field
            pin_field.clear()
            pin_field.send_keys(totp_code)
            
            # Wait a moment for the field to be filled
            time.sleep(1)
            
            # Click continue/submit button
            logger.info("Submitting TOTP code...")
            submit_buttons = [
                "//button[@type='submit']",
                "//button[contains(text(), 'Continue') or contains(text(), 'Submit') or contains(text(), 'Login')]",
                "//button[contains(@class, 'button') or contains(@class, 'btn') or contains(@class, 'submit')]",
                "//input[@type='submit']",
                "//button",
                "//input[@type='button']"
            ]
            
            submit_button = None
            for i, selector in enumerate(submit_buttons):
                try:
                    logger.info(f"Trying submit button selector {i+1}/{len(submit_buttons)}: {selector}")
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
                    logger.debug(f"Submit button selector {selector} timed out")
                    continue
            
            if not submit_button:
                logger.warning("Could not find submit button with explicit search, trying to find any clickable button...")
                # Try to find any button and click the first one
                try:
                    buttons = WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.TAG_NAME, "button"))
                    )
                    if buttons:
                        # Filter out invisible/non-interactable buttons
                        clickable_buttons = []
                        for i, btn in enumerate(buttons):
                            try:
                                # Check if button is displayed and enabled
                                if btn.is_displayed() and btn.is_enabled():
                                    button_text = btn.text.strip()
                                    button_value = btn.get_attribute("value") or ""
                                    button_id = btn.get_attribute("id") or ""
                                    button_class = btn.get_attribute("class") or ""
                                    
                                    logger.info(f"Button {i}: text='{button_text}', value='{button_value}', id='{button_id}', class='{button_class}'")
                                    
                                    # Skip reset/pref buttons
                                    if "reset" in button_text.lower() or "pref" in button_id.lower() or "cancel" in button_text.lower():
                                        continue
                                    
                                    # Prefer buttons with text like "continue", "submit", "login"
                                    if any(keyword in button_text.lower() or keyword in button_value.lower() for keyword in ["continue", "submit", "login", "proceed"]):
                                        submit_button = btn
                                        logger.info(f"Selected submit button with keyword: {button_text}")
                                        break
                                    
                                    clickable_buttons.append(btn)
                            except Exception as e:
                                logger.debug(f"Error checking button {i}: {e}")
                                continue
                        
                        # If we found a good button, use it
                        if not submit_button and clickable_buttons:
                            submit_button = clickable_buttons[0]
                            logger.info(f"Found {len(clickable_buttons)} clickable buttons, clicking the first suitable one")
                            button_text = submit_button.text
                            button_value = submit_button.get_attribute("value")
                            logger.info(f"Selected button text: '{button_text}', value: '{button_value}'")
                        elif not submit_button:
                            raise TimeoutException("No suitable buttons found on page")
                    else:
                        raise TimeoutException("No buttons found on page")
                except TimeoutException:
                    # Last resort: try pressing Enter in the TOTP field
                    logger.warning("No suitable buttons found, trying to submit by pressing Enter in TOTP field...")
                    pin_field.send_keys("\n")
                    time.sleep(3)  # Wait for submission
            
            # Wait a moment for submission
            time.sleep(2)
            
            # IMMEDIATELY extract request token BEFORE any potential redirect errors
            logger.info("Immediately extracting request token...")
            try:
                current_url = driver.current_url
                logger.info(f"Current URL: {current_url}")
                
                from urllib.parse import parse_qs, urlparse
                parsed_url = urlparse(current_url)
                query_params = parse_qs(parsed_url.query)
                request_token = query_params.get('request_token', [None])[0]
                
                if request_token:
                    logger.info(f"SUCCESS: Got request token before any errors: {request_token[:10]}...")
                    # Save request token temporarily in case of errors
                    self._temp_request_token = request_token
                else:
                    logger.warning("No request token in URL yet, continuing...")
            except Exception as url_error:
                logger.warning(f"Could not get URL immediately: {url_error}")
                request_token = None
            
            # NOW click submit button if we have one
            if submit_button:
                # Scroll to button and click
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(1)  # Wait for scroll
                submit_button.click()
            
            # Wait for redirect with increased time
            logger.info("Waiting for redirect with request token...")
            time.sleep(15)  # Increased wait time for redirect
            
            # CRITICAL: Extract request token from URL
            logger.info("Checking for request token in current URL...")
            current_url = driver.current_url
            logger.info(f"Current URL: {current_url}")
            
            # Save page source for debugging if needed
            logger.info(f"Page title: {driver.title}")
            try:
                driver.save_screenshot("post_submit_debug.png")
                logger.info("Saved post-submit debug screenshot as post_submit_debug.png")
            except Exception as debug_error:
                logger.warning(f"Failed to save post-submit debug screenshot: {debug_error}")
            
            # Extract request token using multiple methods
            request_token = self._extract_request_token(driver, current_url)
            
            if not request_token:
                logger.error("❌ Request token not found in URL or page")
                logger.error("This could be due to:")
                logger.error("  1. Incorrect TOTP code")
                logger.error("  2. Session timeout")
                logger.error("  3. Network issues")
                logger.error("  4. Zerodha's security measures")
                return None
            
            logger.info(f"Successfully extracted request token: {request_token[:10]}...")
            
            # Step 2: Exchange request token for access token
            logger.info("Exchanging request token for access token...")
            from kiteconnect import KiteConnect
            kite = KiteConnect(api_key=self.api_key)
            data = kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = data["access_token"]
            
            logger.info("✅ Successfully generated access token!")
            return access_token
            
        except Exception as e:
            logger.error(f"Automated token generation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Even if we get a WebDriver error, check if we have a request token and convert it
            try:
                # Try to extract request token from the error message itself
                error_str = str(e)
                if "request_token=" in error_str:
                    import re
                    token_match = re.search(r'request_token=([^&"\']*)', error_str)
                    if token_match:
                        request_token = token_match.group(1)
                        logger.info(f"Recovered request token from error: {request_token[:10]}...")
                        
                        # Convert to access token
                        access_token = self._convert_request_to_access_token(request_token)
                        if access_token:
                            logger.info("✅ Successfully converted request token to access token despite WebDriver error!")
                            return access_token
                        else:
                            logger.error("❌ Failed to convert request token to access token")
                            return None
                
                # If not in error message, try to get from current state
                if hasattr(self, '_temp_request_token') and self._temp_request_token:
                    access_token = self._convert_request_to_access_token(self._temp_request_token)
                    if access_token:
                        logger.info("✅ Successfully converted cached request token to access token!")
                        return access_token
            except Exception as conversion_error:
                logger.error(f"Failed to convert token despite successful extraction: {conversion_error}")
                
            return None
        
        finally:
            # Close driver
            try:
                if driver:
                    driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
    
    def _check_for_captcha(self, driver):
        """Check for CAPTCHA and warn user"""
        try:
            captcha_elements = driver.find_elements(By.XPATH, "//img[contains(@src, 'captcha') or contains(@alt, 'Captcha') or contains(@class, 'captcha')]")
            if captcha_elements:
                logger.warning("⚠️  CAPTCHA detected - this may prevent automated login")
                return True
        except:
            pass
            
        try:
            captcha_input = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'CAPTCHA') or contains(@id, 'captcha') or contains(@name, 'captcha')]")
            if captcha_input:
                logger.warning("⚠️  CAPTCHA input field detected - manual intervention may be required")
                return True
        except:
            pass
            
        return False
    
    def _check_for_errors(self, driver, context=""):
        """Check for error messages on the page"""
        try:
            error_elements = driver.find_elements(By.XPATH, "//p[contains(@class, 'error') or contains(text(), 'Invalid') or contains(text(), 'error') or contains(text(), 'Error') or contains(text(), 'CAPTCHA') or contains(text(), 'Captcha')]")
            for error_element in error_elements:
                error_text = error_element.text
                if error_text:
                    logger.warning(f"Page error {context}: {error_text}")
                    if "Invalid" in error_text:
                        logger.error("❌ Invalid credentials detected!")
                    elif "CAPTCHA" in error_text or "Captcha" in error_text:
                        logger.error("❌ CAPTCHA validation failed!")
        except Exception as e:
            logger.debug(f"Error checking for page errors: {e}")
    
    def _extract_request_token(self, driver, current_url):
        """Extract request token using multiple methods"""
        from urllib.parse import parse_qs, urlparse
        
        # Method 1: From URL query parameters
        logger.info("Method 1: Checking URL for request_token parameter...")
        parsed_url = urlparse(current_url)
        query_params = parse_qs(parsed_url.query)
        request_token = query_params.get('request_token', [None])[0]
        
        if request_token:
            logger.info("Found request token in URL query parameters")
            return request_token
        
        # Method 2: From anchor tags with request_token
        logger.info("Method 2: Checking for request_token in anchor tags...")
        try:
            anchor_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'request_token')]")
            for anchor in anchor_elements:
                href = anchor.get_attribute("href")
                if href:
                    parsed_href = urlparse(href)
                    href_params = parse_qs(parsed_href.query)
                    token = href_params.get('request_token', [None])[0]
                    if token:
                        logger.info("Found request token in anchor tag")
                        return token
        except Exception as e:
            logger.debug(f"Error checking anchor tags: {e}")
        
        # Method 3: From page source using regex
        logger.info("Method 3: Checking page source for request_token...")
        try:
            page_source = driver.page_source
            import re
            token_match = re.search(r'request_token=([^&"\']*)', page_source)
            if token_match:
                request_token = token_match.group(1)
                logger.info("Found request token in page source")
                return request_token
        except Exception as e:
            logger.debug(f"Error checking page source: {e}")
        
        # Method 4: From form actions
        logger.info("Method 4: Checking form actions for request_token...")
        try:
            form_elements = driver.find_elements(By.XPATH, "//form[@action]")
            for form in form_elements:
                action = form.get_attribute("action")
                if action and "request_token" in action:
                    parsed_action = urlparse(action)
                    action_params = parse_qs(parsed_action.query)
                    token = action_params.get('request_token', [None])[0]
                    if token:
                        logger.info("Found request token in form action")
                        return token
        except Exception as e:
            logger.debug(f"Error checking form actions: {e}")
        
        # Method 5: From JavaScript redirects
        logger.info("Method 5: Checking for JavaScript redirects with request_token...")
        try:
            # Look for JavaScript that might contain the redirect
            page_source = driver.page_source
            import re
            js_matches = re.findall(r'(?:window\.location|document\.location|location)\.href\s*=\s*["\'][^"\']*request_token[^"\']*["\']', page_source)
            for match in js_matches:
                token_match = re.search(r'request_token=([^&"\']*)', match)
                if token_match:
                    request_token = token_match.group(1)
                    logger.info("Found request token in JavaScript redirect")
                    return request_token
        except Exception as e:
            logger.debug(f"Error checking JavaScript redirects: {e}")
        
        logger.info("All methods failed to find request token")
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