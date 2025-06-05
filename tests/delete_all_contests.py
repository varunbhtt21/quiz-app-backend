#!/usr/bin/env python3
"""
Delete All Contests and Related Data Script

This script safely deletes all contests and their related data from the database:
1. All submissions (first, due to foreign key constraints)
2. All contest problems (second, due to foreign key constraints)
3. All contests (finally)

Usage: python delete_all_contests.py

WARNING: This operation is IRREVERSIBLE and will delete ALL contest data!
"""

import sys
import os
from datetime import datetime, timezone
from sqlmodel import Session, select, delete

# Add the parent directory to Python path to access app modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Change to the parent directory to ensure .env file is loaded correctly
os.chdir(parent_dir)

try:
    from app.core.database import get_session
    from app.models.contest import Contest, ContestProblem
    from app.models.submission import Submission
    from app.core.config import settings
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the quiz-app-backend directory or its subdirectories")
    sys.exit(1)

def confirm_deletion():
    """Ask for user confirmation before proceeding with deletion"""
    print("⚠️  WARNING: This will DELETE ALL CONTESTS AND SUBMISSIONS from the database!")
    print("This operation is IRREVERSIBLE!")
    print()
    print(f"🔗 Database: {settings.database_url[:50]}...")
    print()
    
    # Get counts first
    try:
        session = next(get_session())
        
        contest_count = session.exec(select(Contest)).all()
        submission_count = session.exec(select(Submission)).all()
        problem_count = session.exec(select(ContestProblem)).all()
        
        print(f"📊 Current Database State:")
        print(f"   • Contests: {len(contest_count)}")
        print(f"   • Contest Problems: {len(problem_count)}")
        print(f"   • Submissions: {len(submission_count)}")
        print()
        
        if len(contest_count) == 0:
            print("✅ No contests found in database. Nothing to delete.")
            return False
            
        session.close()
        
    except Exception as e:
        print(f"❌ Error checking database: {str(e)}")
        print("💡 Make sure your database is running and .env file is configured correctly")
        return False
    
    print("Type 'DELETE ALL CONTESTS' to confirm deletion:")
    confirmation = input("> ").strip()
    
    if confirmation == "DELETE ALL CONTESTS":
        print("\n🔄 Proceeding with deletion...")
        return True
    else:
        print("\n❌ Deletion cancelled.")
        return False

def delete_all_contests():
    """Delete all contests and related data from the database"""
    try:
        session = next(get_session())
        
        print("🗃️  Starting database cleanup...")
        
        # Step 1: Delete all submissions first (foreign key constraint)
        print("\n📝 Step 1: Deleting all submissions...")
        submissions = session.exec(select(Submission)).all()
        submission_count = len(submissions)
        
        if submission_count > 0:
            for submission in submissions:
                session.delete(submission)
            session.commit()
            print(f"   ✅ Deleted {submission_count} submissions")
        else:
            print("   ℹ️  No submissions found")
        
        # Step 2: Delete all contest problems (foreign key constraint)
        print("\n🧩 Step 2: Deleting all contest problems...")
        contest_problems = session.exec(select(ContestProblem)).all()
        problem_count = len(contest_problems)
        
        if problem_count > 0:
            for problem in contest_problems:
                session.delete(problem)
            session.commit()
            print(f"   ✅ Deleted {problem_count} contest problems")
        else:
            print("   ℹ️  No contest problems found")
        
        # Step 3: Delete all contests
        print("\n🏆 Step 3: Deleting all contests...")
        contests = session.exec(select(Contest)).all()
        contest_count = len(contests)
        
        if contest_count > 0:
            for contest in contests:
                session.delete(contest)
            session.commit()
            print(f"   ✅ Deleted {contest_count} contests")
        else:
            print("   ℹ️  No contests found")
        
        # Verify cleanup
        print("\n🔍 Verifying cleanup...")
        remaining_contests = session.exec(select(Contest)).all()
        remaining_problems = session.exec(select(ContestProblem)).all()
        remaining_submissions = session.exec(select(Submission)).all()
        
        if len(remaining_contests) == 0 and len(remaining_problems) == 0 and len(remaining_submissions) == 0:
            print("   ✅ Cleanup verified - all contest data removed")
        else:
            print(f"   ⚠️  Warning: Some data remains:")
            print(f"      • Contests: {len(remaining_contests)}")
            print(f"      • Problems: {len(remaining_problems)}")
            print(f"      • Submissions: {len(remaining_submissions)}")
        
        session.close()
        
        print("\n🎉 Database cleanup completed successfully!")
        print(f"📊 Summary:")
        print(f"   • Deleted {submission_count} submissions")
        print(f"   • Deleted {problem_count} contest problems")
        print(f"   • Deleted {contest_count} contests")
        print(f"   • Cleanup time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during deletion: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Rollback any pending changes
        try:
            session.rollback()
            session.close()
        except:
            pass
        
        return False

def main():
    """Main function"""
    print("🗑️  Contest Database Cleanup Tool")
    print("=" * 50)
    print("This tool will delete ALL contests and related data from the database.")
    print()
    
    try:
        # Check database connection
        session = next(get_session())
        session.close()
        print("✅ Database connection established")
        
    except Exception as e:
        print(f"❌ Database connection failed: {str(e)}")
        print("💡 Check your .env file and database configuration")
        sys.exit(1)
    
    # Confirm deletion
    if not confirm_deletion():
        print("\nOperation cancelled by user.")
        sys.exit(0)
    
    # Perform deletion
    success = delete_all_contests()
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 CONTEST CLEANUP: COMPLETED SUCCESSFULLY")
        print("All contest data has been removed from the database.")
        sys.exit(0)
    else:
        print("\n" + "=" * 50)
        print("❌ CONTEST CLEANUP: FAILED")
        print("Some errors occurred during cleanup. Please check the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main() 