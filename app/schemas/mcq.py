from pydantic import BaseModel
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


class MCQProblemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    option_a: Optional[str] = None
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    correct_options: Optional[List[str]] = None
    explanation: Optional[str] = None


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


class MCQProblemListResponse(BaseModel):
    id: str
    title: str
    description: str
    created_at: datetime 