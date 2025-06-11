from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union
from datetime import datetime
from app.models.contest import ContestStatus


class ContestProblemCreate(BaseModel):
    problem_id: str  # MCQProblem ID to clone
    marks: float = Field(gt=0, description="Marks must be positive")


class ContestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="Contest name")
    description: Optional[str] = Field(None, max_length=1000, description="Contest description")
    start_time: datetime = Field(description="Contest start time (timezone-aware)")
    end_time: datetime = Field(description="Contest end time (timezone-aware)")
    problems: List[ContestProblemCreate] = Field(min_items=1, description="Contest problems")


class ContestUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Contest name")
    description: Optional[str] = Field(None, max_length=1000, description="Contest description")
    start_time: Optional[datetime] = Field(None, description="Contest start time (timezone-aware)")
    end_time: Optional[datetime] = Field(None, description="Contest end time (timezone-aware)")


class ContestStatusUpdate(BaseModel):
    is_active: bool = Field(description="Whether contest should be enabled/disabled")


class ContestProblemResponse(BaseModel):
    id: str
    question_type: str = Field(description="Question type: mcq or long_answer")
    title: str
    description: str
    option_a: Optional[str] = None  # Optional for Long Answer questions
    option_b: Optional[str] = None
    option_c: Optional[str] = None
    option_d: Optional[str] = None
    marks: float
    order_index: int
    image_url: Optional[str] = None
    correct_options: List[str] = []  # Empty for Long Answer questions
    
    # Long Answer specific fields
    max_word_count: Optional[int] = None
    sample_answer: Optional[str] = None


class ContestResponse(BaseModel):
    id: str
    course_id: str
    name: str
    description: Optional[str]
    is_active: bool = Field(description="Whether contest is enabled/visible to students")
    start_time: datetime = Field(description="Contest start time in UTC")
    end_time: datetime = Field(description="Contest end time in UTC")
    status: ContestStatus
    created_at: datetime = Field(description="Contest creation time in UTC")
    
    # Additional timezone information for frontend
    timezone: str = Field(default="UTC", description="Timezone of the timestamps")
    duration_seconds: Optional[int] = Field(None, description="Contest duration in seconds")
    can_be_deleted: Optional[bool] = Field(None, description="Whether contest can be deleted")
    
    class Config:
        # Ensure datetime fields are serialized with timezone info
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ContestDetailResponse(ContestResponse):
    problems: List[ContestProblemResponse]
    
    # Additional timing information for active contests
    time_info: Optional[Dict] = Field(None, description="Real-time timing information")


class SubmissionCreate(BaseModel):
    answers: Dict[str, Union[List[str], str]] = Field(
        description="Problem answers: {problem_id: [selected_options] for MCQ, text_answer for Long Answer}"
    )
    time_taken_seconds: Optional[int] = Field(
        None, 
        ge=0, 
        description="Time taken to complete the contest in seconds"
    )


class SubmissionResponse(BaseModel):
    id: str
    contest_id: str
    student_id: str
    total_score: float
    max_possible_score: float
    submitted_at: datetime = Field(description="Submission time in UTC")
    time_taken_seconds: Optional[int]
    is_auto_submitted: bool 
    
    # Additional fields for better frontend handling
    percentage: Optional[float] = Field(None, description="Score percentage")
    timezone: str = Field(default="UTC", description="Timezone of the timestamps")
    
    class Config:
        # Ensure datetime fields are serialized with timezone info
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        } 