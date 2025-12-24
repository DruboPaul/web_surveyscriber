import os
import json
from backend.app.services.progress.models import BatchStatus, FileStatus

PROGRESS_DIR = "data/progress"
os.makedirs(PROGRESS_DIR, exist_ok=True)


def _progress_file(batch_id: str) -> str:
    return os.path.join(PROGRESS_DIR, f"{batch_id}.json")


def init_batch(batch_id: str, filenames: list[str]):
    status = BatchStatus(
        batch_id=batch_id,
        total_files=len(filenames),
        processed_files=0,
        status="pending",
        files=[
            FileStatus(filename=f, status="pending")
            for f in filenames
        ]
    )
    save_status(status)


def save_status(status: BatchStatus):
    with open(_progress_file(status.batch_id), "w") as f:
        json.dump(status.dict(), f, indent=2)


def load_status(batch_id: str) -> BatchStatus:
    with open(_progress_file(batch_id)) as f:
        return BatchStatus(**json.load(f))


def update_file_status(
    batch_id: str,
    filename: str,
    new_status: str,
    error: str | None = None
):
    status = load_status(batch_id)

    for f in status.files:
        if f.filename == filename:
            f.status = new_status
            f.error = error

    status.processed_files = sum(
        1 for f in status.files if f.status in ("done", "error")
    )

    status.status = (
        "completed"
        if status.processed_files == status.total_files
        else "running"
    )

    save_status(status)
