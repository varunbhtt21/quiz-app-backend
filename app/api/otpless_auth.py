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
from app.utils.phone_utils import normalize_indian_mobile, MobileValidationError

router = APIRouter(prefix="/auth/otpless", tags=["OTPLESS Authentication"])


def find_user_by_mobile_flexible(session: Session, mobile: str) -> Optional[User]:
    """
    Find user by mobile number, handling both old (+91) and new (10-digit) formats.
    
    This ensures backward compatibility with existing data while supporting new normalized format.
    """
    print(f"📱 === FLEXIBLE MOBILE LOOKUP DEBUG ===")
    print(f"📱 Input mobile: '{mobile}'")
    
    if not mobile:
        print(f"📱 No mobile provided, returning None")
        return None
    
    # First, try exact match (for existing data)
    print(f"📱 Step 1: Exact match lookup for '{mobile}'")
    user = session.exec(select(User).where(User.mobile == mobile)).first()
    if user:
        print(f"📱 ✅ Exact match found: ID={user.id}, email='{user.email}'")
        return user
    print(f"📱 ❌ No exact match")
    
    # Try to normalize the mobile and search again
    print(f"📱 Step 2: Normalize and search")
    try:
        normalized_mobile = normalize_indian_mobile(mobile)
        print(f"📱 Normalized '{mobile}' to '{normalized_mobile}'")
        user = session.exec(select(User).where(User.mobile == normalized_mobile)).first()
        if user:
            print(f"📱 ✅ Normalized match found: ID={user.id}, email='{user.email}'")
            return user
        print(f"📱 ❌ No normalized match for '{normalized_mobile}'")
    except MobileValidationError as e:
        print(f"📱 ❌ Normalization failed: {e}")
    
    # Try to find by adding +91 prefix (for old data compatibility)
    if len(mobile) == 10 and mobile.isdigit():
        prefixed_mobile = f"+91{mobile}"
        print(f"📱 Step 3: Adding +91 prefix: '{prefixed_mobile}'")
        user = session.exec(select(User).where(User.mobile == prefixed_mobile)).first()
        if user:
            print(f"📱 ✅ +91 prefixed match found: ID={user.id}, email='{user.email}'")
            return user
        print(f"📱 ❌ No +91 prefixed match")
    
    # Try to find by removing +91 prefix (for new data compatibility)
    if mobile.startswith("+91") and len(mobile) == 13:
        normalized_mobile = mobile[3:]  # Remove +91
        print(f"📱 Step 4: Removing +91 prefix: '{normalized_mobile}'")
        user = session.exec(select(User).where(User.mobile == normalized_mobile)).first()
        if user:
            print(f"📱 ✅ -91 prefix match found: ID={user.id}, email='{user.email}'")
            return user
        print(f"📱 ❌ No -91 prefix match")
    
    print(f"📱 ❌ No user found with any mobile matching strategy")
    print(f"📱 =====================================")
    return None


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
        
        # 📱 DETAILED MOBILE NUMBER LOGGING FOR DEBUGGING
        otpless_mobile = user_data.get("mobile")
        print(f"📱 =================== MOBILE DEBUG ===================")
        print(f"📱 OTPless returned mobile: '{otpless_mobile}' (type: {type(otpless_mobile)})")
        print(f"📱 Mobile length: {len(otpless_mobile) if otpless_mobile else 'None'}")
        if otpless_mobile:
            print(f"📱 Mobile starts with +91: {otpless_mobile.startswith('+91')}")
            print(f"📱 Mobile starts with 91: {otpless_mobile.startswith('91')}")
            print(f"📱 Mobile is 10 digits: {len(otpless_mobile) == 10 and otpless_mobile.isdigit()}")
            print(f"📱 Mobile is 13 chars (+91XXXXXXXXXX): {len(otpless_mobile) == 13}")
            print(f"📱 Raw mobile representation: {repr(otpless_mobile)}")
        print(f"📱 ===================================================")
        
        # 🔧 NORMALIZE MOBILE NUMBER FOR CONSISTENCY
        normalized_mobile = None
        if otpless_mobile:
            try:
                normalized_mobile = normalize_indian_mobile(otpless_mobile)
                print(f"📱 ✅ Mobile normalized: '{otpless_mobile}' → '{normalized_mobile}'")
                # Update user_data with normalized mobile
                user_data["mobile"] = normalized_mobile
            except MobileValidationError as e:
                print(f"📱 ❌ Mobile normalization failed: {e}")
                # Keep original mobile if normalization fails
                normalized_mobile = otpless_mobile
        
        # Check if user already exists by OTPLESS user ID
        existing_user = None
        if user_data.get("otpless_user_id"):
            print(f"🔍 Looking for user by OTPLESS ID: {user_data.get('otpless_user_id')}")
            statement = select(User).where(User.otpless_user_id == user_data["otpless_user_id"])
            existing_user = session.exec(statement).first()
            if existing_user:
                print(f"✅ Found existing user by OTPLESS ID: {existing_user.id}")
                print(f"📱 Existing user mobile in DB: '{existing_user.mobile}'")
        
        # If not found by OTPLESS ID, check by mobile (with flexible matching)
        if not existing_user and user_data.get("mobile"):
            print(f"🔍 ============= MOBILE LOOKUP DEBUG =============")
            print(f"🔍 Looking for user by mobile: '{user_data.get('mobile')}'")
            
            # First try exact match to see what happens
            print(f"🔍 Step 1: Trying exact match lookup...")
            exact_match = session.exec(select(User).where(User.mobile == otpless_mobile)).first()
            if exact_match:
                print(f"✅ EXACT MATCH found: ID={exact_match.id}, mobile='{exact_match.mobile}', email='{exact_match.email}'")
            else:
                print(f"❌ No exact match found for '{otpless_mobile}'")
            
            print(f"🔍 Step 2: Trying flexible matching...")
            existing_user = find_user_by_mobile_flexible(session, user_data["mobile"])
            if existing_user:
                print(f"✅ FLEXIBLE MATCH found: ID={existing_user.id}")
                print(f"📱 Mobile format - OTPLESS: '{user_data['mobile']}', DB: '{existing_user.mobile}'")
                print(f"📱 User email: '{existing_user.email}'")
                print(f"📱 User status: {existing_user.registration_status}")
            else:
                print(f"❌ No user found even with flexible matching for '{user_data['mobile']}'")
                
                # Debug: Let's see what users exist with similar mobile patterns
                print(f"🔍 DEBUG: Checking users with mobile patterns...")
                # Check for 10-digit version
                if otpless_mobile and otpless_mobile.startswith('+91') and len(otpless_mobile) == 13:
                    ten_digit = otpless_mobile[3:]
                    ten_digit_user = session.exec(select(User).where(User.mobile == ten_digit)).first()
                    print(f"🔍 Looking for 10-digit version '{ten_digit}': {'FOUND' if ten_digit_user else 'NOT FOUND'}")
                    if ten_digit_user:
                        print(f"🔍 Found user: ID={ten_digit_user.id}, email='{ten_digit_user.email}', status={ten_digit_user.registration_status}")
                
                # Check for +91 version
                if otpless_mobile and len(otpless_mobile) == 10 and otpless_mobile.isdigit():
                    plus_version = f"+91{otpless_mobile}"
                    plus_user = session.exec(select(User).where(User.mobile == plus_version)).first()
                    print(f"🔍 Looking for +91 version '{plus_version}': {'FOUND' if plus_user else 'NOT FOUND'}")
                    if plus_user:
                        print(f"🔍 Found user: ID={plus_user.id}, email='{plus_user.email}', status={plus_user.registration_status}")
            
            print(f"🔍 ============================================")
        
        print(f"🔍 Final existing_user result: {existing_user.id if existing_user else 'None'}")
        
        # If not found by mobile, check by email (important for bulk-imported users)
        if not existing_user and user_data.get("email"):
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
            
            # Keep existing mobile if provided during bulk import, otherwise use OTPLESS mobile
            if not existing_user.mobile and user_data.get("mobile"):
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
            print(f"📧 Email: {user.email}")
            print(f"📱 Mobile: {user.mobile}")
            
        # Create new user if doesn't exist
        elif not existing_user:
            print("🆕 Creating new user...")
            
            new_user = User(
                otpless_user_id=user_data.get("otpless_user_id"),
                mobile=user_data.get("mobile"),  # Already normalized above
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
        
        # Check if profile completion is required (using business logic validation)
        requires_profile_completion = not user.is_profile_complete_for_business_logic()
        print(f"🔍 Profile completion required: {requires_profile_completion}")
        print(f"🔍 User has name: {bool(user.name)}, email: {bool(user.email)}, date_of_birth: {bool(user.date_of_birth)}, profile_completed: {user.profile_completed}")
        
        # Create JWT token
        access_token = create_access_token(
            data={
                "sub": user.id,
                "role": user.role,
                "profile_completed": user.profile_completed,
                "requires_profile_completion": requires_profile_completion
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
                date_of_birth=user.date_of_birth,
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
        print(f"📝 === PROFILE COMPLETION DEBUG ===")
        print(f"📝 Current user ID: {current_user.id}")
        print(f"📝 Current user mobile: '{current_user.mobile}'")
        print(f"📝 Current user email: '{current_user.email}'")
        print(f"📝 Current user name: '{current_user.name}'")
        print(f"📝 Current user registration_status: {current_user.registration_status}")
        print(f"📝 Current user profile_completed: {current_user.profile_completed}")
        print(f"📝 Profile data email: '{profile_data.email}'")
        print(f"📝 Profile data name: '{profile_data.name}'")
        print(f"📝 Profile data date_of_birth: {profile_data.date_of_birth}")
        print(f"📝 =================================")
        
        # Validate that user needs profile completion (stricter validation)
        if current_user.profile_completed and current_user.name and current_user.email:
            print(f"📝 ❌ Profile already completed - throwing error")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already completed"
            )
        
        # Validate required fields
        if not profile_data.name or not profile_data.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Name is required"
            )
        
        if not profile_data.email or not profile_data.email.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required"
            )
        
        # Check if email is already taken by another user
        print(f"📝 Checking email conflicts...")
        print(f"📝 Profile email: '{profile_data.email}' vs Current email: '{current_user.email}'")
        
        if profile_data.email != current_user.email:  # Allow keeping same email
            print(f"📝 Email is different, checking for conflicts...")
            statement = select(User).where(
                User.email == profile_data.email,
                User.id != current_user.id
            )
            existing_user = session.exec(statement).first()
            
            if existing_user:
                print(f"📝 Found existing user with email '{profile_data.email}': ID={existing_user.id}")
                print(f"📝 Existing user mobile: '{existing_user.mobile}'")
                print(f"📝 Existing user status: {existing_user.registration_status}")
                print(f"📝 Current user mobile: '{current_user.mobile}'")
                
                # If the existing user is PENDING (bulk imported), check if mobiles match
                if existing_user.registration_status == RegistrationStatus.PENDING:
                    # Normalize both mobiles for comparison
                    try:
                        existing_normalized = normalize_indian_mobile(existing_user.mobile) if existing_user.mobile else None
                        current_normalized = normalize_indian_mobile(current_user.mobile) if current_user.mobile else None
                        
                        print(f"📝 Mobile comparison - Existing: '{existing_user.mobile}' → '{existing_normalized}'")
                        print(f"📝 Mobile comparison - Current: '{current_user.mobile}' → '{current_normalized}'")
                        
                        if existing_normalized == current_normalized:
                            # Perfect match - merge accounts
                            print(f"🔄 ✅ Mobile numbers match! Merging accounts for: {existing_user.email}")
                            
                            # Transfer data from current OTP user to the pre-registered user
                            existing_user.otpless_user_id = current_user.otpless_user_id
                            existing_user.mobile = current_user.mobile  # Keep the OTPless format
                            existing_user.name = profile_data.name
                            existing_user.date_of_birth = profile_data.date_of_birth
                            existing_user.profile_picture = current_user.profile_picture
                            existing_user.auth_provider = current_user.auth_provider
                            existing_user.registration_status = RegistrationStatus.ACTIVE
                            existing_user.profile_completed = True
                            existing_user.updated_at = datetime.utcnow()
                            
                            # Update the user record
                            session.add(existing_user)
                            
                            # Delete the temporary OTP user
                            session.delete(current_user)
                            session.commit()
                            session.refresh(existing_user)
                            
                            print(f"✅ Successfully merged accounts for: {existing_user.email}")
                            
                            return ProfileCompletionResponse(
                                success=True,
                                message="Profile completed successfully! Your account has been linked to your pre-registered email.",
                                user_id=existing_user.id
                            )
                        else:
                            # Mobile numbers don't match - this is the scenario you mentioned
                            print(f"📝 ❌ Mobile mismatch - Current: {current_normalized}, Expected: {existing_normalized}")
                            
                            # Format mobile numbers for display (hide middle digits for privacy)
                            def format_mobile_for_display(mobile):
                                if not mobile:
                                    return "N/A"
                                if len(mobile) == 10:
                                    return f"{mobile[:3]}****{mobile[-3:]}"
                                return f"****{mobile[-4:]}"
                            
                            expected_display = format_mobile_for_display(existing_normalized)
                            current_display = format_mobile_for_display(current_normalized)
                            
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"This email is already registered with a different mobile number ({expected_display}). You're trying to use mobile {current_display}. Please contact your administrator or use the correct mobile number associated with this email."
                            )
                    except MobileValidationError as e:
                        print(f"📝 ❌ Mobile validation error during comparison: {e}")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid mobile number format. Please contact support."
                        )
                else:
                    # Email belongs to an active user - different scenario
                    print(f"📝 ❌ Email belongs to active user - throwing error")
                    
                    # Check if it's the same mobile number (user trying to re-register)
                    try:
                        existing_normalized = normalize_indian_mobile(existing_user.mobile) if existing_user.mobile else None
                        current_normalized = normalize_indian_mobile(current_user.mobile) if current_user.mobile else None
                        
                        if existing_normalized == current_normalized:
                            # Same person trying to register again
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="This email and mobile number combination is already registered and active. Please try logging in instead."
                            )
                        else:
                            # Different person trying to use same email
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="This email is already registered by another user. Please use a different email address or contact support if you believe this is an error."
                            )
                    except MobileValidationError:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="This email is already registered by another user. Please use a different email address."
                        )
            else:
                print(f"📝 No existing user found with email '{profile_data.email}'")
        
        # Update user profile
        current_user.name = profile_data.name
        current_user.email = profile_data.email
        current_user.date_of_birth = profile_data.date_of_birth
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


@router.post("/check-email")
def check_email_status(
    email_data: dict,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Check if email is pre-registered (PENDING) for better UX in profile completion
    """
    email = email_data.get("email", "").strip()
    
    if not email:
        return {"is_pre_registered": False, "status": "invalid", "message": "Please enter a valid email address"}
    
    statement = select(User).where(User.email == email, User.id != current_user.id)
    existing_user = session.exec(statement).first()
    
    if not existing_user:
        return {"is_pre_registered": False, "status": "available", "message": "Email is available"}
    
    if existing_user.registration_status == RegistrationStatus.PENDING:
        # Check if mobile numbers match for better messaging
        try:
            existing_normalized = normalize_indian_mobile(existing_user.mobile) if existing_user.mobile else None
            current_normalized = normalize_indian_mobile(current_user.mobile) if current_user.mobile else None
            
            if existing_normalized == current_normalized:
                return {
                    "is_pre_registered": True, 
                    "status": "pending_match",
                    "message": "Perfect! This email was pre-registered with your mobile number. Your accounts will be linked automatically."
                }
            else:
                # Format mobile for display
                def format_mobile_for_display(mobile):
                    if not mobile or len(mobile) < 4:
                        return "****"
                    if len(mobile) == 10:
                        return f"{mobile[:3]}****{mobile[-3:]}"
                    return f"****{mobile[-4:]}"
                
                expected_display = format_mobile_for_display(existing_normalized)
                
                return {
                    "is_pre_registered": True, 
                    "status": "pending_mismatch",
                    "message": f"This email is registered with a different mobile number ({expected_display}). Please contact your administrator."
                }
        except MobileValidationError:
            return {
                "is_pre_registered": True, 
                "status": "pending_error",
                "message": "This email is pre-registered but there's an issue with mobile number validation. Please contact support."
            }
    else:
        # Active user with this email
        try:
            existing_normalized = normalize_indian_mobile(existing_user.mobile) if existing_user.mobile else None
            current_normalized = normalize_indian_mobile(current_user.mobile) if current_user.mobile else None
            
            if existing_normalized == current_normalized:
                return {
                    "is_pre_registered": False, 
                    "status": "taken_same_mobile",
                    "message": "This email and mobile combination is already registered and active. Please try logging in instead."
                }
            else:
                return {
                    "is_pre_registered": False, 
                    "status": "taken_different_mobile",
                    "message": "This email is already registered by another user. Please use a different email address."
                }
        except MobileValidationError:
            return {
                "is_pre_registered": False, 
                "status": "taken",
                "message": "This email is already registered by another user. Please use a different email address."
            }


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
        date_of_birth=current_user.date_of_birth,
        profile_picture=current_user.profile_picture,
        role=current_user.role,
        auth_provider=current_user.auth_provider,
        profile_completed=current_user.profile_completed,
        is_active=current_user.is_active
    ) 