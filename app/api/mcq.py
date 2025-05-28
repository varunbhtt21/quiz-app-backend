from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
import json

from app.core.database import get_session
from app.models.mcq_problem import MCQProblem
from app.models.user import User
from app.schemas.mcq import (
    MCQProblemCreate, 
    MCQProblemUpdate, 
    MCQProblemResponse, 
    MCQProblemListResponse
)
from app.utils.auth import get_current_admin

router = APIRouter(prefix="/mcq", tags=["MCQ Problems"])


@router.post("/", response_model=MCQProblemResponse)
def create_mcq_problem(
    problem_data: MCQProblemCreate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new MCQ problem"""
    # Validate correct options
    valid_options = ["A", "B", "C", "D"]
    for option in problem_data.correct_options:
        if option not in valid_options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid option: {option}. Must be one of {valid_options}"
            )
    
    if not problem_data.correct_options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one correct option must be specified"
        )
    
    # Create MCQ problem
    mcq_problem = MCQProblem(
        title=problem_data.title,
        description=problem_data.description,
        option_a=problem_data.option_a,
        option_b=problem_data.option_b,
        option_c=problem_data.option_c,
        option_d=problem_data.option_d,
        correct_options=json.dumps(problem_data.correct_options),
        explanation=problem_data.explanation,
        created_by=current_admin.id
    )
    
    session.add(mcq_problem)
    session.commit()
    session.refresh(mcq_problem)
    
    return MCQProblemResponse(
        id=mcq_problem.id,
        title=mcq_problem.title,
        description=mcq_problem.description,
        option_a=mcq_problem.option_a,
        option_b=mcq_problem.option_b,
        option_c=mcq_problem.option_c,
        option_d=mcq_problem.option_d,
        correct_options=mcq_problem.get_correct_options(),
        explanation=mcq_problem.explanation,
        created_by=mcq_problem.created_by,
        created_at=mcq_problem.created_at,
        updated_at=mcq_problem.updated_at
    )


@router.get("/", response_model=List[MCQProblemResponse])
def list_mcq_problems(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List MCQ problems with pagination and search"""
    statement = select(MCQProblem)
    
    if search:
        statement = statement.where(
            MCQProblem.title.contains(search) | 
            MCQProblem.description.contains(search)
        )
    
    statement = statement.offset(skip).limit(limit).order_by(MCQProblem.created_at.desc())
    problems = session.exec(statement).all()
    
    return [
        MCQProblemResponse(
            id=problem.id,
            title=problem.title,
            description=problem.description,
            option_a=problem.option_a,
            option_b=problem.option_b,
            option_c=problem.option_c,
            option_d=problem.option_d,
            correct_options=problem.get_correct_options(),
            explanation=problem.explanation,
            created_by=problem.created_by,
            created_at=problem.created_at,
            updated_at=problem.updated_at
        )
        for problem in problems
    ]


@router.get("/{problem_id}", response_model=MCQProblemResponse)
def get_mcq_problem(
    problem_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a specific MCQ problem"""
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    return MCQProblemResponse(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        option_a=problem.option_a,
        option_b=problem.option_b,
        option_c=problem.option_c,
        option_d=problem.option_d,
        correct_options=problem.get_correct_options(),
        explanation=problem.explanation,
        created_by=problem.created_by,
        created_at=problem.created_at,
        updated_at=problem.updated_at
    )


@router.put("/{problem_id}", response_model=MCQProblemResponse)
def update_mcq_problem(
    problem_id: str,
    problem_data: MCQProblemUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update an MCQ problem"""
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    # Validate correct options if provided
    if problem_data.correct_options is not None:
        valid_options = ["A", "B", "C", "D"]
        for option in problem_data.correct_options:
            if option not in valid_options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid option: {option}. Must be one of {valid_options}"
                )
        
        if not problem_data.correct_options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one correct option must be specified"
            )
    
    # Update fields
    update_data = problem_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "correct_options":
            setattr(problem, field, json.dumps(value))
        else:
            setattr(problem, field, value)
    
    problem.updated_at = datetime.utcnow()
    
    session.add(problem)
    session.commit()
    session.refresh(problem)
    
    return MCQProblemResponse(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        option_a=problem.option_a,
        option_b=problem.option_b,
        option_c=problem.option_c,
        option_d=problem.option_d,
        correct_options=problem.get_correct_options(),
        explanation=problem.explanation,
        created_by=problem.created_by,
        created_at=problem.created_at,
        updated_at=problem.updated_at
    )


@router.delete("/{problem_id}")
def delete_mcq_problem(
    problem_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete an MCQ problem"""
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    session.delete(problem)
    session.commit()
    
    return {"message": "MCQ problem deleted successfully"} 