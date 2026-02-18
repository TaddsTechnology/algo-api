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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from kite_config import API_KEY, API_SECRET, USER_ID, PASSWORD, TOTP_SECRET
    print("OK - Config loaded")
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

try:
    import pyotp
    print("OK - pyotp loaded")
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    import chromedriver_autoinstaller
    try:
        chromedriver_autoinstaller.install()
    except:
        pass
    print("OK - Selenium loaded")
except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)


def generate_totp():
    try:
        totp = pyotp.TOTP(TOTP_SECRET)
        code = totp.now()
        print(f"TOTP: {code}")
        return code
    except Exception as e:
        print(f"TOTP error: {e}")
        return None


def automated_login():
    print("Starting automated login...")
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    
    for path in [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]:
        if os.path.exists(path):
            chrome_options.binary_location = path
            break
    
    print("Initializing Chrome...")
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        login_url = f"https://kite.trade/connect/login?api_key={API_KEY}"
        print(f"Visiting: {login_url}")
        driver.get(login_url)
        
        print("Filling login form...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "userid"))
        )
        
        driver.find_element(By.ID, "userid").send_keys(USER_ID)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.CLASS_NAME, "button-orange").click()
        
        time.sleep(5)
        
        print(f"URL after login: {driver.current_url}")
        
        # Check for CAPTCHA
        captcha = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'CAPTCHA') or contains(@id, 'captcha')]")
        if captcha:
            print("CAPTCHA DETECTED!")
            print("Taking screenshot...")
            driver.save_screenshot("captcha.png")
            print("Please solve CAPTCHA manually. Script will wait 60 seconds...")
            time.sleep(60)
        
        # Try to find PIN field - multiple selectors
        pin_field = None
        selectors = [
            "//input[@id='pin']",
            "//input[@id='totp']", 
            "//input[@placeholder='TWO FA']",
            "//input[@type='number' and @maxlength='6']"
        ]
        
        for sel in selectors:
            try:
                pin_field = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, sel))
                )
                print(f"Found PIN field with: {sel}")
                break
            except:
                continue
        
        if not pin_field:
            print("Could not find PIN field!")
            driver.save_screenshot("no_pin.png")
            # Try anyway with ID
            try:
                pin_field = driver.find_element(By.ID, "pin")
            except:
                pass
        
        if not pin_field:
            print("ERROR: Cannot find PIN/TOTP field")
            return None
        
        totp_code = generate_totp()
        if not totp_code:
            return None
        
        pin_field.clear()
        pin_field.send_keys(totp_code)
        time.sleep(1)
        
        # Click submit - try multiple methods
        print("Clicking submit...")
        try:
            btn = driver.find_element(By.CLASS_NAME, "button-orange")
            print(f"Found button: {btn.text}")
            btn.click()
        except Exception as e:
            print(f"Class method failed: {e}")
            try:
                btn = driver.find_element(By.XPATH, "//button[@type='submit']")
                print(f"Found button XPATH: {btn.text}")
                btn.click()
            except:
                print("Trying enter key...")
                pin_field.send_keys("\n")
        
        # Wait and check page
        print("Waiting for redirect...")
        time.sleep(8)
        
        # Check page title and URL
        print(f"Page title: {driver.title}")
        print(f"Current URL: {driver.current_url}")
        
        # Check if still on login page or error
        page_source = driver.page_source
        page_lower = page_source.lower()
        
        # Print any error messages found
        try:
            # Look for error divs
            errors = driver.find_elements(By.XPATH, "//div[contains(@class, 'error')] | //p[contains(@class, 'error')] | //span[contains(@class, 'error')]")
            for err in errors:
                txt = err.text.strip()
                if txt:
                    print(f"Error message found: {txt}")
        except:
            pass
        
        if "invalid" in page_lower or "error" in page_lower:
            print("ERROR detected on page!")
            driver.save_screenshot("error_page.png")
        
        # Check for any input field with error state
        try:
            error_inputs = driver.find_elements(By.XPATH, "//input[contains(@class, 'error')]")
            if error_inputs:
                for inp in error_inputs:
                    print(f"Input with error: {inp.get_attribute('id')} - {inp.get_attribute('placeholder')}")
        except:
            pass
        
        # Check if there's another PIN/TOTP field (maybe needs re-entry)
        pin_again = driver.find_elements(By.ID, "pin")
        if pin_again:
            print("PIN field still present - might need another TOTP!")
            driver.save_screenshot("pin_again.png")
        
        current_url = driver.current_url
        
        if "request_token=" in current_url:
            request_token = current_url.split("request_token=")[1].split("&")[0]
            print(f"Got request token: {request_token[:15]}...")
            return request_token
        else:
            print("No request token in URL")
            driver.save_screenshot("no_token.png")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        try:
            driver.quit()
        except:
            pass


def convert_request_to_access_token(request_token):
    try:
        checksum_data = f"{API_KEY}{request_token}{API_SECRET}"
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
        
        url = "https://api.kite.trade/session/token"
        data = {
            "api_key": API_KEY,
            "request_token": request_token,
            "checksum": checksum
        }
        
        print("Converting request token...")
        response = requests.post(url, data=data)
        result = response.json()
        
        if response.status_code == 200 and "data" in result:
            access_token = result["data"]["access_token"]
            print(f"Access token: {access_token[:20]}...")
            return access_token
        else:
            print(f"Error: {result}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def save_access_token(access_token):
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'kite_config.py')
        with open(config_path, 'r') as f:
            content = f.read()
        
        import re
        updated_content = re.sub(
            r'ACCESS_TOKEN = [^\n]*',
            f'ACCESS_TOKEN = "{access_token}"',
            content
        )
        
        with open(config_path, 'w') as f:
            f.write(updated_content)
        
        print("Saved to kite_config.py")
        return True
    except Exception as e:
        print(f"Save error: {e}")
        return False


def main():
    print("=" * 50)
    print("Kite TOTP Token Generator")
    print("=" * 50)
    print(f"User: {USER_ID}")
    print()
    
    request_token = automated_login()
    
    if not request_token:
        print("FAILED: Could not get request token")
        return
    
    access_token = convert_request_to_access_token(request_token)
    
    if access_token:
        if save_access_token(access_token):
            print("SUCCESS!")
        else:
            print(f"Manual: ACCESS_TOKEN = \"{access_token}\"")
    else:
        print("FAILED: Could not convert token")


if __name__ == "__main__":
    main()
