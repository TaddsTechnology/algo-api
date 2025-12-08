import os
import redis
import ssl

# Redis configuration
REDIS_URL = os.getenv('REDIS_URL', 'rediss://default:AV__AAIncDIxMzkyZGM1MWMyMDI0MDFmOTM5ZmQ3ZTg1NjhkNTViYXAyMjQ1NzU@willing-asp-24575.upstash.io:6379')

def get_redis_client():
    """Create and return a Redis client instance"""
    try:
        # Parse the Redis URL
        # For Upstash Redis with TLS
        client = redis.from_url(
            REDIS_URL,
            ssl_cert_reqs=ssl.CERT_NONE,  # Only for Upstash free tier
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        return client
    except Exception as e:
        print(f"Error connecting to Redis: {e}")
        return None

# Test connection
if __name__ == "__main__":
    redis_client = get_redis_client()
    if redis_client:
        try:
            redis_client.ping()
            print("✅ Successfully connected to Redis")
            redis_client.set("test_key", "Hello Redis!")
            value = redis_client.get("test_key")
            print(f"✅ Test value: {value}")
        except Exception as e:
            print(f"❌ Redis connection test failed: {e}")
    else:
        print("❌ Failed to create Redis client")