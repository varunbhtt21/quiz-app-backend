from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.models.user import UserRole, RegistrationStatus


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: UserRole


class UserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None
    mobile: Optional[str] = None
    role: UserRole
    is_active: bool
    profile_completed: bool = False
    auth_provider: str = "traditional"
    registration_status: RegistrationStatus = RegistrationStatus.ACTIVE
    course_ids: List[str] = []  # List of course IDs for students


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole 