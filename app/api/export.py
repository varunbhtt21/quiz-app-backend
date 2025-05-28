from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Dict, Any
import pandas as pd
import json
from io import BytesIO
from datetime import datetime

from app.core.database import get_session
from app.models.contest import Contest, ContestProblem
from app.models.submission import Submission
from app.models.course import Course
from app.models.user import User, UserRole
from app.models.student_course import StudentCourse
from app.utils.auth import get_current_admin

router = APIRouter(prefix="/export", tags=["Export"])


@router.get("/{contest_id}/excel")
def export_contest_results(
    contest_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Export contest results to Excel file"""
    # Verify contest exists and admin has access
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
    
    # Get contest problems
    problems_stmt = select(ContestProblem).where(
        ContestProblem.contest_id == contest_id
    ).order_by(ContestProblem.order_index)
    problems = session.exec(problems_stmt).all()
    
    # Get all students enrolled in the course
    students_stmt = select(User).join(
        StudentCourse, User.id == StudentCourse.student_id
    ).where(
        StudentCourse.course_id == contest.course_id,
        StudentCourse.is_active == True,
        User.role == UserRole.STUDENT
    ).order_by(User.email)
    students = session.exec(students_stmt).all()
    
    # Get submissions with student info
    submissions_stmt = select(Submission, User).join(
        User, Submission.student_id == User.id
    ).where(Submission.contest_id == contest_id)
    submission_results = session.exec(submissions_stmt).all()
    
    # Create submission lookup
    submissions_dict = {}
    for submission, student in submission_results:
        submissions_dict[student.id] = submission
    
    # Prepare data for Excel
    excel_data = []
    
    for student in students:
        row = {
            "Student Email": student.email,
            "Student ID": student.id,
            "Submitted": "Yes" if student.id in submissions_dict else "No"
        }
        
        if student.id in submissions_dict:
            submission = submissions_dict[student.id]
            row.update({
                "Total Score": submission.total_score,
                "Max Possible Score": submission.max_possible_score,
                "Percentage": round((submission.total_score / submission.max_possible_score * 100), 2) if submission.max_possible_score > 0 else 0,
                "Submitted At": submission.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Time Taken (seconds)": submission.time_taken_seconds,
                "Auto Submitted": "Yes" if submission.is_auto_submitted else "No"
            })
            
            # Add problem-wise scores
            try:
                problem_scores = json.loads(submission.problem_scores)
                for problem in problems:
                    problem_data = problem_scores.get(problem.id, {})
                    row[f"Q{problem.order_index + 1} Score"] = problem_data.get("score", 0)
                    row[f"Q{problem.order_index + 1} Max"] = problem_data.get("max_score", problem.marks)
                    
                    # Add student answers and correct answers
                    student_answer = problem_data.get("student_answer", [])
                    correct_answer = problem_data.get("correct_answer", [])
                    row[f"Q{problem.order_index + 1} Student Answer"] = ", ".join(student_answer) if student_answer else "No Answer"
                    row[f"Q{problem.order_index + 1} Correct Answer"] = ", ".join(correct_answer)
            except (json.JSONDecodeError, KeyError):
                # Handle cases where problem_scores is malformed
                for problem in problems:
                    row[f"Q{problem.order_index + 1} Score"] = 0
                    row[f"Q{problem.order_index + 1} Max"] = problem.marks
                    row[f"Q{problem.order_index + 1} Student Answer"] = "Error"
                    row[f"Q{problem.order_index + 1} Correct Answer"] = ", ".join(problem.get_correct_options())
        else:
            # Student didn't submit
            row.update({
                "Total Score": 0,
                "Max Possible Score": sum(p.marks for p in problems),
                "Percentage": 0,
                "Submitted At": "Not Submitted",
                "Time Taken (seconds)": None,
                "Auto Submitted": "No"
            })
            
            # Add empty problem scores
            for problem in problems:
                row[f"Q{problem.order_index + 1} Score"] = 0
                row[f"Q{problem.order_index + 1} Max"] = problem.marks
                row[f"Q{problem.order_index + 1} Student Answer"] = "Not Submitted"
                row[f"Q{problem.order_index + 1} Correct Answer"] = ", ".join(problem.get_correct_options())
        
        excel_data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(excel_data)
    
    # Create Excel file with multiple sheets
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main results sheet
        df.to_excel(writer, sheet_name='Results', index=False)
        
        # Summary sheet
        summary_data = {
            "Contest Information": [
                f"Contest Name: {contest.name}",
                f"Course: {course.name}",
                f"Start Time: {contest.start_time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"End Time: {contest.end_time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total Students: {len(students)}",
                f"Submissions: {len(submission_results)}",
                f"Submission Rate: {round(len(submission_results) / len(students) * 100, 2)}%" if students else "0%"
            ]
        }
        
        # Statistics
        if submission_results:
            scores = [s.total_score for s, _ in submission_results]
            max_scores = [s.max_possible_score for s, _ in submission_results]
            percentages = [(s.total_score / s.max_possible_score * 100) if s.max_possible_score > 0 else 0 for s, _ in submission_results]
            
            summary_data["Statistics"] = [
                f"Average Score: {round(sum(scores) / len(scores), 2)}",
                f"Highest Score: {max(scores)}",
                f"Lowest Score: {min(scores)}",
                f"Average Percentage: {round(sum(percentages) / len(percentages), 2)}%",
                f"Highest Percentage: {round(max(percentages), 2)}%",
                f"Lowest Percentage: {round(min(percentages), 2)}%"
            ]
        
        summary_df = pd.DataFrame(dict([(k, pd.Series(v)) for k, v in summary_data.items()]))
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Problem details sheet
        problem_details = []
        for problem in problems:
            problem_details.append({
                "Question Number": f"Q{problem.order_index + 1}",
                "Title": problem.title,
                "Description": problem.description[:100] + "..." if len(problem.description) > 100 else problem.description,
                "Option A": problem.option_a,
                "Option B": problem.option_b,
                "Option C": problem.option_c,
                "Option D": problem.option_d,
                "Correct Options": ", ".join(problem.get_correct_options()),
                "Marks": problem.marks
            })
        
        problems_df = pd.DataFrame(problem_details)
        problems_df.to_excel(writer, sheet_name='Questions', index=False)
    
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"contest_results_{contest.name.replace(' ', '_')}_{timestamp}.xlsx"
    
    # Return as streaming response
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/{contest_id}/csv")
def export_contest_results_csv(
    contest_id: str,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Export contest results to CSV file (simplified version)"""
    # Verify contest exists and admin has access
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
    
    # Get all students enrolled in the course
    students_stmt = select(User).join(
        StudentCourse, User.id == StudentCourse.student_id
    ).where(
        StudentCourse.course_id == contest.course_id,
        StudentCourse.is_active == True,
        User.role == UserRole.STUDENT
    ).order_by(User.email)
    students = session.exec(students_stmt).all()
    
    # Get submissions with student info
    submissions_stmt = select(Submission, User).join(
        User, Submission.student_id == User.id
    ).where(Submission.contest_id == contest_id)
    submission_results = session.exec(submissions_stmt).all()
    
    # Create submission lookup
    submissions_dict = {}
    for submission, student in submission_results:
        submissions_dict[student.id] = submission
    
    # Prepare simplified data for CSV
    csv_data = []
    
    for student in students:
        row = {
            "Student Email": student.email,
            "Submitted": "Yes" if student.id in submissions_dict else "No"
        }
        
        if student.id in submissions_dict:
            submission = submissions_dict[student.id]
            row.update({
                "Total Score": submission.total_score,
                "Max Possible Score": submission.max_possible_score,
                "Percentage": round((submission.total_score / submission.max_possible_score * 100), 2) if submission.max_possible_score > 0 else 0,
                "Submitted At": submission.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Time Taken (minutes)": round(submission.time_taken_seconds / 60, 2) if submission.time_taken_seconds else None
            })
        else:
            # Student didn't submit
            max_possible = session.exec(
                select(ContestProblem).where(ContestProblem.contest_id == contest_id)
            ).all()
            total_marks = sum(p.marks for p in max_possible)
            
            row.update({
                "Total Score": 0,
                "Max Possible Score": total_marks,
                "Percentage": 0,
                "Submitted At": "Not Submitted",
                "Time Taken (minutes)": None
            })
        
        csv_data.append(row)
    
    # Create DataFrame and CSV
    df = pd.DataFrame(csv_data)
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"contest_results_{contest.name.replace(' ', '_')}_{timestamp}.csv"
    
    # Return as streaming response
    return StreamingResponse(
        BytesIO(output.read()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    ) 