# Manual S3 Bucket Policy Setup Guide

Your S3 integration is working! Images are being uploaded successfully to `quiz-master-storage`. However, they're not publicly accessible yet because we need to configure the bucket policy.

## Current Status ✅
- ✅ S3 bucket created: `quiz-master-storage`
- ✅ AWS credentials configured
- ✅ Images uploading successfully
- ⚠️ Images not publicly accessible (403 Forbidden)

## Manual Setup Required

Since your IAM user doesn't have `s3:PutBucketPolicy` permission (which is good for security), you need to set up the bucket policy manually through the AWS Console.

### Step 1: AWS Console Bucket Policy Setup

1. **Go to AWS S3 Console**
   - Open https://console.aws.amazon.com/s3/
   - Find and click on `quiz-master-storage` bucket

2. **Go to Permissions Tab**
   - Click on the **Permissions** tab
   - Scroll down to **Bucket policy** section

3. **Add Bucket Policy**
   - Click **Edit** in the Bucket policy section
   - Paste this policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadGetObject",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::quiz-master-storage/*"
        }
    ]
}
```

4. **Save Changes**
   - Click **Save changes**
   - AWS will show a warning about public access - click **Save** to confirm

### Step 2: Check Public Access Block Settings

1. **In the same Permissions tab**
   - Look for **Block public access (bucket settings)**
   - Click **Edit**

2. **Update Settings**
   - Ensure these are **UNCHECKED** (disabled):
     - ❌ Block public access to buckets and objects granted through new access control lists (ACLs)
     - ❌ Block public access to buckets and objects granted through any access control lists (ACLs)
     - ❌ Block public access to buckets and objects granted through new public bucket or access point policies
     - ❌ Block public access to buckets and objects granted through any public bucket or access point policies

3. **Save Changes**
   - Click **Save changes**
   - Type `confirm` when prompted
   - Click **Confirm**

## Alternative: Test Without Public Access

If you prefer to test the functionality first without making images publicly accessible, you can use presigned URLs instead. Your S3 integration is already working for uploads!

## Testing After Setup

Once you've completed the manual setup:

1. **Run the image upload test**:
   ```bash
   python test_image_upload.py
   ```

2. **Expected output**:
   - ✅ Image uploaded successfully
   - ✅ Image accessible (Status: 200)
   - ✅ Image deleted successfully

## Security Notes

- The bucket policy only allows **read** access to objects
- It doesn't allow listing bucket contents
- Write/delete permissions are still restricted to your IAM user
- This is the standard configuration for serving images in web applications

## Next Steps

After manual setup:
1. Run `python test_image_upload.py` to verify full functionality
2. Your quiz app will now be able to serve images from S3
3. All new image uploads will be publicly accessible via HTTPS URLs 