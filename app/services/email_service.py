#!/usr/bin/env python3
"""
Email Service for QuizMaster Application

This service handles all email communications including:
- Student invitation emails
- Contest notifications  
- Password reset emails
- System notifications
- Email verification

Features:
- SMTP configuration with fallback
- HTML email templates
- Async email sending
- Email validation
- Error handling and logging
- Rate limiting support

Usage:
    from app.services.email_service import email_service
    
    # Send invitation email
    await email_service.send_invitation_email(
        to_email="student@example.com",
        student_name="John Doe",
        login_url="https://app.com/login"
    )
"""

import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import ssl
import logging
from jinja2 import Environment, FileSystemLoader, Template
from pydantic import BaseModel, EmailStr

from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)


class EmailRecipient(BaseModel):
    """Email recipient model"""
    email: EmailStr
    name: Optional[str] = None


class EmailData(BaseModel):
    """Email data model"""
    to: List[EmailRecipient]
    subject: str
    html_content: str
    text_content: Optional[str] = None
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None


class EmailService:
    """
    Comprehensive email service for the QuizMaster application
    """
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.from_email or settings.smtp_username
        self.app_name = settings.app_name
        self.frontend_url = settings.frontend_url
        
        # Check if email service is properly configured
        self.is_configured = bool(
            self.smtp_username and 
            self.smtp_password and 
            self.from_email
        )
        
        if not self.is_configured:
            logger.warning("📧 Email service not fully configured. Email features will be disabled.")
        else:
            logger.info("📧 Email service initialized successfully")
    
    def _create_invitation_template(self, **kwargs) -> str:
        """Create student invitation email template"""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .email-container {{ max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: #f8f9fa; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; color: #666; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>🎓 Welcome to {self.app_name}!</h1>
                </div>
                <div class="content">
                    <h2>Hello {kwargs.get('student_name', 'Student')}!</h2>
                    <p>You've been invited to join <strong>{self.app_name}</strong> - your gateway to exciting quizzes and learning opportunities.</p>
                    
                    <h3>🚀 Getting Started:</h3>
                    <ol>
                        <li>Click the button below to access the platform</li>
                        <li>Complete your profile setup</li>
                        <li>Start taking quizzes and track your progress!</li>
                    </ol>
                    
                    <div style="text-align: center;">
                        <a href="{kwargs.get('login_url', self.frontend_url)}" class="button">
                            🎯 Access QuizMaster
                        </a>
                    </div>
                    
                    <p><strong>Your account details:</strong></p>
                    <ul>
                        <li>📧 Email: {kwargs.get('email', 'N/A')}</li>
                        <li>👤 Role: Student</li>
                        {f"<li>📚 Course: {kwargs.get('course_name')}</li>" if kwargs.get('course_name') else ""}
                    </ul>
                    
                    <p>If you have any questions, feel free to reach out to your instructor.</p>
                </div>
                <div class="footer">
                    <p>© 2025 {self.app_name} | Powered by Jazzee</p>
                    <p><small>This email was sent to {kwargs.get('email', 'you')} because you were invited to join our platform.</small></p>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _create_contest_template(self, **kwargs) -> str:
        """Create contest notification email template"""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                .email-container {{ max-width: 600px; margin: 0 auto; font-family: Arial, sans-serif; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
                .content {{ padding: 30px; background: #f8f9fa; }}
                .button {{ display: inline-block; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; color: #666; border-top: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>⚡ Contest Alert!</h1>
                </div>
                <div class="content">
                    <h2>📢 {kwargs.get('contest_name', 'New Contest')}</h2>
                    <p>A new contest is ready for you in <strong>{kwargs.get('course_name', 'your course')}</strong>!</p>
                    
                    <h3>📋 Contest Details:</h3>
                    <ul>
                        <li>🏆 Contest: <strong>{kwargs.get('contest_name', 'N/A')}</strong></li>
                        <li>📚 Course: {kwargs.get('course_name', 'N/A')}</li>
                        <li>⏰ Start Time: {kwargs.get('start_time', 'N/A')}</li>
                        <li>⏱️ Duration: {kwargs.get('duration', 'N/A')} minutes</li>
                    </ul>
                    
                    <div style="text-align: center;">
                        <a href="{kwargs.get('contest_url', self.frontend_url)}" class="button">
                            🎯 Take Contest
                        </a>
                    </div>
                    
                    <p><strong>💡 Pro Tips:</strong></p>
                    <ul>
                        <li>Ensure stable internet connection</li>
                        <li>Use a desktop/laptop for best experience</li>
                        <li>Read all questions carefully</li>
                    </ul>
                </div>
                <div class="footer">
                    <p>© 2025 {self.app_name} | Good Luck! 🍀</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    async def _send_email_async(self, email_data: EmailData) -> bool:
        """
        Send email asynchronously with proper error handling
        """
        if not self.is_configured:
            logger.error("📧 Email service not configured. Cannot send email.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.app_name} <{self.from_email}>"
            msg['To'] = ", ".join([f"{r.name} <{r.email}>" if r.name else str(r.email) for r in email_data.to])
            msg['Subject'] = email_data.subject
            
            if email_data.cc:
                msg['Cc'] = ", ".join([str(r.email) for r in email_data.cc])
            
            # Add HTML content
            html_part = MIMEText(email_data.html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Add text content if provided
            if email_data.text_content:
                text_part = MIMEText(email_data.text_content, 'plain', 'utf-8')
                msg.attach(text_part)
            
            # Send email using SMTP
            context = ssl.create_default_context()
            
            # Use asyncio to run in thread pool for non-blocking operation
            def _send_smtp():
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_username, self.smtp_password)
                    
                    # Collect all recipients
                    all_recipients = [str(r.email) for r in email_data.to]
                    if email_data.cc:
                        all_recipients.extend([str(r.email) for r in email_data.cc])
                    if email_data.bcc:
                        all_recipients.extend([str(r.email) for r in email_data.bcc])
                    
                    server.send_message(msg, to_addrs=all_recipients)
                    return True
            
            # Run SMTP operation in thread pool
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(None, _send_smtp)
            
            if success:
                logger.info(f"📧 Email sent successfully to {[str(r.email) for r in email_data.to]}")
                return True
            
        except smtplib.SMTPException as e:
            logger.error(f"📧 SMTP error sending email: {e}")
        except Exception as e:
            logger.error(f"📧 Unexpected error sending email: {e}")
        
        return False
    
    # Public email sending methods
    
    async def send_invitation_email(
        self, 
        to_email: str, 
        student_name: str, 
        course_name: Optional[str] = None,
        login_url: Optional[str] = None
    ) -> bool:
        """
        Send invitation email to new student
        """
        
        login_url = login_url or f"{self.frontend_url}/login"
        
        html_content = self._create_invitation_template(
            student_name=student_name,
            email=to_email,
            course_name=course_name,
            login_url=login_url
        )
        
        email_data = EmailData(
            to=[EmailRecipient(email=to_email, name=student_name)],
            subject=f"🎓 Welcome to {self.app_name} - Your Learning Journey Begins!",
            html_content=html_content
        )
        
        return await self._send_email_async(email_data)
    
    async def send_contest_notification(
        self,
        to_email: str,
        student_name: str,
        contest_name: str,
        course_name: str,
        start_time: str,
        duration: int,
        contest_url: Optional[str] = None
    ) -> bool:
        """
        Send contest notification email
        """
        
        contest_url = contest_url or f"{self.frontend_url}/student/contests"
        
        html_content = self._create_contest_template(
            student_name=student_name,
            contest_name=contest_name,
            course_name=course_name,
            start_time=start_time,
            duration=duration,
            contest_url=contest_url
        )
        
        email_data = EmailData(
            to=[EmailRecipient(email=to_email, name=student_name)],
            subject=f"⚡ New Contest Alert: {contest_name} in {course_name}",
            html_content=html_content
        )
        
        return await self._send_email_async(email_data)
    
    async def send_bulk_invitations(
        self,
        student_data: List[Dict[str, str]],
        course_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send bulk invitation emails
        
        Args:
            student_data: List of dicts with 'email', 'name' keys
            course_name: Course name for context
            
        Returns:
            Dict with results summary
        """
        
        results = {
            'total': len(student_data),
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for student in student_data:
            try:
                success = await self.send_invitation_email(
                    to_email=student['email'],
                    student_name=student.get('name', 'Student'),
                    course_name=course_name
                )
                
                if success:
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to send to {student['email']}")
                
                # Small delay to avoid overwhelming SMTP server
                await asyncio.sleep(0.5)
                
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error sending to {student.get('email', 'unknown')}: {str(e)}")
        
        logger.info(f"📧 Bulk invitation results: {results['sent']}/{results['total']} sent successfully")
        return results
    
    def test_connection(self) -> bool:
        """
        Test SMTP connection
        """
        if not self.is_configured:
            logger.error("📧 Email service not configured")
            return False
        
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.smtp_username, self.smtp_password)
                logger.info("📧 SMTP connection test successful")
                return True
        except Exception as e:
            logger.error(f"📧 SMTP connection test failed: {e}")
            return False


# Create singleton instance
email_service = EmailService()

# Test connection on startup if configured
if email_service.is_configured:
    try:
        # Test connection synchronously on startup
        import threading
        
        def test_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            email_service.test_connection()
            loop.close()
        
        test_thread = threading.Thread(target=test_async)
        test_thread.start()
        
    except Exception as e:
        logger.warning(f"📧 Startup connection test failed: {e}") 