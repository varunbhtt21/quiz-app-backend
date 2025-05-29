from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime
from app.models.user import UserRole


class StudentCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.STUDENT  # Default to student


class StudentResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None  # Add password field for updates


class StudentEnrollment(BaseModel):
    student_ids: List[str]  # List of student IDs to enroll


class EnrolledStudentResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    enrolled_at: datetime
    enrollment_active: bool 