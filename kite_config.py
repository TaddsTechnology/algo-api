# Kite API Configuration
# IMPORTANT: These values should be set via environment variables for security
# Set these in your HuggingFace Space secrets:
# - KITE_API_KEY
# - KITE_API_SECRET
# - KITE_USER_ID
# - KITE_PASSWORD
# - KITE_TOTP_SECRET
# - KITE_ACCESS_TOKEN

import os

# Load .env file for local development
from dotenv import load_dotenv
load_dotenv()

# Read from environment variables
API_KEY = os.getenv('KITE_API_KEY', '')
API_SECRET = os.getenv('KITE_API_SECRET', '')
USER_ID = os.getenv('KITE_USER_ID', '')
PASSWORD = os.getenv('KITE_PASSWORD', '')
TOTP_SECRET = os.getenv('KITE_TOTP_SECRET', '')
ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN', '')

# Validation - only warn if running locally without environment setup
if not os.environ.get('KITE_API_KEY'):
    print("[WARNING] Set KITE_API_KEY in environment variables for production")
