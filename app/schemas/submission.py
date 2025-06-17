"""
Pydantic schemas for submission review operations.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class ProblemReview(BaseModel):
    """Schema for individual problem review"""
    problem_id: str = Field(..., description="ID of the problem being reviewed")
    new_score: float = Field(..., ge=0, description="New score assigned after review")
    feedback: Optional[str] = Field(None, max_length=1000, description="Optional feedback for the student")
    
    @validator('new_score')
    def validate_score(cls, v):
        if v < 0:
            raise ValueError('Score cannot be negative')
        return round(v, 2)


class SubmissionReviewUpdate(BaseModel):
    """Schema for updating submission review"""
    problem_reviews: List[ProblemReview] = Field(..., min_items=1, description="List of problem reviews")
    general_feedback: Optional[str] = Field(None, max_length=2000, description="General feedback for the submission")
    
    @validator('problem_reviews')
    def validate_unique_problems(cls, v):
        problem_ids = [review.problem_id for review in v]
        if len(problem_ids) != len(set(problem_ids)):
            raise ValueError('Duplicate problem IDs are not allowed')
        return v


class BulkReviewUpdate(BaseModel):
    """Schema for bulk review updates"""
    submission_ids: List[str] = Field(..., min_items=1, max_items=50, description="Submission IDs to update")
    apply_keyword_scoring: bool = Field(False, description="Whether to apply keyword scoring to all submissions")
    problem_score_overrides: Optional[Dict[str, float]] = Field(None, description="Global score overrides for specific problems")


class SubmissionReviewResponse(BaseModel):
    """Response schema for submission review operations"""
    submission_id: str
    old_total_score: float
    new_total_score: float
    score_change: float
    updated_problems: List[Dict[str, Any]]
    reviewed_by: str
    reviewed_at: str


class ReviewAnalyticsResponse(BaseModel):
    """Response schema for review analytics"""
    total_submissions: int
    manual_review_pending: int
    keyword_scored: int
    manually_reviewed: int
    scoring_failures: int
    total_long_answer_questions: int
    average_keyword_accuracy: float
    scoring_method_breakdown: Dict[str, int]


class KeywordScoringRequest(BaseModel):
    """Request schema for keyword scoring operations"""
    problem_ids: Optional[List[str]] = Field(None, description="Specific problems to rescore")
    force_rescore: bool = Field(False, description="Force rescoring even if already scored")


class ReviewFilterRequest(BaseModel):
    """Request schema for filtering review data"""
    course_id: Optional[str] = None
    contest_id: Optional[str] = None
    scoring_method: Optional[str] = Field(None, pattern="^(manual|keyword_based|manual_fallback)$")
    review_status: Optional[str] = Field(None, pattern="^(pending|completed|needs_attention)$")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None 