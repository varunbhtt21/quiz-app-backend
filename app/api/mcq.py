from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Optional
from datetime import datetime
from io import BytesIO
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


@router.get("/template/download")
def download_mcq_template(
    current_admin: User = Depends(get_current_admin)
):
    """Download CSV template for bulk MCQ import"""
    # Create clean CSV content without comments for better spreadsheet compatibility
    csv_content = """title,description,option_a,option_b,option_c,option_d,correct_options,explanation
What is the capital of France?,Choose the correct capital city,Paris,London,Berlin,Rome,A,Paris is the capital and largest city of France
Which of the following are prime numbers?,Select all prime numbers,2,4,5,6,"A,C","Prime numbers are natural numbers greater than 1 that have no positive divisors other than 1 and themselves"
What is 2 + 2?,Basic arithmetic question,3,4,5,6,B,Simple addition: 2 + 2 = 4
Which programming language is known for web development?,Choose the most popular option,Java,JavaScript,Python,C++,B,JavaScript is widely used for both front-end and back-end web development
What is the largest planet in our solar system?,Select the correct planet,Earth,Mars,Jupiter,Venus,C,Jupiter is the largest planet in our solar system"""
    
    # Create CSV file
    output = BytesIO()
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mcq_import_template_{timestamp}.csv"
    
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/bulk-import")
def bulk_import_mcq_problems(
    file: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Bulk import MCQ problems from CSV file"""
    if not file.filename.endswith(('.csv', '.txt')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file (.csv)"
        )
    
    try:
        # Read CSV file
        contents = file.file.read().decode('utf-8')
        
        # Split into lines and filter out comments and empty lines
        lines = [line.strip() for line in contents.split('\n') 
                if line.strip() and not line.strip().startswith('#')]
        
        if len(lines) < 2:  # Need at least header + 1 data row
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV file must contain at least a header row and one data row"
            )
        
        # Parse header
        header = lines[0].split(',')
        header = [col.strip().lower() for col in header]
        
        # Validate required columns
        required_columns = ['title', 'description', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_options']
        missing_columns = [col for col in required_columns if col not in header]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}. Found columns: {', '.join(header)}"
            )
        
        # Get column indices
        title_idx = header.index('title')
        description_idx = header.index('description')
        option_a_idx = header.index('option_a')
        option_b_idx = header.index('option_b')
        option_c_idx = header.index('option_c')
        option_d_idx = header.index('option_d')
        correct_options_idx = header.index('correct_options')
        explanation_idx = header.index('explanation') if 'explanation' in header else None
        
        # Process MCQ problems
        results = {
            "total_rows": len(lines) - 1,  # Exclude header
            "successful": 0,
            "failed": 0,
            "errors": [],
            "created_problems": []
        }
        
        for line_num, line in enumerate(lines[1:], start=2):  # Start from row 2 (after header)
            try:
                # Parse CSV line (handle quoted commas)
                columns = []
                current_col = ""
                in_quotes = False
                
                for char in line:
                    if char == '"':
                        in_quotes = not in_quotes
                    elif char == ',' and not in_quotes:
                        columns.append(current_col.strip())
                        current_col = ""
                    else:
                        current_col += char
                columns.append(current_col.strip())  # Add the last column
                
                # Remove quotes from columns
                columns = [col.strip('"').strip() for col in columns]
                
                # Check if we have enough columns
                required_col_count = max(title_idx, description_idx, option_a_idx, option_b_idx, 
                                       option_c_idx, option_d_idx, correct_options_idx) + 1
                if len(columns) < required_col_count:
                    results["errors"].append(f"Row {line_num}: Not enough columns in row")
                    results["failed"] += 1
                    continue
                
                # Extract data
                title = columns[title_idx].strip()
                description = columns[description_idx].strip()
                option_a = columns[option_a_idx].strip()
                option_b = columns[option_b_idx].strip()
                option_c = columns[option_c_idx].strip()
                option_d = columns[option_d_idx].strip()
                correct_options_str = columns[correct_options_idx].strip()
                explanation = None
                if explanation_idx is not None and len(columns) > explanation_idx:
                    explanation = columns[explanation_idx].strip() or None
                
                # Validate required fields
                if not title:
                    results["errors"].append(f"Row {line_num}: Title is required")
                    results["failed"] += 1
                    continue
                
                if not description:
                    results["errors"].append(f"Row {line_num}: Description is required")
                    results["failed"] += 1
                    continue
                
                if not all([option_a, option_b, option_c, option_d]):
                    results["errors"].append(f"Row {line_num}: All four options (A, B, C, D) are required")
                    results["failed"] += 1
                    continue
                
                # Parse correct options
                try:
                    if ',' in correct_options_str:
                        # Multiple correct options (e.g., "A,C" or "A, C")
                        correct_options = [opt.strip().upper() for opt in correct_options_str.split(',')]
                    else:
                        # Single correct option (e.g., "A")
                        correct_options = [correct_options_str.strip().upper()]
                    
                    # Validate correct options
                    valid_options = ["A", "B", "C", "D"]
                    for option in correct_options:
                        if option not in valid_options:
                            results["errors"].append(f"Row {line_num}: Invalid correct option '{option}'. Must be one of {valid_options}")
                            results["failed"] += 1
                            continue
                    
                    if not correct_options:
                        results["errors"].append(f"Row {line_num}: At least one correct option must be specified")
                        results["failed"] += 1
                        continue
                        
                except Exception as e:
                    results["errors"].append(f"Row {line_num}: Error parsing correct options: {str(e)}")
                    results["failed"] += 1
                    continue
                
                # Create MCQ problem
                mcq_problem = MCQProblem(
                    title=title,
                    description=description,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c,
                    option_d=option_d,
                    correct_options=json.dumps(correct_options),
                    explanation=explanation,
                    created_by=current_admin.id
                )
                
                session.add(mcq_problem)
                session.flush()  # Get the ID
                
                results["created_problems"].append({
                    "id": mcq_problem.id,
                    "title": mcq_problem.title,
                    "correct_options": correct_options
                })
                results["successful"] += 1
                
            except Exception as e:
                results["errors"].append(f"Row {line_num}: {str(e)}")
                results["failed"] += 1
                continue
        
        # Commit all successful creations
        session.commit()
        
        return results
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a valid text file with UTF-8 encoding"
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing file: {str(e)}"
        ) 