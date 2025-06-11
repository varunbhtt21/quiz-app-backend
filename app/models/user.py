from sqlmodel import SQLModel, Field
from typing import Optional
from enum import Enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime


class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"


class RegistrationStatus(str, Enum):
    PENDING = "PENDING"      # Pre-registered via bulk upload, awaiting first login
    ACTIVE = "ACTIVE"        # Completed profile and actively using the system
    SUSPENDED = "SUSPENDED"  # Account suspended by admin


class VerificationMethod(str, Enum):
    DIRECT = "direct"        # Student registered directly via OTP
    INVITED = "invited"      # Student pre-registered by admin via email invitation


class User(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    
    # Authentication Fields
    email: Optional[str] = Field(default=None, index=True)  # Made optional for OTPLESS users
    hashed_password: Optional[str] = Field(default=None)  # Optional for OTPLESS users
    
    # OTPLESS Authentication Fields
    otpless_user_id: Optional[str] = Field(default=None, unique=True, index=True)
    mobile: Optional[str] = Field(default=None, unique=True, index=True)
    auth_provider: str = Field(default="traditional")  # traditional, otpless_mobile, otpless_email, otpless_google, etc.
    
    # Profile Information
    name: Optional[str] = Field(default=None)
    profile_picture: Optional[str] = Field(default=None)
    profile_completed: bool = Field(default=False)
    
    # Registration Status
    registration_status: RegistrationStatus = Field(default=RegistrationStatus.ACTIVE)
    
    # Email Validation Fields (Phase 1: Email Validation Feature)
    email_sent: bool = Field(default=False, description="Whether invitation email has been sent")
    email_verified: bool = Field(default=False, description="Whether user has completed email verification by logging in")
    invitation_sent_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="Timestamp when invitation email was sent"
    )
    verification_method: VerificationMethod = Field(
        default=VerificationMethod.DIRECT,
        description="How the user was registered: direct signup or admin invitation"
    )
    
    # System Fields
    role: UserRole
    is_active: bool = Field(default=True)
    
    # Metadata - Use timezone-aware datetime with TIMESTAMPTZ
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    
    # Helper methods for email validation
    def is_email_invitation_pending(self) -> bool:
        """Check if user has pending email invitation (sent but not verified)"""
        return (
            self.verification_method == VerificationMethod.INVITED and
            self.email_sent and 
            not self.email_verified
        )
    
    def can_send_invitation_email(self) -> bool:
        """Check if invitation email can be sent to this user"""
        return (
            self.email and  # Has email address
            not self.email_verified and  # Not already verified
            (
                not self.email_sent or  # Never sent email
                (
                    self.invitation_sent_at and 
                    (datetime.now(timezone.utc) - self.invitation_sent_at).total_seconds() > 3600  # Last sent > 1 hour ago
                )
            )
        )
    
    def mark_email_verified(self):
        """Mark user as email verified when they first log in after invitation"""
        if self.verification_method == VerificationMethod.INVITED:
            self.email_verified = True
            self.updated_at = datetime.now(timezone.utc)
    
    class Config:
        use_enum_values = True 