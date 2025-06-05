from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, DateTime


class Submission(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    contest_id: str = Field(foreign_key="contest.id")
    student_id: str = Field(foreign_key="user.id")
    
    # Answers stored as JSON: {problem_id: [selected_options]}
    answers: str = Field(description="JSON object mapping problem_id to selected options")
    
    # Scoring
    total_score: float = Field(default=0.0)
    max_possible_score: float = Field(default=0.0)
    
    # Per-problem correctness stored as JSON: {problem_id: is_correct}
    problem_scores: str = Field(description="JSON object mapping problem_id to correctness")
    
    # Timing - Use timezone-aware datetime with TIMESTAMPTZ
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    time_taken_seconds: Optional[int] = Field(default=None)  # Time taken to complete
    
    # Metadata
    is_auto_submitted: bool = Field(default=False)  # True if auto-submitted on timeout
    
    class Config:
        # Ensure one submission per student per contest
        table_args = {"sqlite_autoincrement": True} 