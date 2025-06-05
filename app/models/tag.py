from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, DateTime


class MCQTag(SQLModel, table=True):
    """Junction table for many-to-many relationship between MCQ and Tag"""
    mcq_id: Optional[str] = Field(default=None, foreign_key="mcqproblem.id", primary_key=True)
    tag_id: Optional[str] = Field(default=None, foreign_key="tag.id", primary_key=True)
    
    # Optional metadata for the relationship - Use timezone-aware datetime with TIMESTAMPTZ
    added_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    added_by: str = Field(foreign_key="user.id", description="User who added this tag to the MCQ")


class Tag(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(index=True, unique=True, description="Unique tag name")
    description: Optional[str] = Field(default=None, description="Optional tag description")
    color: Optional[str] = Field(default="#3B82F6", description="Hex color code for tag display")
    
    # Metadata - Use timezone-aware datetime with TIMESTAMPTZ
    created_by: str = Field(foreign_key="user.id", description="User who created this tag")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    ) 