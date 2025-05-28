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
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate

router = APIRouter()


@router.get("/", response_model=List[StudentResponse])
def list_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str = Query(None),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List all students"""
    statement = select(User).where(User.role == UserRole.STUDENT)
    
    if search:
        statement = statement.where(User.email.contains(search))
    
    statement = statement.offset(skip).limit(limit)
    students = session.exec(statement).all()
    
    return [
        StudentResponse(
            id=student.id,
            email=student.email,
            is_active=student.is_active,
            created_at=student.created_at,
            updated_at=student.updated_at
        )
        for student in students
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
        role=UserRole.STUDENT
    )
    
    session.add(student)
    session.commit()
    session.refresh(student)
    
    return StudentResponse(
        id=student.id,
        email=student.email,
        is_active=student.is_active,
        created_at=student.created_at,
        updated_at=student.updated_at
    )


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(
    student_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a specific student"""
    student = session.get(User, student_id)
    if not student or student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    return StudentResponse(
        id=student.id,
        email=student.email,
        is_active=student.is_active,
        created_at=student.created_at,
        updated_at=student.updated_at
    )


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(
    student_id: str,
    student_data: StudentUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update a student"""
    student = session.get(User, student_id)
    if not student or student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Update fields
    update_data = student_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(student, field, value)
    
    student.updated_at = datetime.utcnow()
    
    session.add(student)
    session.commit()
    session.refresh(student)
    
    return StudentResponse(
        id=student.id,
        email=student.email,
        is_active=student.is_active,
        created_at=student.created_at,
        updated_at=student.updated_at
    )


@router.delete("/{student_id}")
def delete_student(
    student_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a student"""
    student = session.get(User, student_id)
    if not student or student.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    session.delete(student)
    session.commit()
    
    return {"message": "Student deleted successfully"}


@router.get("/template/download")
def download_student_template(
    current_admin: User = Depends(get_current_admin)
):
    """Download CSV template for bulk student import"""
    # Create clean CSV content without comments for better spreadsheet compatibility
    csv_content = """email,password
student1@example.com,password123
student2@example.com,password456
student3@example.com,password789
student4@example.com,mypassword001
student5@example.com,securepass999"""
    
    # Create CSV file
    output = BytesIO()
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"student_import_template_{timestamp}.csv"
    
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
    """Bulk import students from CSV file"""
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
        
        # Validate required columns
        required_columns = ['email', 'password']
        missing_columns = [col for col in required_columns if col not in header]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}. Found columns: {', '.join(header)}"
            )
        
        # Get column indices
        email_idx = header.index('email')
        password_idx = header.index('password')
        
        # Process students
        results = {
            "total_rows": len(lines) - 1,  # Exclude header
            "successful": 0,
            "failed": 0,
            "errors": [],
            "created_students": []
        }
        
        for line_num, line in enumerate(lines[1:], start=2):  # Start from row 2 (after header)
            try:
                # Split CSV line (simple split, doesn't handle quoted commas)
                columns = [col.strip() for col in line.split(',')]
                
                if len(columns) < max(email_idx + 1, password_idx + 1):
                    results["errors"].append(f"Row {line_num}: Not enough columns in row")
                    results["failed"] += 1
                    continue
                
                email = columns[email_idx].strip().lower()
                password = columns[password_idx].strip()
                
                # Validate email format
                if '@' not in email or '.' not in email:
                    results["errors"].append(f"Row {line_num}: Invalid email format '{email}'")
                    results["failed"] += 1
                    continue
                
                # Validate password length
                if len(password) < 6:
                    results["errors"].append(f"Row {line_num}: Password too short (minimum 6 characters)")
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
                
                # Create student
                hashed_password = get_password_hash(password)
                student = User(
                    email=email,
                    hashed_password=hashed_password,
                    role=UserRole.STUDENT
                )
                
                session.add(student)
                session.flush()  # Get the ID
                
                results["created_students"].append({
                    "id": student.id,
                    "email": student.email
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