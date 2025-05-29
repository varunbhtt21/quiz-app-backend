from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from typing import List, Optional
from app.models.mcq_problem import MCQProblem
from app.models.user import User
from app.core.database import get_session
from app.utils.auth import get_current_admin
import json
import os
from datetime import datetime
import uuid
import csv
from io import StringIO
import requests
from urllib.parse import urlparse
import mimetypes

router = APIRouter()

# Configure upload directory
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

async def download_image_from_url(image_url: str) -> Optional[str]:
    """Download image from URL and save it locally. Returns the local image URL or None if failed."""
    try:
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
        
        # Determine file extension
        content_type_to_ext = {
            'image/jpeg': '.jpg',
            'image/png': '.png', 
            'image/gif': '.gif',
            'image/webp': '.webp'
        }
        
        file_extension = content_type_to_ext.get(content_type)
        if not file_extension:
            # Try to get extension from URL
            file_extension = os.path.splitext(parsed_url.path)[1]
            if file_extension not in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                file_extension = '.jpg'  # Default
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Check file size (max 10MB)
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:
            return None
        
        # Save file
        with open(file_path, 'wb') as f:
            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                downloaded_size += len(chunk)
                if downloaded_size > 10 * 1024 * 1024:  # 10MB limit
                    os.remove(file_path)  # Clean up partial file
                    return None
                f.write(chunk)
        
        return f"/uploads/{unique_filename}"
        
    except Exception as e:
        print(f"Error downloading image from {image_url}: {str(e)}")
        return None

@router.post("/mcq")
async def create_mcq(
    title: str = Form(...),
    description: str = Form(...),
    option_a: str = Form(...),
    option_b: str = Form(...),
    option_c: str = Form(...),
    option_d: str = Form(...),
    correct_options: str = Form(...),
    explanation: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    # Validate correct_options
    try:
        correct_options_list = json.loads(correct_options)
        if not isinstance(correct_options_list, list):
            raise ValueError("correct_options must be a JSON array")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid correct_options format")

    # Handle image upload if provided
    image_url = None
    if image:
        # Generate unique filename
        file_extension = os.path.splitext(image.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = await image.read()
            buffer.write(content)
        
        # Store the relative path as the image URL
        image_url = f"/uploads/{unique_filename}"

    # Create MCQ
    mcq = MCQProblem(
        title=title,
        description=description,
        option_a=option_a,
        option_b=option_b,
        option_c=option_c,
        option_d=option_d,
        correct_options=correct_options,
        explanation=explanation,
        image_url=image_url,
        created_by=current_user.id
    )

    session.add(mcq)
    session.commit()
    session.refresh(mcq)

    return mcq

@router.put("/mcq/{mcq_id}")
async def update_mcq(
    mcq_id: str,
    title: str = Form(...),
    description: str = Form(...),
    option_a: str = Form(...),
    option_b: str = Form(...),
    option_c: str = Form(...),
    option_d: str = Form(...),
    correct_options: str = Form(...),
    explanation: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    # Get existing MCQ
    mcq = session.get(MCQProblem, mcq_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")

    # Validate correct_options
    try:
        correct_options_list = json.loads(correct_options)
        if not isinstance(correct_options_list, list):
            raise ValueError("correct_options must be a JSON array")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid correct_options format")

    # Handle image upload if provided
    if image:
        # Delete old image if exists
        if mcq.image_url:
            old_image_path = os.path.join(UPLOAD_DIR, os.path.basename(mcq.image_url))
            if os.path.exists(old_image_path):
                os.remove(old_image_path)

        # Generate unique filename
        file_extension = os.path.splitext(image.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save the file
        with open(file_path, "wb") as buffer:
            content = await image.read()
            buffer.write(content)
        
        # Update image URL
        mcq.image_url = f"/uploads/{unique_filename}"

    # Update MCQ fields
    mcq.title = title
    mcq.description = description
    mcq.option_a = option_a
    mcq.option_b = option_b
    mcq.option_c = option_c
    mcq.option_d = option_d
    mcq.correct_options = correct_options
    mcq.explanation = explanation
    mcq.updated_at = datetime.utcnow()

    session.add(mcq)
    session.commit()
    session.refresh(mcq)

    return mcq

@router.get("/mcq/")
def get_mcqs(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get list of MCQs with pagination and search"""
    statement = select(MCQProblem)
    
    if search:
        statement = statement.where(
            MCQProblem.title.contains(search) | 
            MCQProblem.description.contains(search)
        )
    
    statement = statement.offset(skip).limit(limit).order_by(MCQProblem.created_at.desc())
    mcqs = session.exec(statement).all()
    
    return mcqs

@router.get("/mcq/{mcq_id}")
def get_mcq(
    mcq_id: str,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Get a specific MCQ"""
    mcq = session.get(MCQProblem, mcq_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")
    
    return mcq

@router.delete("/mcq/{mcq_id}")
def delete_mcq(
    mcq_id: str,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Delete an MCQ"""
    mcq = session.get(MCQProblem, mcq_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")
    
    # Delete associated image if exists
    if mcq.image_url:
        image_path = os.path.join(UPLOAD_DIR, os.path.basename(mcq.image_url))
        if os.path.exists(image_path):
            os.remove(image_path)
    
    session.delete(mcq)
    session.commit()
    
    return {"message": "MCQ deleted successfully"}

@router.post("/mcq/{mcq_id}/upload-image")
async def upload_mcq_image(
    mcq_id: str,
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Upload or update image for an existing MCQ (quick upload from table)"""
    # Get existing MCQ
    mcq = session.get(MCQProblem, mcq_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")
    
    # Validate image file
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Check file size (5MB limit)
    content = await image.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image size must be less than 5MB")
    
    # Delete old image if exists
    if mcq.image_url:
        old_image_path = os.path.join(UPLOAD_DIR, os.path.basename(mcq.image_url))
        if os.path.exists(old_image_path):
            os.remove(old_image_path)
    
    # Generate unique filename
    file_extension = os.path.splitext(image.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save the file
    with open(file_path, "wb") as buffer:
        buffer.write(content)
    
    # Update MCQ with new image URL
    mcq.image_url = f"/uploads/{unique_filename}"
    mcq.updated_at = datetime.utcnow()
    
    session.add(mcq)
    session.commit()
    session.refresh(mcq)
    
    return {
        "message": "Image uploaded successfully",
        "image_url": mcq.image_url,
        "mcq_id": mcq.id,
        "title": mcq.title
    }

@router.delete("/mcq/{mcq_id}/remove-image")
async def remove_mcq_image(
    mcq_id: str,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Remove image from an existing MCQ"""
    # Get existing MCQ
    mcq = session.get(MCQProblem, mcq_id)
    if not mcq:
        raise HTTPException(status_code=404, detail="MCQ not found")
    
    if not mcq.image_url:
        raise HTTPException(status_code=400, detail="MCQ has no image to remove")
    
    # Delete image file
    image_path = os.path.join(UPLOAD_DIR, os.path.basename(mcq.image_url))
    if os.path.exists(image_path):
        os.remove(image_path)
    
    # Update MCQ to remove image URL
    mcq.image_url = None
    mcq.updated_at = datetime.utcnow()
    
    session.add(mcq)
    session.commit()
    session.refresh(mcq)
    
    return {
        "message": "Image removed successfully",
        "mcq_id": mcq.id,
        "title": mcq.title
    }

@router.get("/mcq/template/download")
def download_mcq_template(
    current_user: User = Depends(get_current_admin)
):
    """Download CSV template for bulk MCQ import"""
    # Create CSV content
    output = StringIO()
    writer = csv.writer(output)
    
    # Write headers - now includes image_url
    writer.writerow([
        'title', 'description', 'option_a', 'option_b', 
        'option_c', 'option_d', 'correct_options', 'explanation', 'image_url'
    ])
    
    # Write sample data with image examples
    writer.writerow([
        'Sample Question 1',
        'What is 2 + 2?',
        '3',
        '4',
        '5',
        '6',
        'B',
        'Basic arithmetic: 2 + 2 = 4',
        ''  # No image for this question
    ])
    
    writer.writerow([
        'Sample Question 2 (Multiple Answers)',
        'Which of the following are programming languages?',
        'Python',
        'HTML',
        'JavaScript',
        'CSS',
        'A,C',
        'Python and JavaScript are programming languages, while HTML and CSS are markup/styling languages',
        'https://example.com/programming-languages.png'  # Example image URL
    ])
    
    writer.writerow([
        'Image Handling Instructions',
        'Leave image_url empty for no image, or provide a valid URL to download and store the image.',
        'Option A',
        'Option B', 
        'Option C',
        'Option D',
        'A',
        'Supported formats: JPG, PNG, GIF. Max size: 10MB per image.',
        'https://example.com/sample-image.jpg'
    ])
    
    # Get CSV content
    csv_content = output.getvalue()
    output.close()
    
    # Return as file download
    return StreamingResponse(
        iter([csv_content.encode()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mcq_template_with_images.csv"}
    )

@router.post("/mcq/bulk-import")
async def bulk_import_mcqs(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session)
):
    """Bulk import MCQs from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        content = await file.read()
        decoded = content.decode('utf-8')
        csv_reader = csv.DictReader(StringIO(decoded))
        
        created_problems = []
        errors = []
        successful = 0
        failed = 0
        total_rows = 0
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start from 2 because row 1 is headers
            total_rows += 1
            
            try:
                # Validate required fields
                required_fields = ['title', 'description', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_options']
                missing_fields = [field for field in required_fields if not row.get(field, '').strip()]
                
                if missing_fields:
                    errors.append(f"Row {row_num}: Missing required fields: {', '.join(missing_fields)}")
                    failed += 1
                    continue
                
                # Parse correct options
                correct_options_str = row['correct_options'].strip()
                if ',' in correct_options_str:
                    correct_options = [opt.strip().upper() for opt in correct_options_str.split(',')]
                else:
                    correct_options = [correct_options_str.upper()]
                
                # Validate correct options
                valid_options = ['A', 'B', 'C', 'D']
                invalid_options = [opt for opt in correct_options if opt not in valid_options]
                if invalid_options:
                    errors.append(f"Row {row_num}: Invalid correct options: {', '.join(invalid_options)}. Must be A, B, C, or D")
                    failed += 1
                    continue
                
                # Check for duplicate titles
                existing_mcq = session.exec(
                    select(MCQProblem).where(MCQProblem.title == row['title'].strip())
                ).first()
                
                if existing_mcq:
                    errors.append(f"Row {row_num}: Question with title '{row['title'].strip()}' already exists")
                    failed += 1
                    continue
                
                # Handle image URL if provided
                image_url = None
                if row.get('image_url', '').strip():
                    image_url_input = row['image_url'].strip()
                    try:
                        downloaded_image_url = await download_image_from_url(image_url_input)
                        if downloaded_image_url:
                            image_url = downloaded_image_url
                        else:
                            errors.append(f"Row {row_num}: Failed to download image from URL: {image_url_input}")
                            # Continue without image rather than failing the entire row
                    except Exception as e:
                        errors.append(f"Row {row_num}: Error processing image URL {image_url_input}: {str(e)}")
                        # Continue without image rather than failing the entire row
                
                # Create MCQ
                mcq = MCQProblem(
                    title=row['title'].strip(),
                    description=row['description'].strip(),
                    option_a=row['option_a'].strip(),
                    option_b=row['option_b'].strip(),
                    option_c=row['option_c'].strip(),
                    option_d=row['option_d'].strip(),
                    correct_options=json.dumps(correct_options),
                    explanation=row.get('explanation', '').strip() or None,
                    image_url=image_url,
                    created_by=current_user.id
                )
                
                session.add(mcq)
                session.flush()  # Flush to get the ID
                
                created_problems.append({
                    'id': mcq.id,
                    'title': mcq.title,
                    'correct_options': correct_options,
                    'has_image': bool(mcq.image_url),
                    'image_url': mcq.image_url
                })
                
                successful += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                failed += 1
        
        session.commit()
        
        return {
            'total_rows': total_rows,
            'successful': successful,
            'failed': failed,
            'errors': errors,
            'created_problems': created_problems
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

# ... rest of the existing code ... 