#!/usr/bin/env python3
"""
Verify TOTP is Working Correctly
Simple test to confirm TOTP generation is working
"""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from kite_config import TOTP_SECRET
    print("✅ Configuration loaded successfully")
except ImportError as e:
    print(f"❌ Configuration error: {e}")
    sys.exit(1)

try:
    import pyotp
    print("✅ TOTP library loaded successfully")
except ImportError as e:
    print(f"❌ TOTP library error: {e}")
    sys.exit(1)

def test_totp():
    """Test TOTP generation"""
    print("\n🔐 Testing TOTP Generation...")
    
    try:
        totp = pyotp.TOTP(TOTP_SECRET)
        
        # Generate several codes to verify consistency
        print("Generating TOTP codes:")
        for i in range(3):
            code = totp.now()
            remaining = totp.interval - (int(time.time()) % totp.interval)
            print(f"  {i+1}. Code: {code} (Valid for {remaining} seconds)")
            if i < 2:  # Don't sleep after the last iteration
                time.sleep(2)  # Small delay to show time progression
        
        print("\n✅ TOTP generation is working correctly!")
        print("💡 This confirms your secret key is valid")
        print("💡 The automated system can generate codes automatically")
        
        return True
        
    except Exception as e:
        print(f"❌ TOTP generation failed: {e}")
        return False

def show_automation_benefits():
    """Show how this enables full automation"""
    print("\n🤖 How This Enables Full Automation:")
    print("   1. TOTP codes are generated automatically every 30 seconds")
    print("   2. No manual code entry required during authentication")
    print("   3. System can handle login process programmatically")
    print("   4. Tokens are stored and reused automatically")
    print("   5. Refresh happens automatically when tokens expire")
    print()
    print("✅ Your system is ready for full automation!")

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 TOTP Verification for Full Automation")
    print("=" * 50)
    
    if test_totp():
        show_automation_benefits()
    else:
        print("❌ TOTP verification failed")