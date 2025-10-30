#!/usr/bin/env python3
"""
Auto-connecting Kite API wrapper with token management

This wraps your existing KiteConnect class with automatic token refresh.
"""

import logging
from typing import Optional
from .token_manager import KiteTokenManager
from .kiteConnect import KiteConnect

logger = logging.getLogger(__name__)

class AutoKiteConnect(KiteConnect):
    """
    KiteConnect wrapper with automatic token management
    """
    
    def __init__(self, api_key: str, api_secret: str, access_token: str = None, auto_refresh: bool = True):
        """
        Initialize with automatic token management
        
        Args:
            api_key: Kite API key
            api_secret: Kite API secret  
            access_token: Initial access token (optional)
            auto_refresh: Enable automatic token refresh
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.auto_refresh = auto_refresh
        
        # Initialize token manager
        self.token_manager = KiteTokenManager(api_key, api_secret)
        
        # Get valid token
        if auto_refresh:
            valid_token = self.token_manager.get_valid_token(interactive=False)
            if valid_token:
                access_token = valid_token
        
        # Initialize parent class
        super().__init__(api_key=api_key, access_token=access_token)
    
    def _make_request_with_retry(self, method, url, **kwargs):
        """
        Make API request with automatic token refresh on auth failure
        """
        try:
            # First attempt
            return self._make_request(method, url, **kwargs)
            
        except Exception as e:
            # Check if it's an auth error
            if "401" in str(e) or "403" in str(e) or "token" in str(e).lower():
                logger.warning(f"Auth error detected: {e}")
                
                if self.auto_refresh:
                    logger.info("Attempting token refresh...")
                    
                    # Try to refresh token
                    new_token = self.token_manager.get_valid_token(interactive=False)
                    
                    if new_token:
                        # Update token and retry
                        self.access_token = new_token
                        logger.info("Token refreshed, retrying request...")
                        return self._make_request(method, url, **kwargs)
                    else:
                        logger.error("Could not refresh token automatically")
                        raise Exception("Token expired and auto-refresh failed. Please refresh manually.")
                
            # Re-raise if not auth error or auto-refresh disabled
            raise e
    
    def refresh_token_interactive(self) -> bool:
        """
        Manually refresh token with user interaction
        
        Returns:
            bool: True if successful
        """
        try:
            new_token = self.token_manager.get_valid_token(interactive=True)
            if new_token:
                self.access_token = new_token
                logger.info("Token refreshed successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Manual token refresh failed: {e}")
            return False
    
    def start_auto_refresh_scheduler(self):
        """Start background scheduler for daily token refresh checks"""
        if self.auto_refresh:
            self.token_manager.schedule_daily_refresh()
            logger.info("Auto-refresh scheduler started")
    
    def stop_auto_refresh_scheduler(self):
        """Stop background scheduler"""
        self.token_manager.stop_scheduler()
        logger.info("Auto-refresh scheduler stopped")
    
    def get_token_status(self) -> dict:
        """Get current token status information"""
        return {
            'current_token': self.access_token[:20] + "..." if self.access_token else None,
            'is_valid': self.token_manager.is_token_valid() if self.access_token else False,
            'expires_at': self.token_manager.token_expiry.isoformat() if self.token_manager.token_expiry else None,
            'auto_refresh_enabled': self.auto_refresh
        }

def create_auto_kite_connection(interactive_on_fail: bool = False) -> AutoKiteConnect:
    """
    Factory function to create AutoKiteConnect with config
    
    Args:
        interactive_on_fail: If True, prompt user for token if auto-refresh fails
        
    Returns:
        AutoKiteConnect instance
    """
    try:
        from kite_config import API_KEY, API_SECRET, ACCESS_TOKEN
        
        # Create auto-connecting instance
        kite = AutoKiteConnect(
            api_key=API_KEY,
            api_secret=API_SECRET, 
            access_token=ACCESS_TOKEN,
            auto_refresh=True
        )
        
        # Test connection
        if kite.test_connection():
            logger.info("Kite connection established successfully")
            return kite
        
        # Connection failed, try refresh if enabled
        if interactive_on_fail:
            logger.info("Connection failed, attempting interactive token refresh...")
            if kite.refresh_token_interactive():
                logger.info("Token refreshed, testing connection...")
                if kite.test_connection():
                    return kite
        
        logger.error("Failed to establish Kite connection")
        return None
        
    except ImportError:
        logger.error("Could not import Kite config. Check kite_config.py")
        return None
    except Exception as e:
        logger.error(f"Error creating Kite connection: {e}")
        return None

# Example usage functions
def demo_auto_refresh():
    """Demo of auto-refresh functionality"""
    print("🚀 Kite Auto-Connect Demo")
    print("=" * 30)
    
    # Create auto-connecting instance
    kite = create_auto_kite_connection(interactive_on_fail=True)
    
    if kite:
        print("✅ Connected successfully!")
        
        # Show token status
        status = kite.get_token_status()
        print(f"\n📊 Token Status:")
        print(f"  Valid: {status['is_valid']}")
        print(f"  Expires: {status['expires_at']}")
        print(f"  Auto-refresh: {status['auto_refresh_enabled']}")
        
        # Start scheduler
        kite.start_auto_refresh_scheduler()
        print("\n🔄 Auto-refresh scheduler started")
        print("Your API will now auto-check tokens daily at 8 AM")
        
        return kite
    else:
        print("❌ Connection failed")
        return None

if __name__ == "__main__":
    demo_auto_refresh()