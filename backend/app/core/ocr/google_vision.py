"""
Google Cloud Vision OCR Provider.
Uses the Google Cloud Vision API for high-accuracy OCR.
Requires: pip install google-cloud-vision
"""

from typing import List, Dict
import os

try:
    from google.cloud import vision
    from google.oauth2 import service_account
    GOOGLE_VISION_AVAILABLE = True
except ImportError:
    GOOGLE_VISION_AVAILABLE = False

from backend.app.core.ocr.validator import validate_ocr_output


class GoogleVisionOCR:
    """Google Cloud Vision OCR Engine."""
    
    def __init__(self, api_key: str = None, credentials_path: str = None, lang: str = "auto"):
        """
        Initialize Google Vision OCR.
        
        Args:
            api_key: Google Cloud API key (for simple auth)
            credentials_path: Path to service account JSON file
            lang: Language hint (BCP-47 code) for improved accuracy. "auto" = no hint.
        """
        if not GOOGLE_VISION_AVAILABLE:
            raise RuntimeError(
                "Google Cloud Vision is not installed. "
                "Run: pip install google-cloud-vision"
            )
        
        self.api_key = api_key
        self.credentials_path = credentials_path
        self.lang = lang if lang != "auto" else None  # None = auto-detect
        
        # Initialize client
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
        elif api_key:
            # Use API key (simpler setup)
            self.client = vision.ImageAnnotatorClient(
                client_options={"api_key": api_key}
            )
        else:
            # Try default credentials (for GCP environments)
            try:
                self.client = vision.ImageAnnotatorClient()
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize Google Vision client: {e}. "
                    "Provide an API key or credentials file."
                )
    
    def run(self, image_path: str) -> List[Dict]:
        """
        Run OCR on a single image (RAW output).
        
        Returns:
            List of dicts with 'text' and 'confidence' keys.
        """
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        
        # Build image context with language hints if specified
        image_context = None
        if self.lang:
            image_context = vision.ImageContext(
                language_hints=[self.lang]
            )
        
        # Call document_text_detection with optional language hints
        if image_context:
            response = self.client.document_text_detection(image=image, image_context=image_context)
        else:
            response = self.client.document_text_detection(image=image)
        
        if response.error.message:
            raise RuntimeError(f"Google Vision API error: {response.error.message}")
        
        outputs: List[Dict] = []
        
        # Extract text blocks with confidence
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    text = ""
                    confidence_sum = 0
                    word_count = 0
                    
                    for word in paragraph.words:
                        word_text = "".join(
                            symbol.text for symbol in word.symbols
                        )
                        text += word_text + " "
                        confidence_sum += word.confidence
                        word_count += 1
                    
                    if text.strip() and word_count > 0:
                        outputs.append({
                            "text": text.strip(),
                            "confidence": round(confidence_sum / word_count, 3)
                        })
        
        return outputs
    
    def get_text(self, image_path: str) -> str:
        """
        Get VALIDATED OCR text as a single string.
        Applies confidence-based rejection rules.
        
        Returns:
            Multiline OCR text (safe for OpenAI)
        """
        raw_lines = self.run(image_path)
        
        # Apply validation
        valid_lines = validate_ocr_output(raw_lines)
        
        if not valid_lines:
            return ""
        
        return "\n".join(line["text"] for line in valid_lines)


# Convenience function for backwards compatibility
def run_ocr(image_path: str, api_key: str = None) -> str:
    """
    Simple function to run Google Vision OCR.
    
    Args:
        image_path: Path to image file
        api_key: Google Cloud API key
    
    Returns:
        Extracted text as string
    """
    if not api_key:
        return "Error: Google Vision API key not configured"
    
    try:
        engine = GoogleVisionOCR(api_key=api_key)
        return engine.get_text(image_path)
    except Exception as e:
        return f"Error: {str(e)}"
