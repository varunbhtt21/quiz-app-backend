# Supabase Storage Setup Guide

This guide explains how to set up Supabase Storage for handling image uploads in the Quiz App.

## Overview

The Quiz App now uses Supabase Storage instead of local file storage for:
- MCQ question images
- Image uploads via admin interface
- Bulk image imports from URLs

## Prerequisites

1. **Supabase Project**: You need an active Supabase project
2. **Storage Enabled**: Ensure Storage is enabled in your Supabase project
3. **API Keys**: Access to your project's URL and anon key

## Setup Steps

### 1. Configure Environment Variables

Add the following to your `.env` file in the `quiz-app-backend` directory:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key-here
SUPABASE_STORAGE_BUCKET=quiz-images
```

**How to get these values:**
- `SUPABASE_URL`: Found in Project Settings > API > URL
- `SUPABASE_KEY`: Found in Project Settings > API > anon/public key

### 2. Create Storage Bucket

The storage service will automatically create the bucket on first use, but you can also create it manually:

1. Go to your Supabase Dashboard
2. Navigate to Storage
3. Click "Create bucket"
4. Name: `quiz-images`
5. Set as **Public bucket** (recommended for easier access)

### 3. Set Storage Policies (Optional)

For production, you may want to set up Row Level Security (RLS) policies:

```sql
-- Allow authenticated users to upload images
CREATE POLICY "Allow authenticated uploads" ON storage.objects
FOR INSERT WITH CHECK (
  bucket_id = 'quiz-images' 
  AND auth.role() = 'authenticated'
);

-- Allow public read access to images
CREATE POLICY "Allow public read" ON storage.objects
FOR SELECT USING (bucket_id = 'quiz-images');

-- Allow authenticated users to delete their uploads
CREATE POLICY "Allow authenticated delete" ON storage.objects
FOR DELETE USING (
  bucket_id = 'quiz-images' 
  AND auth.role() = 'authenticated'
);
```

### 4. Test Configuration

Run the storage test script to verify everything is working:

```bash
cd quiz-app-backend
python test_storage.py
```

Expected output:
```
🧪 Supabase Storage Test
========================================
🔧 Testing Storage Configuration...
✅ Supabase URL: https://your-project.supabase.co
✅ Storage Bucket: quiz-images
✅ Storage service initialized successfully

🪣 Testing Storage Bucket...
✅ Bucket 'quiz-images' exists
   Public: True

========================================
🎉 All tests passed! Storage is ready to use.
```

## Features

### Image Upload
- **Supported formats**: JPEG, PNG, GIF, WebP
- **Size limit**: 5MB for single uploads, 10MB for bulk imports
- **Automatic validation**: File type and size validation
- **Unique naming**: UUIDs prevent naming conflicts

### URL Handling
The app automatically handles both:
- **Legacy local URLs**: `/uploads/filename.jpg`
- **Supabase URLs**: `https://project.supabase.co/storage/v1/object/public/bucket/path`

### Bulk Import
- Download images from external URLs
- Automatic upload to Supabase Storage
- Fallback handling for failed downloads

## File Structure

```
quiz-app-backend/
├── app/
│   ├── services/
│   │   └── storage.py          # Supabase Storage service
│   ├── core/
│   │   └── config.py           # Configuration with Supabase settings
│   └── routers/
│       └── mcq.py              # Updated to use Supabase Storage
├── test_storage.py             # Storage test script
└── SUPABASE_STORAGE_SETUP.md   # This guide
```

## Migration from Local Storage

If you have existing local images, you can migrate them:

1. **Manual Migration**: Upload existing images through the admin interface
2. **Bulk Migration**: Use the bulk import feature with local file URLs
3. **Script Migration**: Create a custom script to upload existing files

### Example Migration Script

```python
import os
from app.services.storage import storage_service
from pathlib import Path

async def migrate_local_images():
    uploads_dir = Path("uploads")
    if not uploads_dir.exists():
        return
    
    for image_file in uploads_dir.glob("*"):
        if image_file.is_file():
            # Upload to Supabase
            with open(image_file, "rb") as f:
                # Create a mock UploadFile
                # Upload and get new URL
                pass
```

## Troubleshooting

### Common Issues

1. **Storage service not initialized**
   - Check SUPABASE_URL and SUPABASE_KEY in .env
   - Verify the values are correct

2. **Bucket access denied**
   - Ensure bucket exists and is public
   - Check storage policies if using RLS

3. **Upload failures**
   - Verify file size limits
   - Check file type restrictions
   - Ensure bucket has sufficient storage

### Debug Mode

Enable debug logging by setting:
```env
DEBUG=True
```

### Test Storage Access

```python
from app.services.storage import storage_service

# Test bucket access
try:
    bucket_info = storage_service.supabase.storage.get_bucket("quiz-images")
    print("Bucket accessible:", bucket_info)
except Exception as e:
    print("Bucket access error:", e)
```

## Security Considerations

1. **API Keys**: Never commit API keys to version control
2. **Bucket Policies**: Set up appropriate RLS policies for production
3. **File Validation**: The service validates file types and sizes
4. **Access Control**: Consider implementing additional access controls

## Performance Optimization

1. **CDN**: Supabase provides global CDN for fast image delivery
2. **Caching**: Images are cached with appropriate headers
3. **Compression**: Consider implementing image compression before upload
4. **Lazy Loading**: Use lazy loading for image-heavy pages

## Support

If you encounter issues:
1. Check the test script output
2. Verify Supabase project settings
3. Review the application logs
4. Check Supabase Storage dashboard for errors 