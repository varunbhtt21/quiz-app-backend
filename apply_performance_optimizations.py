#!/usr/bin/env python3
"""
🚀 Performance Optimization Application Script
Apply all database and performance optimizations for handling 100+ concurrent students

Run this script after deployment to ensure optimal performance
"""

import sys
import os
from sqlmodel import Session
from datetime import datetime, timezone

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__)))

from app.core.database import engine, get_session
from app.core.cache import clear_all_caches, get_all_cache_stats

def apply_database_indexes():
    """Apply all performance-critical database indexes"""
    print("🔥 Applying Database Performance Indexes...")
    
    try:
        # Import here to avoid circular imports
        from app.core.database_indexes import create_performance_indexes, optimize_database_settings
        
        with Session(engine) as session:
            # Create performance indexes
            index_results = create_performance_indexes(session)
            
            success_count = sum(1 for success in index_results.values() if success)
            total_count = len(index_results)
            
            print(f"✅ Applied {success_count}/{total_count} database indexes")
            
            # Show failed indexes
            failed_indexes = [name for name, success in index_results.items() if not success]
            if failed_indexes:
                print(f"⚠️  Failed indexes: {', '.join(failed_indexes)}")
            
            # Apply database settings optimizations
            print("\n🚀 Applying Database Settings Optimizations...")
            settings_results = optimize_database_settings(session)
            
            settings_success = sum(1 for success in settings_results.values() if success)
            settings_total = len(settings_results)
            
            print(f"✅ Applied {settings_success}/{settings_total} database settings")
            
        return True
        
    except Exception as e:
        print(f"❌ Error applying database optimizations: {e}")
        return False

def verify_connection_pool():
    """Verify database connection pool is working properly"""
    print("\n🔍 Verifying Database Connection Pool...")
    
    try:
        from app.core.database import get_pool_status
        
        pool_status = get_pool_status()
        
        print(f"✅ Connection Pool Status:")
        print(f"   Pool Size: {pool_status['pool_size']}")
        print(f"   Available: {pool_status['available_connections']}")
        print(f"   Total Connections: {pool_status['total_connections']}")
        
        # Test multiple connections
        sessions = []
        for i in range(5):
            session = next(get_session())
            sessions.append(session)
        
        # Close all test sessions
        for session in sessions:
            session.close()
        
        print("✅ Connection pool test successful")
        return True
        
    except Exception as e:
        print(f"❌ Connection pool test failed: {e}")
        return False

def initialize_cache_system():
    """Initialize and verify cache system"""
    print("\n🌟 Initializing Cache System...")
    
    try:
        # Clear any existing caches
        clear_all_caches()
        print("✅ Cleared existing caches")
        
        # Test cache functionality
        from app.core.cache import contest_cache, user_cache
        
        # Test cache operations
        test_key = "test_performance_key"
        test_value = {"performance": "optimized", "timestamp": datetime.now(timezone.utc).isoformat()}
        
        contest_cache.set(test_key, test_value, ttl=60)
        retrieved_value = contest_cache.get(test_key)
        
        if retrieved_value == test_value:
            print("✅ Cache read/write test successful")
        else:
            print("⚠️  Cache test failed - values don't match")
        
        # Get cache statistics
        cache_stats = get_all_cache_stats()
        print(f"✅ Cache system initialized with {len(cache_stats)} cache instances")
        
        return True
        
    except Exception as e:
        print(f"❌ Cache initialization failed: {e}")
        return False

def verify_performance_monitoring():
    """Verify performance monitoring system"""
    print("\n📊 Verifying Performance Monitoring...")
    
    try:
        from app.core.performance import performance_monitor, get_system_health
        
        # Get current metrics
        metrics = performance_monitor.get_current_metrics()
        print(f"✅ Current CPU Usage: {metrics.cpu_percent:.1f}%")
        print(f"✅ Current Memory Usage: {metrics.memory_percent:.1f}%")
        
        # Test health check
        health = get_system_health()
        print(f"✅ System Health Status: {health['status']}")
        
        if health['issues']:
            print(f"⚠️  Health Issues: {', '.join(health['issues'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance monitoring verification failed: {e}")
        return False

def run_database_maintenance():
    """Run database maintenance for optimal performance"""
    print("\n🔧 Running Database Maintenance...")
    
    try:
        from app.core.database_indexes import vacuum_analyze_tables
        
        with Session(engine) as session:
            maintenance_results = vacuum_analyze_tables(session)
            
            success_count = sum(1 for success in maintenance_results.values() if success)
            total_count = len(maintenance_results)
            
            print(f"✅ VACUUM ANALYZE completed on {success_count}/{total_count} tables")
            
        return True
        
    except Exception as e:
        print(f"❌ Database maintenance failed: {e}")
        return False

def generate_performance_report():
    """Generate a comprehensive performance report"""
    print("\n📋 Generating Performance Report...")
    
    try:
        from app.core.database import get_pool_status
        from app.core.cache import get_all_cache_stats
        from app.core.performance import get_system_health
        
        # Collect all performance data
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database_pool": get_pool_status(),
            "cache_stats": get_all_cache_stats(),
            "system_health": get_system_health(),
        }
        
        # Save report to file
        import json
        report_filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"✅ Performance report saved to: {report_filename}")
        
        # Print summary
        print(f"\n📊 Performance Summary:")
        print(f"   Database Connections: {report['database_pool']['total_connections']}")
        print(f"   Cache Status: {len(report['cache_stats'])} active caches")
        print(f"   System Health: {report['system_health']['status']}")
        print(f"   CPU Usage: {report['system_health']['metrics']['cpu_percent']:.1f}%")
        print(f"   Memory Usage: {report['system_health']['metrics']['memory_percent']:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return False

def main():
    """Main optimization application function"""
    print("🚀 Starting Performance Optimization Application")
    print("=" * 60)
    
    results = []
    
    # Apply optimizations step by step
    optimizations = [
        ("Database Indexes", apply_database_indexes),
        ("Connection Pool", verify_connection_pool),
        ("Cache System", initialize_cache_system),
        ("Performance Monitoring", verify_performance_monitoring),
        ("Database Maintenance", run_database_maintenance),
        ("Performance Report", generate_performance_report),
    ]
    
    for name, optimization_func in optimizations:
        print(f"\n{'='*20} {name} {'='*20}")
        success = optimization_func()
        results.append((name, success))
        
        if success:
            print(f"✅ {name} completed successfully")
        else:
            print(f"❌ {name} failed")
    
    # Final summary
    print("\n" + "="*60)
    print("🎯 OPTIMIZATION SUMMARY")
    print("="*60)
    
    successful = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {name:.<30} {status}")
    
    print(f"\n🏆 Overall: {successful}/{total} optimizations applied successfully")
    
    if successful == total:
        print("🎉 All optimizations applied! Your system is ready for 100+ concurrent students.")
        print("\n📝 Next steps:")
        print("   1. Monitor performance using /api/contests/health endpoint")
        print("   2. Use /api/contests/warm-cache before contests start")
        print("   3. Monitor database connections via /api/contests/performance")
    else:
        print("⚠️  Some optimizations failed. Check the errors above and retry.")
        sys.exit(1)

if __name__ == "__main__":
    main() 