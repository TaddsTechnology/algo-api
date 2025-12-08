#!/usr/bin/env python3
"""
Simple TOTP Automation for Kite API
Fully automated token generation without Supabase dependencies
"""

import sys
import os
import time
import hashlib
import requests

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from kite_config import API_KEY, API_SECRET, USER_ID, PASSWORD, TOTP_SECRET
    print("✅ Configuration loaded successfully")
except ImportError as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

try:
    import pyotp
    print("✅ TOTP library loaded successfully")
except ImportError as e:
    print(f"❌ TOTP library error: {e}")
    print("💡 Install with: pip install pyotp")
    sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
    print("✅ Selenium loaded successfully")
except ImportError as e:
    SELENIUM_AVAILABLE = False
    print(f"❌ Selenium error: {e}")
    print("💡 Install with: pip install selenium webdriver-manager")

def generate_totp():
    """Generate TOTP code"""
    try:
        totp = pyotp.TOTP(TOTP_SECRET)
        code = totp.now()
        print(f"🔐 Generated TOTP: {code}")
        return code
    except Exception as e:
        print(f"❌ TOTP generation failed: {e}")
        return None

def automated_login():
    """Perform automated login with TOTP"""
    if not SELENIUM_AVAILABLE:
        print("❌ Selenium not available for automation")
        return None
        
    print("🚀 Starting automated login...")
    
    try:
        # Setup headless Chrome
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Initialize driver
        print("🔧 Initializing Chrome driver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            # Step 1: Go to Kite login
            login_url = f"https://kite.trade/connect/login?api_key={API_KEY}"
            print(f"🌐 Visiting: {login_url}")
            driver.get(login_url)
            
            # Step 2: Login
            print("👤 Logging in...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "userid"))
            )
            
            driver.find_element(By.ID, "userid").send_keys(USER_ID)
            driver.find_element(By.ID, "password").send_keys(PASSWORD)
            driver.find_element(By.CLASS_NAME, "button-orange").click()
            
            # Step 3: Enter TOTP
            print("🔢 Entering TOTP...")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "pin"))
            )
            
            # Generate TOTP
            totp_code = generate_totp()
            if not totp_code:
                return None
                
            driver.find_element(By.ID, "pin").send_keys(totp_code)
            driver.find_element(By.CLASS_NAME, "button-orange").click()
            
            # Step 4: Wait for redirect and extract request_token
            print("⏳ Waiting for redirect...")
            WebDriverWait(driver, 15).until(
                lambda d: "request_token=" in d.current_url
            )
            
            current_url = driver.current_url
            print(f"🔗 Redirect URL: {current_url}")
            
            # Extract request_token
            if "request_token=" in current_url:
                request_token = current_url.split("request_token=")[1].split("&")[0]
                print(f"🎫 Request token extracted: {request_token[:10]}...")
                return request_token
            else:
                print("❌ Could not extract request_token from URL")
                return None
                
        finally:
            driver.quit()
            print("🔒 Browser closed")
            
    except Exception as e:
        print(f"❌ Automation failed: {e}")
        return None

def convert_request_to_access_token(request_token):
    """Convert request token to access token"""
    try:
        # Create checksum
        checksum_data = f"{API_KEY}{request_token}{API_SECRET}"
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
        
        # Make API call
        url = "https://api.kite.trade/session/token"
        data = {
            "api_key": API_KEY,
            "request_token": request_token,
            "checksum": checksum
        }
        
        print("📡 Converting request token to access token...")
        response = requests.post(url, data=data)
        result = response.json()
        
        if response.status_code == 200 and "data" in result:
            access_token = result["data"]["access_token"]
            print(f"✅ Success! Access token: {access_token[:10]}...")
            return access_token
        else:
            error_msg = result.get("message", "Unknown error")
            print(f"❌ Failed: {error_msg}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def save_access_token(access_token):
    """Save access token to config file"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'kite_config.py')
        
        # Read current config
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Replace ACCESS_TOKEN line
        import re
        updated_content = re.sub(
            r'ACCESS_TOKEN = [^\n]*',
            f'ACCESS_TOKEN = "{access_token}"',
            content
        )
        
        # Write back
        with open(config_path, 'w') as f:
            f.write(updated_content)
        
        print("✅ Access token saved to kite_config.py")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save token: {e}")
        return False

def main():
    print("=" * 60)
    print("🤖 Simple TOTP Automated Kite Token Generator")
    print("=" * 60)
    print(f"👤 User ID: {USER_ID}")
    print(f"🔐 API Key: {API_KEY[:10]}...")
    print()
    
    # Automated login and token extraction
    request_token = automated_login()
    
    if not request_token:
        print("❌ Automated login failed")
        return
    
    # Convert to access token
    access_token = convert_request_to_access_token(request_token)
    
    if access_token:
        # Save to config
        if save_access_token(access_token):
            print("\n🎉 Token generation completed successfully!")
            print("✅ Your kite_config.py has been updated with the new access token")
            print("🔄 You can now run your trading algorithms without manual intervention")
        else:
            print(f"\n💡 Manual step: Add this to your kite_config.py:")
            print(f'   ACCESS_TOKEN = "{access_token}"')
    else:
        print("❌ Token generation failed")

if __name__ == "__main__":
    main()