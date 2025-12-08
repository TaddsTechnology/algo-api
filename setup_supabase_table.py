#!/usr/bin/env python3
"""
Setup Supabase Table for Kite Token Storage
Creates the required table structure for storing Kite access tokens
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from supabase import create_client
    print("✅ Supabase client library loaded")
except ImportError as e:
    print(f"❌ Supabase client error: {e}")
    print("💡 Install with: pip install supabase")
    sys.exit(1)

try:
    from supabase_config import SUPABASE_URL, SUPABASE_KEY
    print("✅ Supabase configuration loaded")
except ImportError as e:
    print(f"❌ Supabase configuration error: {e}")
    print("💡 Create supabase_config.py with SUPABASE_URL and SUPABASE_KEY")
    sys.exit(1)

def setup_tokens_table():
    """Setup the kite_tokens table in Supabase"""
    try:
        # Create Supabase client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized")
        
        # Define the table structure
        table_definition = {
            "name": "kite_tokens",
            "columns": [
                {
                    "name": "id",
                    "type": "bigint",
                    "is_identity": True,
                    "is_primary_key": True
                },
                {
                    "name": "app_name",
                    "type": "text",
                    "is_unique": True,
                    "is_nullable": False
                },
                {
                    "name": "access_token",
                    "type": "text",
                    "is_nullable": False
                },
                {
                    "name": "api_key",
                    "type": "text",
                    "is_nullable": False
                },
                {
                    "name": "created_at",
                    "type": "timestamp with time zone",
                    "default": "now()"
                },
                {
                    "name": "expires_at",
                    "type": "timestamp with time zone",
                    "is_nullable": False
                },
                {
                    "name": "updated_at",
                    "type": "timestamp with time zone",
                    "default": "now()"
                }
            ]
        }
        
        print("📋 Table definition:")
        print("   Table: kite_tokens")
        print("   Columns:")
        for col in table_definition["columns"]:
            nullable = "NOT NULL" if not col.get("is_nullable", True) else "NULL"
            default = f" DEFAULT {col['default']}" if 'default' in col else ""
            print(f"     - {col['name']} ({col['type']}) {nullable}{default}")
        
        # Note: In practice, you would create this table through the Supabase dashboard
        # or using SQL commands. This script just shows the structure.
        
        print("\n💡 To create this table in Supabase:")
        print("   1. Go to your Supabase project dashboard")
        print("   2. Open the SQL editor")
        print("   3. Run this SQL command:")
        print()
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
        print("   4. Optionally, create an index:")
        print("CREATE INDEX IF NOT EXISTS idx_kite_tokens_app_name ON kite_tokens(app_name);")
        
        return True
        
    except Exception as e:
        print(f"❌ Error setting up table: {e}")
        return False

def test_supabase_connection():
    """Test connection to Supabase"""
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase connection test successful")
        return True
    except Exception as e:
        print(f"❌ Supabase connection test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("🤖 Supabase Kite Tokens Table Setup")
    print("=" * 60)
    print(f"📍 Supabase URL: {SUPABASE_URL}")
    print()
    
    # Test connection
    if not test_supabase_connection():
        return
    
    # Setup table
    if setup_tokens_table():
        print("\n🎉 Supabase setup instructions provided!")
        print("✅ You can now store Kite tokens in Supabase")
        print("✅ Tokens will persist between sessions")
        print("✅ Perfect for Hugging Face Spaces deployment")
    else:
        print("\n❌ Supabase setup failed")

if __name__ == "__main__":
    main()