from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from app.models.user import UserRole, RegistrationStatus


class OTPLESSTokenRequest(BaseModel):
    """Request model for OTPLESS token verification"""
    token: str


class UserInfo(BaseModel):
    """User information nested object"""
    id: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    name: Optional[str] = None
    role: UserRole
    profile_completed: bool
    registration_status: RegistrationStatus = RegistrationStatus.ACTIVE


class OTPLESSVerifyResponse(BaseModel):
    """Response model for OTPLESS token verification"""
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    requires_profile_completion: bool


class ProfileCompletionRequest(BaseModel):
    """Request model for completing user profile"""
    name: str
    email: EmailStr


class ProfileCompletionResponse(BaseModel):
    """Response model for profile completion"""
    success: bool
    message: str
    user_id: str


class OTPLESSUserResponse(BaseModel):
    """Response model for OTPLESS user information"""
    id: str
    email: Optional[str] = None
    mobile: Optional[str] = None
    name: Optional[str] = None
    profile_picture: Optional[str] = None
    role: UserRole
    auth_provider: str
    profile_completed: bool
    registration_status: RegistrationStatus = RegistrationStatus.ACTIVE
    is_active: bool 