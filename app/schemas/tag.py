from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="Tag name")
    description: Optional[str] = Field(None, max_length=255, description="Tag description")
    color: Optional[str] = Field("#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="Tag name")
    description: Optional[str] = Field(None, max_length=255, description="Tag description")
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")


class TagResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    color: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    mcq_count: Optional[int] = Field(None, description="Number of questions with this tag (all types)")
    question_count: Optional[int] = Field(None, description="Number of questions with this tag (alias for mcq_count)")
    
    def __init__(self, **data):
        # Ensure question_count matches mcq_count for backward compatibility
        if 'mcq_count' in data and 'question_count' not in data:
            data['question_count'] = data['mcq_count']
        elif 'question_count' in data and 'mcq_count' not in data:
            data['mcq_count'] = data['question_count']
        super().__init__(**data)


class TagWithMCQs(TagResponse):
    mcq_problems: List[dict] = Field(default_factory=list, description="MCQ problems with this tag")


class MCQTagResponse(BaseModel):
    mcq_id: str
    tag_id: str
    added_at: datetime
    added_by: str


# For MCQ operations with tags
class MCQTagsUpdate(BaseModel):
    tag_ids: List[str] = Field(..., min_items=1, description="List of tag IDs (at least one required)")


class TagSearchFilters(BaseModel):
    name: Optional[str] = Field(None, description="Search by tag name")
    created_by: Optional[str] = Field(None, description="Filter by creator")
    color: Optional[str] = Field(None, description="Filter by color")
    has_mcqs: Optional[bool] = Field(None, description="Filter tags with/without MCQs") 