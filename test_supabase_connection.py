#!/usr/bin/env python3
"""
Test script to verify Supabase database connection
"""
import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine, Session, text
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# Load environment variables
load_dotenv()

def clean_database_url(database_url):
    """Clean the database URL to remove unsupported parameters"""
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

def test_connection():
    """Test the database connection"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        print("Please make sure your .env file contains:")
        print("DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]/postgres")
        return False
    
    # Clean the database URL
    cleaned_url = clean_database_url(database_url)
    
    print(f"🔗 Testing connection to: {database_url.split('@')[1].split('?')[0] if '@' in database_url else 'database'}")
    
    try:
        # Create engine with cleaned PostgreSQL URL
        engine = create_engine(cleaned_url, echo=True)
        
        # Test connection
        with Session(engine) as session:
            result = session.exec(text("SELECT version()")).first()
            print(f"✅ Connection successful!")
            print(f"📊 PostgreSQL version: {result}")
            
        # Test table creation (simple test)
        with Session(engine) as session:
            session.exec(text("""
                CREATE TABLE IF NOT EXISTS connection_test (
                    id SERIAL PRIMARY KEY,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # Insert test data
            session.exec(text("""
                INSERT INTO connection_test (message) 
                VALUES ('Connection test successful') 
                ON CONFLICT DO NOTHING
            """))
            
            # Query test data
            result = session.exec(text("SELECT message FROM connection_test LIMIT 1")).first()
            print(f"✅ Table operations successful: {result}")
            
            # Clean up test table
            session.exec(text("DROP TABLE IF EXISTS connection_test"))
            session.commit()
            
        print("🎉 All tests passed! Supabase connection is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check if your DATABASE_URL is correct")
        print("2. Verify your Supabase credentials")
        print("3. Make sure your IP is allowed in Supabase dashboard")
        print("4. Try using direct connection string without pgbouncer")
        return False

if __name__ == "__main__":
    print("🚀 Testing Supabase Database Connection")
    print("=" * 50)
    test_connection()