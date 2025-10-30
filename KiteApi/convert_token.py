#!/usr/bin/env python3
"""
Simple Request Token to Access Token Converter for Kite API

Usage:
    python convert_token.py <request_token>
    
Or run interactively:
    python convert_token.py
"""

import sys
import hashlib
import requests


def convert_request_token_to_access_token(api_key, api_secret, request_token):
    """
    Convert Kite request token to access token
    
    Args:
        api_key: Your Kite API key
        api_secret: Your Kite API secret
        request_token: Request token from redirect URL
        
    Returns:
        Access token if successful, None otherwise
    """
    try:
        # Step 1: Create checksum (SHA-256 of api_key + request_token + api_secret)
        checksum_data = f"{api_key}{request_token}{api_secret}"
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
        
        print(f"🔐 Checksum generated: {checksum[:20]}...")
        
        # Step 2: Make API request to get access token
        url = "https://api.kite.trade/session/token"
        data = {
            "api_key": api_key,
            "request_token": request_token,
            "checksum": checksum
        }
        
        print(f"📡 Requesting access token from Kite API...")
        response = requests.post(url, data=data)
        result = response.json()
        
        # Step 3: Extract access token
        if response.status_code == 200 and "data" in result:
            access_token = result["data"]["access_token"]
            user_id = result["data"].get("user_id", "Unknown")
            user_name = result["data"].get("user_name", "Unknown")
            
            print(f"\n✅ SUCCESS! Access Token Generated")
            print("=" * 70)
            print(f"👤 User ID: {user_id}")
            print(f"👤 User Name: {user_name}")
            print(f"🎫 Access Token: {access_token}")
            print("=" * 70)
            
            return access_token
        else:
            error_msg = result.get("message", "Unknown error")
            error_type = result.get("error_type", "Unknown")
            print(f"\n❌ FAILED to generate access token")
            print(f"Error Type: {error_type}")
            print(f"Error Message: {error_msg}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_to_config(access_token):
    """Save access token to kite_config.py"""
    try:
        import os
        import re
        
        # Get config file path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        config_path = os.path.join(parent_dir, 'kite_config.py')
        
        if not os.path.exists(config_path):
            print(f"⚠️ Config file not found at: {config_path}")
            return False
        
        # Read current config
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        # Replace ACCESS_TOKEN line
        updated_content = re.sub(
            r'ACCESS_TOKEN = ["\'].*?["\']',
            f'ACCESS_TOKEN = "{access_token}"',
            config_content
        )
        
        # Write back
        with open(config_path, 'w') as f:
            f.write(updated_content)
        
        print(f"✅ Token saved to kite_config.py!")
        return True
        
    except Exception as e:
        print(f"⚠️ Could not save to config: {e}")
        return False


def main():
    """Main function"""
    print("=" * 70)
    print("🔑 Kite Request Token → Access Token Converter")
    print("=" * 70)
    
    # Load API credentials
    try:
        import os
        import sys
        
        # Add parent directory to path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(script_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from kite_config import API_KEY, API_SECRET
        
        if not API_KEY or API_KEY == "your_api_key_here":
            print("❌ Please update kite_config.py with your API_KEY first!")
            return
        
        if not API_SECRET or API_SECRET == "your_api_secret_here":
            print("❌ Please update kite_config.py with your API_SECRET first!")
            return
        
        print(f"✅ API Key loaded: {API_KEY[:10]}...")
        print(f"✅ API Secret loaded: {API_SECRET[:10]}...")
        
    except ImportError:
        print("❌ Could not import kite_config.py")
        print("💡 Please create kite_config.py with API_KEY and API_SECRET")
        return
    
    # Get request token from command line or user input
    if len(sys.argv) > 1:
        request_token = sys.argv[1].strip()
        print(f"📋 Request token from command line: {request_token[:20]}...")
    else:
        print("\n📋 How to get request token:")
        print("1. Visit: https://kite.trade/connect/login?api_key=" + API_KEY)
        print("2. Login and authorize")
        print("3. Copy the 'request_token' from redirect URL")
        print()
        request_token = input("🔤 Paste your request token here: ").strip()
    
    if not request_token:
        print("❌ Request token is required!")
        return
    
    # Convert to access token
    print(f"\n🚀 Converting request token to access token...")
    access_token = convert_request_token_to_access_token(API_KEY, API_SECRET, request_token)
    
    if access_token:
        # Offer to save
        print("\n💾 Save Options:")
        save = input("Save to kite_config.py? (y/n) [default: y]: ").strip().lower()
        
        if save != 'n':
            if save_to_config(access_token):
                print("\n🎉 All done! You can now run:")
                print("   python kite_near_future.py")
            else:
                print("\n💡 Manually add this to kite_config.py:")
                print(f'   ACCESS_TOKEN = "{access_token}"')
        else:
            print("\n💡 To use this token, add it to kite_config.py:")
            print(f'ACCESS_TOKEN = "{access_token}"')
    else:
        print("\n❌ Failed to convert request token.")
        print("💡 Make sure:")
        print("   1. Your API_KEY and API_SECRET are correct")
        print("   2. The request token is fresh (generated within the last few minutes)")
        print("   3. You haven't used this request token before")


if __name__ == "__main__":
    main()
