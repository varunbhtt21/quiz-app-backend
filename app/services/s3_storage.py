import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from app.core.config import settings
import uuid
import os
from typing import Optional
import mimetypes
from fastapi import HTTPException, UploadFile
from urllib.parse import urlparse


class S3StorageService:
    def __init__(self):
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise ValueError("AWS Access Key ID and Secret Access Key must be configured")
        
        self.bucket_name = settings.aws_s3_bucket
        self.region = settings.aws_region
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=self.region
        )
        
        # Ensure bucket exists and is properly configured
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """Ensure the S3 bucket exists and is properly configured"""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"✅ S3 bucket '{self.bucket_name}' is accessible")
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                # Bucket doesn't exist, create it
                try:
                    if self.region == 'us-east-1':
                        # us-east-1 doesn't need location constraint
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    print(f"✅ Created S3 bucket: {self.bucket_name}")
                except Exception as create_error:
                    print(f"❌ Could not create bucket {self.bucket_name}: {create_error}")
                    raise
            else:
                print(f"❌ Error accessing bucket {self.bucket_name}: {e}")
                raise
    
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
        """Upload image to S3 and return public URL"""
        try:
            # Read file content
            content = await file.read()
            
            # Validate file
            self._validate_image_file(file, content)
            
            # Generate unique filename
            file_extension = self._get_file_extension(file.filename or "", file.content_type or "")
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = f"{folder}/{unique_filename}"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=file.content_type,
                CacheControl="max-age=3600"
                # Note: ACL removed as bucket has ACLs disabled and uses bucket policy for public access
            )
            
            # Generate public URL
            public_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_path}"
            
            return public_url
            
        except HTTPException:
            raise
        except ClientError as e:
            print(f"S3 upload error: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload image to S3")
        except Exception as e:
            print(f"Storage upload error: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload image")
    
    def delete_image(self, image_url: str) -> bool:
        """Delete image from S3 using its URL"""
        try:
            # Extract file path from URL
            # URL format: https://bucket-name.s3.region.amazonaws.com/path/to/file
            parsed_url = urlparse(image_url)
            
            # Check if this is our S3 bucket URL
            expected_host = f"{self.bucket_name}.s3.{self.region}.amazonaws.com"
            if parsed_url.netloc != expected_host:
                print(f"URL doesn't match our bucket: {image_url}")
                return False
            
            # Extract the file path (remove leading slash)
            file_path = parsed_url.path.lstrip('/')
            
            if not file_path:
                return False
            
            # Delete from S3
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_path
            )
            
            return True
            
        except ClientError as e:
            print(f"S3 delete error: {e}")
            return False
        except Exception as e:
            print(f"Storage delete error: {e}")
            return False
    
    def get_public_url(self, file_path: str) -> str:
        """Get public URL for a file in S3"""
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_path}"
    
    async def download_and_upload_from_url(self, image_url: str, folder: str = "mcq") -> Optional[str]:
        """Download image from URL and upload to S3"""
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
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_path,
                Body=content,
                ContentType=content_type,
                CacheControl="max-age=3600"
                # Note: ACL removed as bucket has ACLs disabled and uses bucket policy for public access
            )
            
            # Generate public URL
            public_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{file_path}"
            
            return public_url
            
        except Exception as e:
            print(f"Error downloading and uploading image from {image_url}: {str(e)}")
            return None


# Create a singleton instance with error handling
s3_storage_service = None

def get_s3_storage_service():
    """Get S3 storage service instance with lazy initialization and error handling"""
    global s3_storage_service
    if s3_storage_service is None:
        try:
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                s3_storage_service = S3StorageService()
                print("✅ S3 Storage initialized successfully")
            else:
                print("⚠️ S3 Storage not configured (missing AWS credentials)")
        except Exception as e:
            print(f"❌ Failed to initialize S3 Storage: {e}")
            print("🔄 App will continue without S3 storage functionality")
            s3_storage_service = None
    return s3_storage_service

# Try to initialize on import, but don't crash if it fails
try:
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        s3_storage_service = S3StorageService()
        print("✅ S3 Storage initialized successfully")
except Exception as e:
    print(f"⚠️ S3 Storage initialization failed: {e}")
    print("🔄 Storage will be disabled until AWS credentials are configured")
    s3_storage_service = None 