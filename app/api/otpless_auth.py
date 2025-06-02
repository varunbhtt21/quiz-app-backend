from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from datetime import datetime

from app.core.database import get_session
from app.core.security import create_access_token
from app.models.user import User, UserRole, RegistrationStatus
from app.schemas.otpless import (
    OTPLESSTokenRequest, 
    OTPLESSVerifyResponse, 
    ProfileCompletionRequest, 
    ProfileCompletionResponse,
    OTPLESSUserResponse,
    UserInfo
)
from app.services.otpless_service import otpless_service
from app.utils.auth import get_current_user

router = APIRouter(prefix="/auth/otpless", tags=["OTPLESS Authentication"])


@router.post("/verify", response_model=OTPLESSVerifyResponse)
async def verify_otpless_token(
    token_request: OTPLESSTokenRequest,
    session: Session = Depends(get_session)
):
    """
    Verify OTPLESS token and create/login user
    """
    try:
        print(f"🔍 OTPLESS Token Verification Request:")
        print(f"  - Token: {token_request.token[:20]}...")
        print(f"  - Token Length: {len(token_request.token)}")
        
        # Verify token with OTPLESS service
        user_data = await otpless_service.verify_token(token_request.token)
        print(f"🔍 OTPLESS Service Response: {user_data}")
        
        if not user_data:
            print("❌ OTPLESS token verification failed - no user data returned")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OTPLESS token"
            )
        
        print(f"✅ OTPLESS user data received: {user_data}")
        
        # Check if user already exists by OTPLESS user ID
        existing_user = None
        if user_data.get("otpless_user_id"):
            print(f"🔍 Looking for user by OTPLESS ID: {user_data.get('otpless_user_id')}")
            statement = select(User).where(User.otpless_user_id == user_data["otpless_user_id"])
            existing_user = session.exec(statement).first()
            if existing_user:
                print(f"✅ Found existing user by OTPLESS ID: {existing_user.id}")
        
        # If not found by OTPLESS ID, check by mobile or email
        if not existing_user:
            if user_data.get("mobile"):
                print(f"🔍 Looking for user by mobile: {user_data.get('mobile')}")
                statement = select(User).where(User.mobile == user_data["mobile"])
                existing_user = session.exec(statement).first()
                if existing_user:
                    print(f"✅ Found existing user by mobile: {existing_user.id}")
            elif user_data.get("email"):
                print(f"🔍 Looking for user by email: {user_data.get('email')}")
                statement = select(User).where(User.email == user_data["email"])
                existing_user = session.exec(statement).first()
                if existing_user:
                    print(f"✅ Found existing user by email: {existing_user.id}")
        
        # Handle pre-registered students (PENDING status)
        if existing_user and existing_user.registration_status == RegistrationStatus.PENDING:
            print(f"🔄 Activating pre-registered student: {existing_user.email}")
            # Update pre-registered user with OTPLESS data
            existing_user.otpless_user_id = user_data.get("otpless_user_id")
            existing_user.mobile = user_data.get("mobile")
            if user_data.get("name"):
                existing_user.name = user_data.get("name")
            existing_user.profile_picture = user_data.get("profile_picture")
            existing_user.auth_provider = user_data.get("auth_provider", "otpless")
            existing_user.registration_status = RegistrationStatus.ACTIVE
            existing_user.updated_at = datetime.utcnow()
            
            session.add(existing_user)
            session.commit()
            session.refresh(existing_user)
            user = existing_user
            print(f"✅ Activated pre-registered student: {user.id}")
            
        # Create new user if doesn't exist
        elif not existing_user:
            print("🆕 Creating new user...")
            new_user = User(
                otpless_user_id=user_data.get("otpless_user_id"),
                mobile=user_data.get("mobile"),
                email=user_data.get("email"),
                name=user_data.get("name"),
                profile_picture=user_data.get("profile_picture"),
                auth_provider=user_data.get("auth_provider", "otpless"),
                role=UserRole.STUDENT,  # Auto-assign student role for OTPLESS users
                registration_status=RegistrationStatus.ACTIVE,  # New users are immediately active
                profile_completed=bool(user_data.get("name") and user_data.get("email")),
                is_active=True
            )
            
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            user = new_user
            print(f"✅ Created new user: {user.id}")
        else:
            print("🔄 Updating existing user...")
            # Update existing user with latest OTPLESS data
            if user_data.get("otpless_user_id") and not existing_user.otpless_user_id:
                existing_user.otpless_user_id = user_data["otpless_user_id"]
            if user_data.get("name") and not existing_user.name:
                existing_user.name = user_data["name"]
            if user_data.get("profile_picture") and not existing_user.profile_picture:
                existing_user.profile_picture = user_data["profile_picture"]
            
            existing_user.updated_at = datetime.utcnow()
            session.add(existing_user)
            session.commit()
            session.refresh(existing_user)
            user = existing_user
            print(f"✅ Updated existing user: {user.id}")
        
        # Check if profile completion is required
        requires_profile_completion = not (user.name and user.email)
        print(f"🔍 Profile completion required: {requires_profile_completion}")
        
        # Create JWT token
        access_token = create_access_token(
            data={
                "sub": user.id,
                "role": user.role,
                "profile_completed": user.profile_completed
            }
        )
        
        print(f"✅ JWT token created successfully")
        
        response_data = OTPLESSVerifyResponse(
            access_token=access_token,
            user=UserInfo(
                id=user.id,
                email=user.email,
                mobile=user.mobile,
                name=user.name,
                role=user.role,
                profile_completed=user.profile_completed
            ),
            requires_profile_completion=requires_profile_completion
        )
        
        print(f"✅ Sending response: {response_data}")
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Unexpected error in OTPLESS verification: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@router.post("/complete-profile", response_model=ProfileCompletionResponse)
def complete_profile(
    profile_data: ProfileCompletionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Complete user profile with name and email
    """
    try:
        # Validate that user needs profile completion
        if current_user.profile_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already completed"
            )
        
        # Check if email is already taken by another user
        if profile_data.email != current_user.email:  # Allow keeping same email
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
        
        # Update user profile
        current_user.name = profile_data.name
        current_user.email = profile_data.email
        current_user.profile_completed = True
        current_user.updated_at = datetime.utcnow()
        
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        
        return ProfileCompletionResponse(
            success=True,
            message="Profile completed successfully",
            user_id=current_user.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error completing profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete profile"
        )


@router.get("/me", response_model=OTPLESSUserResponse)
def get_current_otpless_user(
    current_user: User = Depends(get_current_user)
):
    """
    Get current OTPLESS user information
    """
    return OTPLESSUserResponse(
        id=current_user.id,
        email=current_user.email,
        mobile=current_user.mobile,
        name=current_user.name,
        profile_picture=current_user.profile_picture,
        role=current_user.role,
        auth_provider=current_user.auth_provider,
        profile_completed=current_user.profile_completed,
        is_active=current_user.is_active
    ) 