"""
🚀 Database Indexes Optimization
Critical performance indexes for handling 100+ concurrent students

Optimizes the most frequently used queries during contests:
- Student enrollment checks
- Contest data retrieval  
- Submission queries
- User authentication
"""

from sqlalchemy import text, Index
from sqlmodel import Session
from app.core.database import engine, get_session
from app.models import *  # Import all models
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

# 🔥 CRITICAL PERFORMANCE INDEXES
PERFORMANCE_INDEXES = [
    # 🎯 USER & AUTHENTICATION INDEXES
    {
        "name": "idx_user_email_active",
        "table": "user", 
        "columns": ["email", "is_active"],
        "description": "Fast user lookup during login/auth"
    },
    {
        "name": "idx_user_otpless_mobile",
        "table": "user",
        "columns": ["otpless_user_id", "mobile"],
        "description": "OTPLESS authentication lookup"
    },
    
    # 🚀 CONTEST PERFORMANCE INDEXES
    {
        "name": "idx_contest_course_active_times",
        "table": "contest",
        "columns": ["course_id", "is_active", "start_time", "end_time"],
        "description": "Fast contest listing for students (most critical)"
    },
    {
        "name": "idx_contest_times_status",
        "table": "contest", 
        "columns": ["start_time", "end_time", "is_active"],
        "description": "Contest status calculations"
    },
    
    # ⚡ STUDENT ENROLLMENT INDEXES  
    {
        "name": "idx_student_course_active_lookup",
        "table": "studentcourse",
        "columns": ["student_id", "course_id", "is_active"],
        "description": "Critical for enrollment validation (high frequency)"
    },
    {
        "name": "idx_student_course_course_active",
        "table": "studentcourse",
        "columns": ["course_id", "is_active", "student_id"], 
        "description": "List students in course"
    },
    
    # 📝 SUBMISSION PERFORMANCE INDEXES
    {
        "name": "idx_submission_contest_student",
        "table": "submission",
        "columns": ["contest_id", "student_id"],
        "description": "Check existing submissions (prevent duplicates)"
    },
    {
        "name": "idx_submission_student_time",
        "table": "submission",
        "columns": ["student_id", "submitted_at"],
        "description": "Student submission history"
    },
    {
        "name": "idx_submission_contest_time",
        "table": "submission", 
        "columns": ["contest_id", "submitted_at"],
        "description": "Contest submission analytics"
    },
    
    # 🎲 CONTEST PROBLEMS INDEXES
    {
        "name": "idx_contest_problem_contest_order",
        "table": "contestproblem",
        "columns": ["contest_id", "order_index"],
        "description": "Fast problem loading for contests"
    },
    
    # 📚 COURSE & MCQ INDEXES
    {
        "name": "idx_course_instructor",
        "table": "course",
        "columns": ["instructor_id", "is_active"],
        "description": "Admin course listings"
    },
    {
        "name": "idx_mcq_tags_active",
        "table": "mcqproblem", 
        "columns": ["needs_tags", "question_type"],
        "description": "MCQ filtering and validation"
    }
]

# 🌟 PARTIAL INDEXES (PostgreSQL specific optimizations)
PARTIAL_INDEXES = [
    {
        "name": "idx_active_contests_only",
        "table": "contest",
        "columns": ["course_id", "start_time"],
        "condition": "is_active = true",
        "description": "Only active contests (students don't see inactive)"
    },
    {
        "name": "idx_active_enrollments_only", 
        "table": "studentcourse",
        "columns": ["student_id", "course_id"],
        "condition": "is_active = true",
        "description": "Only active enrollments matter for access"
    },
    {
        "name": "idx_recent_submissions",
        "table": "submission",
        "columns": ["contest_id", "submitted_at"],
        "condition": "submitted_at > NOW() - INTERVAL '30 days'",
        "description": "Recent submissions for analytics"
    }
]

def create_performance_indexes(session: Session = None) -> Dict[str, bool]:
    """
    Create all performance-critical indexes
    Returns {index_name: success_status}
    """
    if session is None:
        session = next(get_session())
    
    results = {}
    
    # 🔥 CREATE STANDARD INDEXES
    for index_config in PERFORMANCE_INDEXES:
        try:
            index_name = index_config["name"]
            table_name = index_config["table"]
            columns = index_config["columns"]
            
            # Create index SQL
            columns_str = ", ".join(columns)
            create_sql = f"""
                CREATE INDEX IF NOT EXISTS {index_name} 
                ON {table_name} ({columns_str});
            """
            
            session.execute(text(create_sql))
            results[index_name] = True
            logger.info(f"✅ Created index: {index_name}")
            
        except Exception as e:
            results[index_name] = False
            logger.error(f"❌ Failed to create index {index_name}: {e}")
    
    # 🌟 CREATE PARTIAL INDEXES (PostgreSQL)
    for partial_config in PARTIAL_INDEXES:
        try:
            index_name = partial_config["name"]
            table_name = partial_config["table"]
            columns = partial_config["columns"]
            condition = partial_config["condition"]
            
            columns_str = ", ".join(columns)
            create_sql = f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {table_name} ({columns_str})
                WHERE {condition};
            """
            
            session.execute(text(create_sql))
            results[index_name] = True
            logger.info(f"✅ Created partial index: {index_name}")
            
        except Exception as e:
            results[index_name] = False
            logger.error(f"❌ Failed to create partial index {index_name}: {e}")
    
    session.commit()
    return results

def analyze_query_performance(session: Session = None) -> Dict[str, Any]:
    """
    Analyze current query performance and suggest optimizations
    """
    if session is None:
        session = next(get_session())
    
    try:
        # Get slow queries (PostgreSQL specific)
        slow_queries = session.execute(text("""
            SELECT 
                query,
                calls,
                total_time,
                mean_time,
                rows
            FROM pg_stat_statements 
            WHERE mean_time > 100  -- Queries taking > 100ms on average
            ORDER BY mean_time DESC
            LIMIT 10;
        """)).fetchall()
        
        # Get index usage statistics
        index_usage = session.execute(text("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                idx_scan,
                idx_tup_read,
                idx_tup_fetch
            FROM pg_stat_user_indexes
            WHERE idx_scan > 0
            ORDER BY idx_scan DESC
            LIMIT 20;
        """)).fetchall()
        
        # Check for missing indexes on foreign keys
        missing_fk_indexes = session.execute(text("""
            SELECT 
                c.conrelid::regclass AS table_name,
                a.attname AS column_name,
                c.confrelid::regclass AS referenced_table
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
            WHERE c.contype = 'f'
            AND NOT EXISTS (
                SELECT 1 FROM pg_index i 
                WHERE i.indrelid = c.conrelid 
                AND a.attnum = ANY(i.indkey)
            );
        """)).fetchall()
        
        return {
            "slow_queries": [dict(row) for row in slow_queries],
            "index_usage": [dict(row) for row in index_usage], 
            "missing_fk_indexes": [dict(row) for row in missing_fk_indexes],
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error analyzing query performance: {e}")
        return {"error": str(e)}

def optimize_database_settings(session: Session = None) -> Dict[str, bool]:
    """
    Apply PostgreSQL-specific optimizations for high concurrency
    """
    if session is None:
        session = next(get_session())
    
    # 🚀 HIGH CONCURRENCY OPTIMIZATIONS
    optimizations = [
        # Connection and memory settings
        "SET shared_buffers = '256MB'",
        "SET work_mem = '16MB'", 
        "SET maintenance_work_mem = '128MB'",
        "SET effective_cache_size = '1GB'",
        
        # Query performance
        "SET random_page_cost = 1.1",
        "SET seq_page_cost = 1",
        "SET cpu_tuple_cost = 0.01",
        "SET cpu_index_tuple_cost = 0.005",
        
        # Concurrency settings
        "SET max_connections = 200",
        "SET max_parallel_workers_per_gather = 4",
        "SET max_parallel_workers = 8",
        
        # Logging and monitoring
        "SET log_min_duration_statement = 1000",  # Log slow queries
        "SET track_activities = on",
        "SET track_counts = on",
        "SET track_io_timing = on",
    ]
    
    results = {}
    
    for setting in optimizations:
        try:
            session.execute(text(setting))
            results[setting] = True
            logger.info(f"✅ Applied: {setting}")
        except Exception as e:
            results[setting] = False
            logger.error(f"❌ Failed to apply: {setting} - {e}")
    
    session.commit()
    return results

def get_database_statistics() -> Dict[str, Any]:
    """
    Get comprehensive database performance statistics
    """
    with Session(engine) as session:
        try:
            # Table sizes
            table_sizes = session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """)).fetchall()
            
            # Index sizes  
            index_sizes = session.execute(text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    pg_size_pretty(pg_relation_size(indexname::regclass)) as size
                FROM pg_indexes 
                WHERE schemaname = 'public'
                ORDER BY pg_relation_size(indexname::regclass) DESC
                LIMIT 20;
            """)).fetchall()
            
            # Connection statistics
            connection_stats = session.execute(text("""
                SELECT 
                    state,
                    COUNT(*) as count
                FROM pg_stat_activity 
                WHERE datname = current_database()
                GROUP BY state;
            """)).fetchall()
            
            return {
                "table_sizes": [dict(row) for row in table_sizes],
                "index_sizes": [dict(row) for row in index_sizes],
                "connection_stats": [dict(row) for row in connection_stats],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting database statistics: {e}")
            return {"error": str(e)}

# 🎯 MAINTENANCE FUNCTIONS
def vacuum_analyze_tables(session: Session = None) -> Dict[str, bool]:
    """
    Run VACUUM ANALYZE on critical tables for optimal performance
    """
    if session is None:
        session = next(get_session())
    
    critical_tables = [
        "user", "contest", "studentcourse", "submission", 
        "contestproblem", "course", "mcqproblem"
    ]
    
    results = {}
    
    for table in critical_tables:
        try:
            session.execute(text(f"VACUUM ANALYZE {table};"))
            results[table] = True
            logger.info(f"✅ VACUUM ANALYZE completed for {table}")
        except Exception as e:
            results[table] = False 
            logger.error(f"❌ VACUUM ANALYZE failed for {table}: {e}")
    
    return results

def reindex_critical_tables(session: Session = None) -> Dict[str, bool]:
    """
    Rebuild indexes on critical tables (run during maintenance windows)
    """
    if session is None:
        session = next(get_session())
    
    critical_tables = ["user", "contest", "studentcourse", "submission"]
    results = {}
    
    for table in critical_tables:
        try:
            session.execute(text(f"REINDEX TABLE {table};"))
            results[table] = True
            logger.info(f"✅ REINDEX completed for {table}")
        except Exception as e:
            results[table] = False
            logger.error(f"❌ REINDEX failed for {table}: {e}")
    
    return results 