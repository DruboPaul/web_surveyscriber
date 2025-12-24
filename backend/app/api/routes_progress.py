from fastapi import APIRouter, HTTPException
from backend.app.services.progress.tracker import get_progress

router = APIRouter(prefix="/progress", tags=["Progress"])

@router.get("/{batch_id}")
def get_batch_progress(batch_id: str):
    progress = get_progress(batch_id)

    if not progress:
        raise HTTPException(status_code=404, detail="Batch not found")

    total = progress["total"]
    completed = progress["completed"]

    percent = round((completed / total) * 100, 2) if total else 0

    return {
        "batch_id": batch_id,
        "total": total,
        "completed": completed,
        "percent": percent
    }
