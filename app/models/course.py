from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, DateTime


class Course(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    
    # Instructor (Admin) who created the course
    instructor_id: str = Field(foreign_key="user.id")
    
    # Metadata - Use timezone-aware datetime with TIMESTAMPTZ
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    ) 