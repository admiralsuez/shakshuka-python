"""
Request Deduplication Middleware - Prevent duplicate API calls
"""

from functools import wraps
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import hashlib
import json


class RequestDeduplicator:
    """Deduplicates identical requests within a time window"""
    
    def __init__(self, window_seconds: int = 5):
        """
        Args:
            window_seconds: Time window for deduplication (default 5 seconds)
        """
        self.window_seconds = window_seconds
        self.request_cache: Dict[str, Tuple[datetime, any]] = {}
    
    def _get_request_hash(self, method: str, path: str, data: Optional[str] = None) -> str:
        """Generate hash for request deduplication
        
        Args:
            method: HTTP method
            path: Request path
            data: Request body (JSON string)
        
        Returns:
            Hash string
        """
        key = f"{method}:{path}"
        if data:
            key += f":{data}"
        
        return hashlib.md5(key.encode()).hexdigest()
    
    def is_duplicate(self, method: str, path: str, data: Optional[str] = None) -> bool:
        """Check if request is a duplicate
        
        Args:
            method: HTTP method
            path: Request path
            data: Request body (JSON string)
        
        Returns:
            True if duplicate, False otherwise
        """
        request_hash = self._get_request_hash(method, path, data)
        now = datetime.now()
        
        # Clean old entries
        expired_keys = [
            k for k, (timestamp, _) in self.request_cache.items()
            if (now - timestamp).total_seconds() > self.window_seconds
        ]
        for key in expired_keys:
            del self.request_cache[key]
        
        # Check if duplicate
        if request_hash in self.request_cache:
            return True
        
        # Record request
        self.request_cache[request_hash] = (now, None)
        return False
    
    def cache_response(self, method: str, path: str, data: Optional[str], response: any) -> None:
        """Cache response for duplicate requests
        
        Args:
            method: HTTP method
            path: Request path
            data: Request body (JSON string)
            response: Response to cache
        """
        request_hash = self._get_request_hash(method, path, data)
        now = datetime.now()
        self.request_cache[request_hash] = (now, response)
    
    def get_cached_response(self, method: str, path: str, data: Optional[str] = None) -> Optional[any]:
        """Get cached response for duplicate request
        
        Args:
            method: HTTP method
            path: Request path
            data: Request body (JSON string)
        
        Returns:
            Cached response or None
        """
        request_hash = self._get_request_hash(method, path, data)
        now = datetime.now()
        
        if request_hash in self.request_cache:
            timestamp, response = self.request_cache[request_hash]
            if (now - timestamp).total_seconds() <= self.window_seconds:
                return response
        
        return None


# Global deduplicator instance
_deduplicator = RequestDeduplicator(window_seconds=5)


def deduplicate_request(func):
    """Decorator to deduplicate identical requests
    
    Prevents duplicate API calls within 5 seconds.
    Returns cached response if duplicate detected.
    
    Usage:
        @task_bp.route('/tasks', methods=['GET'])
        @deduplicate_request
        def get_tasks():
            # Identical requests within 5 seconds will return cached response
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from flask import request
        
        # Get request info
        method = request.method
        path = request.path
        data = None
        
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                if request.is_json:
                    data = json.dumps(request.json, sort_keys=True)
                elif request.data:
                    data = request.data.decode('utf-8')
            except Exception:  # noqa: broad-except
                logger.debug("Could not extract request data for deduplication")
        
        # Check for duplicate
        if _deduplicator.is_duplicate(method, path, data):
            cached = _deduplicator.get_cached_response(method, path, data)
            if cached is not None:
                return cached
        
        # Execute function
        response = func(*args, **kwargs)
        
        # Cache response
        _deduplicator.cache_response(method, path, data, response)
        
        return response
    
    return wrapper


def clear_deduplication_cache():
    """Clear deduplication cache (useful for testing)"""
    global _deduplicator
    _deduplicator.request_cache.clear()


def set_deduplication_window(seconds: int):
    """Set deduplication time window
    
    Args:
        seconds: Time window in seconds
    """
    global _deduplicator
    _deduplicator.window_seconds = seconds
