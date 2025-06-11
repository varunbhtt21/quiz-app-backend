from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
import uuid
from sqlalchemy import Column, DateTime
from .mcq_problem import QuestionType, ScoringType


class ContestStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class Contest(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    course_id: str = Field(foreign_key="course.id")
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    
    # Contest visibility control
    is_active: bool = Field(default=True, description="Whether contest is enabled/visible to students")
    
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
    
    def can_be_deleted(self) -> bool:
        """Check if contest can be deleted (only if not started)"""
        return self.get_status() == ContestStatus.NOT_STARTED
    
    class Config:
        use_enum_values = True


class ContestProblem(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    contest_id: str = Field(foreign_key="contest.id")
    
    # Deep copy of the original problem at contest creation time
    cloned_problem_id: str  # Reference to original Problem
    question_type: QuestionType = Field(description="Type of question: MCQ or Long Answer")
    title: str
    description: str
    
    # MCQ-specific fields (optional for long_answer questions)
    option_a: Optional[str] = Field(default=None)
    option_b: Optional[str] = Field(default=None)
    option_c: Optional[str] = Field(default=None)
    option_d: Optional[str] = Field(default=None)
    correct_options: Optional[str] = Field(default=None, description="JSON list of correct options for MCQ")
    
    # Long Answer specific fields
    max_word_count: Optional[int] = Field(default=None, description="Maximum word count for long answer questions")
    sample_answer: Optional[str] = Field(default=None, description="Sample answer for long answer questions")
    scoring_type: ScoringType = Field(default=ScoringType.MANUAL, description="How the long answer should be scored")
    keywords_for_scoring: Optional[str] = Field(default=None, description="JSON list of keywords for keyword-based scoring")
    
    # Common fields
    explanation: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None, description="Image URL for both question types")
    
    # Contest-specific settings
    marks: float = Field(default=1.0)
    order_index: int = Field(default=0)  # Order in the contest 
    
    class Config:
        use_enum_values = True 