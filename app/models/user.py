from sqlmodel import SQLModel, Field
from typing import Optional
from enum import Enum
import uuid
from datetime import datetime


class UserRole(str, Enum):
    ADMIN = "admin"
    STUDENT = "student"


class User(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    role: UserRole
    is_active: bool = Field(default=True)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True 