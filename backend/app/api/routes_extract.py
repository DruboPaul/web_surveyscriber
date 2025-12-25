from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import platform
import re

# OCR Engines
from backend.app.core.ocr.google_vision import GoogleVisionOCR, GOOGLE_VISION_AVAILABLE
from backend.app.core.ocr.azure_ocr import AzureOCR, AZURE_VISION_AVAILABLE
from backend.app.core.ocr.custom_ocr import CustomOCR, CUSTOM_OCR_AVAILABLE
from backend.app.core.ocr.local_ocr import LocalOCR, LOCAL_OCR_AVAILABLE

# AI Extraction
from backend.app.core.ai.extractor import extract, extract_from_image
from backend.app.services.storage.local_excel import save_excel, save_csv
from backend.app.api.routes_settings import load_settings

# 🔹 PostgreSQL services
from backend.app.services.storage.postgres import (
    create_batch,
    save_document
)

# 🔹 Usage tracking
from backend.app.db.database import get_session_local
from backend.app.db.models import UsageHistory

# Note: Using FastAPI BackgroundTasks instead of Celery for simpler deployment

router = APIRouter(tags=["Extract"])

# Track current OCR language for reinitialization
_current_ocr_language = None

# OCR engines cache (lazy load)
ocr_engines = {
    "google": None,
    "azure": None,
    "custom": None,
    "local": None
}



def is_latin_text(text: str, threshold: float = 0.85) -> bool:
    """
    Check if OCR text is predominantly Latin/English characters.
    
    Returns True if >= threshold of alphabetic characters are Latin AND
    no non-Latin scripts are detected.
    Used to detect if we should use OCR flow (English) or Vision AI (non-English).
    
    Latin characters: A-Z, a-z, common extended Latin (with accents)
    Non-Latin: Bengali, Arabic, Hindi, Chinese, Japanese, Korean, etc.
    """
    if not text or not text.strip():
        return False  # Empty text = assume non-Latin, use vision
    
    # First, check for ANY non-Latin Unicode characters
    # These Unicode ranges cover common non-Latin scripts
    non_latin_patterns = [
        r'[\u0980-\u09FF]',  # Bengali
        r'[\u0900-\u097F]',  # Devanagari (Hindi)
        r'[\u0600-\u06FF]',  # Arabic
        r'[\u4E00-\u9FFF]',  # CJK (Chinese)
        r'[\u3040-\u309F]',  # Hiragana (Japanese)
        r'[\u30A0-\u30FF]',  # Katakana (Japanese)
        r'[\uAC00-\uD7AF]',  # Korean Hangul
        r'[\u0B80-\u0BFF]',  # Tamil
        r'[\u0C00-\u0C7F]',  # Telugu
        r'[\u0E00-\u0E7F]',  # Thai
        r'[\u0400-\u04FF]',  # Cyrillic (Russian)
    ]
    
    for pattern in non_latin_patterns:
        if re.search(pattern, text):
            print(f"   Non-Latin script detected (pattern: {pattern[:10]}...)")
            return False  # Non-Latin script found, use vision
    
    # Count Latin alphabetic characters vs all alphabetic characters
    # Latin ranges: Basic Latin (A-Z, a-z) + Latin Extended
    latin_pattern = re.compile(r'[A-Za-zÀ-ÿ]')
    # All Unicode letters
    all_letters = re.findall(r'\w', text)
    # Filter to only alphabetic (remove digits/underscores)
    alphabetic = [c for c in all_letters if c.isalpha()]
    
    if len(alphabetic) < 5:
        # Too few characters to determine - use vision to be safe
        print(f"   Too few alphabetic chars ({len(alphabetic)}) - using vision")
        return False
    
    latin_chars = latin_pattern.findall(text)
    latin_ratio = len(latin_chars) / len(alphabetic) if alphabetic else 0
    
    # Check for signs of garbled OCR (common when OCR fails on non-Latin text)
    # High ratio of special characters or very short meaningless words
    words = text.split()
    if words:
        avg_word_length = sum(len(w) for w in words) / len(words)
        # Garbled OCR often produces very short "words" 
        if avg_word_length < 2 and len(words) > 3:
            print(f"   Garbled OCR detected (avg word length: {avg_word_length:.1f}) - using vision")
            return False
    
    is_latin = latin_ratio >= threshold
    print(f"   Latin ratio: {latin_ratio:.2%} (threshold: {threshold:.0%}) -> {'Latin' if is_latin else 'Non-Latin'}")
    return is_latin


def get_ocr_engine(engine_name: str = None, settings: dict = None):
    """
    Get the specified OCR engine, loading from settings if not specified.
    
    Supports: none, google, azure, custom, local
    Returns None if engine_name is "none" (triggers AI Vision fallback).
    Raises exception if OCR configuration is invalid.
    """
    global _current_ocr_language
    
    # Load settings if not provided
    if settings is None:
        settings = load_settings()
    
    # Use settings OCR provider if not explicitly specified
    if engine_name is None:
        engine_name = settings.get("ocr_provider", "none")
    
    # Get configured language
    ocr_language = settings.get("ocr_language", "en")
    
    # Condition 3: User chose "none" - skip OCR, use AI Vision
    if engine_name == "none":
        print("[INFO] OCR provider set to 'none' - will use AI Vision directly")
        return None
    
    # Google Cloud Vision
    elif engine_name == "google":
        if not GOOGLE_VISION_AVAILABLE:
            raise Exception("Google Vision SDK not installed. Install with: pip install google-cloud-vision")
        
        api_key = settings.get("google_vision_key", "")
        if not api_key:
            raise Exception("Google Vision API key not configured")
        
        try:
            engine = GoogleVisionOCR(api_key=api_key, lang=ocr_language)
            print(f"Google Vision OCR initialized with language: {ocr_language}")
            return engine
        except Exception as e:
            raise Exception(f"Google Vision initialization failed: {e}")
    
    # Azure Computer Vision
    elif engine_name == "azure":
        if not AZURE_VISION_AVAILABLE:
            raise Exception("Azure Vision SDK not installed. Install with: pip install azure-cognitiveservices-vision-computervision")
        
        api_key = settings.get("azure_ocr_key", "")
        endpoint = settings.get("azure_ocr_endpoint", "")
        if not api_key or not endpoint:
            raise Exception("Azure OCR credentials (API key and endpoint) not configured")
        
        try:
            engine = AzureOCR(api_key=api_key, endpoint=endpoint, lang=ocr_language)
            print(f"Azure Computer Vision OCR initialized with language: {ocr_language}")
            return engine
        except Exception as e:
            raise Exception(f"Azure OCR initialization failed: {e}")
    
    # Custom OCR API
    elif engine_name == "custom":
        if not CUSTOM_OCR_AVAILABLE:
            raise Exception("Custom OCR module not available")
        
        endpoint = settings.get("custom_ocr_endpoint", "")
        api_key = settings.get("custom_ocr_key", "")
        if not endpoint:
            raise Exception("Custom OCR endpoint URL not configured")
        
        try:
            engine = CustomOCR(endpoint=endpoint, api_key=api_key, lang=ocr_language)
            print(f"Custom OCR initialized with endpoint: {endpoint[:50]}...")
            return engine
        except Exception as e:
            raise Exception(f"Custom OCR initialization failed: {e}")
    
    # Local/Desktop OCR
    elif engine_name == "local":
        if not LOCAL_OCR_AVAILABLE:
            raise Exception("Local OCR module not available")
        
        exe_path = settings.get("local_ocr_path", "")
        if not exe_path:
            raise Exception("Local OCR executable path not configured")
        
        try:
            engine = LocalOCR(executable_path=exe_path, lang=ocr_language)
            print(f"Local OCR initialized with executable: {exe_path}")
            return engine
        except Exception as e:
            raise Exception(f"Local OCR initialization failed: {e}")
    
    else:
        raise Exception(f"Unknown OCR provider: {engine_name}. Valid options: none, google, azure, custom, local")




class ExtractBatchRequest(BaseModel):
    batch_id: str
    schema: dict
    custom_filename: Optional[str] = None
    ocr_engine: Optional[str] = "paddle"  # "paddle", "google", or "azure"


class ExtractAsyncRequest(BaseModel):
    batch_id: str
    schema: dict
    custom_filename: Optional[str] = None
    ocr_engine: Optional[str] = "paddle"  # "paddle", "google", or "azure"


# ==========================================
# 🔄 ASYNC ENDPOINT (Background Processing)
# ==========================================
from fastapi import BackgroundTasks
import json
import time

# In-memory job store (Global dictionary)
JOBS = {}


def get_job_progress(job_id: str) -> dict:
    """Get job progress from in-memory store."""
    return JOBS.get(job_id, {"job_id": job_id, "status": "not_found"})


def update_job_progress(job_id: str, processed: int, total: int, status: str = "processing", stage: str = None, **extra):
    """Update job progress in in-memory store.
    
    Args:
        job_id: Unique job identifier
        processed: Number of images processed
        total: Total number of images
        status: Job status (queued, processing, completed, error:*)
        stage: Current processing stage for detailed UI feedback
        **extra: Additional data (error_message, file paths, etc.)
    """
    progress_data = {
        "job_id": job_id,
        "processed": processed,
        "total": total,
        "percentage": round((processed / total) * 100, 1) if total > 0 else 0,
        "status": status,
        "stage": stage,
        **extra
    }
    JOBS[job_id] = progress_data
    return progress_data


def process_batch_background(job_id: str, batch_id: str, schema: dict, custom_filename: str = None):
    """
    Background task that processes images and updates Redis with progress.
    This runs in a thread, allowing the endpoint to return immediately.
    """
    import time as time_module
    start_time = time_module.time()
    
    batch_dir = os.path.join("data/uploads", batch_id)
    files = [f for f in os.listdir(batch_dir) if os.path.isfile(os.path.join(batch_dir, f))]
    total = len(files)
    
    print(f"\n[BACKGROUND JOB] Starting: {job_id}")
    print(f"   Batch: {batch_id}, Images: {total}")
    
    # Update status to processing with initial stage
    update_job_progress(job_id, 0, total, "processing", stage="Initializing... Please wait patiently 🙏")
    
    # Load settings
    settings = load_settings()
    
    results = []
    
    # Check if schema contains non-Latin field names (Bengali, Hindi, Arabic, etc.)
    # If so, force Vision AI for all images in this batch
    schema_text = " ".join(schema.keys())
    schema_is_non_latin = not is_latin_text(schema_text, threshold=0.5)
    if schema_is_non_latin:
        print(f"   Schema contains non-Latin field names -> Will use Vision AI for all images")
    
    for i, filename in enumerate(files, 1):
        image_path = os.path.join(batch_dir, filename)
        
        print(f"\nImage [{i}/{total}] Processing: {filename}")
        
        # Track processing status for error reporting
        ocr_status = "skipped"
        ocr_warning = None
        ai_status = "pending"
        
        # Update progress stage
        if i == 1:
            update_job_progress(job_id, i-1, total, "processing", 
                stage="🔄 Initializing... (first image may take longer)")
        else:
            update_job_progress(job_id, i-1, total, "processing",
                stage=f"📷 Processing image {i}/{total}: {filename[:20]}...")
        
        # Step 1: OCR (or skip if "none" or schema is non-Latin)
        ocr_text = ""
        if not schema_is_non_latin:
            try:
                # Get OCR engine (returns None if ocr_provider="none")
                engine = get_ocr_engine(settings=settings)
                
                if engine is not None:
                    # Condition 1: OCR is configured
                    update_job_progress(job_id, i-1, total, "processing",
                        stage=f"🔍 Running OCR on image {i}/{total}...")
                    ocr_text = engine.get_text(image_path)
                    ocr_status = "success" if ocr_text.strip() else "empty"
                    print(f"   OCR completed: {len(ocr_text)} chars extracted")
                else:
                    # Condition 3: User chose "none" - skip OCR
                    ocr_status = "skipped"
                    print(f"   OCR skipped (provider=none) -> using AI Vision")
                    
            except Exception as ocr_error:
                # Condition 2: OCR failed - will fallback to AI Vision
                ocr_status = "failed"
                ocr_warning = f"⚠️ OCR failed: {str(ocr_error)[:100]}. Using AI Vision instead."
                print(f"   [WARN] {ocr_warning}")
        else:
            ocr_status = "skipped"
            print(f"   OCR skipped (non-Latin schema) -> using AI Vision")

        
        # Step 2: AI extraction (text-based or Vision AI)
        try:
            token_usage = None
            
            # Update stage: AI Processing
            update_job_progress(job_id, i-1, total, "processing",
                stage=f"🤖 Analyzing image {i}/{total} with AI...")
            
            # Decide extraction method based on OCR results
            use_vision_ai = (
                schema_is_non_latin or  # Non-Latin schema
                ocr_status in ("skipped", "failed", "empty") or  # No OCR text
                not is_latin_text(ocr_text)  # Non-Latin OCR text
            )
            
            if use_vision_ai:
                # Use Vision AI (direct image analysis)
                if ocr_warning:
                    print(f"   Fallback: {ocr_warning}")
                else:
                    print(f"   Using AI Vision directly (OCR status: {ocr_status})")
                
                update_job_progress(job_id, i-1, total, "processing",
                    stage=f"🌍 AI Vision analyzing image {i}/{total}...")
                
                extracted, token_usage = extract_from_image(
                    image_path=image_path,
                    schema=schema,
                    api_key=settings.get("ai_api_key") or settings.get("openai_api_key"),
                    provider=settings.get("ai_provider", "openai"),
                    custom_endpoint=settings.get("custom_endpoint"),
                    custom_model=settings.get("custom_model")
                )
            else:
                # Use OCR text + AI extraction (more cost-effective)
                print(f"   Using OCR text + AI extraction")
                update_job_progress(job_id, i-1, total, "processing",
                    stage=f"📝 Extracting data from OCR text... ({i}/{total})")
                
                extracted, token_usage = extract(
                    text=ocr_text,
                    schema=schema,
                    api_key=settings.get("ai_api_key") or settings.get("openai_api_key"),
                    provider=settings.get("ai_provider", "openai"),
                    custom_endpoint=settings.get("custom_endpoint"),
                    custom_model=settings.get("custom_model")
                )
            
            ai_status = "success"
            extracted["source_file"] = filename
            
            # Add OCR warning to result if there was a fallback
            if ocr_warning:
                extracted["_ocr_warning"] = ocr_warning
            
            # Add processing metadata
            extracted["_processing"] = {
                "ocr_status": ocr_status,
                "ai_status": ai_status,
                "used_vision_ai": use_vision_ai
            }
            
            # Add token usage to result if available
            if token_usage:
                extracted["_token_usage"] = token_usage
                total_tokens = token_usage.get("total_tokens", 0)
                print(f"   Tokens used: {total_tokens} ({token_usage.get('model', 'unknown')})")
            
            results.append(extracted)
            print(f"   [OK] Extracted: {list(extracted.keys())}")
            
            # Update stage: Success for this image
            update_job_progress(job_id, i, total, "processing",
                stage=f"✅ Completed {i}/{total} images...")

                
        except Exception as e:
            error_msg = str(e).lower()
            print(f"   [ERROR] Extraction failed: {e}")
            # Categorize errors for better frontend messaging
            if "401" in str(e) or "unauthorized" in error_msg or "invalid api key" in error_msg:
                update_job_progress(job_id, i, total, "error:invalid_key", 
                    stage="❌ API key is invalid",
                    error_message="API key is invalid. Check Settings.")
                return
            elif "429" in str(e) or "rate" in error_msg:
                update_job_progress(job_id, i, total, "error:rate_limit",
                    stage="❌ Rate limit exceeded", 
                    error_message="Rate limit exceeded. Wait and retry.")
                return
            elif "quota" in error_msg or "insufficient" in error_msg or "billing" in error_msg or "credit" in error_msg:
                update_job_progress(job_id, i, total, "error:insufficient_credits",
                    stage="❌ API credits exhausted",
                    error_message="API credits exhausted. Add credits to your account.")
                return
    
    # Save Excel & CSV
    if results:
        excel_path = save_excel(results, custom_filename)
        csv_path = save_csv(results, custom_filename)
        
        total_time = time_module.time() - start_time
        
        # Aggregate total token usage
        total_tokens_used = 0
        for r in results:
            if "_token_usage" in r:
                total_tokens_used += r["_token_usage"].get("total_tokens", 0)
        
        print(f"\n[BACKGROUND JOB] Complete!")
        print(f"   Records: {len(results)}, Time: {total_time:.1f}s")
        if total_tokens_used > 0:
            print(f"   Total tokens used: {total_tokens_used:,}")
        print(f"   Excel: {excel_path}")
        print(f"   CSV: {csv_path}")
        
        # Mark as complete with file paths
        update_job_progress(
            job_id, total, total, "completed",
            batch_id=batch_id,
            rows=len(results),
            excel_path=excel_path,
            csv_path=csv_path,
            total_tokens=total_tokens_used
        )
        
        # 💰 Save usage to database for reporting
        if total_tokens_used > 0:
            try:
                # Aggregate token usage details
                prompt_tokens = 0
                completion_tokens = 0
                model_used = None
                provider_used = None
                
                for r in results:
                    if "_token_usage" in r:
                        usage = r["_token_usage"]
                        prompt_tokens += usage.get("prompt_tokens", 0)
                        completion_tokens += usage.get("completion_tokens", 0)
                        if not model_used:
                            model_used = usage.get("model")
                
                settings = load_settings()
                provider_used = settings.get("ai_provider", "openai")
                
                # Save to database
                SessionLocal = get_session_local()
                session = SessionLocal()
                try:
                    cost_cents = UsageHistory.estimate_cost(total_tokens_used, model_used or "gpt-4o")
                    usage_record = UsageHistory(
                        batch_id=batch_id,
                        job_id=job_id,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens_used,
                        model=model_used,
                        provider=provider_used,
                        images_processed=len(results),
                        estimated_cost_cents=cost_cents
                    )
                    session.add(usage_record)
                    session.commit()
                    print(f"   Usage saved to database (est. cost: ${cost_cents/100:.4f})")
                finally:
                    session.close()
            except Exception as usage_err:
                print(f"   [WARN] Failed to save usage: {usage_err}")
    else:
        update_job_progress(job_id, total, total, "error:no_valid_data", error_message="No text could be extracted from the images.")


@router.post("/batch/async")
def extract_batch_async(payload: ExtractAsyncRequest, background_tasks: BackgroundTasks):
    """
    Start batch processing in background.
    Returns job_id immediately for progress tracking via polling.
    
    Use GET /batch/status/{job_id} to check progress.
    """
    batch_dir = os.path.join("data/uploads", payload.batch_id)
    
    if not os.path.exists(batch_dir):
        raise HTTPException(status_code=404, detail="Batch not found")
    
    files = [
        f for f in os.listdir(batch_dir)
        if os.path.isfile(os.path.join(batch_dir, f))
    ]
    
    if not files:
        raise HTTPException(status_code=400, detail="No images found in batch")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Initialize progress in Redis
    update_job_progress(job_id, 0, len(files), "queued")
    
    # Start background processing (runs in thread, non-blocking)
    background_tasks.add_task(
        process_batch_background,
        job_id=job_id,
        batch_id=payload.batch_id,
        schema=payload.schema,
        custom_filename=payload.custom_filename
    )
    
    return {
        "job_id": job_id,
        "batch_id": payload.batch_id,
        "total_images": len(files),
        "status": "queued",
        "message": "Job started. Use /batch/status/{job_id} to check progress."
    }


@router.get("/batch/status/{job_id}")
def get_batch_status(job_id: str):
    """
    Get progress and status of a batch processing job.
    
    Returns:
    - status: queued | processing | completed | error:*
    - processed: number of images processed
    - total: total number of images
    - percentage: completion percentage
    - excel_path / csv_path: (only when completed)
    """
    progress = get_job_progress(job_id)
    
    if progress.get("status") == "not_found":
        raise HTTPException(
            status_code=404, 
            detail="Job not found. It may have expired or doesn't exist."
        )
    
    return progress


# ==========================================
# ⚡ SYNC ENDPOINT (Original - for small batches)
# ==========================================
@router.post("/batch")
def extract_batch(payload: ExtractBatchRequest):
    """
    Synchronous batch processing (original behavior).
    Best for small batches (< 50 images).
    
    For large batches, use POST /batch/async instead.
    """
    import time
    start_time = time.time()
    
    print("\n" + "="*60)
    print("EXTRACTION STARTED")
    print("="*60)
    print(f"Batch ID: {payload.batch_id}")
    print(f"Schema fields: {list(payload.schema.keys())}")
    print(f"Custom filename: {payload.custom_filename or 'auto-generated'}")
    print("="*60 + "\n")

    batch_dir = os.path.join("data/uploads", payload.batch_id)

    if not os.path.exists(batch_dir):
        print("[ERROR] Batch directory not found!")
        raise HTTPException(status_code=404, detail="Batch not found")

    files = [
        f for f in os.listdir(batch_dir)
        if os.path.isfile(os.path.join(batch_dir, f))
    ]

    if not files:
        print("[ERROR] No images found in batch!")
        raise HTTPException(status_code=400, detail="No images found in batch")

    print(f"Found {len(files)} images to process")
    print("-"*60)

    # 1️⃣ Create batch record in PostgreSQL
    print("\n[STEP 1/5] Creating database batch record...")
    try:
        create_batch(
            batch_id=payload.batch_id,
            total_files=len(files)
        )
        print("[OK] Database batch record created")
    except Exception as e:
        print(f"[WARN] Database warning: {e}")

    # Load user settings for OCR and AI
    settings = load_settings()
    ocr_provider = settings.get("ocr_provider", "paddle")
    ai_provider = settings.get("ai_provider", "openai")
    print(f"\nSettings loaded:")
    print(f"   • OCR Engine: {ocr_provider}")
    print(f"   • AI Provider: {ai_provider}")
    print("-"*60)

    results = []
    
    print("\n[STEP 2/5] Starting OCR + AI Extraction...\n")

    for i, filename in enumerate(files, 1):
        image_path = os.path.join(batch_dir, filename)
        img_start = time.time()

        # Progress header
        print(f"\n{'─'*50}")
        print(f"Image {i}/{len(files)}: {filename}")
        print(f"{'─'*50}")

        # 2️⃣ OCR
        print(f"   OCR ({ocr_provider}) starting...")
        selected_engine = get_ocr_engine(payload.ocr_engine, settings)
        ocr_text = selected_engine.get_text(image_path)
        ocr_time = time.time() - img_start
        
        text_preview = ocr_text[:80].replace('\n', ' ') + ('...' if len(ocr_text) > 80 else '') if ocr_text.strip() else "(empty)"
        print(f"   [OK] OCR complete ({ocr_time:.2f}s) - {len(ocr_text)} chars")
        print(f"   Text preview: \"{text_preview}\"")

        # 3️⃣ AI Extraction - Auto-detect language and route
        ai_start = time.time()
        try:
            token_usage = None
            
            if ocr_text.strip() and is_latin_text(ocr_text):
                # English/Latin text → Use OCR + AI text extraction
                print(f"   Latin text detected -> Using AI text extraction ({ai_provider})")
                extracted, token_usage = extract(
                    text=ocr_text,
                    schema=payload.schema,
                    api_key=settings.get("ai_api_key") or settings.get("openai_api_key") or None,
                    provider=settings.get("ai_provider", "openai"),
                    custom_endpoint=settings.get("custom_endpoint"),
                    custom_model=settings.get("custom_model")
                )
            else:
                # Non-English/Mixed or empty OCR → Use Vision AI directly
                if not ocr_text.strip():
                    print(f"   Empty OCR -> Using Vision AI directly ({ai_provider})")
                else:
                    print(f"   Non-Latin text detected -> Using Vision AI ({ai_provider})")
                extracted, token_usage = extract_from_image(
                    image_path=image_path,
                    schema=payload.schema,
                    api_key=settings.get("ai_api_key") or settings.get("openai_api_key") or None,
                    provider=settings.get("ai_provider", "openai"),
                    custom_endpoint=settings.get("custom_endpoint"),
                    custom_model=settings.get("custom_model")
                )
            
            ai_time = time.time() - ai_start
            print(f"   [OK] AI extraction complete ({ai_time:.2f}s)")
            
            # Log token usage
            if token_usage:
                total_tokens = token_usage.get("total_tokens", 0)
                print(f"   Tokens used: {total_tokens} ({token_usage.get('model', 'unknown')})")
                extracted["_token_usage"] = token_usage
            
            print(f"   Extracted: {extracted}")
        except Exception as e:
            print(f"   [ERROR] AI extraction failed: {e}")
            continue

        extracted["source_file"] = filename

        # 4️⃣ Save to PostgreSQL
        print(f"   Saving to database...")
        try:
            save_document(
                batch_id=payload.batch_id,
                filename=filename,
                extracted=extracted
            )
            print(f"   [OK] Saved to database")
        except Exception as e:
            print(f"   [WARN] Database save warning: {e}")

        results.append(extracted)
        
        total_img_time = time.time() - img_start
        print(f"   Total time for this image: {total_img_time:.2f}s")
        print(f"   Progress: {i}/{len(files)} ({int(i/len(files)*100)}%)")

    print("\n" + "="*60)
    
    if not results:
        print("[ERROR] EXTRACTION FAILED: No valid data extracted from batch")
        raise HTTPException(
            status_code=400,
            detail="No valid data extracted from batch"
        )

    # 5️⃣ Save Excel & CSV
    print(f"\n[STEP 3/5] Generating Excel file...")
    excel_path = save_excel(results, payload.custom_filename)
    print(f"[OK] Excel saved: {excel_path}")
    
    print(f"\n[STEP 4/5] Generating CSV file...")
    csv_path = save_csv(results, payload.custom_filename)
    print(f"[OK] CSV saved: {csv_path}")

    total_time = time.time() - start_time
    
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE!")
    print("="*60)
    print(f"Total records extracted: {len(results)}")
    print(f"Total processing time: {total_time:.2f}s")
    print(f"Excel: {excel_path}")
    print(f"CSV: {csv_path}")
    print("="*60 + "\n")

    return {
        "batch_id": payload.batch_id,
        "rows": len(results),
        "excel_path": excel_path,
        "csv_path": csv_path
    }

