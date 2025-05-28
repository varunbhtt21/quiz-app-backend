from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List
from datetime import datetime

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