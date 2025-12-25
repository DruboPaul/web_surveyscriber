"""
Settings API Routes - User-configurable API keys and OCR providers.
Settings are stored in ~/.surveyscriber/settings.json
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
import json
from pathlib import Path

router = APIRouter(tags=["Settings"])

# Settings file location
SETTINGS_DIR = Path.home() / ".surveyscriber"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "ai_provider": "openai",
    "ai_api_key": "",
    "openai_api_key": "",  # Legacy, for backwards compatibility
    "custom_endpoint": "",
    "custom_model": "",
    # OCR Settings
    "ocr_provider": "none",  # "none" | "google" | "azure" | "custom" | "local"
    "ocr_language": "en",
    "google_vision_key": "",
    "azure_ocr_key": "",
    "azure_ocr_endpoint": "",
    "custom_ocr_endpoint": "",
    "custom_ocr_key": "",
    "local_ocr_path": "",
    # Vision AI Settings
    "vision_ai_provider": "same",
    "vision_ai_key": "",
    # Python Runtime Settings
    "python_path": "",  # Path to external Python executable (empty = auto-detect)
    # Database settings
    "database_url": "",
    "enable_history": True
}


class SettingsModel(BaseModel):
    ai_provider: Optional[str] = "openai"
    ai_api_key: Optional[str] = ""
    openai_api_key: Optional[str] = ""
    custom_endpoint: Optional[str] = ""
    custom_model: Optional[str] = ""
    # OCR Settings
    ocr_provider: Optional[str] = "none"
    ocr_language: Optional[str] = "en"
    google_vision_key: Optional[str] = ""
    azure_ocr_key: Optional[str] = ""
    azure_ocr_endpoint: Optional[str] = ""
    custom_ocr_endpoint: Optional[str] = ""
    custom_ocr_key: Optional[str] = ""
    local_ocr_path: Optional[str] = ""
    # Vision AI Settings
    vision_ai_provider: Optional[str] = "same"
    vision_ai_key: Optional[str] = ""
    # Python Runtime
    python_path: Optional[str] = ""
    # Database settings
    database_url: Optional[str] = ""
    enable_history: Optional[bool] = True


def ensure_settings_dir():
    """Create settings directory if it doesn't exist."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    """Load settings from JSON file, return defaults if not found."""
    ensure_settings_dir()
    
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    
    try:
        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)
            # Merge with defaults to handle new fields
            result = DEFAULT_SETTINGS.copy()
            result.update(saved)
            return result
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> bool:
    """Save settings to JSON file."""
    ensure_settings_dir()
    
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
        return True
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {e}")


@router.get("/settings")
def get_settings():
    """
    Get current application settings.
    Returns all configured API keys and provider preferences.
    """
    settings = load_settings()
    
    # Mask API keys for security (only return if they exist)
    masked = settings.copy()
    for key in ["openai_api_key", "google_vision_key", "azure_ocr_key"]:
        if masked.get(key):
            masked[key + "_set"] = True  # Indicate key is set
            # Mask the key: show first 7 and last 4 chars
            val = masked[key]
            if len(val) > 12:
                masked[key] = val[:7] + "..." + val[-4:]
            else:
                masked[key] = "***"
    
    return masked


@router.get("/settings/raw")
def get_settings_raw():
    """
    Get current settings including full API keys.
    Used internally for extraction operations.
    """
    return load_settings()


@router.put("/settings")
def update_settings(payload: SettingsModel):
    """
    Update application settings.
    Saves API keys and provider preferences to local storage.
    """
    # Load existing settings
    current = load_settings()
    
    # Update only provided fields (don't overwrite with empty strings unless intentional)
    updates = payload.model_dump(exclude_unset=True)
    
    for key, value in updates.items():
        # Only update if value is provided (not None)
        if value is not None:
            current[key] = value
    
    save_settings(current)
    
    return {
        "success": True,
        "message": "Settings saved successfully",
        "settings": {
            "ai_provider": current.get("ai_provider"),
            "ocr_provider": current.get("ocr_provider"),
            "openai_api_key_set": bool(current.get("openai_api_key")),
            "google_vision_key_set": bool(current.get("google_vision_key")),
            "azure_ocr_key_set": bool(current.get("azure_ocr_key"))
        }
    }


@router.delete("/settings/key/{key_name}")
def clear_api_key(key_name: str):
    """
    Clear a specific API key from settings.
    """
    valid_keys = ["openai_api_key", "google_vision_key", "azure_ocr_key", "azure_ocr_endpoint"]
    
    if key_name not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Invalid key name. Must be one of: {valid_keys}")
    
    current = load_settings()
    current[key_name] = ""
    save_settings(current)
    
    return {"success": True, "message": f"{key_name} cleared"}


# ==========================================
# Database Settings Endpoints
# ==========================================

@router.get("/database/status")
def get_database_status():
    """
    Get current database connection status.
    Returns database type and connection info.
    """
    from backend.app.db.database import get_database_url, test_connection, mask_database_url
    
    settings = load_settings()
    current_url = get_database_url()
    
    # Test current connection
    result = test_connection()
    
    return {
        "database_url_configured": bool(settings.get("database_url")),
        "using_default_sqlite": current_url.startswith("sqlite"),
        "connection": result,
        "enable_history": settings.get("enable_history", True)
    }


@router.post("/database/test")
def test_database_connection(database_url: str = ""):
    """
    Test a database connection before saving.
    If no URL provided, tests the current/default connection.
    """
    from backend.app.db.database import test_connection, get_database_url
    
    url_to_test = database_url.strip() if database_url else get_database_url()
    
    return test_connection(url_to_test)


@router.post("/database/reset")
def reset_database_engine():
    """
    Reset database engine after changing database_url.
    Call this after saving new database settings.
    """
    from backend.app.db.database import reset_engine, init_database
    
    reset_engine()
    init_database()
    
    return {"success": True, "message": "Database engine reset and reinitialized"}


# ==========================================
# AI Provider Validation Endpoints
# ==========================================

from fastapi import Request

@router.post("/settings/test-ai")
def test_ai_connection(request: Request):
    """
    Test the currently configured AI provider API key.
    
    Accepts credentials from:
    1. Request headers (X-AI-Provider, X-AI-API-Key) - preferred for web security
    2. Fallback to server-stored settings (for desktop app)
    
    Returns: { valid: bool, provider: str, message: str }
    """
    # Try to get credentials from request headers first (secure per-user keys)
    provider = request.headers.get("X-AI-Provider", "")
    api_key = request.headers.get("X-AI-API-Key", "")
    custom_endpoint = request.headers.get("X-Custom-Endpoint", "")
    custom_model = request.headers.get("X-Custom-Model", "")
    
    # Fallback to server settings if no header credentials
    if not api_key and not provider:
        settings = load_settings()
        provider = settings.get("ai_provider", "openai")
        api_key = settings.get("ai_api_key") or settings.get("openai_api_key")
        custom_endpoint = settings.get("custom_endpoint", "")
        custom_model = settings.get("custom_model", "")
    
    # Default provider if still empty
    if not provider:
        provider = "openai"
    
    if not api_key and provider != "custom":
        return {
            "valid": False,
            "provider": provider,
            "message": "No API key configured. Please enter your API key and save settings first."
        }
    
    try:
        if provider == "openai":
            return _test_openai(api_key)
        elif provider == "anthropic":
            return _test_anthropic(api_key)
        elif provider == "google":
            return _test_google(api_key)
        elif provider == "custom":
            return _test_custom(api_key, custom_endpoint, custom_model)
        else:
            return {
                "valid": False,
                "provider": provider,
                "message": f"Unknown provider: {provider}"
            }
    except Exception as e:
        error_msg = str(e)
        # Parse common error types
        if "401" in error_msg or "Unauthorized" in error_msg or "Invalid API Key" in error_msg.lower():
            return {"valid": False, "provider": provider, "message": "Invalid API key. Please check your key."}
        elif "429" in error_msg or "rate" in error_msg.lower():
            return {"valid": False, "provider": provider, "message": "Rate limit exceeded. Wait and try again."}
        elif "quota" in error_msg.lower() or "insufficient" in error_msg.lower() or "billing" in error_msg.lower():
            return {"valid": False, "provider": provider, "message": "API credits exhausted. Add credits to your account."}
        else:
            return {"valid": False, "provider": provider, "message": f"Connection failed: {error_msg[:100]}"}


def _test_openai(api_key: str) -> dict:
    """Test OpenAI API connection."""
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key)
    # Make a minimal API call (list models is lightweight)
    models = client.models.list()
    # If we get here, the key works
    return {
        "valid": True,
        "provider": "openai",
        "message": "✅ OpenAI API key is valid and working!"
    }


def _test_anthropic(api_key: str) -> dict:
    """Test Anthropic Claude API connection."""
    try:
        import anthropic
    except ImportError:
        return {
            "valid": False,
            "provider": "anthropic",
            "message": "Anthropic SDK not installed. Run: pip install anthropic"
        }
    
    client = anthropic.Anthropic(api_key=api_key)
    # Make a minimal message request
    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}]
    )
    return {
        "valid": True,
        "provider": "anthropic",
        "message": "✅ Anthropic Claude API key is valid and working!"
    }


def _test_google(api_key: str) -> dict:
    """Test Google Gemini API connection."""
    try:
        import google.generativeai as genai
    except ImportError:
        return {
            "valid": False,
            "provider": "google",
            "message": "Google Generative AI SDK not installed. Run: pip install google-generativeai"
        }
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    # Make a minimal request
    response = model.generate_content("Hi")
    return {
        "valid": True,
        "provider": "google",
        "message": "✅ Google Gemini API key is valid and working!"
    }


def _test_custom(api_key: str, endpoint: str, model: str) -> dict:
    """Test custom OpenAI-compatible endpoint."""
    if not endpoint:
        return {
            "valid": False,
            "provider": "custom",
            "message": "No custom endpoint URL configured."
        }
    
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key or "not-needed", base_url=endpoint)
    # Try to list models
    try:
        models = client.models.list()
        return {
            "valid": True,
            "provider": "custom",
            "message": f"✅ Custom endpoint is responding! ({endpoint})"
        }
    except Exception as e:
        # Some endpoints don't support listing models, try a chat completion
        try:
            response = client.chat.completions.create(
                model=model or "gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            return {
                "valid": True,
                "provider": "custom",
                "message": f"✅ Custom endpoint is working! Model: {model or 'default'}"
            }
        except Exception as e2:
            raise e2


@router.get("/detect-python")
async def detect_python():
    """Auto-detect Python installations on the system."""
    import shutil
    import subprocess
    
    found_pythons = []
    
    # Check common Python locations
    python_names = ["python", "python3", "python3.11", "python3.10", "python3.9"]
    
    for name in python_names:
        path = shutil.which(name)
        if path:
            try:
                # Get Python version
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version = result.stdout.strip() or result.stderr.strip()
                found_pythons.append({
                    "path": path,
                    "version": version,
                    "name": name
                })
            except:
                found_pythons.append({
                    "path": path,
                    "version": "Unknown",
                    "name": name
                })
    
    # Also check for specific Windows paths
    import os
    import platform
    if platform.system() == "Windows":
        windows_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python311\python.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python310\python.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python39\python.exe"),
            r"C:\Python311\python.exe",
            r"C:\Python310\python.exe",
            r"C:\Python39\python.exe",
        ]
        for wpath in windows_paths:
            if os.path.exists(wpath) and not any(p["path"] == wpath for p in found_pythons):
                try:
                    result = subprocess.run([wpath, "--version"], capture_output=True, text=True, timeout=5)
                    version = result.stdout.strip() or result.stderr.strip()
                    found_pythons.append({"path": wpath, "version": version, "name": "python"})
                except:
                    pass
    
    return {
        "pythons": found_pythons,
        "recommended": found_pythons[0]["path"] if found_pythons else None
    }

