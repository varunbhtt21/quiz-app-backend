from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional, Dict
from datetime import datetime, timezone
import json

from app.core.database import get_session
from app.models.contest import Contest, ContestProblem, ContestStatus
from app.models.submission import Submission
from app.models.mcq_problem import MCQProblem
from app.models.course import Course
from app.models.user import User, UserRole
from app.models.student_course import StudentCourse
from app.schemas.contest import (
    ContestCreate, ContestUpdate, ContestResponse, ContestDetailResponse,
    ContestProblemResponse, SubmissionCreate, SubmissionResponse
)
from app.utils.auth import get_current_admin, get_current_user, get_current_student

router = APIRouter(prefix="/contests", tags=["Contests"])


@router.post("/", response_model=ContestResponse)
def create_contest(
    contest_data: ContestCreate,
    course_id: str = Query(..., description="Course ID for the contest"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new contest"""
    # Verify course exists and admin owns it
    course = session.get(Course, course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found"
        )
    
    if course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create contests for your own courses"
        )
    
    # Validate time range
    if contest_data.start_time >= contest_data.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start time must be before end time"
        )
    
    # Create contest
    contest = Contest(
        course_id=course_id,
        name=contest_data.name,
        description=contest_data.description,
        start_time=contest_data.start_time,
        end_time=contest_data.end_time
    )
    
    session.add(contest)
    session.flush()  # Get contest ID
    
    # Add problems to contest (deep copy from MCQ bank)
    for idx, problem_data in enumerate(contest_data.problems):
        mcq_problem = session.get(MCQProblem, problem_data.problem_id)
        if not mcq_problem:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MCQ problem {problem_data.problem_id} not found"
            )
        
        # Validate that question has tags assigned (cannot use untagged questions in contests)
        if mcq_problem.needs_tags:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question '{mcq_problem.title}' needs tags assigned before it can be used in contests. Please assign tags first."
            )
        
        # Create deep copy of the problem
        contest_problem = ContestProblem(
            contest_id=contest.id,
            cloned_problem_id=mcq_problem.id,
            title=mcq_problem.title,
            description=mcq_problem.description,
            option_a=mcq_problem.option_a,
            option_b=mcq_problem.option_b,
            option_c=mcq_problem.option_c,
            option_d=mcq_problem.option_d,
            correct_options=mcq_problem.correct_options,
            explanation=mcq_problem.explanation,
            image_url=mcq_problem.image_url,
            marks=problem_data.marks,
            order_index=idx
        )
        
        session.add(contest_problem)
    
    session.commit()
    session.refresh(contest)
    
    return ContestResponse(
        id=contest.id,
        course_id=contest.course_id,
        name=contest.name,
        description=contest.description,
        start_time=contest.start_time,
        end_time=contest.end_time,
        status=contest.get_status(),
        created_at=contest.created_at
    )


@router.get("/", response_model=List[ContestResponse])
def list_contests(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List contests (filtered by user role and course access)"""
    statement = select(Contest)
    
    if current_user.role == UserRole.STUDENT:
        # Students only see contests from courses they are enrolled in
        # Get student's enrolled course IDs
        student_courses = session.exec(
            select(StudentCourse.course_id).where(
                StudentCourse.student_id == current_user.id,
                StudentCourse.is_active == True
            )
        ).all()
        
        if not student_courses:
            return []
        
        statement = statement.where(Contest.course_id.in_(student_courses))
    elif course_id:
        # Admin can filter by course_id
        statement = statement.where(Contest.course_id == course_id)
    
    statement = statement.order_by(Contest.start_time.desc())
    contests = session.exec(statement).all()
    
    # Filter contests admin can access (only their courses)
    if current_user.role == UserRole.ADMIN:
        # Get admin's course IDs
        admin_courses = session.exec(
            select(Course.id).where(Course.instructor_id == current_user.id)
        ).all()
        contests = [c for c in contests if c.course_id in admin_courses]
    
    return [
        ContestResponse(
            id=contest.id,
            course_id=contest.course_id,
            name=contest.name,
            description=contest.description,
            start_time=contest.start_time,
            end_time=contest.end_time,
            status=contest.get_status(),
            created_at=contest.created_at
        )
        for contest in contests
    ]


@router.get("/{contest_id}", response_model=ContestDetailResponse)
def get_contest(
    contest_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get contest details with problems"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Check access permissions
    if current_user.role == UserRole.STUDENT:
        # Check if student is enrolled in the contest's course
        enrollment = session.exec(
            select(StudentCourse).where(
                StudentCourse.student_id == current_user.id,
                StudentCourse.course_id == contest.course_id,
                StudentCourse.is_active == True
            )
        ).first()
        
        if not enrollment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this contest"
            )
    elif current_user.role == UserRole.ADMIN:
        # Check if admin owns the course
        course = session.get(Course, contest.course_id)
        if not course or course.instructor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this contest"
            )
    
    # Get contest problems
    statement = select(ContestProblem).where(
        ContestProblem.contest_id == contest_id
    ).order_by(ContestProblem.order_index)
    problems = session.exec(statement).all()
    
    # For students, hide correct answers if contest is active
    contest_status = contest.get_status()
    show_answers = (
        current_user.role == UserRole.ADMIN or 
        contest_status == ContestStatus.ENDED
    )
    
    problem_responses = []
    for problem in problems:
        # Parse correct options for UI to determine single vs multiple choice
        correct_options = json.loads(problem.correct_options)
        
        problem_response = ContestProblemResponse(
            id=problem.id,
            title=problem.title,
            description=problem.description,
            option_a=problem.option_a,
            option_b=problem.option_b,
            option_c=problem.option_c,
            option_d=problem.option_d,
            marks=problem.marks,
            order_index=problem.order_index,
            image_url=problem.image_url,
            correct_options=correct_options
        )
        problem_responses.append(problem_response)
    
    return ContestDetailResponse(
        id=contest.id,
        course_id=contest.course_id,
        name=contest.name,
        description=contest.description,
        start_time=contest.start_time,
        end_time=contest.end_time,
        status=contest_status,
        created_at=contest.created_at,
        problems=problem_responses
    )


@router.put("/{contest_id}", response_model=ContestResponse)
def update_contest(
    contest_id: str,
    contest_data: ContestUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update contest details"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Check if admin owns the course
    course = session.get(Course, contest.course_id)
    if not course or course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update contests for your own courses"
        )
    
    # Get contest status to determine what can be updated
    contest_status = contest.get_status()
    
    # Check if there are any submissions for this contest
    existing_submissions = session.exec(
        select(Submission).where(Submission.contest_id == contest_id)
    ).first()
    
    # Update basic info (always allowed)
    if contest_data.name is not None:
        contest.name = contest_data.name
    if contest_data.description is not None:
        contest.description = contest_data.description
    
    # Time updates have restrictions
    if contest_data.start_time is not None or contest_data.end_time is not None:
        # If contest has started or has submissions, don't allow time changes
        if contest_status != ContestStatus.NOT_STARTED or existing_submissions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify contest times after contest has started or has submissions"
            )
        
        # Validate new time range
        new_start = contest_data.start_time if contest_data.start_time is not None else contest.start_time
        new_end = contest_data.end_time if contest_data.end_time is not None else contest.end_time
        
        if new_start >= new_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time"
            )
        
        if contest_data.start_time is not None:
            contest.start_time = contest_data.start_time
        if contest_data.end_time is not None:
            contest.end_time = contest_data.end_time
    
    # Update timestamp
    contest.updated_at = datetime.utcnow()
    
    session.add(contest)
    session.commit()
    session.refresh(contest)
    
    return ContestResponse(
        id=contest.id,
        course_id=contest.course_id,
        name=contest.name,
        description=contest.description,
        start_time=contest.start_time,
        end_time=contest.end_time,
        status=contest.get_status(),
        created_at=contest.created_at
    )


@router.post("/{contest_id}/submit", response_model=SubmissionResponse)
def submit_contest(
    contest_id: str,
    submission_data: SubmissionCreate,
    current_student: User = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    """Submit answers for a contest"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Check if student is enrolled in the contest's course
    enrollment = session.exec(
        select(StudentCourse).where(
            StudentCourse.student_id == current_student.id,
            StudentCourse.course_id == contest.course_id,
            StudentCourse.is_active == True
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this contest's course"
        )
    
    # Check if contest is active
    contest_status = contest.get_status()
    if contest_status != ContestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest is {contest_status.value}. Submissions not allowed."
        )
    
    # Check if student already submitted
    existing_submission = session.exec(
        select(Submission).where(
            Submission.contest_id == contest_id,
            Submission.student_id == current_student.id
        )
    ).first()
    
    if existing_submission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already submitted for this contest"
        )
    
    # Get contest problems for scoring
    statement = select(ContestProblem).where(ContestProblem.contest_id == contest_id)
    problems = session.exec(statement).all()
    
    # Calculate score
    total_score = 0.0
    max_possible_score = 0.0
    problem_scores = {}
    
    for problem in problems:
        max_possible_score += problem.marks
        
        # Get student's answer for this problem
        student_answer = submission_data.answers.get(problem.id, [])
        correct_options = json.loads(problem.correct_options)  # Parse JSON string to list
        
        # Score using exact set matching
        if set(student_answer) == set(correct_options):
            score = problem.marks
            total_score += score
        else:
            score = 0.0
        
        problem_scores[problem.id] = {
            "score": score,
            "max_score": problem.marks,
            "student_answer": student_answer,
            "correct_answer": correct_options
        }
    
    # Create submission
    submission = Submission(
        contest_id=contest_id,
        student_id=current_student.id,
        answers=json.dumps(submission_data.answers),
        total_score=total_score,
        max_possible_score=max_possible_score,
        time_taken_seconds=submission_data.time_taken_seconds,
        problem_scores=json.dumps(problem_scores),
        is_auto_submitted=False
    )
    
    session.add(submission)
    session.commit()
    session.refresh(submission)
    
    return SubmissionResponse(
        id=submission.id,
        contest_id=submission.contest_id,
        student_id=submission.student_id,
        total_score=submission.total_score,
        max_possible_score=submission.max_possible_score,
        submitted_at=submission.submitted_at,
        time_taken_seconds=submission.time_taken_seconds,
        is_auto_submitted=submission.is_auto_submitted
    )


@router.get("/{contest_id}/submissions")
def get_contest_submissions(
    contest_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get all submissions for a contest (admin only)"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Check if admin owns the course
    course = session.get(Course, contest.course_id)
    if not course or course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this contest"
        )
    
    # Get submissions with student info
    statement = select(Submission, User).join(
        User, Submission.student_id == User.id
    ).where(Submission.contest_id == contest_id)
    
    results = session.exec(statement).all()
    
    submissions = []
    for submission, student in results:
        submissions.append({
            "id": submission.id,
            "student_email": student.email,
            "student_id": student.id,
            "total_score": submission.total_score,
            "max_possible_score": submission.max_possible_score,
            "percentage": (submission.total_score / submission.max_possible_score * 100) if submission.max_possible_score > 0 else 0,
            "submitted_at": submission.submitted_at,
            "time_taken_seconds": submission.time_taken_seconds,
            "is_auto_submitted": submission.is_auto_submitted
        })
    
    return {
        "contest_id": contest_id,
        "contest_name": contest.name,
        "total_submissions": len(submissions),
        "submissions": submissions
    }


@router.get("/{contest_id}/my-submission", response_model=SubmissionResponse)
def get_my_submission(
    contest_id: str,
    current_student: User = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    """Get student's own submission for a contest"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Check if student is enrolled in the contest's course
    enrollment = session.exec(
        select(StudentCourse).where(
            StudentCourse.student_id == current_student.id,
            StudentCourse.course_id == contest.course_id,
            StudentCourse.is_active == True
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this contest's course"
        )
    
    # Get student's submission
    submission = session.exec(
        select(Submission).where(
            Submission.contest_id == contest_id,
            Submission.student_id == current_student.id
        )
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No submission found for this contest"
        )
    
    return SubmissionResponse(
        id=submission.id,
        contest_id=submission.contest_id,
        student_id=submission.student_id,
        total_score=submission.total_score,
        max_possible_score=submission.max_possible_score,
        submitted_at=submission.submitted_at,
        time_taken_seconds=submission.time_taken_seconds,
        is_auto_submitted=submission.is_auto_submitted
    )


@router.get("/{contest_id}/my-submission-details")
def get_my_submission_details(
    contest_id: str,
    current_student: User = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    """Get detailed submission data with questions, answers, and explanations for review"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Check if student is enrolled in the contest's course
    enrollment = session.exec(
        select(StudentCourse).where(
            StudentCourse.student_id == current_student.id,
            StudentCourse.course_id == contest.course_id,
            StudentCourse.is_active == True
        )
    ).first()
    
    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not enrolled in this contest's course"
        )
    
    # Get student's submission
    submission = session.exec(
        select(Submission).where(
            Submission.contest_id == contest_id,
            Submission.student_id == current_student.id
        )
    ).first()
    
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No submission found for this contest"
        )
    
    # Get contest problems with details
    statement = select(ContestProblem).where(
        ContestProblem.contest_id == contest_id
    ).order_by(ContestProblem.order_index)
    problems = session.exec(statement).all()
    
    # Parse submission data
    student_answers = json.loads(submission.answers)
    problem_scores = json.loads(submission.problem_scores)
    
    # Build detailed response
    detailed_problems = []
    for problem in problems:
        correct_options = json.loads(problem.correct_options)
        student_answer = student_answers.get(problem.id, [])
        score_data = problem_scores.get(problem.id, {})
        
        detailed_problems.append({
            "id": problem.id,
            "title": problem.title,
            "description": problem.description,
            "option_a": problem.option_a,
            "option_b": problem.option_b,
            "option_c": problem.option_c,
            "option_d": problem.option_d,
            "explanation": problem.explanation,
            "image_url": problem.image_url,
            "marks": problem.marks,
            "order_index": problem.order_index,
            "correct_options": correct_options,
            "student_answer": student_answer,
            "score": score_data.get("score", 0),
            "max_score": score_data.get("max_score", problem.marks),
            "is_correct": score_data.get("score", 0) == problem.marks
        })
    
    return {
        "submission": {
            "id": submission.id,
            "contest_id": submission.contest_id,
            "student_id": submission.student_id,
            "total_score": submission.total_score,
            "max_possible_score": submission.max_possible_score,
            "submitted_at": submission.submitted_at,
            "time_taken_seconds": submission.time_taken_seconds,
            "is_auto_submitted": submission.is_auto_submitted
        },
        "contest": {
            "id": contest.id,
            "name": contest.name,
            "description": contest.description,
            "start_time": contest.start_time,
            "end_time": contest.end_time
        },
        "problems": detailed_problems
    } 