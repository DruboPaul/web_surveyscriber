"""
Microsoft Azure Computer Vision OCR Provider.
Uses the Azure Cognitive Services Computer Vision API.
Requires: pip install azure-cognitiveservices-vision-computervision
"""

from typing import List, Dict
import time

try:
    from azure.cognitiveservices.vision.computervision import ComputerVisionClient
    from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
    from msrest.authentication import CognitiveServicesCredentials
    AZURE_VISION_AVAILABLE = True
except ImportError:
    AZURE_VISION_AVAILABLE = False

from backend.app.core.ocr.validator import validate_ocr_output


class AzureOCR:
    """Microsoft Azure Computer Vision OCR Engine."""
    
    def __init__(self, api_key: str, endpoint: str, lang: str = "auto"):
        """
        Initialize Azure OCR.
        
        Args:
            api_key: Azure Cognitive Services API key
            endpoint: Azure endpoint URL (e.g., https://YOUR_RESOURCE.cognitiveservices.azure.com)
            lang: Language hint for improved accuracy. "auto" = auto-detect.
        """
        if not AZURE_VISION_AVAILABLE:
            raise RuntimeError(
                "Azure Vision SDK is not installed. "
                "Run: pip install azure-cognitiveservices-vision-computervision"
            )
        
        if not api_key or not endpoint:
            raise ValueError("Azure OCR requires both api_key and endpoint")
        
        self.lang = lang if lang != "auto" else None  # None = auto-detect
        self.client = ComputerVisionClient(
            endpoint=endpoint,
            credentials=CognitiveServicesCredentials(api_key)
        )
    
    def run(self, image_path: str) -> List[Dict]:
        """
        Run OCR on a single image (RAW output).
        
        Returns:
            List of dicts with 'text' and 'confidence' keys.
        """
        with open(image_path, "rb") as image_file:
            # Start the Read operation with optional language hint
            read_response = self.client.read_in_stream(
                image_file, 
                language=self.lang,  # Pass language hint (None = auto-detect)
                raw=True
            )
        
        # Get operation location (URL with operation ID)
        read_operation_location = read_response.headers["Operation-Location"]
        operation_id = read_operation_location.split("/")[-1]
        
        # Wait for the operation to complete
        while True:
            read_result = self.client.get_read_result(operation_id)
            if read_result.status not in [OperationStatusCodes.running, OperationStatusCodes.not_started]:
                break
            time.sleep(0.5)
        
        outputs: List[Dict] = []
        
        if read_result.status == OperationStatusCodes.succeeded:
            for page in read_result.analyze_result.read_results:
                for line in page.lines:
                    # Azure Read API provides confidence per word
                    if hasattr(line, 'words') and line.words:
                        confidence_sum = sum(
                            word.confidence for word in line.words if hasattr(word, 'confidence')
                        )
                        avg_confidence = confidence_sum / len(line.words) if line.words else 0.85
                    else:
                        avg_confidence = 0.85  # Default confidence if not available
                    
                    if line.text.strip():
                        outputs.append({
                            "text": line.text.strip(),
                            "confidence": round(avg_confidence, 3)
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


# Convenience function
def run_ocr(image_path: str, api_key: str = None, endpoint: str = None) -> str:
    """
    Simple function to run Azure OCR.
    
    Args:
        image_path: Path to image file
        api_key: Azure API key
        endpoint: Azure endpoint URL
    
    Returns:
        Extracted text as string
    """
    if not api_key or not endpoint:
        return "Error: Azure OCR requires api_key and endpoint"
    
    try:
        engine = AzureOCR(api_key=api_key, endpoint=endpoint)
        return engine.get_text(image_path)
    except Exception as e:
        return f"Error: {str(e)}"
