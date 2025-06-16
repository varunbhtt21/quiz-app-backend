from supabase import create_client, Client
from app.core.config import settings
import uuid
import os
from typing import Optional
import mimetypes
from fastapi import HTTPException, UploadFile


class StorageService:
    def __init__(self):
        if not settings.supabase_url or not settings.supabase_key:
            raise ValueError("Supabase URL and Key must be configured")
        
        self.supabase: Client = create_client(settings.supabase_url, settings.supabase_key)
        self.bucket_name = settings.supabase_storage_bucket
        
        # Create bucket if it doesn't exist
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the storage bucket exists, create if it doesn't"""
        try:
            # Try to get bucket info
            self.supabase.storage.get_bucket(self.bucket_name)
        except Exception:
            # Bucket doesn't exist, create it
            try:
                self.supabase.storage.create_bucket(
                    self.bucket_name,
                    options={"public": True}  # Make bucket public for easy access
                )
                print(f"Created storage bucket: {self.bucket_name}")
            except Exception as e:
                print(f"Warning: Could not create bucket {self.bucket_name}: {e}")
    
    def _get_file_extension(self, filename: str, content_type: str) -> str:
        """Get file extension from filename or content type"""
        # Try to get extension from filename first
        _, ext = os.path.splitext(filename)
        if ext:
            return ext.lower()
        
        # Fallback to content type
        ext = mimetypes.guess_extension(content_type)
        return ext.lower() if ext else '.jpg'
    
    def _validate_image_file(self, file: UploadFile, content: bytes) -> None:
        """Validate image file type and size"""
        # Check content type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Check file size (5MB limit)
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size must be less than 5MB")
        
        # Check allowed formats
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail="Unsupported image format. Allowed: JPEG, PNG, GIF, WebP"
            )
    
    async def upload_image(self, file: UploadFile, folder: str = "mcq") -> str:
        """Upload image to Supabase Storage and return public URL"""
        try:
            # Read file content
            content = await file.read()
            
            # Validate file
            self._validate_image_file(file, content)
            
            # Generate unique filename
            file_extension = self._get_file_extension(file.filename or "", file.content_type or "")
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"{folder}/{unique_filename}"
            
            # Upload to Supabase Storage
            result = self.supabase.storage.from_(self.bucket_name).upload(
                file_path,
                content,
                file_options={
                    "content-type": file.content_type,
                    "cache-control": "3600"
                }
            )
            
            if result.status_code != 200:
                raise HTTPException(status_code=500, detail="Failed to upload image to storage")
            
            # Get public URL
            public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(file_path)
            
            return public_url
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"Storage upload error: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload image")
    
    def delete_image(self, image_url: str) -> bool:
        """Delete image from Supabase Storage using its URL"""
        try:
            # Extract file path from URL
            # URL format: https://{project}.supabase.co/storage/v1/object/public/{bucket}/{path}
            if f"/{self.bucket_name}/" not in image_url:
                return False
            
            # Extract the file path after the bucket name
            bucket_index = image_url.find(f"/{self.bucket_name}/")
            if bucket_index == -1:
                return False
            
            file_path = image_url[bucket_index + len(f"/{self.bucket_name}/"):]
            
            # Delete from Supabase Storage
            result = self.supabase.storage.from_(self.bucket_name).remove([file_path])
            
            return len(result) > 0
            
        except Exception as e:
            print(f"Storage delete error: {e}")
            return False
    
    def get_public_url(self, file_path: str) -> str:
        """Get public URL for a file in storage"""
        return self.supabase.storage.from_(self.bucket_name).get_public_url(file_path)
    
    async def download_and_upload_from_url(self, image_url: str, folder: str = "mcq") -> Optional[str]:
        """Download image from URL and upload to Supabase Storage"""
        try:
            import requests
            from urllib.parse import urlparse
            
            # Validate URL
            parsed_url = urlparse(image_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return None
            
            # Download image with timeout
            response = requests.get(image_url, timeout=30, stream=True)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                return None
            
            # Check file size (max 10MB for bulk import)
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:
                return None
            
            # Read content with size limit
            content = b""
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > 10 * 1024 * 1024:  # 10MB limit
                    return None
            
            # Generate unique filename
            file_extension = self._get_file_extension("", content_type)
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"{folder}/{unique_filename}"
            
            # Upload to Supabase Storage
            result = self.supabase.storage.from_(self.bucket_name).upload(
                file_path,
                content,
                file_options={
                    "content-type": content_type,
                    "cache-control": "3600"
                }
            )
            
            if result.status_code != 200:
                return None
            
            # Get public URL
            public_url = self.supabase.storage.from_(self.bucket_name).get_public_url(file_path)
            
            return public_url
            
        except Exception as e:
            print(f"Error downloading and uploading image from {image_url}: {str(e)}")
            return None


# Create a unified storage service that can use either Supabase or S3
storage_service = None

def get_storage_service():
    """Get storage service instance with lazy initialization and error handling"""
    global storage_service
    if storage_service is None:
        try:
            # Try S3 first if configured
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                from app.services.s3_storage import get_s3_storage_service
                storage_service = get_s3_storage_service()
                if storage_service:
                    print("✅ Using S3 Storage")
                    return storage_service
            
            # Fallback to Supabase if S3 not available
            if settings.supabase_url and settings.supabase_key:
                storage_service = StorageService()
                print("✅ Using Supabase Storage")
            else:
                print("⚠️ No storage configured (missing AWS or Supabase credentials)")
        except Exception as e:
            print(f"❌ Failed to initialize storage: {e}")
            print("🔄 App will continue without storage functionality")
            storage_service = None
    return storage_service

# Try to initialize on import, but don't crash if it fails
try:
    # Try S3 first
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        from app.services.s3_storage import get_s3_storage_service
        storage_service = get_s3_storage_service()
        if storage_service:
            print("✅ S3 Storage initialized successfully")
    # Fallback to Supabase
    elif settings.supabase_url and settings.supabase_key:
        storage_service = StorageService()
        print("✅ Supabase Storage initialized successfully")
    else:
        print("⚠️ No storage service configured")
except Exception as e:
    print(f"⚠️ Storage initialization failed: {e}")
    print("🔄 Storage will be disabled until configuration issues are resolved")
    storage_service = None 