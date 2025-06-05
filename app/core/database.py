from sqlmodel import SQLModel, create_engine, Session
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

# Create database engine with timezone-aware configuration
engine = create_engine(
    cleaned_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,
    # PostgreSQL-specific timezone configuration
    connect_args={
        "options": "-c timezone=UTC"  # Force all connections to use UTC
    }
)


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
    """Get database session"""
    with Session(engine) as session:
        yield session 