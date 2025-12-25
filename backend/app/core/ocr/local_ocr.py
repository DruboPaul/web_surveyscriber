"""
Local OCR Engine
Wrapper for locally installed OCR software (Tesseract, etc.)
"""

import subprocess
import tempfile
import os
from pathlib import Path


class LocalOCR:
    """
    Wrapper for locally installed OCR executables.
    
    Works with any OCR that accepts an image path and outputs text.
    Default assumes Tesseract-like command: ocr_exe image_path stdout
    
    Supported OCR tools:
    - Tesseract: tesseract.exe image stdout -l eng
    - Other CLI OCR tools with similar interface
    """
    
    def __init__(self, executable_path: str, lang: str = "eng"):
        """
        Initialize local OCR wrapper.
        
        Args:
            executable_path: Full path to OCR executable
            lang: Language code (default: "eng" for Tesseract)
        """
        self.executable_path = executable_path
        self.lang = lang
        
        # Validate executable exists
        if not os.path.exists(executable_path):
            raise FileNotFoundError(f"OCR executable not found: {executable_path}")
    
    def get_text(self, image_path: str) -> str:
        """
        Run local OCR on image and return extracted text.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text from the image
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Detect OCR type from executable name
        exe_name = os.path.basename(self.executable_path).lower()
        
        try:
            if 'tesseract' in exe_name:
                # Tesseract command: tesseract input.png stdout -l eng
                result = subprocess.run(
                    [self.executable_path, str(image_path), 'stdout', '-l', self.lang],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            else:
                # Generic command: ocr_exe input.png
                # Assumes OCR outputs to stdout
                result = subprocess.run(
                    [self.executable_path, str(image_path)],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                raise Exception(f"OCR failed: {error_msg}")
            
            return result.stdout.strip()
            
        except subprocess.TimeoutExpired:
            raise Exception("Local OCR timed out (120s)")
        except FileNotFoundError:
            raise Exception(f"OCR executable not found: {self.executable_path}")
        except Exception as e:
            raise Exception(f"Local OCR error: {e}")


# Check if module is available
LOCAL_OCR_AVAILABLE = True
