from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class ContestStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ENDED = "ended"


class Contest(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    course_id: str = Field(foreign_key="course.id")
    name: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    
    # Time constraints
    start_time: datetime
    end_time: datetime
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_status(self) -> ContestStatus:
        """Get current contest status based on time"""
        now = datetime.utcnow()
        if now < self.start_time:
            return ContestStatus.NOT_STARTED
        elif now > self.end_time:
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
    
    # Contest-specific settings
    marks: float = Field(default=1.0)
    order_index: int = Field(default=0)  # Order in the contest 