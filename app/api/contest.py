from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta
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
from app.utils.time_utils import utc_timestamp_ms, now_utc, to_utc, parse_iso_to_utc

router = APIRouter(prefix="/contests", tags=["Contests"])


@router.get("/time")
def get_server_time():
    """Get current server time in UTC for frontend synchronization"""
    current_utc = now_utc()
    return {
        "epoch_ms": utc_timestamp_ms(),
        "iso": current_utc.isoformat(),
        "timezone": "UTC",
        "timestamp": current_utc.timestamp(),
        "formatted": current_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    }


@router.get("/{contest_id}/time")
def get_contest_time_info(
    contest_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get server time with contest-specific timing information"""
    contest = session.get(Contest, contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    # Basic access control (detailed check done in other endpoints)
    current_utc = now_utc()
    contest_status = contest.get_status()
    
    # Calculate time relationships
    time_to_start = None
    time_to_end = None
    time_remaining = None
    
    if current_utc < contest.start_time:
        time_to_start = int((contest.start_time - current_utc).total_seconds())
    
    if current_utc < contest.end_time:
        time_to_end = int((contest.end_time - current_utc).total_seconds())
        if contest_status == ContestStatus.IN_PROGRESS:
            time_remaining = time_to_end
    
    return {
        "server_time": {
            "epoch_ms": utc_timestamp_ms(),
            "iso": current_utc.isoformat(),
            "timezone": "UTC"
        },
        "contest": {
            "id": contest.id,
            "name": contest.name,
            "status": contest_status.value,
            "start_time": contest.start_time.isoformat(),
            "end_time": contest.end_time.isoformat(),
            "duration_seconds": int((contest.end_time - contest.start_time).total_seconds())
        },
        "timing": {
            "time_to_start_seconds": time_to_start,
            "time_to_end_seconds": time_to_end,
            "time_remaining_seconds": time_remaining,
            "is_accessible": contest_status != ContestStatus.NOT_STARTED,
            "can_submit": contest_status == ContestStatus.IN_PROGRESS
        }
    }


@router.post("/", response_model=ContestResponse)
def create_contest(
    contest_data: ContestCreate,
    course_id: str = Query(..., description="Course ID for the contest"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Create a new contest with timezone-aware validation"""
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
    
    # Ensure datetime inputs are timezone-aware (convert if naive)
    start_time = to_utc(contest_data.start_time) if contest_data.start_time.tzinfo is None else contest_data.start_time
    end_time = to_utc(contest_data.end_time) if contest_data.end_time.tzinfo is None else contest_data.end_time
    
    # Convert to UTC if not already
    if start_time.tzinfo != timezone.utc:
        start_time = start_time.astimezone(timezone.utc)
    if end_time.tzinfo != timezone.utc:
        end_time = end_time.astimezone(timezone.utc)
    
    current_time = now_utc()
    
    # Enhanced time validation
    if start_time >= end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contest start time must be before end time"
        )
    
    # Check minimum contest duration (e.g., 5 minutes)
    min_duration = timedelta(minutes=5)
    if (end_time - start_time) < min_duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest duration must be at least {min_duration.total_seconds() / 60} minutes"
        )
    
    # Check maximum contest duration (e.g., 24 hours)
    max_duration = timedelta(hours=24)
    if (end_time - start_time) > max_duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest duration cannot exceed {max_duration.total_seconds() / 3600} hours"
        )
    
    # Optionally prevent scheduling contests too far in the past
    if start_time < (current_time - timedelta(minutes=5)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create contests that start more than 5 minutes in the past"
        )
    
    # Check for overlapping contests in the same course
    overlapping_contests = session.exec(
        select(Contest).where(
            Contest.course_id == course_id,
            Contest.start_time < end_time,
            Contest.end_time > start_time
        )
    ).all()
    
    if overlapping_contests:
        conflict_names = [c.name for c in overlapping_contests]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest time overlaps with existing contests: {', '.join(conflict_names)}"
        )
    
    # Validate problems list
    if not contest_data.problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contest must have at least one problem"
        )
    
    # Create contest with validated times
    contest = Contest(
        course_id=course_id,
        name=contest_data.name,
        description=contest_data.description,
        start_time=start_time,
        end_time=end_time
    )
    
    session.add(contest)
    session.flush()  # Get contest ID
    
    # Add problems to contest (deep copy from MCQ bank)
    total_marks = 0.0
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
        
        # Validate marks
        if problem_data.marks <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Problem marks must be positive, got {problem_data.marks}"
            )
        
        total_marks += problem_data.marks
        
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
    
    # Validate total marks
    if total_marks <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contest must have at least some marks assigned"
        )
    
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
        created_at=contest.created_at,
        timezone="UTC",
        duration_seconds=int((contest.end_time - contest.start_time).total_seconds())
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
            created_at=contest.created_at,
            timezone="UTC",
            duration_seconds=int((contest.end_time - contest.start_time).total_seconds())
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
    
    # Calculate timing information for frontend
    current_utc = now_utc()
    time_to_start = None
    time_to_end = None
    time_remaining = None
    
    if current_utc < contest.start_time:
        time_to_start = int((contest.start_time - current_utc).total_seconds())
    
    if current_utc < contest.end_time:
        time_to_end = int((contest.end_time - current_utc).total_seconds())
        if contest_status == ContestStatus.IN_PROGRESS:
            time_remaining = time_to_end
    
    time_info = {
        "current_server_time": current_utc.isoformat(),
        "time_to_start_seconds": time_to_start,
        "time_to_end_seconds": time_to_end,
        "time_remaining_seconds": time_remaining,
        "can_submit": contest_status == ContestStatus.IN_PROGRESS,
        "is_accessible": contest_status != ContestStatus.NOT_STARTED
    }
    
    return ContestDetailResponse(
        id=contest.id,
        course_id=contest.course_id,
        name=contest.name,
        description=contest.description,
        start_time=contest.start_time,
        end_time=contest.end_time,
        status=contest_status,
        created_at=contest.created_at,
        timezone="UTC",
        duration_seconds=int((contest.end_time - contest.start_time).total_seconds()),
        problems=problem_responses,
        time_info=time_info
    )


@router.put("/{contest_id}", response_model=ContestResponse)
def update_contest(
    contest_id: str,
    contest_data: ContestUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update contest details with timezone-aware validation"""
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
    current_time = now_utc()
    
    # Check if there are any submissions for this contest
    existing_submissions = session.exec(
        select(Submission).where(Submission.contest_id == contest_id)
    ).first()
    
    # Update basic info (always allowed unless contest has ended and has submissions)
    if contest_data.name is not None:
        if contest_status == ContestStatus.ENDED and existing_submissions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify contest name after contest has ended with submissions"
            )
        contest.name = contest_data.name
        
    if contest_data.description is not None:
        contest.description = contest_data.description
    
    # Time updates have strict restrictions
    if contest_data.start_time is not None or contest_data.end_time is not None:
        # If contest has started or has submissions, don't allow time changes
        if contest_status != ContestStatus.NOT_STARTED or existing_submissions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify contest times after contest has started or has submissions"
            )
        
        # Process timezone-aware time updates
        new_start = contest.start_time
        new_end = contest.end_time
        
        if contest_data.start_time is not None:
            # Ensure timezone-aware and convert to UTC
            start_time = to_utc(contest_data.start_time) if contest_data.start_time.tzinfo is None else contest_data.start_time
            if start_time.tzinfo != timezone.utc:
                start_time = start_time.astimezone(timezone.utc)
            new_start = start_time
            
        if contest_data.end_time is not None:
            # Ensure timezone-aware and convert to UTC
            end_time = to_utc(contest_data.end_time) if contest_data.end_time.tzinfo is None else contest_data.end_time
            if end_time.tzinfo != timezone.utc:
                end_time = end_time.astimezone(timezone.utc)
            new_end = end_time
        
        # Enhanced time validation
        if new_start >= new_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest start time must be before end time"
            )
        
        # Check minimum contest duration (5 minutes)
        min_duration = timedelta(minutes=5)
        if (new_end - new_start) < min_duration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Contest duration must be at least {min_duration.total_seconds() / 60} minutes"
            )
        
        # Check maximum contest duration (24 hours)
        max_duration = timedelta(hours=24)
        if (new_end - new_start) > max_duration:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Contest duration cannot exceed {max_duration.total_seconds() / 3600} hours"
            )
        
        # Prevent scheduling contests too far in the past
        if new_start < (current_time - timedelta(minutes=5)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot schedule contests to start more than 5 minutes in the past"
            )
        
        # Check for overlapping contests in the same course (excluding current contest)
        overlapping_contests = session.exec(
            select(Contest).where(
                Contest.course_id == contest.course_id,
                Contest.id != contest_id,  # Exclude current contest
                Contest.start_time < new_end,
                Contest.end_time > new_start
            )
        ).all()
        
        if overlapping_contests:
            conflict_names = [c.name for c in overlapping_contests]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Contest time overlaps with existing contests: {', '.join(conflict_names)}"
            )
        
        # Apply the validated time updates
        contest.start_time = new_start
        contest.end_time = new_end
    
    # Update timestamp
    contest.updated_at = now_utc()
    
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
        created_at=contest.created_at,
        timezone="UTC",
        duration_seconds=int((contest.end_time - contest.start_time).total_seconds())
    )


@router.post("/{contest_id}/submit", response_model=SubmissionResponse)
def submit_contest(
    contest_id: str,
    submission_data: SubmissionCreate,
    current_student: User = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    """Submit answers for a contest with precise timezone validation"""
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
    
    # Precise timezone-aware contest timing validation
    current_utc = now_utc()
    contest_status = contest.get_status()
    
    # More detailed timing checks
    if contest_status == ContestStatus.NOT_STARTED:
        time_to_start = int((contest.start_time - current_utc).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest hasn't started yet. Starts in {time_to_start} seconds at {contest.start_time.isoformat()}"
        )
    elif contest_status == ContestStatus.ENDED:
        time_since_end = int((current_utc - contest.end_time).total_seconds())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest has ended {time_since_end} seconds ago at {contest.end_time.isoformat()}"
        )
    elif contest_status != ContestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Contest is {contest_status.value}. Submissions not allowed."
        )
    
    # Additional safety check - ensure we're really within contest window
    if current_utc < contest.start_time or current_utc > contest.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission time is outside contest window. Please check your system clock."
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
    
    if not problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contest has no problems to submit answers for"
        )
    
    # Validate submission data
    if not submission_data.answers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Submission must contain answers"
        )
    
    # Validate time_taken_seconds if provided
    if submission_data.time_taken_seconds is not None:
        if submission_data.time_taken_seconds < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time taken cannot be negative"
            )
        
        # Check if time_taken exceeds contest duration
        contest_duration = int((contest.end_time - contest.start_time).total_seconds())
        if submission_data.time_taken_seconds > contest_duration + 60:  # Allow 1 minute buffer
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Time taken ({submission_data.time_taken_seconds}s) exceeds contest duration ({contest_duration}s)"
            )
    
    # Calculate score with validation
    total_score = 0.0
    max_possible_score = 0.0
    problem_scores = {}
    answered_problems = 0
    
    for problem in problems:
        max_possible_score += problem.marks
        
        # Get student's answer for this problem
        student_answer = submission_data.answers.get(problem.id, [])
        if student_answer:  # Count non-empty answers
            answered_problems += 1
        
        try:
            correct_options = json.loads(problem.correct_options)
        except (json.JSONDecodeError, TypeError):
            # Handle malformed JSON in correct_options
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Problem {problem.id} has malformed correct options"
            )
        
        # Validate student answer format
        if not isinstance(student_answer, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Answer for problem {problem.id} must be a list of options"
            )
        
        # Validate answer options are valid (A, B, C, D)
        valid_options = {"A", "B", "C", "D"}
        invalid_options = set(student_answer) - valid_options
        if invalid_options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid answer options for problem {problem.id}: {list(invalid_options)}"
            )
        
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
    
    # Log submission statistics for potential analysis
    submission_stats = {
        "total_problems": len(problems),
        "answered_problems": answered_problems,
        "unanswered_problems": len(problems) - answered_problems,
        "submission_time": current_utc.isoformat()
    }
    
    # Create submission with timezone-aware timestamp
    submission = Submission(
        contest_id=contest_id,
        student_id=current_student.id,
        answers=json.dumps(submission_data.answers),
        total_score=total_score,
        max_possible_score=max_possible_score,
        time_taken_seconds=submission_data.time_taken_seconds,
        problem_scores=json.dumps(problem_scores),
        is_auto_submitted=False
        # submitted_at will be automatically set by the model default
    )
    
    session.add(submission)
    session.commit()
    session.refresh(submission)
    
    # Calculate percentage for response
    percentage = (submission.total_score / submission.max_possible_score * 100) if submission.max_possible_score > 0 else 0
    
    return SubmissionResponse(
        id=submission.id,
        contest_id=submission.contest_id,
        student_id=submission.student_id,
        total_score=submission.total_score,
        max_possible_score=submission.max_possible_score,
        submitted_at=submission.submitted_at,
        time_taken_seconds=submission.time_taken_seconds,
        is_auto_submitted=submission.is_auto_submitted,
        percentage=round(percentage, 2),
        timezone="UTC"
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
    
    # Calculate percentage for response
    percentage = (submission.total_score / submission.max_possible_score * 100) if submission.max_possible_score > 0 else 0
    
    return SubmissionResponse(
        id=submission.id,
        contest_id=submission.contest_id,
        student_id=submission.student_id,
        total_score=submission.total_score,
        max_possible_score=submission.max_possible_score,
        submitted_at=submission.submitted_at,
        time_taken_seconds=submission.time_taken_seconds,
        is_auto_submitted=submission.is_auto_submitted,
        percentage=round(percentage, 2),
        timezone="UTC"
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


@router.post("/{contest_id}/auto-submit", response_model=SubmissionResponse)
def auto_submit_contest(
    contest_id: str,
    submission_data: SubmissionCreate,
    current_student: User = Depends(get_current_student),
    session: Session = Depends(get_session)
):
    """Auto-submit answers when contest time expires with timezone validation"""
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
    
    # Validate timing for auto-submission (more lenient than regular submission)
    current_utc = now_utc()
    contest_status = contest.get_status()
    
    # Auto-submission allowed during contest or just after it ends (within grace period)
    grace_period = timedelta(minutes=2)  # 2-minute grace period for auto-submission
    
    if current_utc < contest.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contest hasn't started yet. Auto-submission not allowed."
        )
    elif current_utc > (contest.end_time + grace_period):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Grace period for auto-submission has expired"
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
    
    if not problems:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Contest has no problems to submit answers for"
        )
    
    # Validate and process answers (more lenient validation for auto-submission)
    answers = submission_data.answers or {}
    time_taken = submission_data.time_taken_seconds
    
    # If time_taken is not provided, calculate based on contest duration
    if time_taken is None:
        if current_utc <= contest.end_time:
            # Contest still active - calculate time from start to now
            time_taken = int((current_utc - contest.start_time).total_seconds())
        else:
            # Contest ended - use full contest duration
            time_taken = int((contest.end_time - contest.start_time).total_seconds())
    
    # Calculate score for auto-submission
    total_score = 0.0
    max_possible_score = 0.0
    problem_scores = {}
    
    for problem in problems:
        max_possible_score += problem.marks
        
        # Get student's answer for this problem (empty if not answered)
        student_answer = answers.get(problem.id, [])
        
        try:
            correct_options = json.loads(problem.correct_options)
        except (json.JSONDecodeError, TypeError):
            correct_options = []
        
        # Validate answer format (skip invalid answers for auto-submission)
        if not isinstance(student_answer, list):
            student_answer = []
        
        # Filter out invalid options
        valid_options = {"A", "B", "C", "D"}
        student_answer = [opt for opt in student_answer if opt in valid_options]
        
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
    
    # Create auto-submission with timezone-aware timestamp
    submission = Submission(
        contest_id=contest_id,
        student_id=current_student.id,
        answers=json.dumps(answers),
        total_score=total_score,
        max_possible_score=max_possible_score,
        time_taken_seconds=time_taken,
        problem_scores=json.dumps(problem_scores),
        is_auto_submitted=True
    )
    
    session.add(submission)
    session.commit()
    session.refresh(submission)
    
    # Calculate percentage for response
    percentage = (submission.total_score / submission.max_possible_score * 100) if submission.max_possible_score > 0 else 0
    
    return SubmissionResponse(
        id=submission.id,
        contest_id=submission.contest_id,
        student_id=submission.student_id,
        total_score=submission.total_score,
        max_possible_score=submission.max_possible_score,
        submitted_at=submission.submitted_at,
        time_taken_seconds=submission.time_taken_seconds,
        is_auto_submitted=submission.is_auto_submitted,
        percentage=round(percentage, 2),
        timezone="UTC"
    ) 