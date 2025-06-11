# **📧 Phase 3: Email Management API Endpoints**

## **Overview**

Phase 3 introduces powerful email management capabilities to the QuizMaster application, enabling administrators to efficiently manage student communications through automated bulk operations, progress tracking, and invitation management.

## **🚀 Key Features**

- **📧 Bulk Email Operations** - Batch processing with background tasks
- **📊 Progress Tracking** - Real-time status updates for email sending
- **🎯 Selective Sending** - Target specific students or bulk operations  
- **🔄 Status Management** - Track email sent/verified states
- **⚡ Background Processing** - Non-blocking email operations

---

## **📋 API Endpoints**

### **1. Get Students with Email Status**
**`GET /api/students/email-status`**

Get paginated list of students with comprehensive email status information.

**Query Parameters:**
- `skip`: Offset for pagination (default: 0)
- `limit`: Number of records per page (default: 100, max: 1000)
- `search`: Filter by email contains
- `email_status`: Filter by status (`sent`, `not_sent`, `verified`, `not_verified`)

**Response:**
```json
[
  {
    "id": "user_123",
    "email": "student@example.com",
    "name": "John Doe",
    "role": "student",
    "is_active": true,
    "registration_status": "pending",
    "email_sent": false,
    "email_verified": false,
    "invitation_sent_at": null,
    "verification_method": "otpless_mobile",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/students/email-status?email_status=not_sent&limit=50" \
  -H "Authorization: Bearer <admin_token>"
```

---

### **2. Get Email Operation Status**
**`GET /api/students/email-operation/{operation_id}`**

Track the progress of bulk email operations in real-time.

**Path Parameters:**
- `operation_id`: Unique identifier for the email operation

**Response:**
```json
{
  "operation_id": "email_op_a1b2c3d4_1705312345",
  "status": "in_progress",
  "total_emails": 50,
  "sent_count": 32,
  "failed_count": 2,
  "progress_percentage": 68.0,
  "errors": [
    "Failed to send email to invalid@domain.com"
  ],
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": null
}
```

**Status Values:**
- `pending`: Operation queued but not started
- `in_progress`: Currently sending emails
- `completed`: All emails processed successfully
- `failed`: Operation failed with errors

**cURL Example:**
```bash
curl -X GET "http://localhost:8000/api/students/email-operation/email_op_a1b2c3d4_1705312345" \
  -H "Authorization: Bearer <admin_token>"
```

---

### **3. Enhanced Bulk Import with Email**
**`POST /api/students/bulk-import-with-email`**

Enhanced version of bulk import that automatically sends invitation emails to newly imported students.

**Form Data:**
- `file`: CSV file with student emails
- `send_emails`: Whether to send emails (default: true)
- `course_id`: Optional course ID for email context
- `email_delay_seconds`: Delay between emails (0-10 seconds, default: 1)

**Response:**
```json
{
  "total_rows": 100,
  "successful": 95,
  "failed": 5,
  "errors": [
    "Row 12: Email 'invalid-email' already exists",
    "Row 45: Invalid email format 'notanemail'"
  ],
  "preregistered_students": [
    {
      "id": "user_123",
      "email": "student1@example.com",
      "status": "pre-registered"
    }
  ],
  "email_operation": {
    "operation_id": "email_op_b2c3d4e5_1705312400",
    "emails_to_send": 95,
    "course_name": "Computer Science 101"
  }
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/students/bulk-import-with-email?send_emails=true&course_id=course_123&email_delay_seconds=2" \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@students.csv"
```

---

### **4. Send Invitation Emails**
**`POST /api/students/send-invitations`**

Send invitation emails to selected students with optional course context.

**Request Body:**
```json
{
  "student_ids": ["user_123", "user_456", "user_789"],
  "course_id": "course_123",
  "custom_message": "Welcome to our advanced programming course!"
}
```

**Response:**
```json
{
  "operation_id": "email_op_c3d4e5f6_1705312500",
  "total_students": 3,
  "eligible_for_email": 2,
  "course_name": "Computer Science 101",
  "message": "Invitation emails are being sent to 2 students"
}
```

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/students/send-invitations" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "student_ids": ["user_123", "user_456"],
    "course_id": "course_123",
    "custom_message": "Welcome to our course!"
  }'
```

---

### **5. Send Bulk Custom Emails**
**`POST /api/students/bulk-email`**

Send custom emails to specified email addresses with custom subject and message.

**Request Body:**
```json
{
  "student_emails": [
    "student1@example.com",
    "student2@example.com",
    "student3@example.com"
  ],
  "subject": "Important Course Update",
  "message": "Please check the updated syllabus on our platform.",
  "course_id": "course_123"
}
```

**Response:**
```json
{
  "operation_id": "email_op_d4e5f6g7_1705312600",
  "total_emails": 3,
  "subject": "Important Course Update",
  "course_name": "Computer Science 101",
  "message": "Custom emails are being sent to 3 recipients"
}
```

**Rate Limiting:** Maximum 100 emails per request.

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/students/bulk-email" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "student_emails": ["student1@example.com", "student2@example.com"],
    "subject": "Course Update",
    "message": "Important announcement about our course.",
    "course_id": "course_123"
  }'
```

---

### **6. Update Student Email Status**
**`PATCH /api/students/{student_id}/email-status`**

Manually update student email status for administrative purposes.

**Path Parameters:**
- `student_id`: Student's unique identifier

**Query Parameters:**
- `email_sent`: Boolean to mark email as sent/not sent
- `email_verified`: Boolean to mark email as verified/not verified

**Response:**
```json
{
  "student_id": "user_123",
  "email": "student@example.com",
  "email_sent": true,
  "email_verified": false,
  "updated_at": "2024-01-15T10:35:00Z"
}
```

**cURL Example:**
```bash
curl -X PATCH "http://localhost:8000/api/students/user_123/email-status?email_sent=true&email_verified=false" \
  -H "Authorization: Bearer <admin_token>"
```

---

## **🔧 Background Processing**

### **Email Operation Tracking**

All bulk email operations are processed in the background to prevent blocking the API. Each operation receives a unique `operation_id` that can be used to track progress.

**Operation ID Format:** `email_op_{8_char_hex}_{timestamp}`

**Progress Tracking Features:**
- Real-time progress percentage calculation
- Detailed error reporting for failed emails
- Completion timestamps
- Retry logic for transient failures

### **Rate Limiting**

- **Bulk Operations:** Maximum 100 emails per request
- **Email Delays:** Configurable 1-10 second delays between emails
- **SMTP Throttling:** Automatic handling of SMTP rate limits

---

## **📊 Email Status Management**

### **Student Email States**

Each student has comprehensive email status tracking:

- `email_sent`: Whether invitation email has been sent
- `email_verified`: Whether student completed email verification
- `invitation_sent_at`: Timestamp of last invitation
- `verification_method`: How student will verify (otpless_mobile, etc.)

### **Eligibility Rules**

Students are eligible for invitation emails when:
- Email not already verified AND
- Profile not completed AND
- (Never sent email OR last sent > 1 hour ago)

---

## **🔒 Security & Authorization**

- **Admin Only:** All email endpoints require admin authentication
- **Course Validation:** Course access verified for instructor ownership
- **Input Validation:** Email format validation and sanitization
- **Rate Limiting:** Protection against spam and abuse

---

## **📈 Integration Examples**

### **Frontend Integration Pattern**

```javascript
// 1. Start bulk email operation
const response = await fetch('/api/students/send-invitations', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    student_ids: selectedStudentIds,
    course_id: currentCourse.id
  })
});

const { operation_id } = await response.json();

// 2. Track progress with polling
const trackProgress = async (operationId) => {
  const statusResponse = await fetch(`/api/students/email-operation/${operationId}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  const status = await statusResponse.json();
  
  // Update UI with progress
  updateProgressBar(status.progress_percentage);
  updateStatusMessage(status.status);
  
  if (status.status === 'completed' || status.status === 'failed') {
    showFinalResults(status);
  } else {
    setTimeout(() => trackProgress(operationId), 2000); // Poll every 2 seconds
  }
};

trackProgress(operation_id);
```

### **Workflow Example**

```bash
# 1. Import students with auto-email
curl -X POST "http://localhost:8000/api/students/bulk-import-with-email" \
  -H "Authorization: Bearer <token>" \
  -F "file=@new_students.csv" \
  -F "course_id=course_123"

# 2. Check students needing email invitations
curl -X GET "http://localhost:8000/api/students/email-status?email_status=not_sent" \
  -H "Authorization: Bearer <token>"

# 3. Send invitations to specific students
curl -X POST "http://localhost:8000/api/students/send-invitations" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"student_ids": ["user_123", "user_456"], "course_id": "course_123"}'

# 4. Track email operation progress
curl -X GET "http://localhost:8000/api/students/email-operation/email_op_a1b2c3d4_1705312345" \
  -H "Authorization: Bearer <token>"
```

---

## **🚀 Next Steps: Phase 4**

Phase 4 will implement the frontend UI components to interact with these email management endpoints:

- **Email Dashboard:** Visual interface for managing student email status
- **Bulk Operation UI:** Forms and progress indicators for bulk operations
- **Student Management:** Enhanced student list with email status columns
- **Progress Tracking:** Real-time progress bars and status updates

---

## **📝 Notes**

- Email operations are processed asynchronously to maintain API responsiveness
- All email templates are customizable through the email service
- SMTP configuration is required for email functionality (see EMAIL_SERVICE_SETUP.md)
- Progress tracking data is stored in memory and will reset on server restart
- Consider implementing persistent progress tracking for production environments 