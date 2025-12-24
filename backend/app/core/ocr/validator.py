from typing import List, Dict


MIN_LINE_CONFIDENCE = 0.60
MIN_IMAGE_CONFIDENCE = 0.65


def validate_ocr_output(ocr_lines: List[Dict]) -> List[Dict]:
    """
    Filters OCR lines based on confidence rules.
    """

    if not ocr_lines:
        return []

    # 1️⃣ Filter low-confidence lines
    valid_lines = [
        line for line in ocr_lines
        if line["confidence"] >= MIN_LINE_CONFIDENCE
        and line["text"].strip()
    ]

    if not valid_lines:
        return []

    # 2️⃣ Image-level confidence
    avg_confidence = sum(
        line["confidence"] for line in valid_lines
    ) / len(valid_lines)

    if avg_confidence < MIN_IMAGE_CONFIDENCE:
        return []

    return valid_lines
