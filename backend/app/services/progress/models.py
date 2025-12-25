from typing import List, Optional
from pydantic import BaseModel


class FileStatus(BaseModel):
    filename: str
    status: str           # pending | processing | done | error
    error: Optional[str] = None


class BatchStatus(BaseModel):
    batch_id: str
    total_files: int
    processed_files: int
    status: str           # pending | running | completed
    files: List[FileStatus]
