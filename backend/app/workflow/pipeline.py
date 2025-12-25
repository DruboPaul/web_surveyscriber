from pathlib import Path

from backend.app.core.ocr.paddle_ocr import PaddleOCREngine
from backend.app.core.validation.rules import validate

# Initialize OCR engine once
ocr_engine = PaddleOCREngine()


def process_single_image(
    image_path: str,
    ocr_output_dir: str
) -> dict:
    """
    Process a single image:
    - Run OCR
    - Save OCR text
    - Return OCR result (dict)
    """

    # 1. Run OCR
    ocr_text = ocr_engine.run(image_path)

    # 2. Save OCR text
    image_name = Path(image_path).stem
    Path(ocr_output_dir).mkdir(parents=True, exist_ok=True)

    ocr_text_file = Path(ocr_output_dir) / f"{image_name}.txt"
    with open(ocr_text_file, "w", encoding="utf-8") as f:
        f.write(ocr_text)

    # 3. Validate (placeholder – will expand later)
    validated_data = validate({
        "raw_text": ocr_text
    })

    return validated_data
