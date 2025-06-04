from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List
from datetime import datetime
from io import BytesIO
import uuid

from app.core.database import get_session
from app.utils.auth import get_current_admin
from app.core.security import get_password_hash
from app.api.auth import generate_random_password
from app.models.user import User, UserRole, RegistrationStatus
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate

router = APIRouter()


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
            email=user.email,
            role=user.role,
            is_active=user.is_active,
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
    
    user.updated_at = datetime.utcnow()
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return StudentResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
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
        
        # Delete related records first to avoid foreign key constraint violations
        
        # 1. Delete student course enrollments (as student)
        enrollments = session.exec(
            select(StudentCourse).where(StudentCourse.student_id == student_id)
        ).all()
        for enrollment in enrollments:
            session.delete(enrollment)
        
        # 2. Delete student's submissions
        try:
            submissions = session.exec(
                select(Submission).where(Submission.student_id == student_id)
            ).all()
            for submission in submissions:
                session.delete(submission)
        except Exception:
            # Submission model might not exist or have different structure
            pass
        
        # 3. Handle MCQ tags created/added by this user
        try:
            # Delete MCQ tag relationships where user added the tag
            mcq_tags = session.exec(
                select(MCQTag).where(MCQTag.added_by == student_id)
            ).all()
            for mcq_tag in mcq_tags:
                session.delete(mcq_tag)
            
            # Handle tags created by this user - we need to be careful here
            # as other MCQs might use these tags
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
                
        except Exception:
            # Tag models might not exist or have different structure
            pass
        
        # 4. Handle MCQ problems created by this user
        try:
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
                
        except Exception:
            # MCQ models might not exist or have different structure
            pass
        
        # 5. If user is an admin, handle courses they created
        if user.role == UserRole.ADMIN:
            # Get courses created by this admin
            admin_courses = session.exec(
                select(Course).where(Course.instructor_id == student_id)
            ).all()
            
            for course in admin_courses:
                # Delete course enrollments
                course_enrollments = session.exec(
                    select(StudentCourse).where(StudentCourse.course_id == course.id)
                ).all()
                for enrollment in course_enrollments:
                    session.delete(enrollment)
                
                # Delete course contests and their dependencies
                try:
                    course_contests = session.exec(
                        select(Contest).where(Contest.course_id == course.id)
                    ).all()
                    
                    for contest in course_contests:
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
                        if submissions or contest_problems:
                            session.flush()
                    
                    # Now delete the contests
                    for contest in course_contests:
                        session.delete(contest)
                        
                except Exception:
                    # Contest model might not exist or have different structure
                    pass
                
                # Delete the course
                session.delete(course)
        
        # 6. Finally delete the user
        session.delete(user)
        session.commit()
        
        return {"message": "User deleted successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}"
        )


@router.get("/template/download")
def download_student_template(
    current_admin: User = Depends(get_current_admin)
):
    """Download CSV template for bulk student pre-registration (email only)"""
    # Create clean CSV content for student pre-registration - only email needed
    csv_content = """email
student1@example.com
student2@example.com
student3@example.com
student4@example.com
student5@example.com"""
    
    # Create CSV file
    output = BytesIO()
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
    """Bulk pre-register students from CSV file (email only, OTP authentication on first login)"""
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
        
        # Validate required columns (only email needed for pre-registration)
        required_columns = ['email']
        missing_columns = [col for col in required_columns if col not in header]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}. Found columns: {', '.join(header)}"
            )
        
        # Get column indices
        email_idx = header.index('email')
        
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
                
                if len(columns) < email_idx + 1:
                    results["errors"].append(f"Row {line_num}: Not enough columns in row")
                    results["failed"] += 1
                    continue
                
                email = columns[email_idx].strip().lower()
                
                # Validate email format
                if '@' not in email or '.' not in email:
                    results["errors"].append(f"Row {line_num}: Invalid email format '{email}'")
                    results["failed"] += 1
                    continue
                
                # Check if email already exists
                existing_user = session.exec(
                    select(User).where(User.email == email)
                ).first()
                
                if existing_user:
                    results["errors"].append(f"Row {line_num}: Email '{email}' already exists")
                    results["failed"] += 1
                    continue
                
                # Create pre-registered student (no password, PENDING status)
                user = User(
                    email=email,
                    hashed_password=None,  # No password - will use OTP authentication
                    role=UserRole.STUDENT,
                    auth_provider="otpless_mobile",  # Will use OTP authentication
                    registration_status=RegistrationStatus.PENDING,  # Pre-registered, awaiting first login
                    profile_completed=False  # Will complete profile on first login
                )
                
                session.add(user)
                session.flush()  # Get the ID
                
                results["preregistered_students"].append({
                    "id": user.id,
                    "email": user.email,
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