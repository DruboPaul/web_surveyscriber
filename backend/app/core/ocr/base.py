class OCREngine:
    """
    Base class for all OCR engines.
    Any OCR engine must implement the run() method.
    """

    def run(self, image_path: str) -> str:
        raise NotImplementedError("OCR engine must implement run()")
