from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func
from typing import List, Optional
from datetime import datetime
from io import BytesIO
import json

from app.core.database import get_session
from app.models.mcq_problem import MCQProblem, QuestionType, ScoringType
from app.models.tag import Tag, MCQTag
from app.models.user import User
from app.schemas.mcq import (
    MCQProblemCreate, 
    MCQProblemUpdate, 
    MCQProblemResponse, 
    MCQProblemListResponse,
    MCQSearchFilters,
    TagInfo
)
from app.utils.auth import get_current_admin

router = APIRouter(prefix="/mcq", tags=["Questions"])


@router.post("/", response_model=MCQProblemResponse)
def create_question(
    problem_data: MCQProblemCreate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new question (MCQ or Long Answer) with optional tags"""
    
    # Validate based on question type
    if problem_data.question_type == QuestionType.MCQ:
        # Validate MCQ fields
        if not all([problem_data.option_a, problem_data.option_b, 
                   problem_data.option_c, problem_data.option_d, 
                   problem_data.correct_options]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="All options and correct answers are required for MCQ questions"
            )
        
        # Validate correct options for MCQ
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
                detail="At least one correct option must be specified for MCQ questions"
            )
    
    elif problem_data.question_type == QuestionType.LONG_ANSWER:
        # Validate Long Answer fields
        if problem_data.max_word_count is not None and problem_data.max_word_count <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Max word count must be positive"
            )
    
    # Check if tags are provided for manual creation (UI requires tags)
    if not problem_data.tag_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one tag is required for manual question creation"
        )
    
    # Validate tags exist
    tags = session.exec(
        select(Tag).where(Tag.id.in_(problem_data.tag_ids))
    ).all()
    
    if len(tags) != len(problem_data.tag_ids):
        found_tag_ids = [tag.id for tag in tags]
        missing_tag_ids = [tag_id for tag_id in problem_data.tag_ids if tag_id not in found_tag_ids]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tags not found: {', '.join(missing_tag_ids)}"
        )
    
    try:
        # Create question
        question = MCQProblem(
            title=problem_data.title,
            description=problem_data.description,
            question_type=problem_data.question_type,
            explanation=problem_data.explanation,
            created_by=current_admin.id,
            needs_tags=False  # Manual creation always has tags
        )
        
        # Set type-specific fields
        if problem_data.question_type == QuestionType.MCQ:
            question.option_a = problem_data.option_a
            question.option_b = problem_data.option_b
            question.option_c = problem_data.option_c
            question.option_d = problem_data.option_d
            question.correct_options = json.dumps(problem_data.correct_options)
        
        elif problem_data.question_type == QuestionType.LONG_ANSWER:
            question.max_word_count = problem_data.max_word_count
            question.sample_answer = problem_data.sample_answer
            question.scoring_type = problem_data.scoring_type or ScoringType.MANUAL
            if problem_data.keywords_for_scoring:
                question.keywords_for_scoring = json.dumps(problem_data.keywords_for_scoring)
        
        session.add(question)
        session.flush()  # Get the ID
        
        # Create tag relationships
        for tag_id in problem_data.tag_ids:
            mcq_tag = MCQTag(
                mcq_id=question.id,
                tag_id=tag_id,
                added_by=current_admin.id
            )
            session.add(mcq_tag)
        
        session.commit()
        session.refresh(question)
        
        # Get tags for response
        tag_info = [
            TagInfo(id=tag.id, name=tag.name, color=tag.color)
            for tag in tags
        ]
        
        return MCQProblemResponse(
            id=question.id,
            title=question.title,
            description=question.description,
            question_type=question.question_type,
            option_a=question.option_a,
            option_b=question.option_b,
            option_c=question.option_c,
            option_d=question.option_d,
            correct_options=question.get_correct_options() if question.question_type == QuestionType.MCQ else None,
            max_word_count=question.max_word_count,
            sample_answer=question.sample_answer,
            scoring_type=question.scoring_type,
            keywords_for_scoring=question.get_scoring_keywords() if question.question_type == QuestionType.LONG_ANSWER else None,
            explanation=question.explanation,
            image_url=question.image_url,
            created_by=question.created_by,
            created_at=question.created_at,
            updated_at=question.updated_at,
            tags=tag_info,
            needs_tags=question.needs_tags
        )
    
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create question: {str(e)}"
        )


@router.get("/", response_model=List[MCQProblemResponse])
def list_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by title or description"),
    tag_ids: Optional[str] = Query(None, description="Comma-separated tag IDs to filter by"),
    tag_names: Optional[str] = Query(None, description="Comma-separated tag names to filter by"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    needs_tags: Optional[bool] = Query(None, description="Filter by questions that need tags"),
    question_type: Optional[QuestionType] = Query(None, description="Filter by question type"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """List questions with advanced filtering by tags, type, and tag status"""
    statement = select(MCQProblem).distinct()
    
    if search:
        statement = statement.where(
            MCQProblem.title.ilike(f"%{search}%") | 
            MCQProblem.description.ilike(f"%{search}%")
        )
    
    if created_by:
        statement = statement.where(MCQProblem.created_by == created_by)
    
    if needs_tags is not None:
        statement = statement.where(MCQProblem.needs_tags == needs_tags)
    
    if question_type is not None:
        statement = statement.where(MCQProblem.question_type == question_type)
    
    # Handle tag filtering
    if tag_ids:
        tag_id_list = [tag_id.strip() for tag_id in tag_ids.split(",") if tag_id.strip()]
        statement = statement.join(MCQTag, MCQProblem.id == MCQTag.mcq_id).where(
            MCQTag.tag_id.in_(tag_id_list)
        )
    elif tag_names:
        tag_name_list = [tag_name.strip() for tag_name in tag_names.split(",") if tag_name.strip()]
        statement = statement.join(MCQTag, MCQProblem.id == MCQTag.mcq_id).join(
            Tag, MCQTag.tag_id == Tag.id
        ).where(Tag.name.in_(tag_name_list))
    
    statement = statement.offset(skip).limit(limit).order_by(MCQProblem.created_at.desc())
    problems = session.exec(statement).all()
    
    # Get tags for each problem and build response
    result = []
    for problem in problems:
        tags = session.exec(
            select(Tag).join(MCQTag, Tag.id == MCQTag.tag_id).where(MCQTag.mcq_id == problem.id)
        ).all()
        
        tag_info = [
            TagInfo(id=tag.id, name=tag.name, color=tag.color)
            for tag in tags
        ]
        
        result.append(MCQProblemResponse(
            id=problem.id,
            title=problem.title,
            description=problem.description,
            question_type=problem.question_type,
            option_a=problem.option_a,
            option_b=problem.option_b,
            option_c=problem.option_c,
            option_d=problem.option_d,
            correct_options=problem.get_correct_options() if problem.question_type == QuestionType.MCQ else None,
            max_word_count=problem.max_word_count,
            sample_answer=problem.sample_answer,
            scoring_type=problem.scoring_type,
            keywords_for_scoring=problem.get_scoring_keywords() if problem.question_type == QuestionType.LONG_ANSWER else None,
            explanation=problem.explanation,
            image_url=problem.image_url,
            created_by=problem.created_by,
            created_at=problem.created_at,
            updated_at=problem.updated_at,
            tags=tag_info,
            needs_tags=problem.needs_tags
        ))
    
    return result


@router.get("/list", response_model=List[MCQProblemListResponse])
def list_questions_simplified(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    tag_ids: Optional[str] = Query(None, description="Comma-separated tag IDs"),
    question_type: Optional[QuestionType] = Query(None, description="Filter by question type"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Simplified list of questions for UI lists"""
    statement = select(MCQProblem).distinct()
    
    if search:
        statement = statement.where(
            MCQProblem.title.ilike(f"%{search}%") | 
            MCQProblem.description.ilike(f"%{search}%")
        )
    
    if question_type is not None:
        statement = statement.where(MCQProblem.question_type == question_type)
    
    if tag_ids:
        tag_id_list = [tag_id.strip() for tag_id in tag_ids.split(",") if tag_id.strip()]
        statement = statement.join(MCQTag, MCQProblem.id == MCQTag.mcq_id).where(
            MCQTag.tag_id.in_(tag_id_list)
        )
    
    statement = statement.offset(skip).limit(limit).order_by(MCQProblem.created_at.desc())
    problems = session.exec(statement).all()
    
    # Get tags for each problem
    result = []
    for problem in problems:
        tags = session.exec(
            select(Tag).join(MCQTag, Tag.id == MCQTag.tag_id).where(MCQTag.mcq_id == problem.id)
        ).all()
        
        tag_info = [
            TagInfo(id=tag.id, name=tag.name, color=tag.color)
            for tag in tags
        ]
        
        result.append(MCQProblemListResponse(
            id=problem.id,
            title=problem.title,
            description=problem.description,
            question_type=problem.question_type,
            image_url=problem.image_url,
            created_at=problem.created_at,
            tags=tag_info,
            needs_tags=problem.needs_tags
        ))
    
    return result


@router.get("/{problem_id}", response_model=MCQProblemResponse)
def get_mcq_problem(
    problem_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a specific MCQ problem with its tags"""
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    # Get tags for this problem
    tags = session.exec(
        select(Tag).join(MCQTag, Tag.id == MCQTag.tag_id).where(MCQTag.mcq_id == problem_id)
    ).all()
    
    tag_info = [
        TagInfo(id=tag.id, name=tag.name, color=tag.color)
        for tag in tags
    ]
    
    return MCQProblemResponse(
        id=problem.id,
        title=problem.title,
        description=problem.description,
        question_type=problem.question_type,
        option_a=problem.option_a,
        option_b=problem.option_b,
        option_c=problem.option_c,
        option_d=problem.option_d,
        correct_options=problem.get_correct_options() if problem.question_type == QuestionType.MCQ else None,
        max_word_count=problem.max_word_count,
        sample_answer=problem.sample_answer,
        scoring_type=problem.scoring_type,
        keywords_for_scoring=problem.get_scoring_keywords() if problem.question_type == QuestionType.LONG_ANSWER else None,
        explanation=problem.explanation,
        image_url=problem.image_url,
        created_by=problem.created_by,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
        tags=tag_info,
        needs_tags=problem.needs_tags
    )


@router.put("/{problem_id}", response_model=MCQProblemResponse)
def update_mcq_problem(
    problem_id: str,
    problem_data: MCQProblemUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update an MCQ problem and its tags"""
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
    
    # Validate tags if provided
    new_tags = []
    if problem_data.tag_ids is not None:
        tags = session.exec(
            select(Tag).where(Tag.id.in_(problem_data.tag_ids))
        ).all()
        
        if len(tags) != len(problem_data.tag_ids):
            found_tag_ids = [tag.id for tag in tags]
            missing_tag_ids = [tag_id for tag_id in problem_data.tag_ids if tag_id not in found_tag_ids]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tags not found: {', '.join(missing_tag_ids)}"
            )
        new_tags = tags
    
    try:
        # Update MCQ problem fields
        update_data = problem_data.dict(exclude_unset=True, exclude={'tag_ids'})
        for field, value in update_data.items():
            if field == "correct_options":
                setattr(problem, field, json.dumps(value))
            else:
                setattr(problem, field, value)
        
        problem.updated_at = datetime.utcnow()
        
        # Update tags if provided
        if problem_data.tag_ids is not None:
            # Remove existing tag relationships
            existing_mcq_tags = session.exec(
                select(MCQTag).where(MCQTag.mcq_id == problem_id)
            ).all()
            
            for mcq_tag in existing_mcq_tags:
                session.delete(mcq_tag)
            
            # Add new tag relationships
            for tag_id in problem_data.tag_ids:
                mcq_tag = MCQTag(
                    mcq_id=problem_id,
                    tag_id=tag_id,
                    added_by=current_admin.id
                )
                session.add(mcq_tag)
            
            # Update needs_tags status based on whether tags are assigned
            if problem_data.tag_ids:  # If tags are being assigned
                problem.needs_tags = False
            else:  # If all tags are being removed
                problem.needs_tags = True
        
        session.add(problem)
        session.commit()
        session.refresh(problem)
        
        # Get current tags for response
        if problem_data.tag_ids is not None:
            current_tags = new_tags
        else:
            current_tags = session.exec(
                select(Tag).join(MCQTag, Tag.id == MCQTag.tag_id).where(MCQTag.mcq_id == problem_id)
            ).all()
        
        tag_info = [
            TagInfo(id=tag.id, name=tag.name, color=tag.color)
            for tag in current_tags
        ]
        
        return MCQProblemResponse(
            id=problem.id,
            title=problem.title,
            description=problem.description,
            question_type=problem.question_type,
            option_a=problem.option_a,
            option_b=problem.option_b,
            option_c=problem.option_c,
            option_d=problem.option_d,
            correct_options=problem.get_correct_options() if problem.question_type == QuestionType.MCQ else None,
            max_word_count=problem.max_word_count,
            sample_answer=problem.sample_answer,
            scoring_type=problem.scoring_type,
            keywords_for_scoring=problem.get_scoring_keywords() if problem.question_type == QuestionType.LONG_ANSWER else None,
            explanation=problem.explanation,
            image_url=problem.image_url,
            created_by=problem.created_by,
            created_at=problem.created_at,
            updated_at=problem.updated_at,
            tags=tag_info,
            needs_tags=problem.needs_tags
        )
    
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update MCQ problem: {str(e)}"
        )


@router.delete("/{problem_id}")
def delete_mcq_problem(
    problem_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete an MCQ problem, its tag relationships, and associated image file"""
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    try:
        # Store image info for deletion after successful database operations
        image_file_path = None
        if problem.image_url:
            from pathlib import Path
            filename = problem.image_url.split("/")[-1]
            image_file_path = Path("uploads/mcq_images") / filename
        
        # Delete tag relationships first
        mcq_tags = session.exec(
            select(MCQTag).where(MCQTag.mcq_id == problem_id)
        ).all()
        
        for mcq_tag in mcq_tags:
            session.delete(mcq_tag)
        
        # CRITICAL FIX: Flush to execute MCQTag deletions immediately
        # This prevents foreign key constraint violations when deleting MCQProblem
        if mcq_tags:
            session.flush()
        
        # Delete the MCQ problem from database
        session.delete(problem)
        session.commit()
        
        # Only delete image file AFTER successful database operations
        if image_file_path and image_file_path.exists():
            import os
            try:
                os.remove(image_file_path)
                print(f"Deleted image file: {image_file_path}")
            except Exception as img_error:
                # Log the error but don't fail since database deletion succeeded
                print(f"Warning: Failed to delete image file {image_file_path}: {str(img_error)}")
        
        return {
            "message": "MCQ problem, its tag relationships, and associated image deleted successfully"
        }
    
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete MCQ problem: {str(e)}"
        )


@router.get("/template/download")
def download_mcq_template(
    current_admin: User = Depends(get_current_admin)
):
    """Download CSV template for bulk MCQ import (tags will be assigned after import)"""
    # Create clean CSV content without tag_names column
    csv_content = """title,description,option_a,option_b,option_c,option_d,correct_options,explanation
What is the capital of France?,Choose the correct capital city,Paris,London,Berlin,Rome,A,Paris is the capital and largest city of France
Which of the following are prime numbers?,Select all prime numbers,2,4,5,6,"A,C","Prime numbers are natural numbers greater than 1 that have no positive divisors other than 1 and themselves"
What is 2 + 2?,Basic arithmetic question,3,4,5,6,B,Simple addition: 2 + 2 = 4
Which programming language is known for web development?,Choose the most popular option,Java,JavaScript,Python,C++,B,JavaScript is widely used for both front-end and back-end web development
What is the largest planet in our solar system?,Select the correct planet,Earth,Mars,Jupiter,Venus,C,Jupiter is the largest planet in our solar system
What is the process of photosynthesis?,Choose the correct description,Plants converting sunlight to energy,Animals breathing oxygen,Water evaporation,Rock formation,A,Photosynthesis is how plants convert light energy into chemical energy
Who wrote Romeo and Juliet?,Select the correct author,Charles Dickens,William Shakespeare,Jane Austen,Mark Twain,B,William Shakespeare wrote this famous tragedy in the 1590s
What is the chemical symbol for gold?,Choose the correct symbol,Au,Ag,Fe,Cu,A,Au comes from the Latin word 'aurum' meaning gold
In which year did World War II end?,Select the correct year,1944,1945,1946,1947,B,World War II ended in 1945 with the surrender of Japan
What is the square root of 64?,Choose the correct answer,6,7,8,9,C,The square root of 64 is 8 because 8 × 8 = 64"""
    
    # Create CSV file
    output = BytesIO()
    output.write(csv_content.encode('utf-8'))
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"mcq_import_template_with_tags_{timestamp}.csv"
    
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
    """Bulk import MCQ problems from CSV file with tag support"""
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
            "created_problems": [],
            "created_tags": []
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
                
                # Determine if MCQ needs tags (imported questions always need tags)
                needs_tags = True  # All imported questions need tags assigned later
                
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
                    created_by=current_admin.id,
                    needs_tags=needs_tags  # Mark as needing tags assignment
                )
                
                session.add(mcq_problem)
                session.flush()  # Get the ID
                
                # No tag relationships created during import - tags assigned later by admin
                
                results["created_problems"].append({
                    "id": mcq_problem.id,
                    "title": mcq_problem.title,
                    "correct_options": correct_options,
                    "tags": 0,  # No tags assigned during import
                    "needs_tags": needs_tags
                })
                results["successful"] += 1
                
            except Exception as e:
                results["errors"].append(f"Row {line_num}: {str(e)}")
                results["failed"] += 1
                continue
        
        # Commit all successful creations
        session.commit()
        
        # Remove duplicates from created_tags
        results["created_tags"] = list(set(results["created_tags"]))
        
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


@router.post("/{problem_id}/upload-image")
def upload_mcq_image(
    problem_id: str,
    image: UploadFile = File(...),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Upload an image for an MCQ problem"""
    # Check if problem exists
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    # Validate file type
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image"
        )
    
    # Validate file size (5MB limit)
    if image.size and image.size > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size must be less than 5MB"
        )
    
    try:
        import os
        import uuid
        from pathlib import Path
        
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads/mcq_images")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_extension = image.filename.split(".")[-1] if image.filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = upload_dir / unique_filename
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = image.file.read()
            buffer.write(content)
        
        # Update the problem with image URL
        problem.image_url = f"/uploads/mcq_images/{unique_filename}"
        session.commit()
        
        return {
            "message": "Image uploaded successfully",
            "image_url": problem.image_url
        }
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )


@router.delete("/{problem_id}/remove-image")
def remove_mcq_image(
    problem_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Remove the image from an MCQ problem"""
    # Check if problem exists
    problem = session.get(MCQProblem, problem_id)
    if not problem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ problem not found"
        )
    
    try:
        # Remove file from disk if it exists
        if problem.image_url:
            import os
            from pathlib import Path
            
            # Extract filename from URL
            filename = problem.image_url.split("/")[-1]
            file_path = Path("uploads/mcq_images") / filename
            
            if file_path.exists():
                os.remove(file_path)
        
        # Remove image URL from database
        problem.image_url = None
        session.commit()
        
        return {"message": "Image removed successfully"}
        
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove image: {str(e)}"
        ) 