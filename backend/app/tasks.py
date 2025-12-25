"""
Celery Background Tasks for Survey Processing
Handles OCR and AI extraction in parallel workers
"""

import os
import json
import redis
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

from backend.app.celery_app import celery_app
from backend.app.core.ocr.paddle_ocr import PaddleOCREngine
from backend.app.core.ai.extractor import extract
from backend.app.services.storage.local_excel import save_excel, save_csv
from backend.app.services.storage.postgres import create_batch, save_document

# Redis client for progress tracking
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# OCR engine (will be initialized per worker)
ocr_engine = None


def get_ocr_engine():
    """Lazy initialization of OCR engine per worker"""
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = PaddleOCREngine()
    return ocr_engine


def update_job_progress(job_id: str, processed: int, total: int, status: str = "processing"):
    """Update job progress in Redis"""
    progress_data = {
        "job_id": job_id,
        "processed": processed,
        "total": total,
        "percentage": round((processed / total) * 100, 1) if total > 0 else 0,
        "status": status,
    }
    redis_client.set(f"job:{job_id}", json.dumps(progress_data), ex=86400)  # 24h expiry
    return progress_data


def get_job_progress(job_id: str) -> Dict[str, Any]:
    """Get job progress from Redis"""
    data = redis_client.get(f"job:{job_id}")
    if data:
        return json.loads(data)
    return {"job_id": job_id, "status": "not_found"}


def process_single_image(image_path: str, filename: str, schema: dict) -> Dict[str, Any]:
    """Process a single image: OCR + AI extraction"""
    engine = get_ocr_engine()
    
    # Run OCR
    ocr_text = engine.get_text(image_path)
    
    if not ocr_text.strip():
        return None  # Skip low-quality OCR
    
    # Run AI extraction
    extracted = extract(text=ocr_text, schema=schema)
    extracted["source_file"] = filename
    
    return extracted


@celery_app.task(bind=True, max_retries=3)
def process_batch_task(self, job_id: str, batch_id: str, schema: dict, custom_filename: str = None):
    """
    Background task to process a batch of images.
    Uses parallel processing for OCR and AI extraction.
    """
    batch_dir = os.path.join("data/uploads", batch_id)
    
    if not os.path.exists(batch_dir):
        update_job_progress(job_id, 0, 0, "error:batch_not_found")
        return {"error": "Batch not found"}
    
    files = [
        f for f in os.listdir(batch_dir)
        if os.path.isfile(os.path.join(batch_dir, f))
    ]
    
    if not files:
        update_job_progress(job_id, 0, 0, "error:no_images")
        return {"error": "No images found in batch"}
    
    total = len(files)
    update_job_progress(job_id, 0, total, "processing")
    
    # Create batch record in PostgreSQL
    try:
        create_batch(batch_id=batch_id, total_files=total)
    except Exception:
        pass  # Batch may already exist
    
    results = []
    processed = 0
    
    # Use ThreadPoolExecutor for parallel processing
    max_workers = min(4, os.cpu_count() or 2)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {
            executor.submit(
                process_single_image,
                os.path.join(batch_dir, filename),
                filename,
                schema
            ): filename
            for filename in files
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_file):
            filename = future_to_file[future]
            processed += 1
            
            try:
                extracted = future.result()
                
                if extracted:
                    results.append(extracted)
                    
                    # Save to PostgreSQL
                    try:
                        save_document(
                            batch_id=batch_id,
                            filename=filename,
                            extracted=extracted
                        )
                    except Exception:
                        pass  # Continue even if DB save fails
                        
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing {filename}: {e}")
            
            # Update progress
            update_job_progress(job_id, processed, total, "processing")
    
    if not results:
        update_job_progress(job_id, processed, total, "error:no_valid_data")
        return {"error": "No valid data extracted from batch", "processed": processed}
    
    # Save Excel & CSV
    try:
        excel_path = save_excel(results, custom_filename)
        csv_path = save_csv(results, custom_filename)
    except Exception as e:
        update_job_progress(job_id, processed, total, f"error:save_failed:{str(e)}")
        return {"error": f"Failed to save files: {str(e)}"}
    
    # Mark as complete
    final_progress = update_job_progress(job_id, total, total, "completed")
    
    # Store result paths in Redis
    result_data = {
        **final_progress,
        "batch_id": batch_id,
        "rows": len(results),
        "excel_path": excel_path,
        "csv_path": csv_path,
    }
    redis_client.set(f"job:{job_id}", json.dumps(result_data), ex=86400)
    
    return result_data
