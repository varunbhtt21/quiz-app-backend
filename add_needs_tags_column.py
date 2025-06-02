#!/usr/bin/env python3
"""
Migration script to add needs_tags column to mcqproblem table
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.config import settings

def add_needs_tags_column():
    """Add needs_tags column to mcqproblem table"""
    
    # Use direct URL for migrations if available, otherwise fallback to regular database_url
    database_url = settings.direct_url if settings.direct_url else settings.database_url
    print(f"📡 Using database URL: {str(database_url)[:50]}...")
    
    try:
        # Create database engine
        engine = create_engine(str(database_url))
        
        print("🔧 Adding needs_tags column to mcqproblem table...")
        
        with engine.connect() as conn:
            # Check if column already exists
            check_column_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'mcqproblem' 
                AND column_name = 'needs_tags'
            """)
            
            result = conn.execute(check_column_query)
            existing_column = result.fetchone()
            
            if existing_column:
                print("✅ Column 'needs_tags' already exists in mcqproblem table")
                return
            
            # Add the needs_tags column
            add_column_query = text("""
                ALTER TABLE mcqproblem 
                ADD COLUMN needs_tags BOOLEAN NOT NULL DEFAULT FALSE
            """)
            
            conn.execute(add_column_query)
            conn.commit()
            
            print("✅ Successfully added 'needs_tags' column to mcqproblem table")
            
            # Check how many MCQs exist and update their needs_tags status
            count_query = text("SELECT COUNT(*) FROM mcqproblem")
            result = conn.execute(count_query)
            mcq_count = result.fetchone()[0]
            
            if mcq_count > 0:
                # Set needs_tags = true for MCQs that don't have any tags
                update_query = text("""
                    UPDATE mcqproblem 
                    SET needs_tags = TRUE 
                    WHERE id NOT IN (
                        SELECT DISTINCT mcq_id 
                        FROM mcqtag
                    )
                """)
                
                result = conn.execute(update_query)
                conn.commit()
                
                updated_count = result.rowcount
                print(f"✅ Updated {updated_count} MCQs to needs_tags=true (MCQs without tags)")
                print(f"📊 Total MCQs: {mcq_count}, Need tags: {updated_count}")
            else:
                print("📊 No existing MCQs found")
        
        print("🎉 Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to add needs_tags column: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting needs_tags column migration...")
    add_needs_tags_column() 