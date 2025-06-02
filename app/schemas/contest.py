from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
from app.models.contest import ContestStatus


class ContestProblemCreate(BaseModel):
    problem_id: str  # MCQProblem ID to clone
    marks: float = 1.0


class ContestCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    problems: List[ContestProblemCreate]


class ContestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ContestProblemResponse(BaseModel):
    id: str
    title: str
    description: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    marks: float
    order_index: int
    image_url: Optional[str] = None
    correct_options: List[str]  # Include for UI to determine single vs multiple choice


class ContestResponse(BaseModel):
    id: str
    course_id: str
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    status: ContestStatus
    created_at: datetime


class ContestDetailResponse(ContestResponse):
    problems: List[ContestProblemResponse]


class SubmissionCreate(BaseModel):
    answers: Dict[str, List[str]]  # {problem_id: [selected_options]}
    time_taken_seconds: Optional[int] = None


class SubmissionResponse(BaseModel):
    id: str
    contest_id: str
    student_id: str
    total_score: float
    max_possible_score: float
    submitted_at: datetime
    time_taken_seconds: Optional[int]
    is_auto_submitted: bool 