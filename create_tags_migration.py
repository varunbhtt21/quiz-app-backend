#!/usr/bin/env python3
"""
Database migration script to add Tag and MCQTag tables for the tagging system.
Run this script to update your existing database with tag support.
"""

import sys
import os
from sqlmodel import SQLModel, Session, create_engine, text
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.config import settings
from app.models.tag import Tag, MCQTag
from app.models.user import User

def create_tags_tables():
    """Create the new tables for the tagging system"""
    print("🏷️  Starting Tags System Migration...")
    
    # Use direct URL for migrations if available, otherwise fallback to regular database_url
    database_url = settings.direct_url if settings.direct_url else settings.database_url
    print(f"📡 Using database URL: {database_url[:50]}...")
    
    # Create engine
    engine = create_engine(str(database_url))
    
    try:
        # Create tables
        print("📊 Creating Tag and MCQTag tables...")
        SQLModel.metadata.create_all(engine, tables=[Tag.__table__, MCQTag.__table__])
        print("✅ Tables created successfully!")
        
        # Create some default tags
        with Session(engine) as session:
            print("🔧 Creating default tags...")
            
            # Check if we have any admin users to assign as creators
            admin_user = session.exec(
                text("SELECT id FROM \"user\" WHERE role = 'ADMIN' LIMIT 1")
            ).first()
            
            if not admin_user:
                print("⚠️  No admin user found. Please create an admin user first.")
                return False
            
            admin_id = admin_user[0]
            
            # Default tags to create
            default_tags = [
                {
                    "name": "Mathematics",
                    "description": "Mathematical problems and concepts",
                    "color": "#3B82F6"
                },
                {
                    "name": "Science",
                    "description": "General science questions",
                    "color": "#10B981"
                },
                {
                    "name": "Programming",
                    "description": "Programming and computer science",
                    "color": "#8B5CF6"
                },
                {
                    "name": "General Knowledge",
                    "description": "General knowledge and trivia",
                    "color": "#F59E0B"
                },
                {
                    "name": "History",
                    "description": "Historical events and figures",
                    "color": "#EF4444"
                },
                {
                    "name": "Geography",
                    "description": "Geography and world facts",
                    "color": "#06B6D4"
                },
                {
                    "name": "Language",
                    "description": "Language and literature",
                    "color": "#EC4899"
                },
                {
                    "name": "Basic",
                    "description": "Basic level questions",
                    "color": "#84CC16"
                },
                {
                    "name": "Intermediate",
                    "description": "Intermediate level questions", 
                    "color": "#F97316"
                },
                {
                    "name": "Advanced",
                    "description": "Advanced level questions",
                    "color": "#DC2626"
                }
            ]
            
            created_tags = []
            for tag_data in default_tags:
                # Check if tag already exists
                existing_tag = session.exec(
                    text("SELECT id FROM tag WHERE name = :name").params(name=tag_data["name"])
                ).first()
                
                if not existing_tag:
                    tag = Tag(
                        name=tag_data["name"],
                        description=tag_data["description"],
                        color=tag_data["color"],
                        created_by=admin_id
                    )
                    session.add(tag)
                    created_tags.append(tag_data["name"])
            
            session.commit()
            
            if created_tags:
                print(f"✅ Created {len(created_tags)} default tags: {', '.join(created_tags)}")
            else:
                print("ℹ️  Default tags already exist")
            
            # Check for existing MCQ problems without tags
            untagged_mcqs = session.exec(
                text("""
                    SELECT COUNT(*) 
                    FROM mcqproblem m 
                    WHERE NOT EXISTS (
                        SELECT 1 FROM mcqtag mt WHERE mt.mcq_id = m.id
                    )
                """)
            ).first()
            
            if untagged_mcqs and untagged_mcqs[0] > 0:
                print(f"⚠️  Found {untagged_mcqs[0]} MCQ problems without tags.")
                print("💡 You'll need to assign tags to existing MCQ problems through the admin interface.")
                print("   Each MCQ must have at least one tag as per the new requirements.")
            
        print("🎉 Tags system migration completed successfully!")
        print("\n📝 Next steps:")
        print("   1. Restart your FastAPI server")
        print("   2. Visit /docs to see the new tag endpoints")
        print("   3. Use the admin interface to manage tags and assign them to MCQs")
        return True
        
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        return False

def main():
    """Main migration function"""
    print("=" * 60)
    print("🏷️  QUIZ APP - TAGS SYSTEM MIGRATION")
    print("=" * 60)
    print()
    
    success = create_tags_tables()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 