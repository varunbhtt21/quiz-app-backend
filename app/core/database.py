from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import QueuePool
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from .config import settings

# Import models to ensure they are registered with SQLModel
from app.models.user import User
from app.models.course import Course
from app.models.student_course import StudentCourse
from app.models.mcq_problem import MCQProblem
from app.models.contest import Contest, ContestProblem
from app.models.submission import Submission
from app.models.tag import Tag, MCQTag

def clean_database_url(database_url: str) -> str:
    """Clean the database URL to remove unsupported parameters and use correct driver"""
    # Convert to psycopg3 format if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    # Parse URL and remove unsupported parameters
    parsed = urlparse(database_url)
    query_params = parse_qs(parsed.query)
    
    # Remove pgbouncer parameter as it's not supported by psycopg
    if 'pgbouncer' in query_params:
        del query_params['pgbouncer']
    
    # Rebuild the URL
    new_query = urlencode(query_params, doseq=True)
    cleaned_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))
    
    return cleaned_url

# Clean the database URL for compatibility
cleaned_database_url = clean_database_url(settings.database_url)

# 🚀 PERFORMANCE OPTIMIZATION: Enhanced connection pool for high concurrency
# Optimized for 100 concurrent students on t3.medium
engine = create_engine(
    cleaned_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections every hour
    
    # 🔥 HIGH CONCURRENCY POOL SETTINGS
    poolclass=QueuePool,
    pool_size=20,              # Base connection pool (up from default 5)
    max_overflow=30,           # Allow burst to 50 total connections
    pool_timeout=30,           # Wait up to 30s for a connection
    pool_reset_on_return="commit",  # Reset connections efficiently
    
    # 🎯 POSTGRESQL PERFORMANCE OPTIMIZATIONS
    connect_args={
        "options": "-c timezone=UTC",  # Force UTC timezone
        "connect_timeout": 10,         # Connection timeout
        # Note: server_side_cursors and prepared_statement_cache_size 
        # are not supported in psycopg3, removed for compatibility
    },
    
    # 🚀 EXECUTION OPTIONS
    execution_options={
        "isolation_level": "READ_COMMITTED",  # Optimal for high concurrency
        "autocommit": False,
        "compiled_cache": {},  # Enable query compilation cache
    }
)

# 🌟 ASYNC ENGINE for high-performance async operations (using psycopg async)
async_database_url = cleaned_database_url.replace("postgresql+psycopg://", "postgresql+psycopg_async://")
try:
    async_engine = create_async_engine(
        async_database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=3600,
        
        # Async pool settings
        pool_size=15,
        max_overflow=25,
        pool_timeout=30,
        
        # Psycopg async-specific optimizations  
        connect_args={
            "options": "-c timezone=UTC -c application_name=quiz_app_async",
            "connect_timeout": 10,
            # Note: prepare_threshold removed for psycopg3 compatibility
        }
    )
except Exception as e:
    print(f"⚠️  Async engine not available, using sync only: {e}")
    async_engine = None


def create_db_and_tables():
    """Create database tables using direct connection for compatibility"""
    # Use DIRECT_URL for table creation if available, otherwise fallback to DATABASE_URL
    direct_url = getattr(settings, 'direct_url', None)
    table_creation_url = direct_url if direct_url else settings.database_url
    
    # Clean the URL
    cleaned_url = clean_database_url(table_creation_url)
    
    # Create a separate engine for table creation with timezone configuration
    table_engine = create_engine(
        cleaned_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_recycle=3600,
        # PostgreSQL-specific timezone configuration
        connect_args={
            "options": "-c timezone=UTC"  # Force all connections to use UTC
        }
    )
    
    try:
        SQLModel.metadata.create_all(table_engine)
        print("✅ Database tables created/verified successfully")
    except Exception as e:
        print(f"⚠️  Table creation warning: {e}")
        print("📝 Tables may already exist or there might be a connection issue")
    finally:
        table_engine.dispose()


def get_session():
    """Get database session with connection pooling"""
    with Session(engine) as session:
        yield session

# 🚀 ASYNC SESSION SUPPORT for high-performance operations
async def get_async_session():
    """Get async database session for high-performance operations"""
    if async_engine is None:
        raise RuntimeError("Async engine not available - falling back to sync operations")
    async with AsyncSession(async_engine) as session:
        yield session

# 🔥 CONNECTION POOL MONITORING
def get_pool_status():
    """Get connection pool status for monitoring"""
    pool = engine.pool
    try:
        return {
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "total_connections": pool.size() + pool.overflow(),
            "available_connections": pool.checkedin(),
            "status": "healthy"
        }
    except AttributeError as e:
        # Fallback for different pool implementations
        return {
            "pool_size": getattr(pool, '_pool_size', 'unknown'),
            "status": f"monitoring_limited: {str(e)}",
            "total_connections": "unknown"
        } 