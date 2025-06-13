"""
🎯 Monitoring API Endpoints
Public lightweight endpoints for beautiful monitoring dashboard
No authentication required - designed for system administrators
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from app.core.lightweight_monitor import lightweight_monitor

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get("/dashboard-data")
def get_dashboard_data() -> Dict[str, Any]:
    """
    Get comprehensive dashboard data for monitoring frontend
    Public endpoint for system monitoring - no authentication required
    """
    # Track monitoring access
    lightweight_monitor.track_user_session("monitoring_user")
    
    # Get current status
    current_status = lightweight_monitor.get_current_status()
    
    # Get historical data (last 4 hours)
    historical_data = lightweight_monitor.get_historical_data(hours=4)
    
    # Get capacity analysis
    capacity_analysis = lightweight_monitor.get_capacity_analysis()
    
    return {
        "current": current_status,
        "historical": historical_data,
        "capacity": capacity_analysis,
        "monitoring_info": {
            "collection_interval_seconds": 60,
            "data_retention_hours": 4,
            "buffer_memory_usage_kb": lightweight_monitor.metrics_buffer.get_memory_usage_kb()
        }
    }

@router.get("/quick-status")
def get_quick_status() -> Dict[str, Any]:
    """
    Get quick status for lightweight polling
    Returns only essential current metrics
    Public endpoint for quick monitoring checks
    """
    
    # Get only current status (faster than full dashboard data)
    current_status = lightweight_monitor.get_current_status()
    
    return {
        "status": current_status["health_status"]["status"],
        "cpu": current_status["metrics"]["cpu_percent"],
        "memory": current_status["metrics"]["memory_percent"],
        "users": current_status["metrics"]["active_users"],
        "response_time": current_status["metrics"]["response_time_ms"],
        "timestamp": current_status["timestamp"]
    }

@router.get("/historical/{hours}")
def get_historical_data(hours: int) -> Dict[str, Any]:
    """
    Get historical data for specific number of hours
    Useful for different chart timeframes
    Public endpoint for historical monitoring data
    """
    
    # Validate hours parameter
    if hours < 1 or hours > 24:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hours must be between 1 and 24"
        )
    
    return lightweight_monitor.get_historical_data(hours=hours)

@router.post("/track-session")
def track_user_session(user_id: str) -> Dict[str, str]:
    """
    Manually track a user session (for testing or monitoring purposes)
    Public endpoint for session tracking
    """
    
    lightweight_monitor.track_user_session(user_id)
    
    return {
        "message": f"User session {user_id} tracked",
        "active_users": str(lightweight_monitor.get_active_user_count())
    } 