"""
🚀 Performance Monitoring & Rate Limiting Module
Designed for handling 100+ concurrent students during contests

Features:
- Smart rate limiting with burst allowance
- Performance monitoring and metrics
- Memory usage tracking
- Request queuing for high load
"""

import time
import psutil
import asyncio
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
from functools import wraps
from fastapi import HTTPException, status
import threading
from dataclasses import dataclass

# 📊 PERFORMANCE METRICS TRACKING
@dataclass
class PerformanceMetrics:
    """Performance metrics container"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    active_connections: int
    requests_per_minute: int
    average_response_time_ms: float
    error_rate_percent: float

class PerformanceMonitor:
    """Real-time performance monitoring"""
    
    def __init__(self, history_minutes: int = 60):
        self.history_minutes = history_minutes
        self.metrics_history: deque = deque(maxlen=history_minutes * 60)  # Store per second
        self.request_times: deque = deque(maxlen=1000)  # Last 1000 requests
        self.error_count: int = 0
        self.total_requests: int = 0
        self.start_time: datetime = datetime.now(timezone.utc)
        
        # Thread-safe locks
        self._lock = threading.Lock()
        
        # Auto-cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    def record_request(self, duration_ms: float, is_error: bool = False) -> None:
        """Record a request for performance tracking"""
        with self._lock:
            self.request_times.append(duration_ms)
            self.total_requests += 1
            if is_error:
                self.error_count += 1
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get current system performance metrics"""
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        # Application metrics
        current_time = datetime.now(timezone.utc)
        with self._lock:
            # Calculate requests per minute
            recent_requests = len([
                req_time for req_time in self.request_times
                if (time.time() - req_time) < 60
            ])
            
            # Calculate average response time
            avg_response_time = (
                sum(self.request_times) / len(self.request_times)
                if self.request_times else 0.0
            )
            
            # Calculate error rate
            error_rate = (
                (self.error_count / self.total_requests * 100)
                if self.total_requests > 0 else 0.0
            )
        
        metrics = PerformanceMetrics(
            timestamp=current_time,
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            active_connections=0,  # Will be set by database module
            requests_per_minute=recent_requests,
            average_response_time_ms=avg_response_time,
            error_rate_percent=error_rate
        )
        
        self.metrics_history.append(metrics)
        return metrics
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for the last hour"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        recent_metrics = list(self.metrics_history)[-300:]  # Last 5 minutes
        
        return {
            "current": {
                "cpu_percent": recent_metrics[-1].cpu_percent if recent_metrics else 0,
                "memory_percent": recent_metrics[-1].memory_percent if recent_metrics else 0,
                "requests_per_minute": recent_metrics[-1].requests_per_minute if recent_metrics else 0,
                "average_response_time_ms": recent_metrics[-1].average_response_time_ms if recent_metrics else 0,
            },
            "averages_5min": {
                "cpu_percent": sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0,
                "memory_percent": sum(m.memory_percent for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0,
                "response_time_ms": sum(m.average_response_time_ms for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0,
            },
            "peak_usage": {
                "max_cpu": max((m.cpu_percent for m in recent_metrics), default=0),
                "max_memory": max((m.memory_percent for m in recent_metrics), default=0),
                "max_response_time": max((m.average_response_time_ms for m in recent_metrics), default=0),
            },
            "total_requests": self.total_requests,
            "error_rate": recent_metrics[-1].error_rate_percent if recent_metrics else 0,
            "uptime_seconds": (datetime.now(timezone.utc) - self.start_time).total_seconds()
        }
    
    def _cleanup_loop(self):
        """Background cleanup of old metrics"""
        while True:
            time.sleep(60)  # Run every minute
            current_time = time.time()
            
            # Clean up old request times (keep only last hour)
            with self._lock:
                while self.request_times and (current_time - self.request_times[0]) > 3600:
                    self.request_times.popleft()

# 🔥 SMART RATE LIMITING
class SmartRateLimiter:
    """Advanced rate limiting with burst allowance and contest awareness"""
    
    def __init__(self):
        self.user_requests: Dict[str, deque] = defaultdict(lambda: deque())
        self.contest_mode: bool = False
        self.contest_multiplier: float = 2.0  # Allow 2x more requests during contests
        self._lock = threading.Lock()
    
    def set_contest_mode(self, enabled: bool, multiplier: float = 2.0):
        """Enable/disable contest mode with higher rate limits"""
        with self._lock:
            self.contest_mode = enabled
            self.contest_multiplier = multiplier
    
    def check_rate_limit(self, user_id: str, requests_per_minute: int = 60) -> tuple[bool, Dict[str, Any]]:
        """
        Check if user is within rate limits
        Returns (is_allowed, rate_limit_info)
        """
        current_time = time.time()
        
        with self._lock:
            user_queue = self.user_requests[user_id]
            
            # Remove requests older than 1 minute
            while user_queue and (current_time - user_queue[0]) > 60:
                user_queue.popleft()
            
            # Calculate effective rate limit
            effective_limit = (
                int(requests_per_minute * self.contest_multiplier)
                if self.contest_mode else requests_per_minute
            )
            
            # Check if under limit
            current_count = len(user_queue)
            is_allowed = current_count < effective_limit
            
            if is_allowed:
                user_queue.append(current_time)
            
            rate_info = {
                "requests_made": current_count,
                "requests_limit": effective_limit,
                "requests_remaining": max(0, effective_limit - current_count),
                "reset_time": int(current_time + 60),
                "contest_mode": self.contest_mode,
                "retry_after": 60 if not is_allowed else 0
            }
            
            return is_allowed, rate_info
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get rate limiting stats for a specific user"""
        current_time = time.time()
        
        with self._lock:
            user_queue = self.user_requests[user_id]
            
            # Clean old requests
            while user_queue and (current_time - user_queue[0]) > 60:
                user_queue.popleft()
            
            return {
                "user_id": user_id,
                "requests_last_minute": len(user_queue),
                "first_request_time": user_queue[0] if user_queue else None,
                "last_request_time": user_queue[-1] if user_queue else None,
                "contest_mode": self.contest_mode
            }

# 📈 REQUEST QUEUE MANAGEMENT
class RequestQueue:
    """Request queuing system for high load periods"""
    
    def __init__(self, max_queue_size: int = 1000):
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.processing = False
        self.processed_count = 0
        self.dropped_count = 0
        
    async def enqueue_request(self, request_data: Dict[str, Any], priority: int = 1) -> bool:
        """
        Enqueue a request for processing
        priority: 1 (normal), 2 (high), 3 (critical)
        """
        try:
            request_item = {
                "data": request_data,
                "priority": priority,
                "timestamp": time.time(),
                "request_id": f"{request_data.get('user_id', 'unknown')}_{time.time()}"
            }
            
            self.queue.put_nowait(request_item)
            return True
        except asyncio.QueueFull:
            self.dropped_count += 1
            return False
    
    async def process_queue(self, processor_func):
        """Process queued requests with priority handling"""
        self.processing = True
        
        while self.processing:
            try:
                # Wait for requests with timeout
                request_item = await asyncio.wait_for(
                    self.queue.get(), timeout=1.0
                )
                
                # Process the request
                await processor_func(request_item)
                self.processed_count += 1
                
                # Mark task done
                self.queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing queued request: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        return {
            "queue_size": self.queue.qsize(),
            "max_size": self.queue.maxsize,
            "processing": self.processing,
            "processed_count": self.processed_count,
            "dropped_count": self.dropped_count,
            "queue_full": self.queue.full()
        }

# 🌟 GLOBAL INSTANCES
performance_monitor = PerformanceMonitor()
rate_limiter = SmartRateLimiter()
request_queue = RequestQueue()

# 🚀 DECORATORS
def monitor_performance(func):
    """Decorator to monitor endpoint performance"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        is_error = False
        
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            is_error = True
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            performance_monitor.record_request(duration_ms, is_error)
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        is_error = False
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            is_error = True
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            performance_monitor.record_request(duration_ms, is_error)
    
    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

def rate_limit(requests_per_minute: int = 60):
    """Decorator for rate limiting endpoints"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract user_id from kwargs or args
            current_user = kwargs.get('current_user')
            user_id = getattr(current_user, 'id', 'anonymous') if current_user else 'anonymous'
            
            is_allowed, rate_info = rate_limiter.check_rate_limit(user_id, requests_per_minute)
            
            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {rate_info['retry_after']} seconds.",
                    headers={
                        "X-RateLimit-Limit": str(rate_info['requests_limit']),
                        "X-RateLimit-Remaining": str(rate_info['requests_remaining']),
                        "X-RateLimit-Reset": str(rate_info['reset_time']),
                        "Retry-After": str(rate_info['retry_after'])
                    }
                )
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract user_id from kwargs or args  
            current_user = kwargs.get('current_user')
            user_id = getattr(current_user, 'id', 'anonymous') if current_user else 'anonymous'
            
            is_allowed, rate_info = rate_limiter.check_rate_limit(user_id, requests_per_minute)
            
            if not is_allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Try again in {rate_info['retry_after']} seconds.",
                    headers={
                        "X-RateLimit-Limit": str(rate_info['requests_limit']),
                        "X-RateLimit-Remaining": str(rate_info['requests_remaining']),
                        "X-RateLimit-Reset": str(rate_info['reset_time']),
                        "Retry-After": str(rate_info['retry_after'])
                    }
                )
            
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

# 🎯 HEALTH CHECK UTILITIES
def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health status"""
    metrics = performance_monitor.get_current_metrics()
    
    # Determine health status
    health_status = "healthy"
    issues = []
    
    if metrics.cpu_percent > 80:
        health_status = "warning"
        issues.append("High CPU usage")
    
    if metrics.memory_percent > 85:
        health_status = "critical" if health_status != "critical" else health_status
        issues.append("High memory usage")
    
    if metrics.average_response_time_ms > 1000:
        health_status = "warning" if health_status == "healthy" else health_status
        issues.append("Slow response times")
    
    if metrics.error_rate_percent > 5:
        health_status = "critical"
        issues.append("High error rate")
    
    return {
        "status": health_status,
        "timestamp": metrics.timestamp.isoformat(),
        "issues": issues,
        "metrics": {
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "memory_used_mb": metrics.memory_used_mb,
            "requests_per_minute": metrics.requests_per_minute,
            "average_response_time_ms": metrics.average_response_time_ms,
            "error_rate_percent": metrics.error_rate_percent
        },
        "queue_stats": request_queue.get_queue_stats(),
        "performance_summary": performance_monitor.get_performance_summary()
    } 