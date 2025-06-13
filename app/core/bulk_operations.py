"""
🚀 Bulk Operations Module
Optimized for handling multiple database operations efficiently during contests

Reduces individual API calls and database queries for better performance
Designed for 100+ concurrent students scenarios
"""

from typing import List, Dict, Any, Optional, Tuple
from sqlmodel import Session, select
from sqlalchemy import and_, or_, text
from datetime import datetime, timezone
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.models.contest import Contest, ContestProblem
from app.models.submission import Submission
from app.models.user import User
from app.models.student_course import StudentCourse
from app.core.cache import cache_contest_data, cache_user_data

class BulkOperations:
    """High-performance bulk operations for contest scenarios"""
    
    def __init__(self, session: Session):
        self.session = session
        self._executor = ThreadPoolExecutor(max_workers=4)
    
    # 🚀 BULK USER VALIDATION
    @cache_user_data(ttl=300)  # Cache for 5 minutes
    def bulk_validate_students(self, student_ids: List[str], course_id: str) -> Dict[str, bool]:
        """
        Validate multiple students' enrollment in a single query
        Returns {student_id: is_enrolled} mapping
        """
        # Single query to get all enrollments
        enrollments = self.session.exec(
            select(StudentCourse.student_id).where(
                and_(
                    StudentCourse.student_id.in_(student_ids),
                    StudentCourse.course_id == course_id,
                    StudentCourse.is_active == True
                )
            )
        ).all()
        
        enrolled_students = set(enrollments)
        return {student_id: student_id in enrolled_students for student_id in student_ids}
    
    # 🔥 BULK SUBMISSION CHECKING  
    def bulk_check_existing_submissions(self, contest_id: str, student_ids: List[str]) -> Dict[str, bool]:
        """
        Check if multiple students have already submitted for a contest
        Returns {student_id: has_submitted} mapping
        """
        existing_submissions = self.session.exec(
            select(Submission.student_id).where(
                and_(
                    Submission.contest_id == contest_id,
                    Submission.student_id.in_(student_ids)
                )
            )
        ).all()
        
        submitted_students = set(existing_submissions)
        return {student_id: student_id in submitted_students for student_id in student_ids}
    
    # 🎯 BULK CONTEST DATA LOADING
    @cache_contest_data(ttl=180)  # Cache for 3 minutes
    def bulk_load_contest_problems(self, contest_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load problems for multiple contests in a single query
        Returns {contest_id: [problems]} mapping
        """
        problems = self.session.exec(
            select(ContestProblem).where(
                ContestProblem.contest_id.in_(contest_ids)
            ).order_by(ContestProblem.contest_id, ContestProblem.order_index)
        ).all()
        
        contest_problems = {}
        for problem in problems:
            if problem.contest_id not in contest_problems:
                contest_problems[problem.contest_id] = []
            
            contest_problems[problem.contest_id].append({
                "id": problem.id,
                "title": problem.title,
                "description": problem.description,
                "question_type": problem.question_type,
                "marks": problem.marks,
                "order_index": problem.order_index,
                "correct_options": problem.correct_options,
                "option_a": problem.option_a,
                "option_b": problem.option_b,
                "option_c": problem.option_c,
                "option_d": problem.option_d,
            })
        
        return contest_problems
    
    # ⚡ BULK SUBMISSION PROCESSING
    def bulk_create_submissions(self, submissions_data: List[Dict[str, Any]]) -> List[Submission]:
        """
        Create multiple submissions in a single transaction
        Optimized for auto-submissions and batch processing
        """
        submissions = []
        
        for data in submissions_data:
            submission = Submission(
                contest_id=data["contest_id"],
                student_id=data["student_id"],
                answers=json.dumps(data["answers"]),
                total_score=data["total_score"],
                max_possible_score=data["max_possible_score"],
                time_taken_seconds=data["time_taken_seconds"],
                problem_scores=json.dumps(data["problem_scores"]),
                is_auto_submitted=data.get("is_auto_submitted", False)
            )
            submissions.append(submission)
        
        # Bulk insert
        self.session.add_all(submissions)
        self.session.commit()
        
        # Refresh all to get IDs
        for submission in submissions:
            self.session.refresh(submission)
        
        return submissions
    
    # 📊 BULK STATISTICS QUERIES
    def bulk_get_contest_stats(self, contest_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for multiple contests efficiently
        Returns submission counts, averages, etc.
        """
        # Single query for all contest statistics
        results = self.session.exec(
            text("""
                SELECT 
                    contest_id,
                    COUNT(*) as total_submissions,
                    AVG(total_score) as avg_score,
                    MAX(total_score) as max_score,
                    MIN(total_score) as min_score,
                    AVG(time_taken_seconds) as avg_time_taken,
                    COUNT(CASE WHEN is_auto_submitted = true THEN 1 END) as auto_submissions
                FROM submission 
                WHERE contest_id = ANY(:contest_ids)
                GROUP BY contest_id
            """).params(contest_ids=contest_ids)
        ).all()
        
        stats = {}
        for row in results:
            stats[row.contest_id] = {
                "total_submissions": row.total_submissions,
                "avg_score": float(row.avg_score) if row.avg_score else 0.0,
                "max_score": float(row.max_score) if row.max_score else 0.0,
                "min_score": float(row.min_score) if row.min_score else 0.0,
                "avg_time_taken": int(row.avg_time_taken) if row.avg_time_taken else 0,
                "auto_submissions": row.auto_submissions,
            }
        
        return stats
    
    # 🔄 BULK USER ACTIVITY QUERIES
    def bulk_get_student_submissions(self, student_ids: List[str], course_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all submissions for multiple students in a course
        Optimized for dashboard loading
        """
        submissions = self.session.exec(
            select(Submission, Contest).join(Contest).where(
                and_(
                    Submission.student_id.in_(student_ids),
                    Contest.course_id == course_id
                )
            ).order_by(Submission.submitted_at.desc())
        ).all()
        
        student_submissions = {student_id: [] for student_id in student_ids}
        
        for submission, contest in submissions:
            percentage = (submission.total_score / submission.max_possible_score * 100) if submission.max_possible_score > 0 else 0
            
            student_submissions[submission.student_id].append({
                "id": submission.id,
                "contest_id": submission.contest_id,
                "contest_name": contest.name,
                "total_score": submission.total_score,
                "max_possible_score": submission.max_possible_score,
                "percentage": round(percentage, 2),
                "submitted_at": submission.submitted_at,
                "time_taken_seconds": submission.time_taken_seconds,
                "is_auto_submitted": submission.is_auto_submitted
            })
        
        return student_submissions

# 🎯 ASYNC BULK OPERATIONS (for heavy workloads)
class AsyncBulkOperations:
    """Async bulk operations for maximum performance"""
    
    @staticmethod
    async def parallel_score_calculation(submissions_data: List[Dict[str, Any]], problem_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Calculate scores for multiple submissions in parallel
        Useful for batch processing and auto-submissions
        """
        async def calculate_single_score(submission: Dict[str, Any]) -> Dict[str, Any]:
            # Simulate score calculation (replace with actual logic)
            await asyncio.sleep(0.01)  # Simulate processing time
            
            total_score = 0.0
            max_score = 0.0
            problem_scores = {}
            
            for problem_id, answer in submission["answers"].items():
                if problem_id in problem_data:
                    problem = problem_data[problem_id]
                    max_score += problem["marks"]
                    
                    # Simple scoring logic (extend as needed)
                    if problem["question_type"] == "mcq":
                        correct_options = json.loads(problem["correct_options"])
                        if set(answer) == set(correct_options):
                            score = problem["marks"]
                        else:
                            score = 0.0
                    else:
                        score = 0.0  # Long answer needs manual scoring
                    
                    total_score += score
                    problem_scores[problem_id] = {
                        "score": score,
                        "max_score": problem["marks"]
                    }
            
            return {
                **submission,
                "total_score": total_score,
                "max_possible_score": max_score,
                "problem_scores": problem_scores
            }
        
        # Process all submissions in parallel
        tasks = [calculate_single_score(submission) for submission in submissions_data]
        return await asyncio.gather(*tasks)

# 🚀 PERFORMANCE UTILITIES
def batch_process_large_dataset(data: List[Any], batch_size: int = 100, processor_func: callable = None):
    """
    Process large datasets in batches to avoid memory issues
    Useful for processing thousands of submissions or students
    """
    results = []
    
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        if processor_func:
            batch_results = processor_func(batch)
            results.extend(batch_results)
        else:
            results.extend(batch)
    
    return results

def optimize_query_execution(session: Session, enable_parallel_queries: bool = True):
    """
    Optimize database session for bulk operations
    """
    if enable_parallel_queries:
        # Enable parallel query execution
        session.execute(text("SET max_parallel_workers_per_gather = 4"))
        session.execute(text("SET parallel_tuple_cost = 0.1"))
        session.execute(text("SET parallel_setup_cost = 1000"))
    
    # Optimize for bulk operations
    session.execute(text("SET work_mem = '256MB'"))
    session.execute(text("SET maintenance_work_mem = '512MB'"))
    
    session.commit() 