#!/usr/bin/env python3
"""
Simple Supabase Connection Test
Tests connection to Supabase without full client
"""

import sys
import os
import requests
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from supabase_config import SUPABASE_URL, SUPABASE_KEY
    print("✅ Supabase configuration loaded")
except ImportError as e:
    print(f"❌ Supabase configuration error: {e}")
    sys.exit(1)

def test_supabase_rest_api():
    """Test Supabase using REST API directly"""
    try:
        # Test endpoint
        test_url = f"{SUPABASE_URL}/rest/v1/"
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        print("📡 Testing Supabase REST API connection...")
        response = requests.get(test_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ Supabase REST API connection successful")
            return True
        else:
            print(f"❌ Supabase REST API connection failed: {response.status_code}")
            print(f"Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Supabase REST API test failed: {e}")
        return False

def show_table_creation_sql():
    """Show SQL to create the tokens table"""
    print("\n📋 SQL to create kite_tokens table:")
    print("=" * 50)
    print("CREATE TABLE IF NOT EXISTS kite_tokens (")
    print("    id BIGSERIAL PRIMARY KEY,")
    print("    app_name TEXT UNIQUE NOT NULL,")
    print("    access_token TEXT NOT NULL,")
    print("    api_key TEXT NOT NULL,")
    print("    created_at TIMESTAMPTZ DEFAULT NOW(),")
    print("    expires_at TIMESTAMPTZ NOT NULL,")
    print("    updated_at TIMESTAMPTZ DEFAULT NOW()")
    print(");")
    print()
    print("CREATE INDEX IF NOT EXISTS idx_kite_tokens_app_name ON kite_tokens(app_name);")
    print("=" * 50)

def main():
    print("=" * 60)
    print("🤖 Simple Supabase Connection Test")
    print("=" * 60)
    print(f"📍 Supabase URL: {SUPABASE_URL[:30]}...")
    print()
    
    # Test connection
    if test_supabase_rest_api():
        print("\n🎉 Supabase connection successful!")
        show_table_creation_sql()
        print("\n💡 Instructions:")
        print("   1. Copy the SQL above")
        print("   2. Go to your Supabase dashboard")
        print("   3. Open the SQL Editor")
        print("   4. Paste and run the SQL to create the table")
        print("   5. Your AutoKiteTokenManager will automatically use this table")
    else:
        print("\n❌ Supabase connection failed")
        show_table_creation_sql()

if __name__ == "__main__":
    main()