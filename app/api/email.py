#!/usr/bin/env python3
"""
Email API Endpoints for QuizMaster Application

This module provides RESTful API endpoints for email operations including:
- Sending student invitation emails
- Contest notification emails
- Bulk email operations
- Email service health checks

Features:
- Admin-only access for sensitive operations
- Input validation and error handling
- Async email operations
- Comprehensive logging
- Rate limiting considerations
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
import logging
import asyncio

from app.core.database import get_session
from app.models.user import User, UserRole, VerificationMethod
from app.models.course import Course
from app.models.contest import Contest
from app.models.student_course import StudentCourse
from app.utils.auth import get_current_admin, get_current_user
from app.services.email_service import email_service
from app.utils.time_utils import now_utc

router = APIRouter(prefix="/api/email", tags=["Email"])
logger = logging.getLogger(__name__)


# Request/Response Models

class SendInvitationRequest(BaseModel):
    """Request model for sending invitation email"""
    email: EmailStr = Field(..., description="Student's email address")
    name: str = Field(..., min_length=1, max_length=100, description="Student's name")
    course_id: Optional[str] = Field(None, description="Course ID for context")


class BulkInvitationRequest(BaseModel):
    """Request model for sending bulk invitation emails"""
    students: List[Dict[str, str]] = Field(..., description="List of student data with email and name")
    course_id: Optional[str] = Field(None, description="Course ID for context")


class ContestNotificationRequest(BaseModel):
    """Request model for contest notification email"""
    contest_id: str = Field(..., description="Contest ID")
    student_emails: Optional[List[EmailStr]] = Field(None, description="Specific student emails (optional)")


class EmailResponse(BaseModel):
    """Standard email operation response"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


# Utility Functions

def validate_email_service() -> bool:
    """Validate email service is configured and working"""
    if not email_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service is not configured. Please check SMTP settings."
        )
    return True


async def update_user_email_status(
    session: Session, 
    user_email: str, 
    email_sent: bool = True
) -> Optional[User]:
    """Update user's email sent status"""
    try:
        user = session.exec(select(User).where(User.email == user_email)).first()
        if user:
            user.email_sent = email_sent
            user.invitation_sent_at = now_utc()
            session.add(user)
            session.commit()
            session.refresh(user)
            return user
    except Exception as e:
        logger.error(f"Failed to update email status for {user_email}: {e}")
    return None


# API Endpoints

@router.get("/health")
def check_email_service_health(
    current_admin: User = Depends(get_current_admin)
):
    """
    Check email service health and configuration
    """
    
    try:
        # Test SMTP connection
        connection_test = email_service.test_connection()
        
        return {
            "email_service_configured": email_service.is_configured,
            "smtp_connection_working": connection_test,
            "smtp_host": email_service.smtp_host,
            "smtp_port": email_service.smtp_port,
            "from_email": email_service.from_email,
            "status": "healthy" if (email_service.is_configured and connection_test) else "unhealthy"
        }
        
    except Exception as e:
        logger.error(f"Email health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email service health check failed: {str(e)}"
        )


@router.post("/send-invitation", response_model=EmailResponse)
async def send_invitation_email(
    request: SendInvitationRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """
    Send invitation email to a single student
    """
    
    validate_email_service()
    
    try:
        # Get course information if provided
        course_name = None
        if request.course_id:
            course = session.get(Course, request.course_id)
            if course:
                # Verify admin owns the course
                if course.instructor_id != current_admin.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only send invitations for your own courses"
                    )
                course_name = course.name
        
        # Check if user exists and can receive invitation
        existing_user = session.exec(select(User).where(User.email == request.email)).first()
        if existing_user:
            if not existing_user.can_send_invitation_email():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Student has already been invited or verified recently"
                )
        
        # Send email in background
        async def send_email_task():
            try:
                success = await email_service.send_invitation_email(
                    to_email=request.email,
                    student_name=request.name,
                    course_name=course_name
                )
                
                if success:
                    # Update user email status if user exists
                    await update_user_email_status(session, request.email, True)
                    logger.info(f"📧 Invitation sent successfully to {request.email}")
                else:
                    logger.error(f"📧 Failed to send invitation to {request.email}")
                    
            except Exception as e:
                logger.error(f"📧 Background email task failed: {e}")
        
        background_tasks.add_task(send_email_task)
        
        return EmailResponse(
            success=True,
            message=f"Invitation email is being sent to {request.email}",
            details={
                "email": request.email,
                "name": request.name,
                "course": course_name
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send invitation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send invitation: {str(e)}"
        )


@router.post("/send-bulk-invitations", response_model=EmailResponse)
async def send_bulk_invitation_emails(
    request: BulkInvitationRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """
    Send bulk invitation emails to multiple students
    """
    
    validate_email_service()
    
    if not request.students:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student list cannot be empty"
        )
    
    if len(request.students) > 100:  # Rate limiting
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send more than 100 invitations at once"
        )
    
    try:
        # Get course information if provided
        course_name = None
        if request.course_id:
            course = session.get(Course, request.course_id)
            if course:
                # Verify admin owns the course
                if course.instructor_id != current_admin.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only send invitations for your own courses"
                    )
                course_name = course.name
        
        # Validate student data
        valid_students = []
        for student in request.students:
            if 'email' not in student or 'name' not in student:
                continue
                
            # Check if user can receive invitation
            existing_user = session.exec(select(User).where(User.email == student['email'])).first()
            if existing_user and not existing_user.can_send_invitation_email():
                continue  # Skip users who can't receive invitations
                
            valid_students.append(student)
        
        if not valid_students:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid students found for invitation"
            )
        
        # Send bulk emails in background
        async def send_bulk_emails_task():
            try:
                results = await email_service.send_bulk_invitations(
                    student_data=valid_students,
                    course_name=course_name
                )
                
                # Update email status for successful sends
                for student in valid_students:
                    if student['email'] not in [error for error in results.get('errors', []) if student['email'] in error]:
                        await update_user_email_status(session, student['email'], True)
                
                logger.info(f"📧 Bulk invitation results: {results}")
                
            except Exception as e:
                logger.error(f"📧 Bulk email task failed: {e}")
        
        background_tasks.add_task(send_bulk_emails_task)
        
        return EmailResponse(
            success=True,
            message=f"Bulk invitations are being sent to {len(valid_students)} students",
            details={
                "total_students": len(valid_students),
                "course": course_name,
                "admin": current_admin.email
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk invitation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send bulk invitations: {str(e)}"
        )


@router.post("/send-contest-notification", response_model=EmailResponse)
async def send_contest_notification_email(
    request: ContestNotificationRequest,
    background_tasks: BackgroundTasks,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """
    Send contest notification emails to enrolled students
    """
    
    validate_email_service()
    
    try:
        # Get contest information
        contest = session.get(Contest, request.contest_id)
        if not contest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contest not found"
            )
        
        # Get course information and verify ownership
        course = session.get(Course, contest.course_id)
        if not course or course.instructor_id != current_admin.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only send notifications for your own courses"
            )
        
        # Get target students
        if request.student_emails:
            # Send to specific students
            target_students = session.exec(
                select(User).where(
                    User.email.in_(request.student_emails),
                    User.role == UserRole.STUDENT
                )
            ).all()
        else:
            # Send to all enrolled students
            enrolled_students = session.exec(
                select(User).join(StudentCourse).where(
                    StudentCourse.course_id == contest.course_id,
                    User.role == UserRole.STUDENT,
                    User.is_active == True
                )
            ).all()
            target_students = enrolled_students
        
        if not target_students:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No students found for notification"
            )
        
        # Send contest notifications in background
        async def send_contest_notifications_task():
            try:
                sent_count = 0
                failed_count = 0
                
                for student in target_students:
                    try:
                        success = await email_service.send_contest_notification(
                            to_email=student.email,
                            student_name=student.name or "Student",
                            contest_name=contest.name,
                            course_name=course.name,
                            start_time=contest.start_time.strftime("%B %d, %Y at %I:%M %p UTC"),
                            duration=int((contest.end_time - contest.start_time).total_seconds() / 60),
                            contest_url=f"{email_service.frontend_url}/student/contests/{contest.id}"
                        )
                        
                        if success:
                            sent_count += 1
                        else:
                            failed_count += 1
                            
                        # Small delay between emails
                        await asyncio.sleep(0.5)
                        
                    except Exception as e:
                        logger.error(f"Failed to send contest notification to {student.email}: {e}")
                        failed_count += 1
                
                logger.info(f"📧 Contest notifications: {sent_count} sent, {failed_count} failed")
                
            except Exception as e:
                logger.error(f"📧 Contest notification task failed: {e}")
        
        background_tasks.add_task(send_contest_notifications_task)
        
        return EmailResponse(
            success=True,
            message=f"Contest notifications are being sent to {len(target_students)} students",
            details={
                "contest": contest.name,
                "course": course.name,
                "total_students": len(target_students),
                "start_time": contest.start_time.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Contest notification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send contest notifications: {str(e)}"
        ) 