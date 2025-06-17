from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime

from app.core.database import get_session
from app.utils.auth import get_current_admin, get_current_user
from app.models.tag import Tag, MCQTag
from app.models.mcq_problem import MCQProblem
from app.models.user import User
from app.schemas.tag import (
    TagCreate, TagUpdate, TagResponse, TagWithMCQs, 
    MCQTagResponse, TagSearchFilters
)

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.post("/", response_model=TagResponse)
def create_tag(
    tag_data: TagCreate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new tag"""
    # Check if tag with same name already exists
    existing_tag = session.exec(
        select(Tag).where(Tag.name.ilike(tag_data.name))
    ).first()
    
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag with name '{tag_data.name}' already exists"
        )
    
    tag = Tag(
        name=tag_data.name.strip(),
        description=tag_data.description,
        color=tag_data.color,
        created_by=current_admin.id
    )
    
    session.add(tag)
    session.commit()
    session.refresh(tag)
    
    return TagResponse(
        id=tag.id,
        name=tag.name,
        description=tag.description,
        color=tag.color,
        created_by=tag.created_by,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
        mcq_count=0,
        question_count=0
    )


@router.get("/", response_model=List[TagResponse])
def list_tags(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by tag name"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List all tags with optional search and filtering"""
    statement = select(Tag, func.count(MCQTag.mcq_id).label("question_count")).outerjoin(
        MCQTag, Tag.id == MCQTag.tag_id
    ).group_by(Tag.id)
    
    # Apply filters
    if search:
        statement = statement.where(Tag.name.ilike(f"%{search}%"))
    
    if created_by:
        statement = statement.where(Tag.created_by == created_by)
    
    # Apply pagination and ordering
    statement = statement.offset(skip).limit(limit).order_by(Tag.name)
    
    results = session.exec(statement).all()
    
    return [
        TagResponse(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            color=tag.color,
            created_by=tag.created_by,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
            mcq_count=question_count,  # Backend compatibility: mcq_count field contains all question types
            question_count=question_count  # New field for frontend compatibility
        )
        for tag, question_count in results
    ]


@router.get("/{tag_id}", response_model=TagWithMCQs)
def get_tag(
    tag_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific tag with its MCQ problems"""
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    
    # Get MCQ problems with this tag
    mcq_statement = select(MCQProblem).join(
        MCQTag, MCQProblem.id == MCQTag.mcq_id
    ).where(MCQTag.tag_id == tag_id)
    
    mcq_problems = session.exec(mcq_statement).all()
    
    mcq_list = [
        {
            "id": mcq.id,
            "title": mcq.title,
            "description": mcq.description,
            "created_at": mcq.created_at
        }
        for mcq in mcq_problems
    ]
    
    return TagWithMCQs(
        id=tag.id,
        name=tag.name,
        description=tag.description,
        color=tag.color,
        created_by=tag.created_by,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
        mcq_count=len(mcq_list),
        mcq_problems=mcq_list
    )


@router.put("/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: str,
    tag_data: TagUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update a tag"""
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    
    # Check if admin owns this tag
    if tag.created_by != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own tags"
        )
    
    # Check for name conflicts if name is being updated
    if tag_data.name and tag_data.name != tag.name:
        existing_tag = session.exec(
            select(Tag).where(Tag.name.ilike(tag_data.name), Tag.id != tag_id)
        ).first()
        
        if existing_tag:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag with name '{tag_data.name}' already exists"
            )
    
    # Update fields
    update_data = tag_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "name" and value:
            setattr(tag, field, value.strip())
        else:
            setattr(tag, field, value)
    
    tag.updated_at = datetime.utcnow()
    
    session.add(tag)
    session.commit()
    session.refresh(tag)
    
    # Get MCQ count
    mcq_count = session.exec(
        select(func.count(MCQTag.mcq_id)).where(MCQTag.tag_id == tag_id)
    ).first() or 0
    
    return TagResponse(
        id=tag.id,
        name=tag.name,
        description=tag.description,
        color=tag.color,
        created_by=tag.created_by,
        created_at=tag.created_at,
        updated_at=tag.updated_at,
        mcq_count=mcq_count,
        question_count=mcq_count
    )


@router.delete("/{tag_id}")
def delete_tag(
    tag_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete a tag and remove it from all MCQs"""
    tag = session.get(Tag, tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    
    # Check if admin owns this tag
    if tag.created_by != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own tags"
        )
    
    try:
        # Get count of MCQs that would be affected
        mcq_count = session.exec(
            select(func.count(MCQTag.mcq_id)).where(MCQTag.tag_id == tag_id)
        ).first() or 0
        
        # Check if any MCQs would be left without tags after deletion
        mcqs_with_only_this_tag = session.exec(
            select(MCQTag.mcq_id).where(MCQTag.tag_id == tag_id)
        ).all()
        
        for mcq_id in mcqs_with_only_this_tag:
            other_tags_count = session.exec(
                select(func.count(MCQTag.tag_id)).where(
                    MCQTag.mcq_id == mcq_id,
                    MCQTag.tag_id != tag_id
                )
            ).first() or 0
            
            if other_tags_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot delete tag: MCQ {mcq_id} would be left without any tags. Each MCQ must have at least one tag."
                )
        
        # Delete tag relationships first
        mcq_tags = session.exec(
            select(MCQTag).where(MCQTag.tag_id == tag_id)
        ).all()
        
        for mcq_tag in mcq_tags:
            session.delete(mcq_tag)
        
        # Delete the tag
        session.delete(tag)
        session.commit()
        
        return {
            "message": f"Tag '{tag.name}' deleted successfully",
            "details": {
                "tag_name": tag.name,
                "mcqs_affected": mcq_count
            }
        }
        
    except Exception as e:
        session.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tag: {str(e)}"
        )


@router.get("/search/suggestions")
def get_tag_suggestions(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get tag suggestions for autocomplete"""
    statement = select(Tag).where(
        Tag.name.ilike(f"%{query}%")
    ).limit(limit).order_by(Tag.name)
    
    tags = session.exec(statement).all()
    
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "color": tag.color
        }
        for tag in tags
    ] 