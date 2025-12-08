#!/usr/bin/env python3
"""
Initial Setup Helper for Kite Token Generation
Helps with the one-time manual setup required for full automation
"""

import sys
import os
import pyotp
import webbrowser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from kite_config import API_KEY, USER_ID, TOTP_SECRET
    print("✅ Configuration loaded successfully")
except ImportError as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

def show_setup_instructions():
    """Show step-by-step setup instructions"""
    print("=" * 60)
    print("🤖 Initial Setup Helper")
    print("=" * 60)
    
    # Generate current TOTP
    totp = pyotp.TOTP(TOTP_SECRET)
    current_code = totp.now()
    
    print("📋 STEP-BY-STEP SETUP INSTRUCTIONS:")
    print()
    print("1️⃣  Visit this URL to start authentication:")
    login_url = f"https://kite.trade/connect/login?api_key={API_KEY}"
    print(f"   🔗 {login_url}")
    print()
    print("2️⃣  Login with your credentials:")
    print(f"   👤 User ID: {USER_ID}")
    print(f"   🔐 Password: [your password]")
    print()
    print("3️⃣  When prompted for TOTP, enter this code:")
    print(f"   🔢 TOTP Code: {current_code}")
    print(f"   ⏰ Valid for: {totp.interval - (int(time.time()) % totp.interval)} seconds")
    print()
    print("4️⃣  After successful authentication:")
    print("   🔄 You will be redirected to a URL")
    print("   📋 Copy the FULL redirect URL")
    print("   💡 It will look like: https://your-app.com/?request_token=XXXXXXX")
    print()
    print("5️⃣  Convert the request token to access token:")
    print("   ▶ Run: python KiteApi/convert_token.py")
    print("   📋 Paste the redirect URL when prompted")
    print()
    print("6️⃣  After generating access token:")
    print("   💾 The token will be saved to kite_config.py automatically")
    print("   🔄 Future token refreshes will be automatic")
    print()
    print("✅ THAT'S IT! After this one-time setup, everything is automated!")

def open_browser():
    """Optionally open browser to login URL"""
    login_url = f"https://kite.trade/connect/login?api_key={API_KEY}"
    
    response = input("🌐 Open browser to login URL? (y/n): ").strip().lower()
    if response == 'y':
        try:
            webbrowser.open(login_url)
            print("✅ Browser opened successfully")
        except Exception as e:
            print(f"❌ Failed to open browser: {e}")
            print(f"📋 Manually visit: {login_url}")

def show_totp_countdown():
    """Show TOTP countdown"""
    import time
    
    totp = pyotp.TOTP(TOTP_SECRET)
    while True:
        try:
            current_code = totp.now()
            remaining = totp.interval - (int(time.time()) % totp.interval)
            print(f"\r🔢 Current TOTP: {current_code} | ⏰ Valid for: {remaining}s", end="", flush=True)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 TOTP display stopped")
            break

if __name__ == "__main__":
    import time
    
    show_setup_instructions()
    print()
    open_browser()
    
    print("\n🔄 Displaying TOTP codes (press Ctrl+C to stop):")
    show_totp_countdown()