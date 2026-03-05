#!/usr/bin/env python3
"""
Kite Access Token Refresher (HTTP-based, no Selenium needed)

Automatically generates a fresh access token using:
1. POST /api/login with user_id + password
2. POST /api/twofa with request_id + TOTP code  
3. POST /session/token to exchange request_token for access_token
4. Updates .env file with new token

Usage:
    python refresh_token.py
"""

import os
import sys
import hashlib
import requests
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env
from dotenv import load_dotenv
load_dotenv()


def get_credentials():
    """Load credentials from environment / .env"""
    api_key = os.getenv('KITE_API_KEY', '')
    api_secret = os.getenv('KITE_API_SECRET', '')
    user_id = os.getenv('KITE_USER_ID', '')
    password = os.getenv('KITE_PASSWORD', '')
    totp_secret = os.getenv('KITE_TOTP_SECRET', '')

    missing = []
    if not api_key: missing.append('KITE_API_KEY')
    if not api_secret: missing.append('KITE_API_SECRET')
    if not user_id: missing.append('KITE_USER_ID')
    if not password: missing.append('KITE_PASSWORD')
    if not totp_secret: missing.append('KITE_TOTP_SECRET')

    if missing:
        print(f"[ERROR] Missing credentials in .env: {', '.join(missing)}")
        return None

    return {
        'api_key': api_key,
        'api_secret': api_secret,
        'user_id': user_id,
        'password': password,
        'totp_secret': totp_secret
    }


def generate_totp(totp_secret):
    """Generate current TOTP code"""
    try:
        import pyotp
        totp = pyotp.TOTP(totp_secret)
        code = totp.now()
        return code
    except ImportError:
        print("[ERROR] pyotp not installed. Run: pip install pyotp")
        return None


def login_and_get_request_token(api_key, user_id, password, totp_secret):
    """Login to Kite via HTTP and get request_token (no browser needed)"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'X-Kite-Version': '3'
    })

    # Step 1: POST login with user_id + password
    print(f"[1/3] Logging in as {user_id}...")
    login_resp = session.post(
        'https://kite.zerodha.com/api/login',
        data={'user_id': user_id, 'password': password},
        timeout=15
    )

    if login_resp.status_code != 200:
        print(f"[ERROR] Login failed: HTTP {login_resp.status_code}")
        print(f"  Response: {login_resp.text[:300]}")
        return None

    login_data = login_resp.json()
    if login_data.get('status') != 'success':
        print(f"[ERROR] Login failed: {login_data.get('message', 'Unknown error')}")
        return None

    request_id = login_data['data']['request_id']
    print(f"[OK] Login successful, request_id: {request_id[:15]}...")

    # Step 2: POST twofa with TOTP
    totp_code = generate_totp(totp_secret)
    if not totp_code:
        return None

    print(f"[2/3] Submitting TOTP code: {totp_code}...")
    twofa_resp = session.post(
        'https://kite.zerodha.com/api/twofa',
        data={
            'user_id': user_id,
            'request_id': request_id,
            'twofa_value': totp_code,
            'twofa_type': 'totp'
        },
        timeout=15
    )

    if twofa_resp.status_code != 200:
        print(f"[ERROR] 2FA failed: HTTP {twofa_resp.status_code}")
        print(f"  Response: {twofa_resp.text[:300]}")
        return None

    twofa_data = twofa_resp.json()
    if twofa_data.get('status') != 'success':
        print(f"[ERROR] 2FA failed: {twofa_data.get('message', 'Unknown error')}")
        return None

    # First check: does the 2FA response contain request_token directly?
    request_token = twofa_data.get('data', {}).get('request_token')
    
    if request_token:
        print(f"[OK] Got request_token directly from 2FA response: {request_token[:15]}...")
        return request_token
    
    # If no request_token in response, get it from the OAuth redirect
    # Try to get it from successful response, or extract from error if redirect fails
    print("[OK] 2FA successful, getting request_token from OAuth flow...")
    
    request_token = None
    try:
        # Use original session to maintain cookies
        auth_resp = session.get(
            f'https://kite.trade/connect/login?api_key={api_key}&v=3',
            allow_redirects=True,
            timeout=15
        )
        
        # Check the final URL for request_token
        final_url = auth_resp.url
        print(f"[DEBUG] Final URL: {final_url}")
        
        if 'request_token=' in final_url:
            request_token = final_url.split('request_token=')[1].split('&')[0]
            print(f"[OK] Got request_token from final URL: {request_token[:15]}...")
            return request_token
            
    except requests.exceptions.RequestException as e:
        # The error might contain the request_token in the redirect URL!
        error_str = str(e)
        print(f"[DEBUG] Error during redirect: {error_str[:200]}...")
        
        # Extract request_token from error message
        if 'request_token=' in error_str:
            match = re.search(r'request_token=([A-Za-z0-9]+)', error_str)
            if match:
                request_token = match.group(1)
                print(f"[OK] Got request_token from error message: {request_token[:15]}...")
                return request_token

    if not request_token:
        print(f"[ERROR] Could not get request_token from OAuth flow")
        return None

    print(f"[OK] Got request_token: {request_token[:15]}...")
    return request_token


def exchange_for_access_token(api_key, api_secret, request_token):
    """Exchange request_token for access_token via Kite API"""
    print(f"[3/3] Exchanging request_token for access_token...")

    checksum_data = f"{api_key}{request_token}{api_secret}"
    checksum = hashlib.sha256(checksum_data.encode()).hexdigest()

    resp = requests.post(
        'https://api.kite.trade/session/token',
        data={
            'api_key': api_key,
            'request_token': request_token,
            'checksum': checksum
        },
        timeout=15
    )

    if resp.status_code != 200:
        print(f"[ERROR] Token exchange failed: HTTP {resp.status_code}")
        print(f"  Response: {resp.text[:300]}")
        return None

    result = resp.json()
    if 'data' not in result or 'access_token' not in result.get('data', {}):
        print(f"[ERROR] Unexpected response: {result}")
        return None

    access_token = result['data']['access_token']
    user_name = result['data'].get('user_name', 'Unknown')
    print(f"[OK] Access token generated for {user_name}: {access_token[:15]}...")
    return access_token


def update_env_file(access_token):
    """Update KITE_ACCESS_TOKEN in .env file"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')

    if not os.path.exists(env_path):
        print(f"[ERROR] .env file not found at {env_path}")
        return False

    with open(env_path, 'r') as f:
        content = f.read()

    # Replace existing KITE_ACCESS_TOKEN line
    if 'KITE_ACCESS_TOKEN=' in content:
        updated = re.sub(
            r'KITE_ACCESS_TOKEN=.*',
            f'KITE_ACCESS_TOKEN={access_token}',
            content
        )
    else:
        updated = content.rstrip() + f'\nKITE_ACCESS_TOKEN={access_token}\n'

    with open(env_path, 'w') as f:
        f.write(updated)

    print(f"[OK] Updated .env file with new access token")
    return True


def refresh_access_token():
    """Main function: generate fresh access token and update .env"""
    creds = get_credentials()
    if not creds:
        return None

    request_token = login_and_get_request_token(
        creds['api_key'], creds['user_id'], creds['password'], creds['totp_secret']
    )
    if not request_token:
        return None

    access_token = exchange_for_access_token(
        creds['api_key'], creds['api_secret'], request_token
    )
    if not access_token:
        return None

    # Update .env file
    update_env_file(access_token)

    # Also update current process environment
    os.environ['KITE_ACCESS_TOKEN'] = access_token

    return access_token


def validate_current_token():
    """Check if current token in .env is still valid"""
    api_key = os.getenv('KITE_API_KEY', '')
    access_token = os.getenv('KITE_ACCESS_TOKEN', '')

    if not api_key or not access_token:
        print("[ERROR] KITE_API_KEY or KITE_ACCESS_TOKEN not set")
        return False

    try:
        headers = {
            'Authorization': f'token {api_key}:{access_token}',
            'Content-Type': 'application/json'
        }
        resp = requests.get(
            'https://api.kite.trade/user/profile',
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            user = data.get('data', {}).get('user_name', 'Unknown')
            print(f"[OK] Current token is VALID (user: {user})")
            return True
        else:
            print(f"[EXPIRED] Current token is INVALID (HTTP {resp.status_code})")
            return False
    except Exception as e:
        print(f"[ERROR] Token validation failed: {e}")
        return False


if __name__ == '__main__':
    print("=" * 55)
    print("  Kite Access Token Refresher (HTTP-based)")
    print("=" * 55)
    print()

    # Check current token
    print("[STEP 1] Checking current token...")
    if validate_current_token():
        print("\nYour current token is still valid!")
        choice = input("Generate a new one anyway? (y/n): ").strip().lower()
        if choice != 'y':
            print("OK, keeping current token.")
            sys.exit(0)

    # Generate new token
    print("\n[STEP 2] Generating fresh access token...")
    new_token = refresh_access_token()

    if new_token:
        print("\n" + "=" * 55)
        print(f"  SUCCESS! New access token: {new_token[:20]}...")
        print(f"  .env file updated automatically")
        print(f"  Restart your app to use the new token")
        print("=" * 55)
    else:
        print("\n[FAILED] Could not generate new token.")
        print("Make sure your .env has correct:")
        print("  KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID,")
        print("  KITE_PASSWORD, KITE_TOTP_SECRET")
        sys.exit(1)
