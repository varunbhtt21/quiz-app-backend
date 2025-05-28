from pydantic import BaseModel, EmailStr
from typing import Optional, List
from app.models.user import UserRole


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
    email: str
    role: UserRole
    is_active: bool
    course_ids: List[str] = []  # List of course IDs for students


class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole 