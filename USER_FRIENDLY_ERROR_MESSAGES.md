# User-Friendly Error Messages for OTPless Authentication

This document outlines all the user-friendly error messages implemented for different scenarios in the OTPless authentication flow.

## Overview

The system now provides clear, actionable error messages for various conflict scenarios that can occur during profile completion, helping users understand what went wrong and what they should do next.

## Error Scenarios and Messages

### 1. Email Check Endpoint (`/api/auth/otpless/check-email`)

#### 1.1 Email Available
- **Status**: `available`
- **Message**: "Email is available"
- **When**: Email is not registered by any other user

#### 1.2 Pre-registered Email - Mobile Match
- **Status**: `pending_match`
- **Message**: "Perfect! This email was pre-registered with your mobile number. Your accounts will be linked automatically."
- **When**: Admin bulk-imported student with same email + mobile, user logs in with OTPless using same mobile

#### 1.3 Pre-registered Email - Mobile Mismatch
- **Status**: `pending_mismatch`
- **Message**: "This email is registered with a different mobile number (790****914). Please contact your administrator."
- **When**: Admin bulk-imported student with email + mobile A, user logs in with OTPless using mobile B
- **Note**: Mobile numbers are partially masked for privacy (e.g., `790****914`)

#### 1.4 Active User - Same Mobile
- **Status**: `taken_same_mobile`
- **Message**: "This email and mobile combination is already registered and active. Please try logging in instead."
- **When**: User tries to register again with same email + mobile combination

#### 1.5 Active User - Different Mobile
- **Status**: `taken_different_mobile`
- **Message**: "This email is already registered by another user. Please use a different email address."
- **When**: User tries to use email that belongs to a different active user

#### 1.6 Invalid Email
- **Status**: `invalid`
- **Message**: "Please enter a valid email address"
- **When**: Empty or invalid email provided

### 2. Profile Completion Endpoint (`/api/auth/otpless/complete-profile`)

#### 2.1 Successful Account Merge
- **Success**: `true`
- **Message**: "Profile completed successfully! Your account has been linked to your pre-registered email."
- **When**: Mobile numbers match between OTPless user and bulk-imported user

#### 2.2 Mobile Number Mismatch (Main Scenario)
- **Status Code**: `400`
- **Error**: "This email is already registered with a different mobile number (790****914). You're trying to use mobile 812****789. Please contact your administrator or use the correct mobile number associated with this email."
- **When**: Admin bulk-imported with mobile A, user logs in with OTPless using mobile B
- **Features**:
  - Shows both expected and current mobile (partially masked)
  - Clear instruction to contact administrator
  - Suggests using correct mobile number

#### 2.3 Already Active - Same Mobile
- **Status Code**: `400`
- **Error**: "This email and mobile number combination is already registered and active. Please try logging in instead."
- **When**: User tries to complete profile for already active account with same mobile

#### 2.4 Already Active - Different Mobile
- **Status Code**: `400`
- **Error**: "This email is already registered by another user. Please use a different email address or contact support if you believe this is an error."
- **When**: User tries to use email belonging to different active user

#### 2.5 Mobile Validation Error
- **Status Code**: `400`
- **Error**: "Invalid mobile number format. Please contact support."
- **When**: Mobile number normalization fails during comparison

#### 2.6 Profile Already Completed
- **Status Code**: `400`
- **Error**: "Profile already completed"
- **When**: User tries to complete profile that's already completed

#### 2.7 Missing Required Fields
- **Status Code**: `400`
- **Error**: "Name is required" or "Email is required"
- **When**: Required fields are empty or contain only whitespace

## Privacy Features

### Mobile Number Masking
- **10-digit numbers**: `7906986914` → `790****914`
- **Shorter numbers**: Shows only last 4 digits with `****` prefix
- **Invalid/empty**: Shows `****` or `N/A`

### Security Considerations
- Mobile numbers are normalized before comparison to prevent format-based bypasses
- All database operations are properly wrapped in try-catch blocks
- Detailed logging for debugging while maintaining user privacy in responses

## Implementation Details

### Mobile Normalization
- Uses `normalize_indian_mobile()` function for consistent comparison
- Handles various input formats: `7906986914`, `917906986914`, `+917906986914`, etc.
- Normalizes to 10-digit format for storage and comparison

### Error Handling Flow
1. **Input Validation**: Check required fields
2. **Mobile Normalization**: Convert to standard format
3. **Database Lookup**: Find existing users with same email
4. **Status Check**: Determine if user is PENDING or ACTIVE
5. **Mobile Comparison**: Compare normalized mobile numbers
6. **Response Generation**: Return appropriate message based on scenario

### Database Operations
- Uses SQLModel/SQLAlchemy for database operations
- Proper transaction handling with rollback on errors
- Account merging includes deletion of temporary OTPless user

## Frontend Integration

The frontend can use the `status` field from the check-email endpoint to:
- Show real-time feedback as user types email
- Display appropriate warnings or success messages
- Guide user actions (contact admin, use different email, etc.)

Example frontend handling:
```javascript
const response = await checkEmail(email);
switch(response.status) {
  case 'pending_match':
    showSuccessMessage(response.message);
    break;
  case 'pending_mismatch':
    showWarningMessage(response.message);
    break;
  case 'taken_different_mobile':
    showErrorMessage(response.message);
    break;
  // ... other cases
}
```

## Testing Scenarios

### Test Case 1: Perfect Match
1. Admin bulk imports: `student@example.com` + `7906986914`
2. Student logs in via OTPless with `7906986914`
3. Student enters `student@example.com` in profile
4. **Expected**: Success message, accounts merged

### Test Case 2: Mobile Mismatch (Your Scenario)
1. Admin bulk imports: `student@example.com` + `7906986914`
2. Student logs in via OTPless with `8123456789`
3. Student enters `student@example.com` in profile
4. **Expected**: Error message showing mobile mismatch with masked numbers

### Test Case 3: Email Taken by Active User
1. User A completes registration: `student@example.com` + `7906986914`
2. User B logs in via OTPless with `8123456789`
3. User B tries to use `student@example.com` in profile
4. **Expected**: Error message indicating email is taken by another user

## Logging and Debugging

All scenarios include detailed logging for debugging:
- Mobile number normalization steps
- Database lookup results
- Comparison logic outcomes
- Error conditions and their causes

Logs use emojis for easy visual scanning:
- 📝 Profile completion steps
- 📱 Mobile number operations
- ✅ Success operations
- ❌ Error conditions
- 🔄 Account merging operations 