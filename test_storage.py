#!/usr/bin/env python3
"""
Test script for Supabase Storage functionality
"""
import os
import sys
from pathlib import Path

# Add app directory to path
sys.path.append(str(Path(__file__).parent))

from app.core.config import settings
from app.services.storage import storage_service

def test_storage_configuration():
    """Test if storage service is properly configured"""
    print("🔧 Testing Storage Configuration...")
    
    if not settings.supabase_url:
        print("❌ SUPABASE_URL not configured")
        return False
    
    if not settings.supabase_key:
        print("❌ SUPABASE_KEY not configured")
        return False
    
    if not storage_service:
        print("❌ Storage service not initialized")
        return False
    
    print(f"✅ Supabase URL: {settings.supabase_url}")
    print(f"✅ Storage Bucket: {settings.supabase_storage_bucket}")
    print("✅ Storage service initialized successfully")
    
    return True

def test_bucket_exists():
    """Test if the storage bucket exists"""
    print("\n🪣 Testing Storage Bucket...")
    
    if not storage_service:
        print("❌ Storage service not available")
        return False
    
    try:
        # Try to get bucket info - using the correct method
        bucket_info = storage_service.supabase.storage.get_bucket(storage_service.bucket_name)
        print(f"✅ Bucket '{storage_service.bucket_name}' exists")
        print(f"   Public: {bucket_info.public if hasattr(bucket_info, 'public') else 'Unknown'}")
        return True
    except Exception as e:
        print(f"❌ Failed to access bucket: {e}")
        return False

def print_usage():
    """Print usage instructions"""
    print("\n📋 Setup Instructions:")
    print("1. Set SUPABASE_URL in your .env file")
    print("2. Set SUPABASE_KEY in your .env file") 
    print("3. Make sure the storage bucket exists in your Supabase project")
    print("\nExample .env configuration:")
    print("SUPABASE_URL=https://your-project.supabase.co")
    print("SUPABASE_KEY=your-anon-key")

def main():
    """Main test function"""
    print("🧪 Supabase Storage Test")
    print("=" * 40)
    
    # Test configuration
    config_ok = test_storage_configuration()
    
    if not config_ok:
        print_usage()
        return
    
    # Test bucket access
    bucket_ok = test_bucket_exists()
    
    print("\n" + "=" * 40)
    if config_ok and bucket_ok:
        print("🎉 All tests passed! Storage is ready to use.")
    else:
        print("❌ Some tests failed. Please check your configuration.")

if __name__ == "__main__":
    main() 