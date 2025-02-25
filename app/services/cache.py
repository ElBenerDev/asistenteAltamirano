from typing import Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class PropertyCache:
    def __init__(self, ttl_minutes: int = 15):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self.ttl = timedelta(minutes=ttl_minutes)
        logger.info(f"Property cache initialized with {ttl_minutes} minutes TTL")

    def get(self, key: str) -> Any:
        """Get value from cache if not expired"""
        if key not in self._cache:
            return None
        
        if datetime.now() - self._timestamps[key] > self.ttl:
            del self._cache[key]
            del self._timestamps[key]
            return None
            
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp"""
        self._cache[key] = value
        self._timestamps[key] = datetime.now()

    def clear(self) -> None:
        """Clear all cached data"""
        self._cache.clear()
        self._timestamps.clear()