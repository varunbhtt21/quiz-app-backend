from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from app.models.mcq_problem import QuestionType, ScoringType


class QuestionCreateBase(BaseModel):
    title: str
    description: str
    question_type: QuestionType
    explanation: Optional[str] = None
    tag_ids: Optional[List[str]] = Field(None, description="List of tag IDs (optional for bulk import)")


class MCQProblemCreate(QuestionCreateBase):
    # MCQ-specific fields (required for MCQ type)
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_options: Optional[List[str]] = None  # e.g., ["A", "B"] for multi-select
    
    # Long Answer specific fields (required for Long Answer type)
    max_word_count: Optional[int] = None
    sample_answer: Optional[str] = None
    scoring_type: Optional[ScoringType] = ScoringType.MANUAL
    keywords_for_scoring: Optional[List[str]] = None
    
    @validator('option_a', 'option_b', 'option_c', 'option_d', 'correct_options')
    def validate_mcq_fields(cls, v, values):
        """Validate that MCQ fields are provided for MCQ question type"""
        if values.get('question_type') == QuestionType.MCQ:
            if v is None:
                raise ValueError('MCQ fields are required for MCQ question type')
        return v
    
    @validator('correct_options')
    def validate_correct_options(cls, v, values):
        """Validate correct options for MCQ"""
        if values.get('question_type') == QuestionType.MCQ and v:
            valid_options = ['A', 'B', 'C', 'D']
            for option in v:
                if option not in valid_options:
                    raise ValueError(f'Invalid option: {option}. Must be one of {valid_options}')
        return v
    
    @validator('max_word_count')
    def validate_max_word_count(cls, v, values):
        """Validate max word count for long answer questions"""
        if values.get('question_type') == QuestionType.LONG_ANSWER:
            if v is not None and v <= 0:
                raise ValueError('Max word count must be positive')
        return v


class MCQProblemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    question_type: Optional[QuestionType] = None
    
    # MCQ-specific fields
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_options: Optional[List[str]] = None
    
    # Long Answer specific fields
    max_word_count: Optional[int] = None
    sample_answer: Optional[str] = None
    scoring_type: Optional[ScoringType] = None
    keywords_for_scoring: Optional[List[str]] = None
    
    # Common fields
    explanation: Optional[str] = None
    tag_ids: Optional[List[str]] = Field(None, description="List of tag IDs (optional)")


class TagInfo(BaseModel):
    id: str
    name: str
    color: str


class MCQProblemResponse(BaseModel):
    id: str
    title: str
    description: str
    question_type: QuestionType
    
    # MCQ-specific fields (optional for long answer)
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_options: Optional[List[str]] = None
    
    # Long Answer specific fields (optional for MCQ)
    max_word_count: Optional[int] = None
    sample_answer: Optional[str] = None
    scoring_type: Optional[ScoringType] = None
    keywords_for_scoring: Optional[List[str]] = None
    
    # Common fields
    explanation: Optional[str] = None
    image_url: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime
    tags: List[TagInfo] = Field(default_factory=list, description="Tags associated with this question")
    needs_tags: bool = Field(default=False, description="True if question was imported without tags and needs tagging")


class MCQProblemListResponse(BaseModel):
    id: str
    title: str
    description: str
    question_type: QuestionType
    image_url: Optional[str] = None
    created_at: datetime
    tags: List[TagInfo] = Field(default_factory=list, description="Tags associated with this question")
    needs_tags: bool = Field(default=False, description="True if question was imported without tags and needs tagging")


class MCQSearchFilters(BaseModel):
    search: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    tag_names: Optional[List[str]] = None
    created_by: Optional[str] = None
    needs_tags: Optional[bool] = None  # Filter for questions that need tags 
    question_type: Optional[QuestionType] = None  # Filter by question type


# Backward compatibility aliases
QuestionCreate = MCQProblemCreate
QuestionUpdate = MCQProblemUpdate
QuestionResponse = MCQProblemResponse
QuestionListResponse = MCQProblemListResponse
QuestionSearchFilters = MCQSearchFilters 