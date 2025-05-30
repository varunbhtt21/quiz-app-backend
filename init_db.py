#!/usr/bin/env python3
"""
Database initialization script for Quiz App
"""

import os
import sys
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Load environment variables
load_dotenv()

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

def get_database_url():
    """Get the appropriate database URL for initialization"""
    # Try to use DIRECT_URL first (for migrations), fallback to DATABASE_URL
    direct_url = os.getenv("DIRECT_URL")
    database_url = os.getenv("DATABASE_URL")
    
    if direct_url:
        print("Using DIRECT_URL for database initialization (recommended for migrations)")
        return clean_database_url(direct_url)
    elif database_url:
        print("Using DATABASE_URL for database initialization")
        return clean_database_url(database_url)
    else:
        raise ValueError("Neither DIRECT_URL nor DATABASE_URL found in environment variables")

def init_database():
    """Initialize the database with all tables"""
    # Import models to ensure they are registered
    from app.models.user import User
    from app.models.course import Course
    from app.models.student_course import StudentCourse
    from app.models.mcq_problem import MCQProblem
    from app.models.contest import Contest, ContestProblem
    from app.models.submission import Submission
    
    print("Creating database tables...")
    
    # Get the appropriate database URL
    database_url = get_database_url()
    
    # Create engine
    engine = create_engine(database_url, echo=True)
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    print("✅ Database tables created successfully!")
    return engine

def create_sample_admin():
    """Create a sample admin user"""
    from app.models.user import User
    from app.core.security import get_password_hash
    from sqlmodel import Session
    
    try:
        engine = init_database()
        
        with Session(engine) as session:
            # Check if admin already exists
            existing_admin = session.query(User).filter(User.email == "admin@jazzee.com").first()
            
            if existing_admin:
                print("ℹ️  Admin user already exists: admin@jazzee.com")
                return
            
            # Create admin user
            admin_user = User(
                email="admin@jazzee.com",
                hashed_password=get_password_hash("admin123"),
                role="admin",
                is_active=True
            )
            
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
            
            print("✅ Sample admin user created!")
            print("📧 Email: admin@jazzee.com")
            print("🔑 Password: admin123")
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")

if __name__ == "__main__":
    print("🚀 Initializing QuizMaster by Jazzee Database")
    print("=" * 50)
    
    try:
        init_database()
        
        # Ask if user wants to create sample admin
        create_admin = input("\n🤔 Would you like to create a sample admin user? (y/n): ").lower().strip()
        if create_admin in ['y', 'yes']:
            create_sample_admin()
        
        print("\n🎉 Database initialization completed!")
        print("\n📝 Next steps:")
        print("1. Start the backend server: uvicorn app.main:app --reload")
        print("2. Access API docs: http://localhost:8000/docs")
        if create_admin in ['y', 'yes']:
            print("3. Login with admin@jazzee.com / admin123")
            
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1) 