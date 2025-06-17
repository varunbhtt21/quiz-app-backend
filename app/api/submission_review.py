"""
Submission Review API endpoints.
Handles manual review and keyword-based scoring review for long answer questions.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json

from app.core.database import get_session
from app.core.performance import monitor_performance, rate_limit
from app.models.submission import Submission
from app.models.contest import Contest, ContestProblem
from app.models.mcq_problem import MCQProblem, ScoringType
from app.models.course import Course
from app.models.user import User
from app.utils.auth import get_current_admin
from app.utils.scoring import calculate_keyword_score, validate_keyword_configuration
from app.schemas.submission import (
    SubmissionReviewUpdate, SubmissionReviewResponse, 
    BulkReviewUpdate, ReviewAnalyticsResponse
)

router = APIRouter(prefix="/submission-review", tags=["Submission Review"])


@router.get("/pending")
@monitor_performance
@rate_limit(requests_per_minute=100)
def get_pending_reviews(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    contest_id: Optional[str] = Query(None, description="Filter by contest ID"),
    scoring_method: Optional[str] = Query(None, description="Filter by scoring method: manual, keyword_based"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """
    Get all submissions that need manual review.
    Includes keyword-scored submissions that might need review adjustment.
    """
    print(f"DEBUG: get_pending_reviews called with course_id={course_id}, contest_id={contest_id}, scoring_method={scoring_method}")
    
    # Build query for submissions with long answer questions (include student info)
    query = select(
        Submission, Contest, Course, User
    ).join(
        Contest, Submission.contest_id == Contest.id
    ).join(
        Course, Contest.course_id == Course.id
    ).join(
        User, Submission.student_id == User.id
    ).where(
        Course.instructor_id == current_admin.id
    )
    
    # Apply filters
    if course_id:
        query = query.where(Course.id == course_id)
        
    if contest_id:
        query = query.where(Contest.id == contest_id)
    
    results = session.exec(query).all()
    
    pending_reviews = []
    
    for submission, contest, course, student in results:
        try:
            problem_scores = json.loads(submission.problem_scores) if submission.problem_scores else {}
            
            # Check for long answer questions that need review
            review_items = []
            
            for problem_id, score_data in problem_scores.items():
                keyword_analysis = score_data.get('keyword_analysis')
                
                if keyword_analysis:
                    scoring_method_filter = keyword_analysis.get('scoring_method', 'manual')
                    
                    # Determine if needs review first
                    needs_review = False
                    review_priority = "low"
                    
                    if not keyword_analysis.get('auto_scored', False):
                        # Manual review required
                        needs_review = True
                        review_priority = "high"
                    elif keyword_analysis.get('scoring_method') == 'keyword_based':
                        # Keyword scored but might need adjustment
                        needs_review = True
                        review_priority = "medium"
                    elif keyword_analysis.get('error'):
                        # Keyword scoring failed
                        needs_review = True
                        review_priority = "high"
                    
                    # Apply scoring method filter if specified
                    # For 'manual' filter, show all items that need manual review
                    if scoring_method:
                        if scoring_method == 'manual':
                            # Show all items that need manual review regardless of original scoring method
                            if not needs_review:
                                print(f"DEBUG: Filtering out problem {problem_id} - scoring_method filter is 'manual' but item doesn't need review")
                                continue
                            else:
                                print(f"DEBUG: Including problem {problem_id} for manual review - needs_review=True, original_scoring_method={scoring_method_filter}")
                        elif scoring_method == 'keyword_based':
                            # Show only keyword-based items
                            if scoring_method_filter != 'keyword_based':
                                print(f"DEBUG: Filtering out problem {problem_id} - scoring_method filter is 'keyword_based' but item has scoring_method={scoring_method_filter}")
                                continue
                        else:
                            # Show only items with exact scoring method match
                            if scoring_method != scoring_method_filter:
                                print(f"DEBUG: Filtering out problem {problem_id} - scoring_method filter is '{scoring_method}' but item has scoring_method={scoring_method_filter}")
                                continue
                    
                    # Get problem details (using ContestProblem, not MCQProblem)
                    problem = session.get(ContestProblem, problem_id)
                    if not problem:
                        print(f"DEBUG: ContestProblem {problem_id} not found in database")
                        continue
                    
                    if needs_review:
                        print(f"DEBUG: Adding review item for problem {problem_id}, contest {contest.name}, scoring_method: {keyword_analysis.get('scoring_method')}, auto_scored: {keyword_analysis.get('auto_scored')}, error: {keyword_analysis.get('error')}")
                        review_items.append({
                            "problem_id": problem_id,
                            "problem_title": problem.title[:100] + "..." if len(problem.title) > 100 else problem.title,
                            "student_answer": score_data.get('student_answer', '')[:200] + "..." if len(score_data.get('student_answer', '')) > 200 else score_data.get('student_answer', ''),
                            "current_score": score_data.get('score', 0),
                            "max_score": score_data.get('max_score', 0),
                            "scoring_method": scoring_method_filter,
                            "keyword_analysis": keyword_analysis,
                            "review_priority": review_priority
                        })
            
            if review_items:
                print(f"DEBUG: Adding pending review for submission {submission.id}, contest {contest.name}, {len(review_items)} items")
                pending_reviews.append({
                    "submission_id": submission.id,
                    "contest_name": contest.name,
                    "course_name": course.name,
                    "student_id": submission.student_id,
                    "student_name": student.name if student.name else student.email.split('@')[0],
                    "student_email": student.email,
                    "submitted_at": submission.submitted_at,
                    "total_score": submission.total_score,
                    "max_possible_score": submission.max_possible_score,
                    "review_items": review_items
                })
                
        except Exception as e:
            print(f"Error processing submission {submission.id}: {str(e)}")
            continue
    
    return {
        "pending_reviews": pending_reviews,
        "total_pending": len(pending_reviews),
        "filters_applied": {
            "course_id": course_id,
            "contest_id": contest_id,
            "scoring_method": scoring_method
        }
    }


@router.get("/submission/{submission_id}")
@monitor_performance
def get_submission_for_review(
    submission_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get detailed submission data for review interface"""
    submission = session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Verify admin access
    contest = session.get(Contest, submission.contest_id)
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found"
        )
    
    course = session.get(Course, contest.course_id)
    if not course or course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this submission"
        )
    
    # Get student details
    student = session.get(User, submission.student_id)
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )
    
    # Parse problem scores and get detailed data
    try:
        problem_scores = json.loads(submission.problem_scores) if submission.problem_scores else {}
        submission_answers = json.loads(submission.answers) if submission.answers else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid submission data"
        )
    
    # Get contest problems for context (using ContestProblem directly)
    contest_problems = session.exec(
        select(ContestProblem).where(ContestProblem.contest_id == contest.id)
    ).all()
    
    detailed_problems = []
    
    for contest_problem in contest_problems:
        problem_id = contest_problem.id  # Use ContestProblem ID directly
        score_data = problem_scores.get(problem_id, {})
        student_answer = submission_answers.get(problem_id, "")
        
        problem_data = {
            "problem_id": problem_id,
            "title": contest_problem.title,
            "question": contest_problem.description,  # ContestProblem uses 'description' field
            "question_type": contest_problem.question_type.value,
            "scoring_type": contest_problem.scoring_type.value if contest_problem.scoring_type else None,
            "marks": contest_problem.marks,
            "keywords_for_scoring": contest_problem.keywords_for_scoring,
            "student_answer": student_answer,
            "current_score": score_data.get('score', 0),
            "keyword_analysis": score_data.get('keyword_analysis'),
            "needs_review": (
                contest_problem.question_type.value == "long_answer" and 
                (not score_data.get('keyword_analysis', {}).get('auto_scored', False) or
                 score_data.get('keyword_analysis', {}).get('scoring_method') == 'keyword_based' or
                 score_data.get('keyword_analysis', {}).get('error'))
            )
        }
        
        detailed_problems.append(problem_data)
    
    return {
        "submission": {
            "id": submission.id,
            "contest_id": submission.contest_id,
            "contest_name": contest.name,
            "course_name": course.name,
            "student_email": student.email,
            "submitted_at": submission.submitted_at,
            "time_taken_seconds": submission.time_taken_seconds,
            "is_auto_submitted": submission.is_auto_submitted,
            "total_score": submission.total_score,
            "max_possible_score": submission.max_possible_score
        },
        "problems": detailed_problems
    }


@router.put("/submission/{submission_id}/review")
@monitor_performance
@rate_limit(requests_per_minute=50)
def update_submission_review(
    submission_id: str,
    review_data: SubmissionReviewUpdate,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Update scores for reviewed submission"""
    submission = session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Verify admin access
    contest = session.get(Contest, submission.contest_id)
    course = session.get(Course, contest.course_id)
    if not course or course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this submission"
        )
    
    try:
        problem_scores = json.loads(submission.problem_scores) if submission.problem_scores else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid submission data"
        )
    
    # Update problem scores with review data
    total_score_change = 0.0
    updated_problems = []
    
    for problem_review in review_data.problem_reviews:
        problem_id = problem_review.problem_id
        new_score = problem_review.new_score
        feedback = problem_review.feedback
        
        if problem_id in problem_scores:
            old_score = problem_scores[problem_id].get('score', 0)
            max_score = problem_scores[problem_id].get('max_score', 0)
            
            # Validate new score
            if new_score < 0 or new_score > max_score:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid score {new_score} for problem {problem_id}. Must be between 0 and {max_score}"
                )
            
            # Update score and add review metadata
            problem_scores[problem_id]['score'] = new_score
            problem_scores[problem_id]['reviewed_score'] = new_score
            problem_scores[problem_id]['original_score'] = old_score
            problem_scores[problem_id]['reviewed_by'] = current_admin.id
            problem_scores[problem_id]['reviewed_at'] = datetime.now(timezone.utc).isoformat()
            problem_scores[problem_id]['feedback'] = feedback
            
            # Update keyword analysis to mark as reviewed
            if 'keyword_analysis' in problem_scores[problem_id]:
                problem_scores[problem_id]['keyword_analysis']['manually_reviewed'] = True
                problem_scores[problem_id]['keyword_analysis']['review_method'] = 'manual_override'
            
            total_score_change += (new_score - old_score)
            updated_problems.append({
                "problem_id": problem_id,
                "old_score": old_score,
                "new_score": new_score,
                "score_change": new_score - old_score
            })
    
    # Update total score
    new_total_score = submission.total_score + total_score_change
    submission.total_score = new_total_score
    submission.problem_scores = json.dumps(problem_scores)
    
    session.add(submission)
    session.commit()
    
    return {
        "submission_id": submission_id,
        "old_total_score": submission.total_score - total_score_change,
        "new_total_score": new_total_score,
        "score_change": total_score_change,
        "updated_problems": updated_problems,
        "reviewed_by": current_admin.email,
        "reviewed_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/keyword-rescore/{submission_id}")
@monitor_performance
@rate_limit(requests_per_minute=30)
def rescore_with_keywords(
    submission_id: str,
    problem_ids: Optional[List[str]] = Query(None, description="Specific problems to rescore"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Re-run keyword scoring for specific problems in a submission"""
    submission = session.get(Submission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Submission not found"
        )
    
    # Verify admin access
    contest = session.get(Contest, submission.contest_id)
    course = session.get(Course, contest.course_id)
    if not course or course.instructor_id != current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this submission"
        )
    
    try:
        problem_scores = json.loads(submission.problem_scores) if submission.problem_scores else {}
        submission_answers = json.loads(submission.answers) if submission.answers else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid submission data"
        )
    
    rescored_problems = []
    total_score_change = 0.0
    
    # Get problems to rescore
    problems_to_rescore = problem_ids if problem_ids else list(problem_scores.keys())
    
    for problem_id in problems_to_rescore:
        if problem_id not in problem_scores:
            continue
            
        # Get problem details (using ContestProblem, not MCQProblem)
        problem = session.get(ContestProblem, problem_id)
        if not problem or problem.question_type.value != "long_answer":
            continue
            
        if problem.scoring_type != ScoringType.KEYWORD_BASED or not problem.keywords_for_scoring:
            continue
        
        student_answer = submission_answers.get(problem_id, "")
        if not isinstance(student_answer, str):
            continue
        
        try:
            # Re-run keyword scoring
            scoring_result = calculate_keyword_score(
                student_answer, 
                problem.keywords_for_scoring, 
                problem.marks
            )
            
            old_score = problem_scores[problem_id].get('score', 0)
            new_score = scoring_result.score
            
            # Update problem score
            problem_scores[problem_id]['score'] = new_score
            problem_scores[problem_id]['rescored_score'] = new_score
            problem_scores[problem_id]['original_score'] = old_score
            problem_scores[problem_id]['rescored_by'] = current_admin.id
            problem_scores[problem_id]['rescored_at'] = datetime.now(timezone.utc).isoformat()
            
            # Update keyword analysis
            problem_scores[problem_id]['keyword_analysis'] = {
                "found_keywords": scoring_result.found_keywords,
                "missing_keywords": scoring_result.missing_keywords,
                "match_details": scoring_result.match_details,
                "auto_scored": True,
                "scoring_method": "keyword_based",
                "rescored": True
            }
            
            total_score_change += (new_score - old_score)
            
            rescored_problems.append({
                "problem_id": problem_id,
                "problem_title": problem.title,
                "old_score": old_score,
                "new_score": new_score,
                "score_change": new_score - old_score,
                "found_keywords": scoring_result.found_keywords,
                "missing_keywords": scoring_result.missing_keywords
            })
            
        except Exception as e:
            print(f"Failed to rescore problem {problem_id}: {str(e)}")
            continue
    
    if rescored_problems:
        # Update total score
        submission.total_score += total_score_change
        submission.problem_scores = json.dumps(problem_scores)
        
        session.add(submission)
        session.commit()
    
    return {
        "submission_id": submission_id,
        "rescored_problems": rescored_problems,
        "total_score_change": total_score_change,
        "new_total_score": submission.total_score,
        "rescored_by": current_admin.email,
        "rescored_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/analytics")
@monitor_performance
def get_review_analytics(
    course_id: Optional[str] = Query(None, description="Filter by course ID"),
    contest_id: Optional[str] = Query(None, description="Filter by contest ID"),
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get analytics on review status and scoring methods"""
    print(f"DEBUG: get_review_analytics called with course_id={course_id}, contest_id={contest_id}")
    
    # Build base query
    query = select(
        Submission, Contest, Course
    ).join(
        Contest, Submission.contest_id == Contest.id
    ).join(
        Course, Contest.course_id == Course.id
    ).where(
        Course.instructor_id == current_admin.id
    )
    
    # Apply filters
    if course_id:
        query = query.where(Course.id == course_id)
    if contest_id:
        query = query.where(Contest.id == contest_id)
    
    results = session.exec(query).all()
    
    analytics = {
        "total_submissions": len(results),
        "manual_review_pending": 0,
        "keyword_scored": 0,
        "manually_reviewed": 0,
        "scoring_failures": 0,
        "total_long_answer_questions": 0,
        "average_keyword_accuracy": 0.0,
        "scoring_method_breakdown": {
            "manual": 0,
            "keyword_based": 0,
            "manual_fallback": 0
        }
    }
    
    keyword_scores = []
    
    for submission, contest, course in results:
        try:
            problem_scores = json.loads(submission.problem_scores) if submission.problem_scores else {}
            
            for problem_id, score_data in problem_scores.items():
                keyword_analysis = score_data.get('keyword_analysis')
                
                if keyword_analysis:
                    analytics["total_long_answer_questions"] += 1
                    
                    scoring_method = keyword_analysis.get('scoring_method', 'manual')
                    if scoring_method in analytics["scoring_method_breakdown"]:
                        analytics["scoring_method_breakdown"][scoring_method] += 1
                    
                    if keyword_analysis.get('auto_scored'):
                        analytics["keyword_scored"] += 1
                        
                        # Track keyword accuracy if we have scoring details
                        if 'match_details' in keyword_analysis:
                            score = score_data.get('score', 0)
                            max_score = score_data.get('max_score', 1)
                            keyword_scores.append(score / max_score if max_score > 0 else 0)
                    
                    if keyword_analysis.get('manually_reviewed'):
                        analytics["manually_reviewed"] += 1
                    else:
                        # Determine if this item needs review (same logic as pending reviews)
                        needs_review = False
                        
                        if not keyword_analysis.get('auto_scored', False):
                            # Manual review required
                            needs_review = True
                        elif keyword_analysis.get('scoring_method') == 'keyword_based':
                            # Keyword scored but might need adjustment
                            needs_review = True
                        elif keyword_analysis.get('error'):
                            # Keyword scoring failed
                            needs_review = True
                        
                        if needs_review:
                            analytics["manual_review_pending"] += 1
                    
                    if keyword_analysis.get('error'):
                        analytics["scoring_failures"] += 1
                        
        except Exception as e:
            print(f"Error analyzing submission {submission.id}: {str(e)}")
            continue
    
    # Calculate average keyword accuracy
    if keyword_scores:
        analytics["average_keyword_accuracy"] = sum(keyword_scores) / len(keyword_scores) * 100
    
    return analytics 