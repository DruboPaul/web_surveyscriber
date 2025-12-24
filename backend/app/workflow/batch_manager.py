import uuid
from pathlib import Path
from typing import List

from backend.app.workflow.pipeline import process_single_image


def create_batch(image_paths: List[str]) -> str:
    """
    Create and process a batch of images
    """
    batch_id = str(uuid.uuid4())

    # Define batch folders
    ocr_text_dir = f"data/ocr_text/batch_{batch_id}"

    total_images = len(image_paths)
    completed = 0

    print(f"[BATCH STARTED] {batch_id} | Total images: {total_images}")

    for image_path in image_paths:
        try:
            result = process_single_image(
                image_path=image_path,
                ocr_output_dir=ocr_text_dir
            )
            completed += 1

            print(f"[DONE] {image_path} ({completed}/{total_images})")

        except Exception as e:
            print(f"[FAILED] {image_path} | Error: {e}")

    print(f"[BATCH COMPLETED] {batch_id}")

    return batch_id
