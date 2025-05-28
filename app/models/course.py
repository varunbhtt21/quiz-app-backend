from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class Course(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    
    # Instructor (Admin) who created the course
    instructor_id: str = Field(foreign_key="user.id")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow) 