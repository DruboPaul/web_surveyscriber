from fastapi import APIRouter, UploadFile, File, Form
import os
import shutil
from uuid import uuid4
from typing import Optional

router = APIRouter()

UPLOAD_DIR = "data/uploads"

# ✅ Supported image formats
ALLOWED_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".jfif",
    ".heic"
)


@router.post("/images")
async def upload_images(
    files: list[UploadFile] = File(...),
    batch_id: Optional[str] = Form(None)  # ✅ Accept existing batch_id for chunked uploads
):
    """
    Upload one or multiple image files.
    Creates a batch directory and saves images inside it.
    If batch_id is provided, appends to existing batch (for chunked uploads).
    """
    import time
    start_time = time.time()
    
    print("\n" + "="*60)
    print("IMAGE UPLOAD STARTED")
    print("="*60)
    print(f"Received {len(files)} file(s)")
    print("-"*60)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    saved_files = []
    skipped_files = []
    
    # ✅ Use existing batch_id or create new one
    if batch_id and os.path.exists(os.path.join(UPLOAD_DIR, batch_id)):
        print(f"Appending to existing batch: {batch_id}")
    else:
        batch_id = str(uuid4())
        print(f"Created new batch: {batch_id}")

    batch_dir = os.path.join(UPLOAD_DIR, batch_id)
    os.makedirs(batch_dir, exist_ok=True)
    
    print(f"\nSaving files...")

    for i, file in enumerate(files, 1):
        # ✅ File type validation
        if not file.filename:
            continue

        if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
            skipped_files.append(file.filename)
            print(f"   [WARN] [{i}/{len(files)}] Skipped (unsupported): {file.filename}")
            continue  # Skip unsupported file types

        # ✅ Extract base filename
        base_filename = os.path.basename(file.filename)
        
        # ✅ Convert to JPG for compatibility (Fixes JFIF/HEIC issues)
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            import PIL.ImageOps
            
            # Reset file pointer just in case
            file.file.seek(0)
            
            image = Image.open(file.file)
            
            # ✅ STEP 1: Apply EXIF orientation first (if available)
            exif_applied = False
            try:
                original_size = image.size
                image = PIL.ImageOps.exif_transpose(image)
                if image.size != original_size:
                    exif_applied = True
                    print(f"   Applied EXIF orientation correction")
            except Exception as exif_err:
                pass  # No EXIF or failed, will try auto-detection
            
            image = image.convert("RGB")  # Convert RGBA/P to RGB
            
            # ✅ STEP 2: If no EXIF orientation was applied, try auto-detection
            # Save temp file for orientation detection
            if not exif_applied:
                try:
                    import tempfile
                    import numpy as np
                    
                    # Save temp file for PaddleOCR analysis
                    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                        temp_path = tmp.name
                        image.save(temp_path, "JPEG", quality=85)
                    
                    # Use PaddleOCR's orientation detection
                    from paddleocr import PaddleOCR
                    orientation_detector = PaddleOCR(
                        lang='en',
                        use_doc_orientation_classify=True,
                        use_textline_orientation=False,
                        use_doc_unwarping=False,
                    )
                    
                    # Get orientation
                    result = orientation_detector.predict(temp_path)
                    
                    # Check if rotation was detected
                    if result and len(result) > 0:
                        for page_result in result:
                            if isinstance(page_result, dict) and 'doc_preprocessor_res' in page_result:
                                preprocess = page_result.get('doc_preprocessor_res', {})
                                rotation = preprocess.get('output_orient_class', 0)
                                if rotation != 'UP' and rotation != 0:
                                    # Rotate image to correct orientation
                                    rotation_map = {'LEFT': 90, 'DOWN': 180, 'RIGHT': 270}
                                    if rotation in rotation_map:
                                        angle = rotation_map[rotation]
                                        image = image.rotate(-angle, expand=True)
                                        print(f"   Auto-rotated {angle} degrees to correct orientation")
                    
                    # Clean up temp file
                    os.unlink(temp_path)
                    
                except Exception as orient_err:
                    print(f"   [WARN] Auto-orientation detection skipped: {orient_err}")
            
            # Force .jpg extension
            base_filename = os.path.splitext(base_filename)[0] + ".jpg"
            file_path = os.path.join(batch_dir, base_filename)
            
            image.save(file_path, "JPEG", quality=95)
            print(f"   [OK] [{i}/{len(files)}] Converted & Saved: {base_filename}")
            
        except Exception as e:
            print(f"   [WARN] Conversion failed ({e}), saving original...")
            file_path = os.path.join(batch_dir, base_filename)
            file.file.seek(0)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            print(f"   [OK] [{i}/{len(files)}] Saved (Original): {base_filename}")

        saved_files.append(file_path)

    elapsed = time.time() - start_time
    
    print("\n" + "="*60)
    print("UPLOAD COMPLETE!")
    print("="*60)
    print(f"[OK] Saved: {len(saved_files)} files")
    if skipped_files:
        print(f"[WARN] Skipped: {len(skipped_files)} files (unsupported format)")
    print(f"Batch ID: {batch_id}")
    print(f"Time: {elapsed:.2f}s")
    print("="*60 + "\n")

    return {
        "batch_id": batch_id,
        "files": saved_files,
        "total_uploaded": len(saved_files)
    }

