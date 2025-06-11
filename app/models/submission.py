from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, DateTime


class Submission(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    contest_id: str = Field(foreign_key="contest.id")
    student_id: str = Field(foreign_key="user.id")
    
    # Answers stored as JSON: 
    # For MCQ: {problem_id: [selected_options]}
    # For Long Answer: {problem_id: "text_answer"}
    answers: str = Field(description="JSON object mapping problem_id to answers (array for MCQ, string for long answer)")
    
    # Scoring
    total_score: float = Field(default=0.0)
    max_possible_score: float = Field(default=0.0)
    
    # Per-problem correctness stored as JSON: {problem_id: score_value}
    # For MCQ: boolean (0.0 or full marks)
    # For Long Answer: actual score assigned
    problem_scores: str = Field(description="JSON object mapping problem_id to scores")
    
    # Manual scoring support for long answer questions
    manual_scores: Optional[str] = Field(default=None, description="JSON object mapping problem_id to manually assigned scores")
    needs_manual_review: bool = Field(default=False, description="True if submission contains long answers needing manual scoring")
    reviewed_by: Optional[str] = Field(default=None, foreign_key="user.id", description="Admin who reviewed the long answers")
    reviewed_at: Optional[datetime] = Field(
        default=None, 
        sa_column=Column(DateTime(timezone=True), nullable=True),
        description="When manual review was completed"
    )
    
    # Timing - Use timezone-aware datetime with TIMESTAMPTZ
    submitted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    time_taken_seconds: Optional[int] = Field(default=None)  # Time taken to complete
    
    # Metadata
    is_auto_submitted: bool = Field(default=False)  # True if auto-submitted on timeout
    
    def is_fully_scored(self) -> bool:
        """Check if all questions (including long answers) have been scored"""
        return not self.needs_manual_review or (self.reviewed_by is not None and self.reviewed_at is not None)
    
    class Config:
        # Ensure one submission per student per contest
        table_args = {"sqlite_autoincrement": True} 