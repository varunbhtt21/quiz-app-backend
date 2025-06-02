#!/usr/bin/env python3
"""
Initialize the database with the new schema and sample data
"""

from sqlmodel import SQLModel, create_engine, Session
from app.core.database import engine
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.student_course import StudentCourse
from app.models.mcq_problem import MCQProblem
from app.models.contest import Contest, ContestProblem, ContestStatus
from app.models.submission import Submission

def init_database():
    """Initialize database with new schema"""
    print("Creating database tables...")
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    print("Database tables created successfully!")
    
    # Add sample data
    with Session(engine) as session:
        # Create admin user
        admin = User(
            email="admin@quiz.com",
            hashed_password=get_password_hash("admin123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        session.add(admin)
        session.commit()
        session.refresh(admin)
        
        print(f"Created admin user: {admin.email}")
        
        # Create a sample course
        course = Course(
            name="Python Programming",
            description="Learn Python programming fundamentals",
            instructor_id=admin.id
        )
        session.add(course)
        session.commit()
        session.refresh(course)
        
        print(f"Created sample course: {course.name}")
        
        # Create some sample students
        students = []
        for i in range(3):
            student = User(
                email=f"student{i+1}@example.com",
                hashed_password=get_password_hash("student123"),
                role=UserRole.STUDENT,
                is_active=True
            )
            session.add(student)
            students.append(student)
        
        session.commit()
        
        # Refresh students to get their IDs
        for student in students:
            session.refresh(student)
        
        print(f"Created {len(students)} sample students")
        
        # Enroll first two students in the course
        for student in students[:2]:
            enrollment = StudentCourse(
                student_id=student.id,
                course_id=course.id,
                is_active=True
            )
            session.add(enrollment)
        
        session.commit()
        print("Enrolled 2 students in the sample course")
        
        print("\nDatabase initialization complete!")
        print("\nLogin credentials:")
        print("Admin: admin@quiz.com / admin123")
        print("Students: student1@example.com / student123")
        print("          student2@example.com / student123")
        print("          student3@example.com / student123")

if __name__ == "__main__":
    init_database() 