import redis.asyncio as redis
import json
from typing import Any, Optional
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

class RedisClient:
    """Redis client for caching and session storage."""
    
    def __init__(self):
        self.redis_pool = None
    
    async def init_redis(self):
        """Initialize Redis connection pool."""
        try:
            self.redis_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            
            # Test connection
            async with redis.Redis(connection_pool=self.redis_pool) as r:
                await r.ping()
                logger.info("Redis connection established")
                
        except Exception as e:
            logger.error("Failed to connect to Redis", exc_info=e)
            raise
    
    async def get_redis(self) -> redis.Redis:
        """Get Redis client instance."""
        if not self.redis_pool:
            await self.init_redis()
        return redis.Redis(connection_pool=self.redis_pool)
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair in Redis."""
        try:
            client = await self.get_redis()
            serialized_value = json.dumps(value) if not isinstance(value, str) else value
            
            if expire:
                return await client.setex(key, expire, serialized_value)
            else:
                return await client.set(key, serialized_value)
                
        except Exception as e:
            logger.error("Redis SET error", key=key, exc_info=e)
            return False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis."""
        try:
            client = await self.get_redis()
            value = await client.get(key)
            
            if value is None:
                return None
            
            # Try to deserialize JSON, fallback to string
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
                
        except Exception as e:
            logger.error("Redis GET error", key=key, exc_info=e)
            return None
    
    async def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        try:
            client = await self.get_redis()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error("Redis DELETE error", key=key, exc_info=e)
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        try:
            client = await self.get_redis()
            return await client.exists(key) > 0
        except Exception as e:
            logger.error("Redis EXISTS error", key=key, exc_info=e)
            return False
    
    async def set_slot_lock(self, business_id: int, staff_id: int, start_time: str, duration_minutes: int = 5) -> bool:
        """Lock a time slot during booking process."""
        lock_key = f"slot_lock:{business_id}:{staff_id}:{start_time}"
        return await self.set(lock_key, "locked", expire=duration_minutes * 60)
    
    async def release_slot_lock(self, business_id: int, staff_id: int, start_time: str) -> bool:
        """Release a time slot lock."""
        lock_key = f"slot_lock:{business_id}:{staff_id}:{start_time}"
        return await self.delete(lock_key)
    
    async def is_slot_locked(self, business_id: int, staff_id: int, start_time: str) -> bool:
        """Check if a time slot is locked."""
        lock_key = f"slot_lock:{business_id}:{staff_id}:{start_time}"
        return await self.exists(lock_key)

# Global Redis client instance
redis_client = RedisClient()