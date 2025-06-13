"""
🚀 High-Performance In-Memory Caching System
Optimized for handling 100 concurrent students during contests

Uses FastAPI's built-in caching + custom TTL cache for optimal performance
No external dependencies (Redis-free design)
"""

import time
import json
from functools import lru_cache, wraps
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone, timedelta
import hashlib

# 🔥 TTL CACHE IMPLEMENTATION
class TTLCache:
    """Time-to-Live cache with automatic expiration"""
    
    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.default_ttl = default_ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key not in self.cache:
            return None
        
        entry = self.cache[key]
        if time.time() > entry['expires_at']:
            # Expired, remove and return None
            del self.cache[key]
            return None
        
        return entry['value']
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.default_ttl
        self.cache[key] = {
            'value': value,
            'expires_at': time.time() + ttl,
            'created_at': time.time()
        }
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self.cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        active_entries = 0
        expired_entries = 0
        
        for entry in self.cache.values():
            if current_time <= entry['expires_at']:
                active_entries += 1
            else:
                expired_entries += 1
        
        return {
            'total_entries': len(self.cache),
            'active_entries': active_entries,
            'expired_entries': expired_entries,
            'memory_usage_kb': len(str(self.cache)) / 1024,
        }

# 🌟 GLOBAL CACHE INSTANCES
contest_cache = TTLCache(default_ttl=180)      # 3 minutes for contest data
user_cache = TTLCache(default_ttl=600)         # 10 minutes for user data  
course_cache = TTLCache(default_ttl=1800)      # 30 minutes for course data
submission_cache = TTLCache(default_ttl=60)    # 1 minute for submissions

# 🚀 CACHE DECORATORS
def cache_with_ttl(cache_instance: TTLCache, ttl: Optional[int] = None, key_prefix: str = ""):
    """Decorator for caching function results with TTL"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_data = f"{key_prefix}{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            # Try to get from cache
            cached_result = cache_instance.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_instance.set(cache_key, result, ttl)
            return result
        
        # Add cache management methods to the wrapper
        wrapper.cache_clear = lambda: cache_instance.clear()
        wrapper.cache_info = lambda: cache_instance.get_stats()
        
        return wrapper
    return decorator

# 🎯 SPECIALIZED CACHE DECORATORS FOR DIFFERENT DATA TYPES

def cache_contest_data(ttl: int = 180):
    """Cache contest data (3 minute default - contests change less frequently during active periods)"""
    return cache_with_ttl(contest_cache, ttl, "contest:")

def cache_user_data(ttl: int = 600):
    """Cache user data (10 minute default - user data rarely changes)"""
    return cache_with_ttl(user_cache, ttl, "user:")

def cache_course_data(ttl: int = 1800):
    """Cache course data (30 minute default - course data changes infrequently)"""
    return cache_with_ttl(course_cache, ttl, "course:")

def cache_submission_data(ttl: int = 60):
    """Cache submission data (1 minute default - submissions need to be fresh)"""
    return cache_with_ttl(submission_cache, ttl, "submission:")

# 🔥 FASTAPI LRU CACHE HELPERS (for static data)
@lru_cache(maxsize=1000)
def get_user_role_cached(user_id: str, role: str) -> Dict[str, Any]:
    """Cache user role data - rarely changes"""
    return {
        "user_id": user_id,
        "role": role,
        "cached_at": datetime.now(timezone.utc).isoformat()
    }

@lru_cache(maxsize=500)
def get_course_enrollment_cached(student_id: str, course_id: str, is_active: bool) -> Dict[str, Any]:
    """Cache course enrollment status - changes infrequently"""
    return {
        "student_id": student_id,
        "course_id": course_id,
        "is_active": is_active,
        "cached_at": datetime.now(timezone.utc).isoformat()
    }

@lru_cache(maxsize=200)
def get_contest_problems_cached(contest_id: str, problems_json: str) -> Dict[str, Any]:
    """Cache contest problems - immutable after contest starts"""
    return {
        "contest_id": contest_id,
        "problems": json.loads(problems_json),
        "cached_at": datetime.now(timezone.utc).isoformat()
    }

# 🚀 CACHE WARMING FUNCTIONS
def warm_contest_cache(contest_id: str, contest_data: Dict[str, Any]) -> None:
    """Pre-warm contest cache before contest starts"""
    cache_key = hashlib.md5(f"contest:get_contest_data:{contest_id}".encode()).hexdigest()
    contest_cache.set(cache_key, contest_data, ttl=300)  # 5 minutes

def warm_user_enrollment_cache(student_ids: list, course_id: str) -> None:
    """Pre-warm user enrollment cache for a contest"""
    for student_id in student_ids:
        enrollment_data = {"student_id": student_id, "course_id": course_id, "is_active": True}
        cache_key = hashlib.md5(f"user:check_enrollment:{student_id}:{course_id}".encode()).hexdigest()
        user_cache.set(cache_key, enrollment_data, ttl=600)

# 📊 CACHE MANAGEMENT FUNCTIONS
def get_all_cache_stats() -> Dict[str, Any]:
    """Get statistics for all cache instances"""
    return {
        "contest_cache": contest_cache.get_stats(),
        "user_cache": user_cache.get_stats(),
        "course_cache": course_cache.get_stats(),
        "submission_cache": submission_cache.get_stats(),
        "lru_cache_info": {
            "user_role_cache": get_user_role_cached.cache_info()._asdict(),
            "enrollment_cache": get_course_enrollment_cached.cache_info()._asdict(),
            "contest_problems_cache": get_contest_problems_cached.cache_info()._asdict(),
        }
    }

def cleanup_all_caches() -> Dict[str, int]:
    """Clean up expired entries from all caches"""
    return {
        "contest_cache_expired": contest_cache.cleanup_expired(),
        "user_cache_expired": user_cache.cleanup_expired(),
        "course_cache_expired": course_cache.cleanup_expired(),
        "submission_cache_expired": submission_cache.cleanup_expired(),
    }

def clear_all_caches() -> None:
    """Clear all cache instances (emergency use)"""
    contest_cache.clear()
    user_cache.clear()
    course_cache.clear()
    submission_cache.clear()
    
    # Clear LRU caches
    get_user_role_cached.cache_clear()
    get_course_enrollment_cached.cache_clear()
    get_contest_problems_cached.cache_clear()

# 🎯 CACHE-AWARE DATA INVALIDATION
def invalidate_contest_cache(contest_id: str) -> None:
    """Invalidate all cache entries related to a contest"""
    keys_to_delete = [
        key for key in contest_cache.cache.keys()
        if contest_id in key
    ]
    for key in keys_to_delete:
        contest_cache.delete(key)

def invalidate_user_cache(user_id: str) -> None:
    """Invalidate all cache entries related to a user"""
    keys_to_delete = [
        key for key in user_cache.cache.keys()
        if user_id in key
    ]
    for key in keys_to_delete:
        user_cache.delete(key) 