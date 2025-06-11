# Email Service Setup Guide - QuizMaster by Jazzee

## Overview

The QuizMaster Email Service provides comprehensive email functionality for the application, including:

- 📧 **Student invitation emails** - Welcome new students to courses
- ⚡ **Contest notification emails** - Alert students about new contests  
- 🔧 **SMTP configuration** - Flexible email provider support
- 📊 **Admin email management** - Bulk operations and monitoring
- 🛡️ **Security & validation** - Proper authentication and rate limiting

## Features

✅ **Multiple Email Types**
- Student invitation emails with course context
- Contest notification emails with timing details
- Bulk email operations for efficient communication
- Beautiful HTML email templates with fallback support

✅ **Production Ready**
- Async email sending (non-blocking)
- Background task processing
- SMTP connection testing
- Comprehensive error handling and logging
- Rate limiting protection

✅ **Security**
- Admin-only access to email endpoints
- Email validation and spam prevention
- Secure SMTP authentication

## SMTP Provider Setup

### Option 1: Gmail SMTP (Recommended for Development)

1. **Enable 2-Factor Authentication** on your Gmail account

2. **Generate App Password**:
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Security → 2-Step Verification → App passwords
   - Generate password for "Mail"

3. **Environment Variables**:
   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-16-digit-app-password
   FROM_EMAIL=your-email@gmail.com
   ```

### Option 2: SendGrid (Recommended for Production)

1. **Create SendGrid Account**: [sendgrid.com](https://sendgrid.com)

2. **Generate API Key**:
   - Settings → API Keys → Create API Key
   - Select "Full Access" or "Mail Send" permissions

3. **Environment Variables**:
   ```bash
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USERNAME=apikey
   SMTP_PASSWORD=your-sendgrid-api-key
   FROM_EMAIL=your-verified-sender@yourdomain.com
   ```

### Option 3: AWS SES (Enterprise)

1. **Setup AWS SES**: Configure in AWS Console

2. **Get SMTP Credentials**: Generate SMTP credentials in SES console

3. **Environment Variables**:
   ```bash
   SMTP_HOST=email-smtp.us-east-1.amazonaws.com
   SMTP_PORT=587
   SMTP_USERNAME=your-aws-smtp-username
   SMTP_PASSWORD=your-aws-smtp-password
   FROM_EMAIL=your-verified-email@yourdomain.com
   ```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
FROM_EMAIL=your-email@gmail.com

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:8080
```

### Testing Email Service

1. **Check Service Health**:
   ```bash
   curl -X GET "http://localhost:8000/api/email/health" \
     -H "Authorization: Bearer your-admin-token"
   ```

2. **Expected Response**:
   ```json
   {
     "email_service_configured": true,
     "smtp_connection_working": true,
     "smtp_host": "smtp.gmail.com",
     "smtp_port": 587,
     "from_email": "your-email@gmail.com",
     "status": "healthy"
   }
   ```

## API Usage

### 1. Send Single Invitation Email

```bash
curl -X POST "http://localhost:8000/api/email/send-invitation" \
  -H "Authorization: Bearer your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@example.com",
    "name": "John Doe",
    "course_id": "course-uuid-here"
  }'
```

### 2. Send Bulk Invitations

```bash
curl -X POST "http://localhost:8000/api/email/send-bulk-invitations" \
  -H "Authorization: Bearer your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "students": [
      {"email": "student1@example.com", "name": "John Doe"},
      {"email": "student2@example.com", "name": "Jane Smith"}
    ],
    "course_id": "course-uuid-here"
  }'
```

### 3. Send Contest Notifications

```bash
curl -X POST "http://localhost:8000/api/email/send-contest-notification" \
  -H "Authorization: Bearer your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "contest_id": "contest-uuid-here",
    "student_emails": ["student1@example.com", "student2@example.com"]
  }'
```

## Integration with Application Features

### Student Management

When creating students via the admin panel, the email service automatically:
- Sends welcome/invitation emails
- Updates user email status tracking
- Provides feedback on email delivery

### Contest Management

When creating or updating contests, admins can:
- Send automatic notifications to enrolled students
- Schedule email reminders before contest start
- Track email delivery status

### Bulk Operations

For CSV student uploads:
- Bulk invitation emails are sent automatically
- Progress tracking and error reporting
- Rate limiting prevents SMTP server overload

## Email Templates

The service includes responsive HTML email templates:

### Student Invitation Template
- **Subject**: "🎓 Welcome to QuizMaster - Your Learning Journey Begins!"
- **Content**: Welcome message, login instructions, course details
- **CTA**: Direct link to platform login

### Contest Notification Template  
- **Subject**: "⚡ New Contest Alert: [Contest Name] in [Course Name]"
- **Content**: Contest details, timing, duration, pro tips
- **CTA**: Direct link to contest page

### Template Customization

Templates support variables:
- `{{student_name}}` - Student's name
- `{{course_name}}` - Course name
- `{{contest_name}}` - Contest name
- `{{start_time}}` - Formatted start time
- `{{login_url}}` - Direct login link

## Error Handling

### Common Issues & Solutions

1. **"Email service not configured"**
   - ✅ Verify all SMTP environment variables are set
   - ✅ Check `.env` file is being loaded

2. **"SMTP connection failed"**
   - ✅ Verify SMTP credentials are correct
   - ✅ Check firewall/network restrictions
   - ✅ Ensure 2FA is enabled for Gmail

3. **"Failed to send email"**
   - ✅ Check recipient email addresses are valid
   - ✅ Verify sender email is verified with provider
   - ✅ Check SMTP rate limits

### Monitoring & Logging

Email operations are logged with structured information:

```
📧 Email sent successfully to ['student@example.com']
📧 Bulk invitation results: 45/50 sent successfully
📧 SMTP connection test successful
```

Monitor logs for:
- Email delivery success/failure rates
- SMTP connection issues  
- Rate limiting warnings
- Authentication failures

## Production Deployment

### Security Considerations

1. **Use App-Specific Passwords**: Never use main account passwords
2. **Verify Sender Domains**: Configure SPF/DKIM records
3. **Rate Limiting**: Built-in protection against abuse
4. **Secure Storage**: Use environment variables, not code

### Performance Optimization

1. **Background Processing**: All emails sent asynchronously
2. **Connection Pooling**: Efficient SMTP connection management
3. **Batch Operations**: Bulk emails with proper delays
4. **Fallback Templates**: Graceful degradation if template loading fails

### Monitoring

Track these metrics in production:
- Email delivery rates
- SMTP connection health
- Processing queue length
- Error rates by email type

## Development & Testing

### Running Tests

```bash
# Test email service configuration
python -c "from app.services.email_service import email_service; print(email_service.test_connection())"

# Test with development SMTP (MailHog)
docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog
# Then set SMTP_HOST=localhost, SMTP_PORT=1025
```

### Development SMTP Servers

For development/testing without real email delivery:

1. **MailHog** (Recommended):
   ```bash
   docker run -p 1025:1025 -p 8025:8025 mailhog/mailhog
   # Web UI: http://localhost:8025
   ```

2. **Mailtrap**:
   - Sign up at [mailtrap.io](https://mailtrap.io)
   - Use provided SMTP credentials

## Troubleshooting

### Step-by-Step Debugging

1. **Verify Configuration**:
   ```bash
   curl http://localhost:8000/api/email/health
   ```

2. **Check Environment Variables**:
   ```bash
   echo $SMTP_USERNAME
   echo $SMTP_HOST
   echo $FROM_EMAIL
   ```

3. **Test SMTP Connection**:
   ```python
   from app.services.email_service import email_service
   print(f"Configured: {email_service.is_configured}")
   print(f"Connection: {email_service.test_connection()}")
   ```

4. **Review Logs**:
   ```bash
   # Look for email-related log entries
   grep "📧" logs/app.log
   ```

### Common Solutions

| Problem | Solution |
|---------|----------|
| Gmail "Less secure app" error | Use App Password instead of account password |
| SendGrid authentication failed | Verify API key has Mail Send permissions |
| AWS SES bounce rate high | Check email list quality and sender reputation |
| Emails going to spam | Configure SPF, DKIM, DMARC records |

## Support

For additional help:
- 📚 Check FastAPI docs: `/docs` endpoint
- 🐛 Report issues in project repository  
- 📧 Email service logs provide detailed error information
- 🔧 Use `/api/email/health` endpoint for service diagnostics

---

**Phase 2: Email Service + SMTP Setup** ✅ **COMPLETE**

Your QuizMaster application now has professional-grade email capabilities! 