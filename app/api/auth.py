from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.core.security import verify_password, get_password_hash, create_access_token
from app.models.user import User, UserRole
from app.models.student_course import StudentCourse
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse, CreateUserRequest
from app.utils.auth import get_current_user, get_current_admin
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import secrets
import string

router = APIRouter(prefix="/auth", tags=["Authentication"])


class ProfileCompletionRequest(BaseModel):
    """Request model for completing user profile"""
    name: str
    mobile: Optional[str] = None
    email: Optional[str] = None


class ProfileCompletionResponse(BaseModel):
    """Response model for profile completion"""
    success: bool
    message: str
    user: UserResponse


@router.post("/login", response_model=TokenResponse)
def login(
    login_data: LoginRequest,
    session: Session = Depends(get_session)
):
    """Authenticate user and return JWT token"""
    # Find user by email
    statement = select(User).where(User.email == login_data.email)
    user = session.exec(statement).first()
    
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": user.id})
    
    return TokenResponse(
        access_token=access_token,
        user_id=user.id,
        email=user.email,
        role=user.role
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get current user information"""
    # Get course IDs for students
    course_ids = []
    if current_user.role == UserRole.STUDENT:
        student_courses = session.exec(
            select(StudentCourse.course_id).where(
                StudentCourse.student_id == current_user.id,
                StudentCourse.is_active == True
            )
        ).all()
        course_ids = list(student_courses)
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        mobile=current_user.mobile,
        role=current_user.role,
        is_active=current_user.is_active,
        profile_completed=current_user.profile_completed,
        auth_provider=current_user.auth_provider,
        course_ids=course_ids
    )


@router.post("/create-admin", response_model=UserResponse)
def create_admin_user(
    user_data: CreateUserRequest,
    session: Session = Depends(get_session)
):
    """Create admin user (for initial setup)"""
    # Check if admin already exists
    statement = select(User).where(User.role == UserRole.ADMIN)
    existing_admin = session.exec(statement).first()
    
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user already exists"
        )
    
    # Check if email already exists
    statement = select(User).where(User.email == user_data.email)
    existing_user = session.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create admin user
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        role=UserRole.ADMIN
    )
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        course_ids=[]  # Admins don't have course enrollments
    )


def generate_random_password(length: int = 8) -> str:
    """Generate a random password"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length)) 


@router.post("/complete-profile", response_model=ProfileCompletionResponse)
def complete_user_profile(
    profile_data: ProfileCompletionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Complete user profile with name, mobile, and optionally email"""
    try:
        # Update user profile
        current_user.name = profile_data.name.strip()
        
        # Update mobile if provided (for admins)
        if profile_data.mobile:
            current_user.mobile = profile_data.mobile.strip()
        
        # Update email if provided (for students completing OTPLESS profile)
        if profile_data.email:
            # Check if email is already taken by another user
            if profile_data.email != current_user.email:
                statement = select(User).where(
                    User.email == profile_data.email,
                    User.id != current_user.id
                )
                existing_user = session.exec(statement).first()
                
                if existing_user:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email already registered by another user"
                    )
            
            current_user.email = profile_data.email.strip()
        
        current_user.profile_completed = True
        current_user.updated_at = datetime.utcnow()
        
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        
        # Get course IDs for students
        course_ids = []
        if current_user.role == UserRole.STUDENT:
            student_courses = session.exec(
                select(StudentCourse.course_id).where(
                    StudentCourse.student_id == current_user.id,
                    StudentCourse.is_active == True
                )
            ).all()
            course_ids = list(student_courses)
        
        return ProfileCompletionResponse(
            success=True,
            message="Profile completed successfully",
            user=UserResponse(
                id=current_user.id,
                email=current_user.email,
                role=current_user.role,
                is_active=current_user.is_active,
                course_ids=course_ids
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error completing profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete profile"
        ) 