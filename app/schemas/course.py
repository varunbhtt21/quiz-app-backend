from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CourseCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CourseResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    instructor_id: str
    created_at: datetime
    updated_at: datetime


class StudentEnrollment(BaseModel):
    student_ids: List[str]  # List of student IDs to enroll in course 