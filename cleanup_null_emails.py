#!/usr/bin/env python3
"""
Script to clean up users with NULL email addresses
This fixes the Pydantic validation error in StudentWithEmailStatus
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, select
from app.core.database import engine
from app.models.user import User, UserRole
from datetime import datetime

def cleanup_null_emails():
    """Delete users with NULL email addresses"""
    
    print("🧹 Starting cleanup of users with NULL emails...")
    
    with Session(engine) as session:
        # Find users with NULL emails
        statement = select(User).where(User.email.is_(None))
        null_email_users = session.exec(statement).all()
        
        if not null_email_users:
            print("✅ No users with NULL emails found. Database is clean!")
            return
        
        print(f"📊 Found {len(null_email_users)} users with NULL emails:")
        
        # Display users to be deleted
        for user in null_email_users:
            print(f"   - ID: {user.id}")
            print(f"     Role: {user.role}")
            print(f"     Mobile: {user.mobile}")
            print(f"     Name: {user.name}")
            print(f"     Registration Status: {user.registration_status}")
            print(f"     Created: {user.created_at}")
            print()
        
        # Confirm deletion
        response = input("❓ Do you want to delete these users? (yes/no): ").lower().strip()
        
        if response not in ['yes', 'y']:
            print("❌ Cleanup cancelled by user.")
            return
        
        # Delete users with NULL emails
        deleted_count = 0
        for user in null_email_users:
            try:
                session.delete(user)
                deleted_count += 1
                print(f"🗑️  Deleted user {user.id} ({user.role})")
            except Exception as e:
                print(f"❌ Error deleting user {user.id}: {e}")
        
        # Commit changes
        session.commit()
        
        print(f"\n✅ Cleanup completed!")
        print(f"📊 Successfully deleted {deleted_count} users with NULL emails")
        
        # Verify cleanup
        remaining_null_users = session.exec(select(User).where(User.email.is_(None))).all()
        if remaining_null_users:
            print(f"⚠️  Warning: {len(remaining_null_users)} users with NULL emails still remain")
        else:
            print("✅ Verification: No users with NULL emails remain in database")

def show_email_statistics():
    """Show statistics about email fields in the database"""
    
    print("\n📊 Email Statistics:")
    print("-" * 40)
    
    with Session(engine) as session:
        # Total users
        total_users = len(session.exec(select(User)).all())
        
        # Users with NULL emails
        null_email_users = len(session.exec(select(User).where(User.email.is_(None))).all())
        
        # Users with valid emails
        valid_email_users = len(session.exec(select(User).where(User.email.is_not(None))).all())
        
        # Students with NULL emails
        null_email_students = len(session.exec(
            select(User).where(User.email.is_(None), User.role == UserRole.STUDENT)
        ).all())
        
        # Admins with NULL emails
        null_email_admins = len(session.exec(
            select(User).where(User.email.is_(None), User.role == UserRole.ADMIN)
        ).all())
        
        print(f"Total Users: {total_users}")
        print(f"Users with NULL emails: {null_email_users}")
        print(f"Users with valid emails: {valid_email_users}")
        print(f"Students with NULL emails: {null_email_students}")
        print(f"Admins with NULL emails: {null_email_admins}")
        
        if null_email_users > 0:
            print(f"\n⚠️  {null_email_users} users have NULL emails and will cause API errors!")
        else:
            print(f"\n✅ All users have valid email addresses!")

def main():
    print("🔧 Database Email Cleanup Tool")
    print("=" * 50)
    
    # Show current statistics
    show_email_statistics()
    
    # Perform cleanup if needed
    cleanup_null_emails()
    
    # Show final statistics
    show_email_statistics()

if __name__ == "__main__":
    main() 