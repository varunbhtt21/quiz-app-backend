#!/usr/bin/env python3
"""
Fix script to update needs_tags status for existing MCQs that already have tags assigned
"""

import os
import sys
from sqlalchemy import create_engine, text

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.config import settings

def fix_needs_tags_status():
    """Fix needs_tags status for existing MCQs with tags"""
    
    # Use direct URL for migrations if available, otherwise fallback to regular database_url
    database_url = settings.direct_url if settings.direct_url else settings.database_url
    print(f"📡 Using database URL: {str(database_url)[:50]}...")
    
    try:
        # Create database engine
        engine = create_engine(str(database_url))
        
        print("🔧 Fixing needs_tags status for existing MCQs...")
        
        with engine.connect() as conn:
            # Get count of MCQs that have tags but needs_tags=true
            count_query = text("""
                SELECT COUNT(DISTINCT m.id)
                FROM mcqproblem m
                JOIN mcqtag mt ON m.id = mt.mcq_id
                WHERE m.needs_tags = true
            """)
            
            result = conn.execute(count_query)
            mcqs_to_fix = result.fetchone()[0]
            
            if mcqs_to_fix == 0:
                print("✅ No MCQs need fixing - all tagged MCQs already have needs_tags=false")
                return
            
            print(f"📊 Found {mcqs_to_fix} MCQs with tags that need needs_tags status fixed")
            
            # Update needs_tags = false for MCQs that have tags
            update_query = text("""
                UPDATE mcqproblem 
                SET needs_tags = false 
                WHERE id IN (
                    SELECT DISTINCT mcq_id 
                    FROM mcqtag
                ) AND needs_tags = true
            """)
            
            result = conn.execute(update_query)
            conn.commit()
            
            updated_count = result.rowcount
            print(f"✅ Updated {updated_count} MCQs to needs_tags=false (MCQs with tags)")
            
            # Verify the results
            verify_query = text("""
                SELECT 
                    COUNT(CASE WHEN needs_tags = true THEN 1 END) as needs_tags_count,
                    COUNT(CASE WHEN needs_tags = false THEN 1 END) as has_tags_count,
                    COUNT(*) as total_mcqs
                FROM mcqproblem
            """)
            
            result = conn.execute(verify_query)
            stats = result.fetchone()
            
            print(f"📊 Final status:")
            print(f"   - MCQs needing tags: {stats[0]}")
            print(f"   - MCQs with tags: {stats[1]}")
            print(f"   - Total MCQs: {stats[2]}")
        
        print("🎉 Fix completed successfully!")
        
    except Exception as e:
        print(f"❌ ERROR: Failed to fix needs_tags status: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Starting needs_tags status fix...")
    fix_needs_tags_status() 