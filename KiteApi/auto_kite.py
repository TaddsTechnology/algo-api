#!/usr/bin/env python3
"""
Drop-in replacement for KiteConnect with automatic token management

Use this instead of your regular KiteConnect import for automatic token refresh.
"""

import logging
from typing import Optional
from .auto_token_manager import setup_automated_kite_manager
from .kiteConnect import KiteConnect

logger = logging.getLogger(__name__)

class AutoKite(KiteConnect):
    """
    Drop-in replacement for KiteConnect with automatic token management
    """
    
    _manager = None
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        # Singleton pattern - reuse the same manager
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, api_key: str = None, access_token: str = None):
        # Initialize manager only once
        if AutoKite._manager is None:
            AutoKite._manager = setup_automated_kite_manager()
            
            if AutoKite._manager:
                # Start background service
                AutoKite._manager.start_automated_refresh_service()
                logger.info("🤖 Auto token manager started")
            else:
                logger.error("❌ Failed to initialize auto token manager")
        
        # Get valid token
        if AutoKite._manager:
            valid_token = AutoKite._manager.get_valid_token()
            if valid_token:
                access_token = valid_token
                api_key = AutoKite._manager.api_key
        
        # Initialize parent KiteConnect
        if hasattr(self, '_initialized'):
            return
            
        super().__init__(api_key=api_key, access_token=access_token)
        self._initialized = True
    
    def _make_request(self, method, url, **kwargs):
        """Override to add automatic retry with token refresh"""
        try:
            # First attempt
            return super()._make_request(method, url, **kwargs)
            
        except Exception as e:
            # Check if it's an authentication error
            error_str = str(e).lower()
            if any(x in error_str for x in ['401', '403', 'token', 'unauthorized', 'forbidden']):
                logger.warning(f"Auth error detected: {e}")
                
                if AutoKite._manager:
                    logger.info("Attempting automatic token refresh...")
                    
                    # Get fresh token
                    new_token = AutoKite._manager.get_valid_token()
                    
                    if new_token:
                        # Update token and retry
                        self.access_token = new_token
                        logger.info("Token refreshed, retrying request...")
                        return super()._make_request(method, url, **kwargs)
                    else:
                        logger.error("Could not refresh token automatically")
                        
            # Re-raise if not auth error or refresh failed
            raise e
    
    @staticmethod
    def stop_auto_refresh():
        """Stop the background auto-refresh service"""
        if AutoKite._manager:
            AutoKite._manager.stop_service()
            logger.info("Auto-refresh service stopped")

# Factory function for easy usage
def get_kite() -> AutoKite:
    """
    Get an auto-refreshing Kite connection
    
    Returns:
        AutoKite instance with automatic token management
    """
    return AutoKite()

# For backward compatibility
def create_kite_connection() -> AutoKite:
    """Create auto-refreshing Kite connection (alias for get_kite)"""
    return get_kite()

# Example usage
if __name__ == "__main__":
    print("🚀 Auto Kite Demo")
    print("=" * 30)
    
    # Simple usage - just import and use
    kite = get_kite()
    
    if kite:
        try:
            # Test API calls
            profile = kite.get_user_profile()
            print(f"✅ User: {profile.get('user_name', 'Unknown')}")
            
            instruments = kite.get_instruments()
            print(f"✅ Instruments: {len(instruments)}")
            
            print("\n🎯 Auto-refresh is active!")
            print("Your tokens will refresh automatically")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    else:
        print("❌ Could not create Kite connection")