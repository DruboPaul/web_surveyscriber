"""
Custom OCR API Client
Connects to any REST API endpoint for OCR operations.
"""

import requests
import base64
from pathlib import Path


class CustomOCR:
    """
    Generic OCR client for custom REST API endpoints.
    
    Expected API format:
    - POST request with image in body (base64 or multipart)
    - Returns JSON with 'text' field or plain text
    """
    
    def __init__(self, endpoint: str, api_key: str = None, lang: str = "en"):
        self.endpoint = endpoint.rstrip('/')
        self.api_key = api_key
        self.lang = lang
    
    def get_text(self, image_path: str) -> str:
        """
        Send image to custom OCR API and return extracted text.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text from the image
        """
        if not self.endpoint:
            raise ValueError("Custom OCR endpoint not configured")
        
        # Read and encode image
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['X-API-Key'] = self.api_key  # Common alternative
        
        # Prepare payload (base64 encoded image)
        payload = {
            'image': base64.b64encode(image_data).decode('utf-8'),
            'language': self.lang
        }
        
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                timeout=60
            )
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                data = response.json()
                # Handle common response formats
                if isinstance(data, dict):
                    return data.get('text', '') or data.get('result', '') or data.get('ocr_text', '') or str(data)
                elif isinstance(data, str):
                    return data
                else:
                    return str(data)
            except:
                # If not JSON, return raw text
                return response.text
                
        except requests.exceptions.Timeout:
            raise Exception("Custom OCR request timed out (60s)")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Custom OCR request failed: {e}")


# Check if module is available
CUSTOM_OCR_AVAILABLE = True
