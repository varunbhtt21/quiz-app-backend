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

# Create database engine with basic configuration
engine = create_engine(
    cleaned_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600
)


def create_db_and_tables():
    """Create database tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session 