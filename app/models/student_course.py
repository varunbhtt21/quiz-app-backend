from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, DateTime


class StudentCourse(SQLModel, table=True):
    """Many-to-many relationship between students and courses"""
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    student_id: str = Field(foreign_key="user.id")
    course_id: str = Field(foreign_key="course.id")
    
    # Enrollment metadata - Use timezone-aware datetime with TIMESTAMPTZ
    enrolled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    is_active: bool = Field(default=True)
    
    class Config:
        # Ensure unique combination of student and course
        table_args = {"sqlite_unique": ["student_id", "course_id"]} 