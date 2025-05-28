from sqlmodel import SQLModel, Field
from typing import Optional, List
from datetime import datetime
import uuid
import json


class MCQProblem(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str = Field(index=True)
    description: str
    
    # Options
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    
    # Correct options (stored as JSON list, e.g., ["A", "B"] for multi-select)
    correct_options: str = Field(description="JSON list of correct options")
    
    # Optional explanation
    explanation: Optional[str] = Field(default=None)
    
    # Metadata
    created_by: str = Field(foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def get_correct_options(self) -> List[str]:
        """Get correct options as a list"""
        return json.loads(self.correct_options)
    
    def set_correct_options(self, options: List[str]):
        """Set correct options from a list"""
        self.correct_options = json.dumps(options) 