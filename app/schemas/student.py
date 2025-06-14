from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, date
from app.models.user import UserRole, RegistrationStatus, VerificationMethod


class StudentCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.STUDENT  # Default to student


class StudentResponse(BaseModel):
    id: str
    email: Optional[str] = None  # Made optional to handle NULL emails gracefully
    role: UserRole
    is_active: bool
    registration_status: RegistrationStatus = RegistrationStatus.ACTIVE
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


# Email Management Request/Response Models

class BulkImportWithEmailRequest(BaseModel):
    """Request model for bulk import with automatic email sending"""
    send_emails: bool = True
    course_id: Optional[str] = None
    email_delay_seconds: int = 1  # Delay between emails to avoid rate limiting


class SendInvitationsRequest(BaseModel):
    """Request model for sending invitations to selected students"""
    student_ids: List[str]
    course_id: Optional[str] = None
    custom_message: Optional[str] = None


class BulkEmailRequest(BaseModel):
    """Request model for bulk email operations"""
    student_emails: List[EmailStr]
    subject: str
    message: str
    course_id: Optional[str] = None


class EmailStatusResponse(BaseModel):
    """Response model for email operation status"""
    operation_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    total_emails: int
    sent_count: int
    failed_count: int
    progress_percentage: float
    errors: List[str]
    started_at: datetime
    completed_at: Optional[datetime] = None


class StudentWithEmailStatus(BaseModel):
    """Extended student response with email status"""
    id: str
    email: Optional[str] = None  # Made optional to handle NULL emails gracefully
    name: Optional[str] = None
    date_of_birth: Optional[date] = None
    role: UserRole
    is_active: bool
    registration_status: RegistrationStatus
    email_sent: bool
    email_verified: bool
    invitation_sent_at: Optional[datetime] = None
    verification_method: VerificationMethod
    created_at: datetime
    updated_at: datetime


class EmailStatusUpdateRequest(BaseModel):
    """Request model for updating student email status"""
    email_sent: Optional[bool] = None
    email_verified: Optional[bool] = None 