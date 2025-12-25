"""
Database Storage Service - Flexible SQLite/PostgreSQL/MySQL support

Saves extraction history to the configured database.
Uses SQLite by default, can be configured for external databases.
"""

from sqlalchemy.orm import Session
from backend.app.db.database import get_session_local
from backend.app.db.models import Batch, Document, ExtractionHistory
from backend.app.api.routes_settings import load_settings
import json


def is_history_enabled() -> bool:
    """Check if history tracking is enabled in settings."""
    settings = load_settings()
    return settings.get("enable_history", True)


def get_db() -> Session:
    """Get a database session."""
    SessionLocal = get_session_local()
    return SessionLocal()


def create_batch(batch_id: str, total_files: int, custom_filename: str = None):
    """Create a new batch record."""
    if not is_history_enabled():
        return
    
    try:
        db = get_db()
        batch = Batch(
            id=batch_id,
            total_files=total_files,
            custom_filename=custom_filename
        )
        db.add(batch)
        db.commit()
        db.close()
    except Exception as e:
        print(f"⚠️ Failed to create batch record: {e}")


def save_document(batch_id: str, filename: str, extracted: dict, status: str = "success", error_message: str = None):
    """Save a document extraction record."""
    if not is_history_enabled():
        return
    
    try:
        db = get_db()
        doc = Document(
            batch_id=batch_id,
            filename=filename,
            extracted_data_json=json.dumps(extracted) if extracted else None,
            status=status,
            error_message=error_message
        )
        db.add(doc)
        db.commit()
        db.close()
    except Exception as e:
        print(f"⚠️ Failed to save document record: {e}")


def save_extraction_history(
    batch_id: str,
    total_images: int,
    successful: int,
    failed: int,
    output_filename: str = None,
    excel_path: str = None,
    csv_path: str = None,
    schema_fields: list = None
):
    """Save extraction history summary."""
    if not is_history_enabled():
        return
    
    try:
        db = get_db()
        history = ExtractionHistory(
            batch_id=batch_id,
            total_images=total_images,
            successful_extractions=successful,
            failed_extractions=failed,
            output_filename=output_filename,
            excel_path=excel_path,
            csv_path=csv_path,
            schema_fields=json.dumps(schema_fields) if schema_fields else None
        )
        db.add(history)
        db.commit()
        db.close()
    except Exception as e:
        print(f"⚠️ Failed to save extraction history: {e}")


def get_extraction_history(limit: int = 50) -> list:
    """Get recent extraction history."""
    if not is_history_enabled():
        return []
    
    try:
        db = get_db()
        history = db.query(ExtractionHistory).order_by(
            ExtractionHistory.created_at.desc()
        ).limit(limit).all()
        db.close()
        
        return [
            {
                "batch_id": h.batch_id,
                "total_images": h.total_images,
                "successful": h.successful_extractions,
                "failed": h.failed_extractions,
                "output_filename": h.output_filename,
                "created_at": h.created_at.isoformat() if h.created_at else None
            }
            for h in history
        ]
    except Exception as e:
        print(f"⚠️ Failed to get extraction history: {e}")
        return []
