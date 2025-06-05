from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid
from sqlalchemy import Column, DateTime


class ContestStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class Contest(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    course_id: str = Field(foreign_key="course.id")
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    
    # Time constraints - Use timezone-aware datetime with TIMESTAMPTZ
    start_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end_time: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    
    # Metadata - Use timezone-aware datetime with TIMESTAMPTZ
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    
    def get_status(self) -> ContestStatus:
        """Get current contest status based on time"""
        # Use UTC time for consistent comparison across all timezones
        now = datetime.now(timezone.utc)
        
        # Ensure contest times are timezone-aware for comparison
        start_time = self.start_time
        end_time = self.end_time
        
        # If stored times are naive, assume they are UTC
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        if now < start_time:
            return ContestStatus.NOT_STARTED
        elif now > end_time:
            return ContestStatus.ENDED
        else:
            return ContestStatus.IN_PROGRESS
    
    class Config:
        use_enum_values = True


class ContestProblem(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    contest_id: str = Field(foreign_key="contest.id")
    
    # Deep copy of the original problem at contest creation time
    cloned_problem_id: str  # Reference to original MCQProblem
    title: str
    description: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_options: str  # JSON list
    explanation: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None)  # Store image URL from original MCQ
    
    # Contest-specific settings
    marks: float = Field(default=1.0)
    order_index: int = Field(default=0)  # Order in the contest 