from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime

from app.core.database import get_session
from app.utils.auth import get_current_admin, get_current_user
from app.core.security import get_password_hash
from app.api.auth import generate_random_password
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.student_course import StudentCourse
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, StudentEnrollment
from app.schemas.student import EnrolledStudentResponse

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse)
def create_course(
    course_data: CourseCreate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new course"""
    course = Course(
        name=course_data.name,
        description=course_data.description,
        instructor_id=current_admin.id
    )
    
    session.add(course)
    session.commit()
    session.refresh(course)
    
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        instructor_id=course.instructor_id,
        created_at=course.created_at,
        updated_at=course.updated_at
    )


@router.get("/", response_model=List[CourseResponse])
def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List courses (admin sees all their courses, students see their enrolled courses)"""
    statement = select(Course)
    
    if current_user.role == UserRole.STUDENT:
        # Students only see courses they're enrolled in via StudentCourse table
        enrolled_course_ids = session.exec(
            select(StudentCourse.course_id).where(
                StudentCourse.student_id == current_user.id,
                StudentCourse.is_active == True
            )
        ).all()
        
        if not enrolled_course_ids:
            return []  # Student not enrolled in any course
        
        statement = statement.where(Course.id.in_(enrolled_course_ids))
    elif current_user.role == UserRole.ADMIN:
        # Admins only see courses they created
        statement = statement.where(Course.instructor_id == current_user.id)
    
    statement = statement.offset(skip).limit(limit).order_by(Course.created_at.desc())
    courses = session.exec(statement).all()
    
    return [
        CourseResponse(
            id=course.id,
            name=course.name,
            description=course.description,
            instructor_id=course.instructor_id,
            created_at=course.created_at,
            updated_at=course.updated_at
        )
        for course in courses
    ]


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific course"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check permissions
    if current_user.role == UserRole.STUDENT:
        # Check if student is enrolled in this course
        enrollment = session.exec(
            select(StudentCourse).where(
                StudentCourse.student_id == current_user.id,
                StudentCourse.course_id == course_id,
                StudentCourse.is_active == True
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this course"
            )
    elif current_user.role == UserRole.ADMIN:
        # Admins can only access their own courses
        if course.instructor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this course"
            )
    
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        instructor_id=course.instructor_id,
        created_at=course.created_at,
        updated_at=course.updated_at
    )


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: str,
    course_data: CourseUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update a course"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if admin owns this course
    if course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own courses"
        )
    
    # Update fields
    update_data = course_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)
    
    course.updated_at = datetime.utcnow()
    
    session.add(course)
    session.commit()
    session.refresh(course)
    
    return CourseResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        instructor_id=course.instructor_id,
        created_at=course.created_at,
        updated_at=course.updated_at
    )


@router.delete("/{course_id}")
def delete_course(
    course_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a course"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if admin owns this course
    if course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own courses"
        )
    
    session.delete(course)
    session.commit()
    
    return {"message": "Course deleted successfully"}


@router.post("/{course_id}/enroll")
def enroll_students(
    course_id: str,
    enrollment_data: StudentEnrollment,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Enroll existing students in a course"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if admin owns this course
    if course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only enroll students in your own courses"
        )
    
    enrolled_count = 0
    errors = []
    
    for student_id in enrollment_data.student_ids:
        # Check if student exists
        student = session.get(User, student_id)
        if not student or student.role != UserRole.STUDENT:
            errors.append(f"Student with ID {student_id} not found")
            continue
        
        # Check if already enrolled
        statement = select(StudentCourse).where(
            StudentCourse.student_id == student_id,
            StudentCourse.course_id == course_id
        )
        existing_enrollment = session.exec(statement).first()
        
        if existing_enrollment:
            if not existing_enrollment.is_active:
                # Reactivate enrollment
                existing_enrollment.is_active = True
                existing_enrollment.enrolled_at = datetime.utcnow()
                session.add(existing_enrollment)
                enrolled_count += 1
            else:
                errors.append(f"Student {student.email} is already enrolled in this course")
        else:
            # Create new enrollment
            enrollment = StudentCourse(
                student_id=student_id,
                course_id=course_id
            )
            session.add(enrollment)
            enrolled_count += 1
    
    session.commit()
    
    response = {
        "message": f"Enrolled {enrolled_count} students in course {course.name}",
        "enrolled_count": enrolled_count
    }
    
    if errors:
        response["errors"] = errors
    
    return response


@router.get("/{course_id}/students")
def get_course_students(
    course_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get list of students enrolled in a course"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if admin owns this course
    if course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view students in your own courses"
        )
    
    # Get students enrolled in this course
    statement = select(User, StudentCourse).join(
        StudentCourse, User.id == StudentCourse.student_id
    ).where(
        StudentCourse.course_id == course_id,
        StudentCourse.is_active == True,
        User.role == UserRole.STUDENT
    )
    
    results = session.exec(statement).all()
    
    students = []
    for user, enrollment in results:
        students.append({
            "id": user.id,
            "email": user.email,
            "is_active": user.is_active,
            "enrolled_at": enrollment.enrolled_at,
            "enrollment_active": enrollment.is_active
        })
    
    return {
        "course_id": course_id,
        "course_name": course.name,
        "students": students
    }


@router.delete("/{course_id}/students/{student_id}")
def unenroll_student(
    course_id: str,
    student_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Remove a student from a course"""
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    # Check if admin owns this course
    if course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage students in your own courses"
        )
    
    # Find enrollment
    statement = select(StudentCourse).where(
        StudentCourse.student_id == student_id,
        StudentCourse.course_id == course_id
    )
    enrollment = session.exec(statement).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student is not enrolled in this course"
        )
    
    # Deactivate enrollment instead of deleting
    enrollment.is_active = False
    session.add(enrollment)
    session.commit()
    
    return {"message": "Student removed from course successfully"} 