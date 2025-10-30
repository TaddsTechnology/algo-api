import requests
import json
import logging
from urllib.parse import urljoin

log = logging.getLogger(__name__)

class KiteConnect:
    """Simple Kite Connect API wrapper"""
    
    def __init__(self, api_key=None, access_token=None):
        self.api_key = api_key
        self.access_token = access_token
        self.base_url = "https://api.kite.trade"
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}" if api_key and access_token else ""
        })
    
    def set_access_token(self, access_token):
        """Set access token after manual generation"""
        self.access_token = access_token
        self.session.headers.update({
            "Authorization": f"token {self.api_key}:{access_token}"
        })
        print(f"✅ Access token set: {access_token[:20]}...")
    
    def _request(self, method, endpoint, params=None):
        """Make API request"""
        url = urljoin(self.base_url, endpoint)
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params)
            elif method.upper() == "POST":
                response = self.session.post(url, data=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API Request failed: {e}")
            if e.response is not None and hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            return None
    
    def instruments(self, exchange=None):
        """Get all instruments"""
        if exchange:
            endpoint = f"/instruments/{exchange}"
        else:
            endpoint = "/instruments"
        
        try:
            response = self.session.get(urljoin(self.base_url, endpoint))
            response.raise_for_status()
            
            # Kite returns CSV for instruments
            lines = response.text.strip().split('\n')
            headers = lines[0].split(',')
            
            instruments = []
            for line in lines[1:]:
                values = line.split(',')
                if len(values) == len(headers):
                    instrument = dict(zip(headers, values))
                    instruments.append(instrument)
            
            return {"data": instruments}
            
        except Exception as e:
            print(f"❌ Error fetching instruments: {e}")
            return {"data": []}
    
    def quote(self, instruments):
        """Get market quotes (requires market data subscription)"""
        if isinstance(instruments, str):
            instruments = [instruments]
        
        params = {"i": instruments}
        return self._request("GET", "/quote", params)
    
    def ltp(self, instruments):
        """Get Last Traded Price (basic endpoint, may work without full market data subscription)"""
        if isinstance(instruments, str):
            instruments = [instruments]
        
        params = {"i": instruments}
        return self._request("GET", "/quote/ltp", params)
    
    def historical_data(self, instrument_token, from_date, to_date, interval="day"):
        """Get historical data"""
        endpoint = f"/instruments/historical/{instrument_token}/{interval}"
        params = {
            "from": from_date,
            "to": to_date
        }
        return self._request("GET", endpoint, params)
    
    def profile(self):
        """Get user profile"""
        return self._request("GET", "/user/profile")
    
    def margins(self):
        """Get account margins"""
        return self._request("GET", "/user/margins")
    
    def positions(self):
        """Get positions"""
        return self._request("GET", "/portfolio/positions")
    
    def holdings(self):
        """Get holdings"""
        return self._request("GET", "/portfolio/holdings")
    
    def orders(self):
        """Get orders"""
        return self._request("GET", "/orders")
    
    def place_order(self, variety, exchange, tradingsymbol, transaction_type, 
                   quantity, product, order_type, price=None, validity="DAY"):
        """Place order"""
        params = {
            "variety": variety,
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "product": product,
            "order_type": order_type,
            "validity": validity
        }
        
        if price:
            params["price"] = price
            
        return self._request("POST", "/orders/regular", params)
    
    def test_connection(self):
        """Test API connection"""
        try:
            profile = self.profile()
            if profile and 'data' in profile:
                print(f"✅ Connected to Kite API")
                print(f"👤 User: {profile['data'].get('user_name', 'Unknown')}")
                print(f"📧 Email: {profile['data'].get('email', 'Unknown')}")
                return True
            else:
                print("❌ Failed to get profile data")
                return False
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False