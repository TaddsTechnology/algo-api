#!/usr/bin/env python3
"""
Manual Kite Access Token Generator

This script helps you get the access token by opening the browser 
and guiding you through the manual process.
"""

import webbrowser
import hashlib
import base64
import secrets
from urllib.parse import urlencode

def generate_login_url(api_key):
    """Generate Kite Connect login URL"""
    base_url = "https://kite.trade/connect/login"
    params = {
        "api_key": api_key,
        "v": "3"
    }
    return f"{base_url}?{urlencode(params)}"

def get_kite_access_token():
    """Interactive token generation process"""
    
    print("🔑 Kite Access Token Generator")
    print("=" * 50)
    
    # Step 1: Get API key
    try:
        import sys
        import os
        # Add parent directory to path to import kite_config
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from kite_config import API_KEY, API_SECRET
        if API_KEY == "your_api_key_here":
            raise ImportError("Please update kite_config.py with your actual API key")
        print(f"✅ Using API Key from config: {API_KEY[:10]}...")
    except ImportError:
        API_KEY = input("Enter your Kite API Key: ").strip()
        API_SECRET = input("Enter your Kite API Secret: ").strip()
    
    if not API_KEY or not API_SECRET:
        print("❌ API Key and Secret are required!")
        return None
    
    # Step 2: Generate login URL
    login_url = generate_login_url(API_KEY)
    print(f"\n🌐 Login URL: {login_url}")
    
    # Step 3: Open browser
    try:
        print("\n📱 Opening login page in your browser...")
        webbrowser.open(login_url)
    except Exception:
        print("⚠️ Could not open browser automatically")
    
    print("\n" + "="*60)
    print("📋 MANUAL STEPS:")
    print("1. Complete login in the opened browser window")
    print("2. After successful login, you'll be redirected to a URL like:")
    print("   https://yourapp.com/?request_token=ABC123&action=login&status=success")
    print("3. Copy the 'request_token' value from the URL")
    print("="*60)
    
    # Step 4: Get request token from user
    request_token = input("\n🔤 Paste the request_token from the redirect URL: ").strip()
    
    if not request_token:
        print("❌ Request token is required!")
        return None
    
    # Step 5: Generate access token
    try:
        import hashlib
        
        # Create checksum
        checksum_data = API_KEY + request_token + API_SECRET
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
        
        # Make request to get access token
        import requests
        
        url = "https://api.kite.trade/session/token"
        data = {
            "api_key": API_KEY,
            "request_token": request_token,
            "checksum": checksum
        }
        
        response = requests.post(url, data=data)
        result = response.json()
        
        if response.status_code == 200 and "data" in result:
            access_token = result["data"]["access_token"]
            print(f"\n✅ Access Token Generated Successfully!")
            print(f"🎫 Access Token: {access_token}")
            print(f"\n💡 Copy this token to kite_config.py:")
            print(f'ACCESS_TOKEN = "{access_token}"')
            
            # Optionally save to config
            save_to_config = input("\n💾 Save to kite_config.py automatically? (y/n): ").strip().lower()
            if save_to_config == 'y':
                try:
                    import os
                    import re
                    # Get parent directory path
                    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    config_path = os.path.join(parent_dir, 'kite_config.py')
                    
                    # Read current config
                    with open(config_path, 'r') as f:
                        config_content = f.read()
                    
                    # Replace ACCESS_TOKEN line
                    updated_content = re.sub(
                        r'ACCESS_TOKEN = ".*?"',
                        f'ACCESS_TOKEN = "{access_token}"',
                        config_content
                    )
                    
                    # Write back
                    with open(config_path, 'w') as f:
                        f.write(updated_content)
                    
                    print("✅ Token saved to kite_config.py!")
                    
                except Exception as e:
                    print(f"⚠️ Could not save to config: {e}")
            
            return access_token
            
        else:
            print(f"❌ Failed to generate access token: {result}")
            return None
            
    except Exception as e:
        print(f"❌ Error generating access token: {e}")
        return None

def quick_test_token():
    """Quick test of the generated token"""
    try:
        import sys
        import os
        # Add parent directory to path to import kite_config
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from kite_config import API_KEY, ACCESS_TOKEN
        
        if not ACCESS_TOKEN:
            print("⚠️ No access token found in kite_config.py")
            return
        
        from KiteApi.kiteConnect import KiteConnect
        
        kite = KiteConnect(api_key=API_KEY, access_token=ACCESS_TOKEN)
        
        if kite.test_connection():
            print("🎉 Token is working! You can now use the Near Future system.")
        else:
            print("❌ Token test failed. Please regenerate token.")
            
    except Exception as e:
        print(f"❌ Error testing token: {e}")

def main():
    """Main function"""
    print("🚀 Welcome to Kite Token Generator")
    print("This will help you get an access token for Zerodha Kite API")
    print("\n" + "="*60)
    
    # Generate token
    token = get_kite_access_token()
    
    if token:
        print("\n" + "="*60)
        print("🎯 Next Steps:")
        print("1. Run: python kite_near_future.py")
        print("2. Or run: python kite_website.py")
        print("="*60)
        
        # Test token
        test = input("\n🧪 Test token now? (y/n): ").strip().lower()
        if test == 'y':
            quick_test_token()
    else:
        print("❌ Token generation failed. Please try again.")

if __name__ == "__main__":
    main()