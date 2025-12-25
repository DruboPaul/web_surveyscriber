
from fastapi import APIRouter, UploadFile, File
from backend.app.workflow.batch_manager import create_batch

router = APIRouter()

@router.post("/process-images")
async def process_images(files: list[UploadFile] = File(...)):
    batch_id = await create_batch(files)
    return {"batch_id": batch_id}
