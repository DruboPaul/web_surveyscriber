from typing import List, Dict


class OCRValidator:
    def __init__(
        self,
        min_confidence: float = 0.6,
        min_lines: int = 2
    ):
        """
        min_confidence: minimum OCR confidence to accept a line
        min_lines: minimum number of valid lines to accept an image
        """
        self.min_confidence = min_confidence
        self.min_lines = min_lines

    def validate(self, ocr_lines: List[Dict]) -> List[Dict]:
        """
        Filter OCR lines based on confidence.
        """
        return [
            line
            for line in ocr_lines
            if line.get("confidence", 0) >= self.min_confidence
        ]

    def is_valid_image(self, valid_lines: List[Dict]) -> bool:
        """
        Decide whether an image is usable.
        """
        return len(valid_lines) >= self.min_lines
