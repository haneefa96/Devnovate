"""
Munshi - LLM cache

This module handles disk caching for LLM responses.
"""

import os
import json
import hashlib
import pickle
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from functools import wraps

from munshi.config import settings


class DiskCache:
    """
    Disk cache for LLM responses.
    
    Cache key is based on:
    - Model ID
    - Message hash
    - Temperature
    - Response format
    
    Cache entries expire after TTL (default 24 hours).
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(exist_ok=True)
        self._ttl_seconds = int(os.getenv("CACHE_TTL", "86400"))  # Default 24 hours
    
    def _make_key(self, model: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate cache key from inputs."""
        key_data = {
            "model": model,
            "messages": messages,
            **kwargs,
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()[:32]
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for key."""
        return self._cache_dir / f"{key}.pkl"
    
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response if valid.
        
        Args:
            key: Cache key
        
        Returns:
            Cached response dict or None if not found or expired
        """
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, "rb") as f:
                entry = pickle.load(f)
            
            # Check if expired
            created_at = entry.get("created_at", 0)
            if time.time() - created_at > self._ttl_seconds:
                # Delete expired entry
                cache_path.unlink()
                return None
            
            return entry.get("data")
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
            return None
    
    def set(self, key: str, value: Dict[str, Any]) -> bool:
        """
        Set cached response.
        
        Args:
            key: Cache key
            value: Response data to cache
        
        Returns:
            True if successful
        """
        cache_path = self._get_cache_path(key)
        try:
            entry = {
                "data": value,
                "created_at": time.time(),
                "ttl_seconds": self._ttl_seconds,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(entry, f)
            return True
        except Exception as e:
            logger.warning(f"Cache write error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete cached entry.
        
        Args:
            key: Cache key
        
        Returns:
            True if deleted
        """
        cache_path = self._get_cache_path(key)
        try:
            if cache_path.exists():
                cache_path.unlink()
            return True
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False
    
    def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries deleted
        """
        deleted = 0
        for cache_file in self._cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete {cache_file}: {e}")
        return deleted
    
    def clear_expired(self) -> int:
        """
        Clear expired cache entries.
        
        Returns:
            Number of entries deleted
        """
        deleted = 0
        current_time = time.time()
        
        for cache_file in self._cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, "rb") as f:
                    entry = pickle.load(f)
                
                created_at = entry.get("created_at", 0)
                ttl = entry.get("ttl_seconds", self._ttl_seconds)
                
                if current_time - created_at > ttl:
                    cache_file.unlink()
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to check {cache_file}: {e}")
        
        return deleted
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        files = list(self._cache_dir.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in files)
        return {
            "total_entries": len(files),
            "total_size_bytes": total_size,
            "cache_dir": str(self._cache_dir),
        }


# Global cache instance
cache = DiskCache()


def cached_llm_call(model: str):
    """
    Decorator for caching LLM calls.
    
    Usage:
        @cached_llm_call("openai/gpt-oss-120b")
        async def my_llm_call(messages):
            ...
    
    Args:
        model: Model ID to cache under
    
    Returns:
        Decorated async function
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function arguments
            cache_key = cache._make_key(
                model,
                args[0] if args else [],
                **kwargs,
            )
            
            # Check cache
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {cache_key[:8]}...")
                return cached
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result (don't fail if cache write fails)
            cache.set(cache_key, result)
            
            return result
        
        return wrapper
    return decorator


class AsyncCache:
    """
    Async wrapper for DiskCache with TTL support.
    """
    
    def __init__(self, cache: DiskCache = None):
        self._cache = cache or cache
    
    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response."""
        return self._cache.get(key)
    
    async def set(self, key: str, value: Dict[str, Any]) -> bool:
        """Set cached response."""
        return self._cache.set(key, value)
    
    async def delete(self, key: str) -> bool:
        """Delete cached entry."""
        return self._cache.delete(key)
    
    async def clear_expired(self) -> int:
        """Clear expired entries."""
        return self._cache.clear_expired()


async_cache = AsyncCache(cache)


def generate_cache_key(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    response_format: str = None,
    **kwargs,
) -> str:
    """
    Generate cache key for LLM request.
    
    Args:
        model: Model ID
        messages: Message history
        temperature: Sampling temperature
        response_format: Response format identifier
    
    Returns:
        Cache key string
    """
    key_data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": response_format,
        **kwargs,
    }
    key_json = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_json.encode()).hexdigest()[:32]
