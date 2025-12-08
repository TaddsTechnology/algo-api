#!/usr/bin/env python3
"""
Test TOTP Integration with KiteApi
"""

import sys
import os
import time

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

def test_totp_generation():
    """Test TOTP generation with your secret"""
    print("\n🔐 Testing TOTP Generation...")
    
    try:
        totp = pyotp.TOTP(TOTP_SECRET)
        current_code = totp.now()
        
        print(f"✅ Current TOTP: {current_code}")
        print(f"⏰ Valid for: {totp.interval - (int(time.time()) % totp.interval)} seconds")
        
        # Verify it's a valid 6-digit number
        if len(current_code) == 6 and current_code.isdigit():
            print("✅ TOTP format is correct")
            return True
        else:
            print("❌ TOTP format is incorrect")
            return False
            
    except Exception as e:
        print(f"❌ TOTP generation failed: {e}")
        return False

def show_automated_login_info():
    """Show information about automated login"""
    print("\n🤖 Automated Login Information:")
    print(f"   👤 User ID: {USER_ID}")
    print(f"   🔐 API Key: {API_KEY[:10]}...")
    print(f"   🔢 TOTP Secret: {TOTP_SECRET[:10]}...")
    print()
    print("The AutoKiteTokenManager will:")
    print("   1. Automatically open a headless browser")
    print("   2. Login with your credentials")
    print("   3. Generate and enter TOTP code automatically")
    print("   4. Extract request token")
    print("   5. Convert to access token")
    print("   6. Save to configuration automatically")

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 KiteApi TOTP Integration Test")
    print("=" * 50)
    
    if test_totp_generation():
        show_automated_login_info()
        print("\n✅ TOTP integration is ready for automated login!")
    else:
        print("❌ TOTP integration test failed")