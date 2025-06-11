#!/usr/bin/env python3
"""
Debug script to diagnose contest visibility issues
Run this script to check:
1. Student enrollments
2. Course-Contest relationships
3. Contest active status
4. User roles and permissions
"""

import asyncio
from sqlmodel import Session, select, create_engine
from app.models import User, Course, Contest, StudentCourse, UserRole
from app.core.config import settings
from app.core.database import cleaned_database_url

def diagnose_contest_visibility():
    """Diagnose why students can't see contests"""
    
    # Create database connection using the same settings as the app
    engine = create_engine(
        cleaned_database_url,
        echo=False,  # Set to True for SQL debugging
        pool_pre_ping=True,
        connect_args={"options": "-c timezone=UTC"}
    )
    
    with Session(engine) as session:
        print("🔍 CONTEST VISIBILITY DIAGNOSTIC REPORT")
        print("=" * 50)
        
        # 1. Check all courses and their contest counts
        print("\n📚 COURSES AND CONTESTS:")
        courses = session.exec(select(Course)).all()
        
        for course in courses:
            contest_count = len(session.exec(
                select(Contest).where(Contest.course_id == course.id)
            ).all())
            
            active_contest_count = len(session.exec(
                select(Contest).where(
                    Contest.course_id == course.id,
                    Contest.is_active == True
                )
            ).all())
            
            enrollment_count = len(session.exec(
                select(StudentCourse).where(
                    StudentCourse.course_id == course.id,
                    StudentCourse.is_active == True
                )
            ).all())
            
            print(f"  📖 Course: {course.name}")
            print(f"     ID: {course.id}")
            print(f"     Instructor: {course.instructor_id}")
            print(f"     Total Contests: {contest_count}")
            print(f"     Active Contests: {active_contest_count}")
            print(f"     Active Enrollments: {enrollment_count}")
            print()
        
        # 2. Check all contests and their status
        print("\n🏆 CONTESTS DETAIL:")
        contests = session.exec(select(Contest)).all()
        
        for contest in contests:
            course = session.get(Course, contest.course_id)
            print(f"  🎯 Contest: {contest.name}")
            print(f"     ID: {contest.id}")
            print(f"     Course: {course.name if course else 'COURSE NOT FOUND!'}")
            print(f"     Course ID: {contest.course_id}")
            print(f"     Is Active: {contest.is_active}")
            print(f"     Status: {contest.get_status()}")
            print(f"     Start: {contest.start_time}")
            print(f"     End: {contest.end_time}")
            print()
        
        # 3. Check all students and their enrollments
        print("\n👥 STUDENT ENROLLMENTS:")
        students = session.exec(
            select(User).where(User.role == UserRole.STUDENT)
        ).all()
        
        for student in students:
            enrollments = session.exec(
                select(StudentCourse, Course).join(
                    Course, StudentCourse.course_id == Course.id
                ).where(
                    StudentCourse.student_id == student.id,
                    StudentCourse.is_active == True
                )
            ).all()
            
            print(f"  👤 Student: {student.email}")
            print(f"     ID: {student.id}")
            print(f"     Name: {student.name or 'Not set'}")
            print(f"     Role: {student.role}")
            print(f"     Is Active: {student.is_active}")
            print(f"     Profile Completed: {student.profile_completed}")
            
            if enrollments:
                print("     📚 Enrolled Courses:")
                for enrollment, course in enrollments:
                    # Count visible contests for this student in this course
                    visible_contests = session.exec(
                        select(Contest).where(
                            Contest.course_id == course.id,
                            Contest.is_active == True
                        )
                    ).all()
                    
                    print(f"       - {course.name} (ID: {course.id})")
                    print(f"         Enrolled: {enrollment.enrolled_at}")
                    print(f"         Visible Contests: {len(visible_contests)}")
                    
                    for contest in visible_contests:
                        print(f"           * {contest.name} ({contest.get_status()})")
            else:
                print("     📚 No active course enrollments found!")
            print()
        
        # 4. Check for data integrity issues
        print("\n⚠️  DATA INTEGRITY CHECKS:")
        
        # Check for contests with missing courses
        orphaned_contests = session.exec(
            select(Contest).where(
                ~Contest.course_id.in_(select(Course.id))
            )
        ).all()
        
        if orphaned_contests:
            print("  🚨 ORPHANED CONTESTS (missing course):")
            for contest in orphaned_contests:
                print(f"     - {contest.name} (Course ID: {contest.course_id})")
        else:
            print("  ✅ No orphaned contests found")
        
        # Check for enrollments with missing courses
        orphaned_enrollments = session.exec(
            select(StudentCourse).where(
                ~StudentCourse.course_id.in_(select(Course.id))
            )
        ).all()
        
        if orphaned_enrollments:
            print("  🚨 ORPHANED ENROLLMENTS (missing course):")
            for enrollment in orphaned_enrollments:
                print(f"     - Student: {enrollment.student_id}, Course: {enrollment.course_id}")
        else:
            print("  ✅ No orphaned enrollments found")
        
        # Check for enrollments with missing students
        orphaned_student_enrollments = session.exec(
            select(StudentCourse).where(
                ~StudentCourse.student_id.in_(select(User.id))
            )
        ).all()
        
        if orphaned_student_enrollments:
            print("  🚨 ORPHANED ENROLLMENTS (missing student):")
            for enrollment in orphaned_student_enrollments:
                print(f"     - Student: {enrollment.student_id}, Course: {enrollment.course_id}")
        else:
            print("  ✅ No orphaned student enrollments found")
        
        print("\n" + "=" * 50)
        print("🎯 DIAGNOSIS SUMMARY:")
        print("For students to see contests, they must:")
        print("1. ✅ Be enrolled in a course (StudentCourse.is_active = True)")
        print("2. ✅ Contest must be active (Contest.is_active = True)")
        print("3. ✅ Contest must belong to an enrolled course")
        print("4. ✅ Student must have role = 'student'")
        print("5. ✅ Student must be active (User.is_active = True)")
        
        print("\n💡 QUICK FIXES:")
        print("- To activate contests: UPDATE contest SET is_active = true WHERE id = 'contest_id';")
        print("- To enroll students: INSERT INTO studentcourse (student_id, course_id, is_active) VALUES (...);")
        print("- To check specific student: Check their enrollments in the report above")


if __name__ == "__main__":
    try:
        diagnose_contest_visibility()
    except Exception as e:
        print(f"❌ Error running diagnostic: {e}")
        print("Make sure the database is running and accessible.") 