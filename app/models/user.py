from sqlmodel import SQLModel, Field
from typing import Optional
from enum import Enum
import uuid
from datetime import datetime


class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"


class RegistrationStatus(str, Enum):
    PENDING = "PENDING"      # Pre-registered via bulk upload, awaiting first login
    ACTIVE = "ACTIVE"        # Completed profile and actively using the system
    SUSPENDED = "SUSPENDED"  # Account suspended by admin


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
    
    # System Fields
    role: UserRole
    is_active: bool = Field(default=True)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True 