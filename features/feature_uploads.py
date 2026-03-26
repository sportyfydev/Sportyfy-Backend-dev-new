"""
SportyFY - Image Upload Feature

Purpose:
This module provides endpoints for uploading and optimizing images for 
user profiles, training plans, and exercises. It uses Pillow for 
validation and optimization before uploading to Supabase Storage.

Application Context:
Shared utility feature for all modules requiring media assets.

Data Flow:
Client (File) -> feature_uploads.py (Optimization) -> Supabase Storage -> URL returned
"""

import io
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from PIL import Image, ImageSequence
from supabase import Client
from database import get_supabase
from dependencies import get_current_user

# Configure logger
logger = logging.getLogger(__name__)

router = APIRouter()

MAX_IMAGE_SIZE_PX = 1200
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}

def optimize_image(file_content: bytes, filename: str) -> tuple[bytes, str]:
    """
    Validates, resizes, and optimizes an image while preserving GIF animations.
    
    Returns:
        tuple: (optimized_content, content_type)
    """
    extension = filename.split(".")[-1].lower()
    img = Image.open(io.BytesIO(file_content))
    
    output = io.BytesIO()
    content_type = f"image/{extension}" if extension != "jpg" else "image/jpeg"
    
    # --- GIF Logic: Preserve Animation ---
    if extension == "gif":
        logger.info("Processing GIF - preserving animation frames.")
        # We don't resize GIFs to avoid breaking frames without complex logic.
        # Just ensure it's a valid GIF.
        img.save(output, format="GIF", save_all=True, loop=0)
        return output.getvalue(), "image/gif"
    
    # --- Standard Image Logic (JPEG/PNG) ---
    # Resize if too large while maintaining aspect ratio
    width, height = img.size
    if width > MAX_IMAGE_SIZE_PX or height > MAX_IMAGE_SIZE_PX:
        logger.info(f"Resizing image from {width}x{height}")
        img.thumbnail((MAX_IMAGE_SIZE_PX, MAX_IMAGE_SIZE_PX), Image.Resampling.LANCZOS)
    
    # Convert RGBA to RGB if saving as JPEG
    if img.mode in ("RGBA", "P") and extension in ("jpg", "jpeg"):
        img = img.convert("RGB")
        
    save_format = "JPEG" if extension in ("jpg", "jpeg") else "PNG"
    img.save(output, format=save_format, optimize=True, quality=85)
    
    return output.getvalue(), content_type

@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Upload and optimize an image file. 
    Supported formats: JPEG, PNG, GIF (animated).
    Max dimension: 1200px.
    """
    filename = file.filename
    extension = filename.split(".")[-1].lower()
    
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    try:
        content = await file.read()
        optimized_content, content_type = optimize_image(content, filename)
        
        # Unique filename to avoid collisions
        unique_name = f"{current_user['id']}/{uuid.uuid4()}.{extension}"
        
        # Upload to Supabase Storage 'uploads' bucket
        # Note: bucket name must exist.
        res = supabase.storage.from_("uploads").upload(
            path=unique_name,
            file=optimized_content,
            file_options={"content-type": content_type, "cache-control": "3600"}
        )
        
        # Get Public URL
        url_res = supabase.storage.from_("uploads").get_public_url(unique_name)
        
        return {"url": url_res}
        
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process or upload image: {str(e)}"
        )
