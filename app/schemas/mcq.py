from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MCQProblemCreate(BaseModel):
    title: str
    description: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_options: List[str]  # e.g., ["A", "B"] for multi-select
    explanation: Optional[str] = None
    tag_ids: Optional[List[str]] = Field(None, description="List of tag IDs (optional for bulk import)")


class MCQProblemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_options: Optional[List[str]] = None
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
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_options: List[str]
    explanation: Optional[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    tags: List[TagInfo] = Field(default_factory=list, description="Tags associated with this MCQ")
    needs_tags: bool = Field(default=False, description="True if MCQ was imported without tags and needs tagging")


class MCQProblemListResponse(BaseModel):
    id: str
    title: str
    description: str
    created_at: datetime
    tags: List[TagInfo] = Field(default_factory=list, description="Tags associated with this MCQ")
    needs_tags: bool = Field(default=False, description="True if MCQ was imported without tags and needs tagging")


class MCQSearchFilters(BaseModel):
    search: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    tag_names: Optional[List[str]] = None
    created_by: Optional[str] = None
    needs_tags: Optional[bool] = None  # Filter for questions that need tags 