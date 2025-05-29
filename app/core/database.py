from sqlmodel import SQLModel, create_engine, Session
from .config import settings

# Import models to ensure they are registered with SQLModel
from app.models.user import User
from app.models.course import Course
from app.models.student_course import StudentCourse
from app.models.mcq_problem import MCQProblem
from app.models.contest import Contest, ContestProblem
from app.models.submission import Submission

# Create database engine
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)


def create_db_and_tables():
    """Create database tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session 