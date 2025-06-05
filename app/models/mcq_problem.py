from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json
from sqlalchemy import Column, DateTime


class MCQProblem(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(index=True)
    description: str
    
    # Optional image URL for the question
    image_url: Optional[str] = Field(default=None, description="URL of the question image if any")
    
    # Options
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    
    # Correct options (stored as JSON list, e.g., ["A", "B"] for multi-select)
    correct_options: str = Field(description="JSON list of correct options")
    
    # Optional explanation
    explanation: Optional[str] = Field(default=None)
    
    # Tag status - for tracking MCQs that need tags assigned
    needs_tags: bool = Field(default=False, description="True if MCQ was imported without tags and needs tagging")
    
    # Metadata - Use timezone-aware datetime with TIMESTAMPTZ
    created_by: str = Field(foreign_key="user.id")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    
    def get_correct_options(self) -> List[str]:
        """Get correct options as a list"""
        return json.loads(self.correct_options)
    
    def set_correct_options(self, options: List[str]):
        """Set correct options from a list"""
        self.correct_options = json.dumps(options) 