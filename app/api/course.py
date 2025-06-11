from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
import csv
import io
from fastapi.responses import StreamingResponse

from app.core.database import get_session
from app.utils.auth import get_current_admin, get_current_user
from app.core.security import get_password_hash
from app.api.auth import generate_random_password
from app.models.user import User, UserRole
from app.models.course import Course
from app.models.student_course import StudentCourse
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, StudentEnrollment, CSVEnrollmentResult
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
        updated_at=course.updated_at,
        enrollment_count=0  # New course has no enrollments yet
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
    
    # Calculate enrollment counts for each course
    course_responses = []
    for course in courses:
        # Count active enrollments for this course
        enrollment_count = len(session.exec(
            select(StudentCourse).where(
                StudentCourse.course_id == course.id,
                StudentCourse.is_active == True
            )
        ).all())
        
        course_responses.append(CourseResponse(
            id=course.id,
            name=course.name,
            description=course.description,
            instructor_id=course.instructor_id,
            created_at=course.created_at,
            updated_at=course.updated_at,
            enrollment_count=enrollment_count
        ))
    
    return course_responses


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
        updated_at=course.updated_at,
        enrollment_count=len(session.exec(
            select(StudentCourse).where(
                StudentCourse.course_id == course.id,
                StudentCourse.is_active == True
            )
        ).all())
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
        updated_at=course.updated_at,
        enrollment_count=len(session.exec(
            select(StudentCourse).where(
                StudentCourse.course_id == course.id,
                StudentCourse.is_active == True
            )
        ).all())
    )


@router.delete("/{course_id}")
def delete_course(
    course_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a course and all related data (enrollments, contests, etc.)"""
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
    
    try:
        # First, get counts for deletion summary
        enrollment_count = len(session.exec(
            select(StudentCourse).where(StudentCourse.course_id == course_id)
        ).all())
        
        # Import Contest and related models to avoid circular imports
        from app.models.contest import Contest, ContestProblem
        from app.models.submission import Submission
        
        contests = session.exec(
            select(Contest).where(Contest.course_id == course_id)
        ).all()
        contest_count = len(contests)
        
        # Delete related records in order to avoid foreign key constraints
        
        # 1. Delete all student enrollments
        enrollments = session.exec(
            select(StudentCourse).where(StudentCourse.course_id == course_id)
        ).all()
        for enrollment in enrollments:
            session.delete(enrollment)
        
        # 2. For each contest, delete dependent records first
        for contest in contests:
            # Delete submissions for this contest
            submissions = session.exec(
                select(Submission).where(Submission.contest_id == contest.id)
            ).all()
            for submission in submissions:
                session.delete(submission)
            
            # Delete contest problems for this contest
            contest_problems = session.exec(
                select(ContestProblem).where(ContestProblem.contest_id == contest.id)
        ).all()
            for contest_problem in contest_problems:
                session.delete(contest_problem)
            
            # CRITICAL FIX: Flush to execute dependent record deletions immediately
            # This prevents foreign key constraint violations when deleting Contest
            if submissions or contest_problems:
                session.flush()
        
        # 3. Now delete all contests (dependent records are already deleted)
        for contest in contests:
            session.delete(contest)
        
        # Flush contest deletions before deleting course
        if contests:
            session.flush()
        
        # 4. Finally delete the course
        session.delete(course)
        session.commit()
    
        return {
            "message": "Course deleted successfully",
            "details": {
                "course_name": course.name,
                "enrollments_deleted": enrollment_count,
                "contests_deleted": contest_count
            }
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete course: {str(e)}"
        )


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


@router.post("/{course_id}/enroll-csv", response_model=CSVEnrollmentResult)
async def enroll_students_csv(
    course_id: str,
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Enroll students in a course using CSV file with email addresses"""
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
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    try:
        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        
        # Validate CSV headers
        if 'email' not in csv_reader.fieldnames:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV must contain 'email' column"
            )
        
        emails = []
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
            email = row.get('email', '').strip()
            if email:
                emails.append(email.lower())
            elif not email:
                continue  # Skip empty rows
        
        if not emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid email addresses found in CSV"
            )
        
        # Process enrollments
        enrolled_count = 0
        errors = []
        enrolled_students = []
        
        for email in emails:
            try:
                # Find user by email
                statement = select(User).where(
                    User.email == email,
                    User.role == UserRole.STUDENT
                )
                user = session.exec(statement).first()
                
                if not user:
                    errors.append(f"Student with email {email} not found in system")
                    continue
                
                # Check if already enrolled
                enrollment_statement = select(StudentCourse).where(
                    StudentCourse.student_id == user.id,
                    StudentCourse.course_id == course_id
                )
                existing_enrollment = session.exec(enrollment_statement).first()
                
                if existing_enrollment:
                    if not existing_enrollment.is_active:
                        # Reactivate enrollment
                        existing_enrollment.is_active = True
                        existing_enrollment.enrolled_at = datetime.utcnow()
                        session.add(existing_enrollment)
                        enrolled_count += 1
                        enrolled_students.append({
                            "email": user.email,
                            "name": user.name or "Not provided",
                            "id": user.id,
                            "status": "reactivated"
                        })
                    else:
                        errors.append(f"Student {email} is already enrolled in this course")
                else:
                    # Create new enrollment
                    enrollment = StudentCourse(
                        student_id=user.id,
                        course_id=course_id
                    )
                    session.add(enrollment)
                    enrolled_count += 1
                    enrolled_students.append({
                        "email": user.email,
                        "name": user.name or "Not provided",
                        "id": user.id,
                        "status": "enrolled"
                    })
                    
            except Exception as e:
                errors.append(f"Error processing {email}: {str(e)}")
        
        session.commit()
        
        return CSVEnrollmentResult(
            total_emails=len(emails),
            successful_enrollments=enrolled_count,
            failed_enrollments=len(emails) - enrolled_count,
            errors=errors,
            enrolled_students=enrolled_students
        )
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid CSV file encoding. Please use UTF-8 encoding."
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CSV enrollment: {str(e)}"
        )


@router.get("/{course_id}/enrollment-template")
def download_enrollment_template(
    course_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Download CSV template for course enrollment"""
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
            detail="You can only download templates for your own courses"
        )
    
    # Create CSV content for course enrollment
    csv_content = """email
student1@university.edu
student2@university.edu
student3@university.edu
student4@university.edu
student5@university.edu"""
    
    # Create file-like object
    output = io.StringIO()
    output.write(csv_content)
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"course_enrollment_template_{course.name.replace(' ', '_')}_{timestamp}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    ) 