from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import json
from enum import Enum
from sqlalchemy import Column, DateTime


class QuestionType(str, Enum):
    MCQ = "mcq"
    LONG_ANSWER = "long_answer"


class ScoringType(str, Enum):
    MANUAL = "manual"
    KEYWORD_BASED = "keyword_based"
    AUTO = "auto"


class MCQProblem(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(index=True)
    description: str
    
    # Question type - new field with default for backward compatibility
    question_type: QuestionType = Field(default=QuestionType.MCQ, description="Type of question: MCQ or Long Answer")
    
    # Optional image URL for the question (available for both question types)
    image_url: Optional[str] = Field(default=None, description="URL of the question image if any")
    
    # MCQ-specific fields (now optional for long_answer questions)
    option_a: Optional[str] = Field(default=None)
    option_b: Optional[str] = Field(default=None)
    option_c: Optional[str] = Field(default=None)
    option_d: Optional[str] = Field(default=None)
    
    # Correct options (stored as JSON list, e.g., ["A", "B"] for multi-select)
    # Optional for long_answer questions
    correct_options: Optional[str] = Field(default=None, description="JSON list of correct options for MCQ")
    
    # Long Answer specific fields
    max_word_count: Optional[int] = Field(default=None, description="Maximum word count for long answer questions")
    sample_answer: Optional[str] = Field(default=None, description="Sample answer for long answer questions")
    scoring_type: ScoringType = Field(default=ScoringType.MANUAL, description="How the long answer should be scored")
    keywords_for_scoring: Optional[str] = Field(default=None, description="JSON list of keywords for keyword-based scoring")
    
    # Optional explanation (available for both question types)
    explanation: Optional[str] = Field(default=None)
    
    # Tag status - for tracking questions that need tags assigned
    needs_tags: bool = Field(default=False, description="True if question was imported without tags and needs tagging")
    
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
    
    # Helper methods for MCQ questions
    def get_correct_options(self) -> List[str]:
        """Get correct options as a list for MCQ questions"""
        if self.question_type == QuestionType.MCQ and self.correct_options:
            return json.loads(self.correct_options)
        return []
    
    def set_correct_options(self, options: List[str]):
        """Set correct options from a list for MCQ questions"""
        if self.question_type == QuestionType.MCQ:
            self.correct_options = json.dumps(options)
    
    # Helper methods for Long Answer questions
    def get_scoring_keywords(self) -> List[str]:
        """Get scoring keywords as a list for long answer questions"""
        if self.question_type == QuestionType.LONG_ANSWER and self.keywords_for_scoring:
            return json.loads(self.keywords_for_scoring)
        return []
    
    def set_scoring_keywords(self, keywords: List[str]):
        """Set scoring keywords from a list for long answer questions"""
        if self.question_type == QuestionType.LONG_ANSWER:
            self.keywords_for_scoring = json.dumps(keywords)
    
    # Validation methods
    def is_valid_mcq(self) -> bool:
        """Check if MCQ question has all required fields"""
        if self.question_type != QuestionType.MCQ:
            return True  # Not an MCQ, so MCQ validation doesn't apply
        
        return all([
            self.option_a,
            self.option_b, 
            self.option_c,
            self.option_d,
            self.correct_options
        ])
    
    def is_valid_long_answer(self) -> bool:
        """Check if Long Answer question has valid configuration"""
        if self.question_type != QuestionType.LONG_ANSWER:
            return True  # Not a long answer, so validation doesn't apply
        
        # Basic validation - sample_answer is recommended but not required
        return True
    
    class Config:
        use_enum_values = True 