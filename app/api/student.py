from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from datetime import datetime
from io import BytesIO
import uuid
import asyncio
import json

from app.core.database import get_session
from app.utils.auth import get_current_admin
from app.utils.time_utils import now_utc  # Use UTC time utilities
from app.core.security import get_password_hash
from app.api.auth import generate_random_password
from app.models.user import User, UserRole, RegistrationStatus, VerificationMethod
from app.schemas.student import (
    StudentCreate, StudentResponse, StudentUpdate,
    BulkImportWithEmailRequest, SendInvitationsRequest, BulkEmailRequest,
    EmailStatusResponse, StudentWithEmailStatus, EmailStatusUpdateRequest
)
from app.services.email_service import email_service

router = APIRouter()

# In-memory progress tracking for email operations
email_operation_progress = {}


# Helper Functions

def generate_operation_id() -> str:
    """Generate unique operation ID for tracking"""
    return f"email_op_{uuid.uuid4().hex[:8]}_{int(now_utc().timestamp())}"


def update_progress(operation_id: str, **kwargs):
    """Update progress for an email operation"""
    if operation_id in email_operation_progress:
        email_operation_progress[operation_id].update(kwargs)
        # Calculate progress percentage
        total = email_operation_progress[operation_id].get('total_emails', 0)
        sent = email_operation_progress[operation_id].get('sent_count', 0)
        failed = email_operation_progress[operation_id].get('failed_count', 0)
        if total > 0:
            email_operation_progress[operation_id]['progress_percentage'] = ((sent + failed) / total) * 100


async def send_bulk_emails_background(
    operation_id: str,
    students: List[Dict[str, Any]],
    course_name: Optional[str] = None,
    delay_seconds: int = 1
):
    """Background task for sending bulk emails"""
    try:
        update_progress(operation_id, status="in_progress")
        
        for i, student in enumerate(students):
            try:
                success = await email_service.send_invitation_email(
                    to_email=student['email'],
                    student_name=student.get('name', 'Student'),
                    course_name=course_name
                )
                
                if success:
                    current_sent = email_operation_progress[operation_id].get('sent_count', 0)
                    update_progress(operation_id, sent_count=current_sent + 1)
                else:
                    current_failed = email_operation_progress[operation_id].get('failed_count', 0)
                    errors = email_operation_progress[operation_id].get('errors', [])
                    errors.append(f"Failed to send email to {student['email']}")
                    update_progress(operation_id, failed_count=current_failed + 1, errors=errors)
                
                # Delay between emails to avoid rate limiting
                if i < len(students) - 1:  # Don't delay after the last email
                    await asyncio.sleep(delay_seconds)
                    
            except Exception as e:
                current_failed = email_operation_progress[operation_id].get('failed_count', 0)
                errors = email_operation_progress[operation_id].get('errors', [])
                errors.append(f"Error sending to {student['email']}: {str(e)}")
                update_progress(operation_id, failed_count=current_failed + 1, errors=errors)
        
        update_progress(
            operation_id, 
            status="completed", 
            completed_at=now_utc()
        )
        
    except Exception as e:
        errors = email_operation_progress[operation_id].get('errors', [])
        errors.append(f"Background task error: {str(e)}")
        update_progress(
            operation_id, 
            status="failed", 
            completed_at=now_utc(),
            errors=errors
        )


# Extended Email Management Endpoints

@router.get("/email-status", response_model=List[StudentWithEmailStatus])
def get_students_with_email_status(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None),
    email_status: str = Query(None, description="Filter by email status: sent, not_sent, verified, not_verified"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get students with email status information (excludes users with NULL emails)"""
    # Filter out users with NULL emails to prevent Pydantic validation errors
    statement = select(User).where(
        User.role == UserRole.STUDENT,
        User.email.is_not(None)  # Exclude NULL emails
    )
    
    # Apply search filter
    if search:
        statement = statement.where(User.email.contains(search))
    
    # Apply email status filter
    if email_status:
        if email_status == "sent":
            statement = statement.where(User.email_sent == True)
        elif email_status == "not_sent":
            statement = statement.where(User.email_sent == False)
        elif email_status == "verified":
            statement = statement.where(User.email_verified == True)
        elif email_status == "not_verified":
            statement = statement.where(User.email_verified == False)
    
    statement = statement.offset(skip).limit(limit)
    students = session.exec(statement).all()
    
    return [
        StudentWithEmailStatus(
            id=student.id,
            email=student.email,
            name=student.name,
            date_of_birth=student.date_of_birth,
            role=student.role,
            is_active=student.is_active,
            registration_status=student.registration_status,
            email_sent=student.email_sent,
            email_verified=student.email_verified,
            invitation_sent_at=student.invitation_sent_at,
            verification_method=student.verification_method,
            created_at=student.created_at,
            updated_at=student.updated_at
        )
        for student in students
    ]


@router.get("/email-operation/{operation_id}", response_model=EmailStatusResponse)
def get_email_operation_status(
    operation_id: str,
    current_admin: User = Depends(get_current_admin)
):
    """Get status of an email operation"""
    if operation_id not in email_operation_progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email operation not found"
        )
    
    operation_data = email_operation_progress[operation_id]
    
    return EmailStatusResponse(
        operation_id=operation_id,
        status=operation_data.get('status', 'unknown'),
        total_emails=operation_data.get('total_emails', 0),
        sent_count=operation_data.get('sent_count', 0),
        failed_count=operation_data.get('failed_count', 0),
        progress_percentage=operation_data.get('progress_percentage', 0.0),
        errors=operation_data.get('errors', []),
        started_at=operation_data.get('started_at'),
        completed_at=operation_data.get('completed_at')
    )


@router.post("/bulk-import-with-email")
def bulk_import_students_with_email(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    send_emails: bool = Query(True, description="Whether to send invitation emails"),
    course_id: str = Query(None, description="Course ID for email context"),
    email_delay_seconds: int = Query(1, ge=0, le=10, description="Delay between emails in seconds"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Enhanced bulk import with automatic email invitation sending"""
    
    # First, perform the regular bulk import
    regular_import_result = bulk_import_students(file, current_admin, session)
    
    # If import was successful and emails should be sent
    if send_emails and regular_import_result['successful'] > 0:
        # Validate email service is configured
        if not email_service.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service not configured. Import completed but emails not sent."
            )
        
        # Get course information for email context
        course_name = None
        if course_id:
            from app.models.course import Course
            course = session.get(Course, course_id)
            if course and course.instructor_id == current_admin.id:
                course_name = course.name
        
        # Generate operation ID for tracking
        operation_id = generate_operation_id()
        
        # Initialize progress tracking
        students_for_email = [
            {
                'email': student['email'],
                'name': student.get('name', 'Student')
            }
            for student in regular_import_result['preregistered_students']
        ]
        
        email_operation_progress[operation_id] = {
            'status': 'pending',
            'total_emails': len(students_for_email),
            'sent_count': 0,
            'failed_count': 0,
            'progress_percentage': 0.0,
            'errors': [],
            'started_at': now_utc(),
            'completed_at': None
        }
        
        # Start background email sending
        background_tasks.add_task(
            send_bulk_emails_background,
            operation_id,
            students_for_email,
            course_name,
            email_delay_seconds
        )
        
        # Update import result with email operation info
        regular_import_result['email_operation'] = {
            'operation_id': operation_id,
            'emails_to_send': len(students_for_email),
            'course_name': course_name
        }
    
    return regular_import_result


@router.post("/send-invitations")
def send_invitation_emails(
    request: SendInvitationsRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Send invitation emails to selected students"""
    
    # Validate email service
    if not email_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured"
        )
    
    # Get students
    students = session.exec(
        select(User).where(
            User.id.in_(request.student_ids),
            User.role == UserRole.STUDENT
        )
    ).all()
    
    if not students:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No students found with provided IDs"
        )
    
    # Filter students who can receive emails
    eligible_students = []
    for student in students:
        if student.can_send_invitation_email():
            eligible_students.append({
                'email': student.email,
                'name': student.name or 'Student',
                'user_id': student.id
            })
    
    if not eligible_students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No students are eligible to receive invitation emails"
        )
    
    # Get course information
    course_name = None
    if request.course_id:
        from app.models.course import Course
        course = session.get(Course, request.course_id)
        if course and course.instructor_id == current_admin.id:
            course_name = course.name
    
    # Generate operation ID and initialize progress
    operation_id = generate_operation_id()
    
    email_operation_progress[operation_id] = {
        'status': 'pending',
        'total_emails': len(eligible_students),
        'sent_count': 0,
        'failed_count': 0,
        'progress_percentage': 0.0,
        'errors': [],
        'started_at': now_utc(),
        'completed_at': None
    }
    
    # Start background email sending
    background_tasks.add_task(
        send_bulk_emails_background,
        operation_id,
        eligible_students,
        course_name,
        1  # 1 second delay between emails
    )
    
    return {
        'operation_id': operation_id,
        'total_students': len(request.student_ids),
        'eligible_for_email': len(eligible_students),
        'course_name': course_name,
        'message': f'Invitation emails are being sent to {len(eligible_students)} students'
    }


@router.post("/bulk-email")
def send_bulk_custom_email(
    request: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Send custom bulk emails to specified email addresses"""
    
    # Validate email service
    if not email_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured"
        )
    
    if len(request.student_emails) > 100:  # Rate limiting
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send more than 100 emails at once"
        )
    
    # Get course information
    course_name = None
    if request.course_id:
        from app.models.course import Course
        course = session.get(Course, request.course_id)
        if course and course.instructor_id == current_admin.id:
            course_name = course.name
    
    # Prepare student data for bulk email
    students_for_email = []
    for email in request.student_emails:
        # Try to get student name from database
        student = session.exec(select(User).where(User.email == email)).first()
        students_for_email.append({
            'email': email,
            'name': student.name if student else 'Student'
        })
    
    # Generate operation ID and initialize progress
    operation_id = generate_operation_id()
    
    email_operation_progress[operation_id] = {
        'status': 'pending',
        'total_emails': len(students_for_email),
        'sent_count': 0,
        'failed_count': 0,
        'progress_percentage': 0.0,
        'errors': [],
        'started_at': now_utc(),
        'completed_at': None
    }
    
    # For custom bulk emails, we'll need to extend the email service
    # For now, use the invitation template with custom message
    
    # Start background email sending
    background_tasks.add_task(
        send_bulk_emails_background,
        operation_id,
        students_for_email,
        course_name,
        1  # 1 second delay between emails
    )
    
    return {
        'operation_id': operation_id,
        'total_emails': len(students_for_email),
        'subject': request.subject,
        'course_name': course_name,
        'message': f'Custom emails are being sent to {len(students_for_email)} recipients'
    }


@router.patch("/{student_id}/email-status")
def update_student_email_status(
    student_id: str,
    email_sent: Optional[bool] = None,
    email_verified: Optional[bool] = None,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Manually update student email status"""
    
    student = session.get(User, student_id)
    if not student or student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Update email status fields
    if email_sent is not None:
        student.email_sent = email_sent
        if email_sent:
            student.invitation_sent_at = now_utc()
    
    if email_verified is not None:
        student.email_verified = email_verified
    
    student.updated_at = now_utc()
    
    session.add(student)
    session.commit()
    session.refresh(student)
    
    return {
        'student_id': student.id,
        'email': student.email,
        'email_sent': student.email_sent,
        'email_verified': student.email_verified,
        'updated_at': student.updated_at
    }


@router.get("/", response_model=List[StudentResponse])
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None),
    role: str = Query(None, description="Filter by role: admin or student"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List all users (admins and students)"""
    statement = select(User)
    
    # Filter by role if specified
    if role and role in ['admin', 'student']:
        statement = statement.where(User.role == UserRole(role))
    
    if search:
        statement = statement.where(User.email.contains(search))
    
    statement = statement.offset(skip).limit(limit)
    users = session.exec(statement).all()
    
    return [
        StudentResponse(
            id=user.id,
            email=user.email or f"user_{user.id[:8]}@pending.com",  # Provide fallback for null emails
            role=user.role,
            is_active=user.is_active,
            registration_status=user.registration_status,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        for user in users
    ]


@router.post("/", response_model=StudentResponse)
def create_student(
    student_data: StudentCreate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new student"""
    # Check if email already exists
    statement = select(User).where(User.email == student_data.email)
    existing_user = session.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_password = get_password_hash(student_data.password)
    
    # Create student
    student = User(
        email=student_data.email,
        hashed_password=hashed_password,
        role=student_data.role  # Use role from request data
    )
    
    session.add(student)
    session.commit()
    session.refresh(student)
    
    return StudentResponse(
        id=student.id,
        email=student.email,
        role=student.role,
        is_active=student.is_active,
        registration_status=student.registration_status,
        created_at=student.created_at,
        updated_at=student.updated_at
    )


@router.get("/{student_id}", response_model=StudentResponse)
def get_user(
    student_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a specific user"""
    user = session.get(User, student_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return StudentResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        registration_status=user.registration_status,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


@router.put("/{student_id}", response_model=StudentResponse)
def update_user(
    student_id: str,
    student_data: StudentUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update a user"""
    user = session.get(User, student_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields
    update_data = student_data.dict(exclude_unset=True)
    
    # Handle password update separately (needs hashing)
    if 'password' in update_data:
        password = update_data.pop('password')
        if password:  # Only update if password is not empty
            user.hashed_password = get_password_hash(password)
    
    # Update other fields
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = now_utc()
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return StudentResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        registration_status=user.registration_status,
        created_at=user.created_at,
        updated_at=user.updated_at
    )


@router.delete("/{student_id}")
def delete_user(
    student_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a user and all related data"""
    user = session.get(User, student_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # Import here to avoid circular imports
        from app.models.student_course import StudentCourse
        from app.models.submission import Submission
        from app.models.course import Course
        from app.models.contest import Contest, ContestProblem
        from app.models.tag import Tag, MCQTag
        from app.models.mcq_problem import MCQProblem
        
        # Execute deletion steps in proper order
        _delete_student_enrollments(session, student_id)
        _delete_student_submissions(session, student_id)
        _delete_user_mcq_tags(session, student_id)
        _delete_user_mcq_problems(session, student_id)
        
        # If admin, handle courses they created
        if user.role == UserRole.ADMIN:
            _delete_admin_courses(session, student_id)
        
        # Finally delete the user
        session.delete(user)
        session.commit()
        
        return {"message": "User deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}"
        )


def _delete_student_enrollments(session: Session, student_id: str):
    """Delete student course enrollments"""
    try:
        from app.models.student_course import StudentCourse
        
        enrollments = session.exec(
            select(StudentCourse).where(StudentCourse.student_id == student_id)
        ).all()
        
        for enrollment in enrollments:
            session.delete(enrollment)
            
        if enrollments:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        # Log but don't fail - enrollment model might not exist
        print(f"Warning: Could not delete student enrollments: {e}")


def _delete_student_submissions(session: Session, student_id: str):
    """Delete all submissions by the student"""
    try:
        from app.models.submission import Submission
        
        submissions = session.exec(
            select(Submission).where(Submission.student_id == student_id)
        ).all()
        
        for submission in submissions:
            session.delete(submission)
            
        if submissions:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        # Log but don't fail - submission model might not exist
        print(f"Warning: Could not delete student submissions: {e}")


def _delete_user_mcq_tags(session: Session, student_id: str):
    """Delete MCQ tags created/added by the user"""
    try:
        from app.models.tag import Tag, MCQTag
        
        # Delete MCQ tag relationships where user added the tag
        mcq_tags = session.exec(
            select(MCQTag).where(MCQTag.added_by == student_id)
        ).all()
        
        for mcq_tag in mcq_tags:
            session.delete(mcq_tag)
        
        # Handle tags created by this user
        user_created_tags = session.exec(
            select(Tag).where(Tag.created_by == student_id)
        ).all()
        
        for tag in user_created_tags:
            # First, delete all MCQTag relationships using this tag
            related_mcq_tags = session.exec(
                select(MCQTag).where(MCQTag.tag_id == tag.id)
            ).all()
            
            for mcq_tag in related_mcq_tags:
                session.delete(mcq_tag)
            
            # Then delete the tag itself
            session.delete(tag)
        
        if mcq_tags or user_created_tags:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        # Log but don't fail - tag models might not exist
        print(f"Warning: Could not delete user MCQ tags: {e}")


def _delete_user_mcq_problems(session: Session, student_id: str):
    """Delete MCQ problems created by the user"""
    try:
        from app.models.mcq_problem import MCQProblem
        from app.models.tag import MCQTag
        
        user_mcqs = session.exec(
            select(MCQProblem).where(MCQProblem.created_by == student_id)
        ).all()
        
        for mcq in user_mcqs:
            # First delete all tag relationships for this MCQ
            mcq_tag_relations = session.exec(
                select(MCQTag).where(MCQTag.mcq_id == mcq.id)
            ).all()
            
            for relation in mcq_tag_relations:
                session.delete(relation)
            
            # Then delete the MCQ
            session.delete(mcq)
        
        if user_mcqs:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        # Log but don't fail - MCQ models might not exist
        print(f"Warning: Could not delete user MCQ problems: {e}")


def _delete_admin_courses(session: Session, admin_id: str):
    """Delete courses created by an admin user"""
    try:
        from app.models.course import Course
        from app.models.student_course import StudentCourse
        
        # Get courses created by this admin
        admin_courses = session.exec(
            select(Course).where(Course.instructor_id == admin_id)
        ).all()
        
        for course in admin_courses:
            # Delete course enrollments first
            _delete_course_enrollments(session, course.id)
            
            # Delete course contests and their dependencies
            _delete_course_contests(session, course.id)
            
            # Delete the course itself
            session.delete(course)
        
        if admin_courses:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        # Log but don't fail - course models might not exist
        print(f"Warning: Could not delete admin courses: {e}")


def _delete_course_enrollments(session: Session, course_id: str):
    """Delete all enrollments for a course"""
    try:
        from app.models.student_course import StudentCourse
        
        course_enrollments = session.exec(
            select(StudentCourse).where(StudentCourse.course_id == course_id)
        ).all()
        
        for enrollment in course_enrollments:
            session.delete(enrollment)
            
        if course_enrollments:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        print(f"Warning: Could not delete course enrollments: {e}")


def _delete_course_contests(session: Session, course_id: str):
    """Delete all contests for a course and their dependencies"""
    try:
        from app.models.contest import Contest, ContestProblem
        from app.models.submission import Submission
        
        course_contests = session.exec(
            select(Contest).where(Contest.course_id == course_id)
        ).all()
        
        for contest in course_contests:
            # Delete contest submissions first
            _delete_contest_submissions(session, contest.id)
            
            # Delete contest problems
            _delete_contest_problems(session, contest.id)
            
            # Delete the contest itself
            session.delete(contest)
        
        if course_contests:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        print(f"Warning: Could not delete course contests: {e}")


def _delete_contest_submissions(session: Session, contest_id: str):
    """Delete all submissions for a contest"""
    try:
        from app.models.submission import Submission
        
        submissions = session.exec(
            select(Submission).where(Submission.contest_id == contest_id)
        ).all()
        
        for submission in submissions:
            session.delete(submission)
            
        if submissions:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        print(f"Warning: Could not delete contest submissions: {e}")


def _delete_contest_problems(session: Session, contest_id: str):
    """Delete all problems for a contest"""
    try:
        from app.models.contest import ContestProblem
        
        contest_problems = session.exec(
            select(ContestProblem).where(ContestProblem.contest_id == contest_id)
        ).all()
        
        for contest_problem in contest_problems:
            session.delete(contest_problem)
            
        if contest_problems:
            session.flush()  # Ensure deletions are executed
            
    except Exception as e:
        print(f"Warning: Could not delete contest problems: {e}")


@router.get("/template/download")
def download_student_template(
    current_admin: User = Depends(get_current_admin)
):
    """Download CSV template for bulk student pre-registration (email and mobile - BOTH MANDATORY)"""
    # Create enhanced CSV content for student pre-registration - email and mobile BOTH REQUIRED
    csv_content = """email,mobile
student1@example.com,+919876543210
student2@example.com,+919876543211
student3@example.com,+919876543212
student4@example.com,+919876543213
student5@example.com,+919876543214"""
    
    # Create CSV file
    output = BytesIO()
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    # Generate filename
    timestamp = now_utc().strftime("%Y%m%d_%H%M%S")
    filename = f"student_preregistration_template_{timestamp}.csv"
    
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/bulk-import")
def bulk_import_students(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Bulk pre-register students from CSV file (email and mobile BOTH MANDATORY, OTPLESS authentication on first login)"""
    if not file.filename.endswith(('.csv', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file (.csv)"
        )
    
    try:
        # Read CSV file
        contents = file.file.read().decode('utf-8')
        
        # Split into lines and filter out comments and empty lines
        lines = [line.strip() for line in contents.split('\n') 
                if line.strip() and not line.strip().startswith('#')]
        
        if len(lines) < 2:  # Need at least header + 1 data row
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file must contain at least a header row and one data row"
            )
        
        # Parse header
        header = lines[0].split(',')
        header = [col.strip().lower() for col in header]
        
        # Validate required columns (BOTH email and mobile are MANDATORY for enhanced pre-registration)
        required_columns = ['email', 'mobile']
        missing_columns = [col for col in required_columns if col not in header]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}. Found columns: {', '.join(header)}"
            )
        
        # Get column indices
        email_idx = header.index('email')
        mobile_idx = header.index('mobile')
        
        # Process students (pre-registration only)
        results = {
            "total_rows": len(lines) - 1,  # Exclude header
            "successful": 0,
            "failed": 0,
            "errors": [],
            "preregistered_students": []
        }
        
        for line_num, line in enumerate(lines[1:], start=2):  # Start from row 2 (after header)
            try:
                # Split CSV line (simple split, doesn't handle quoted commas)
                columns = [col.strip() for col in line.split(',')]
                
                if len(columns) < max(email_idx + 1, mobile_idx + 1):
                    results["errors"].append(f"Row {line_num}: Not enough columns in row")
                    results["failed"] += 1
                    continue
                
                email = columns[email_idx].strip().lower()
                mobile = columns[mobile_idx].strip()
                
                # MANDATORY VALIDATION: Both email and mobile must be present and valid
                # Check if email is empty or missing
                if not email or email == '':
                    results["errors"].append(f"Row {line_num}: Email is mandatory and cannot be empty")
                    results["failed"] += 1
                    continue
                
                # Check if mobile is empty or missing
                if not mobile or mobile == '':
                    results["errors"].append(f"Row {line_num}: Mobile number is mandatory and cannot be empty")
                    results["failed"] += 1
                    continue
                
                # Validate email format
                if '@' not in email or '.' not in email:
                    results["errors"].append(f"Row {line_num}: Invalid email format '{email}'")
                    results["failed"] += 1
                    continue
                
                # Validate mobile format (basic validation)
                if len(mobile) < 10:
                    results["errors"].append(f"Row {line_num}: Invalid mobile format '{mobile}' (minimum 10 digits)")
                    results["failed"] += 1
                    continue
                
                # Clean mobile number (remove spaces, ensure + prefix for international)
                mobile_clean = mobile.replace(' ', '').replace('-', '')
                if not mobile_clean.startswith('+'):
                    # Assume Indian number if no country code
                    mobile_clean = '+91' + mobile_clean.lstrip('0')
                
                # Validate cleaned mobile
                if len(mobile_clean) < 12 or not mobile_clean[1:].isdigit():
                    results["errors"].append(f"Row {line_num}: Invalid mobile format '{mobile}' after cleaning")
                    results["failed"] += 1
                    continue
                
                # Check if email already exists
                existing_user_email = session.exec(
                    select(User).where(User.email == email)
                ).first()
                
                if existing_user_email:
                    results["errors"].append(f"Row {line_num}: Email '{email}' already exists")
                    results["failed"] += 1
                    continue
                
                # Check if mobile already exists
                existing_user_mobile = session.exec(
                    select(User).where(User.mobile == mobile_clean)
                ).first()
                
                if existing_user_mobile:
                    results["errors"].append(f"Row {line_num}: Mobile '{mobile_clean}' already exists")
                    results["failed"] += 1
                    continue
                
                # Create pre-registered student (no password, PENDING status, with mobile)
                user = User(
                    email=email,
                    mobile=mobile_clean,  # Store cleaned mobile number
                    hashed_password=None,  # No password - will use OTPLESS authentication
                    role=UserRole.STUDENT,
                    auth_provider="traditional",  # Will be updated to "otpless" when they first login
                    registration_status=RegistrationStatus.PENDING,  # Pre-registered, awaiting first login
                    profile_completed=False,  # Will complete profile on first login
                    verification_method=VerificationMethod.INVITED  # Invited by admin via bulk import
                )
                
                session.add(user)
                session.flush()  # Get the ID
                
                results["preregistered_students"].append({
                    "id": user.id,
                    "email": user.email,
                    "mobile": user.mobile,
                    "status": "pre-registered"
                })
                results["successful"] += 1
                
            except Exception as e:
                results["errors"].append(f"Row {line_num}: {str(e)}")
                results["failed"] += 1
                continue
        
        # Commit all successful creations
        session.commit()
        
        return results
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a valid text file with UTF-8 encoding"
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        ) 