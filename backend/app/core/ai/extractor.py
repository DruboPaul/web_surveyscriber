"""
Multi-Provider AI Extractor
Supports: OpenAI, Anthropic Claude, Google Gemini, and Custom OpenAI-compatible APIs
"""

import os
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Provider-specific imports (lazy loaded)
_openai_client = None
_anthropic_client = None
_google_client = None


def get_openai_client(api_key: str, base_url: str = None):
    """Get OpenAI client (also works for OpenAI-compatible APIs)."""
    from openai import OpenAI
    
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    
    return OpenAI(**kwargs)


def get_anthropic_client(api_key: str):
    """Get Anthropic Claude client."""
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        raise RuntimeError("Anthropic SDK not installed. Run: pip install anthropic")


def get_google_client(api_key: str):
    """Get Google Gemini client."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai
    except ImportError:
        raise RuntimeError("Google Generative AI SDK not installed. Run: pip install google-generativeai")


def extract_with_openai(text: str, schema: Dict[str, Any], api_key: str, 
                        base_url: str = None, model: str = "gpt-4o-mini") -> Dict[str, Any]:
    """Extract using OpenAI or OpenAI-compatible API."""
    client = get_openai_client(api_key, base_url)
    fields = ", ".join(schema.keys())

    prompt = f"""Extract the following fields from the OCR text below.

Fields:
{fields}

Rules:
- Return ONLY valid JSON
- Keys must EXACTLY match the field names
- If a value is missing, use null
- Do NOT add extra keys
- Do NOT use markdown or explanation

OCR Error Correction (IMPORTANT):
- The text comes from OCR which may have errors
- Common OCR mistakes: 'l' misread as 'i' or '1', 'O' as '0', 'rn' as 'm'
- For names: "Ai" is likely "Ali", "Moh" likely "Md.", "Tuhin" might be "Tohin"
- Use context and common sense to fix obvious OCR errors in names

Text:
\"\"\"
{text}
\"\"\""""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You extract structured document data."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    raw = response.choices[0].message.content.strip()
    
    # Remove markdown wrappers
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    
    # Capture token usage
    token_usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
        "model": model
    }
    
    return json.loads(raw), token_usage


def extract_with_anthropic(text: str, schema: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Extract using Anthropic Claude."""
    client = get_anthropic_client(api_key)
    fields = ", ".join(schema.keys())

    prompt = f"""Extract the following fields from the OCR text below.

Fields:
{fields}

Rules:
- Return ONLY valid JSON
- Keys must EXACTLY match the field names
- If a value is missing, use null
- Do NOT add extra keys
- Do NOT use markdown or explanation

OCR Error Correction (IMPORTANT):
- The text comes from OCR which may have errors
- Common OCR mistakes: 'l' misread as 'i' or '1', 'O' as '0', 'rn' as 'm'
- For names: "Ai" is likely "Ali", "Moh" likely "Md.", "Tuhin" might be "Tohin"
- Use context and common sense to fix obvious OCR errors in names

Text:
\"\"\"
{text}
\"\"\""""

    message = client.messages.create(
        model="claude-3-haiku-20240307",  # Fast and cheap
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    raw = message.content[0].text.strip()
    
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    
    # Capture token usage from Anthropic
    token_usage = {
        "prompt_tokens": message.usage.input_tokens if message.usage else 0,
        "completion_tokens": message.usage.output_tokens if message.usage else 0,
        "total_tokens": (message.usage.input_tokens + message.usage.output_tokens) if message.usage else 0,
        "model": "claude-3-haiku-20240307"
    }
    
    return json.loads(raw), token_usage


def extract_with_google(text: str, schema: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Extract using Google Gemini."""
    genai = get_google_client(api_key)
    fields = ", ".join(schema.keys())

    prompt = f"""Extract the following fields from the OCR text below.

Fields:
{fields}

Rules:
- Return ONLY valid JSON
- Keys must EXACTLY match the field names
- If a value is missing, use null
- Do NOT add extra keys
- Do NOT use markdown or explanation

OCR Error Correction (IMPORTANT):
- The text comes from OCR which may have errors
- Common OCR mistakes: 'l' misread as 'i' or '1', 'O' as '0', 'rn' as 'm'
- For names: "Ai" is likely "Ali", "Moh" likely "Md.", "Tuhin" might be "Tohin"
- Use context and common sense to fix obvious OCR errors in names

Text:
\"\"\"
{text}
\"\"\""""

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    
    raw = response.text.strip()
    
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    
    # Capture token usage from Gemini (estimates based on text length)
    token_usage = {
        "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
        "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
        "model": "gemini-1.5-flash"
    }
    
    return json.loads(raw), token_usage


def extract(text: str, schema: Dict[str, Any], 
            api_key: Optional[str] = None,
            provider: str = "openai",
            custom_endpoint: str = None,
            custom_model: str = None) -> Dict[str, Any]:
    """
    Extract structured fields from OCR text using configured AI provider.
    
    Args:
        text: OCR text to extract from
        schema: Dictionary defining expected fields
        api_key: API key for the provider
        provider: AI provider (openai, anthropic, google, custom)
        custom_endpoint: Custom API endpoint (for local LLMs)
        custom_model: Custom model name
        
    Returns:
        Tuple of (extracted_data, token_usage)
    """
    # Fall back to environment if no key provided
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key and provider != "custom":
        raise RuntimeError(f"API key not configured for {provider}. Set it in Settings.")

    token_usage = None
    
    try:
        if provider == "openai":
            data, token_usage = extract_with_openai(text, schema, api_key)
        elif provider == "anthropic":
            data, token_usage = extract_with_anthropic(text, schema, api_key)
        elif provider == "google":
            data, token_usage = extract_with_google(text, schema, api_key)
        elif provider == "custom":
            # Custom OpenAI-compatible endpoint
            model = custom_model or "gpt-3.5-turbo"
            data, token_usage = extract_with_openai(text, schema, api_key or "not-needed", 
                                       base_url=custom_endpoint, model=model)
        else:
            # Default to OpenAI
            data, token_usage = extract_with_openai(text, schema, api_key)
            
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"AI extraction failed ({provider}): {str(e)}")

    # Enforce schema strictly
    output = {}
    for key in schema.keys():
        output[key] = data.get(key)

    return output, token_usage


# ==========================================
# VISION-BASED EXTRACTION (for non-English)
# ==========================================

import base64


def encode_image_base64(image_path: str) -> str:
    """Encode image file to base64 string."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_media_type(image_path: str) -> str:
    """Get MIME type for image based on extension."""
    ext = image_path.lower().split(".")[-1]
    mime_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "jfif": "image/jpeg",
    }
    return mime_types.get(ext, "image/jpeg")


def extract_from_image_openai(image_path: str, schema: Dict[str, Any], api_key: str,
                               base_url: str = None, model: str = "gpt-4o") -> Dict[str, Any]:
    """Extract using OpenAI Vision (GPT-4o) directly from image."""
    client = get_openai_client(api_key, base_url)
    fields = ", ".join(schema.keys())
    
    # Encode image
    base64_image = encode_image_base64(image_path)
    media_type = get_image_media_type(image_path)
    
    # Simple, direct extraction prompt
    prompt = f"""Look at this image and extract the following information.

Fields to find: {fields}

Instructions:
- Read all text in the image (it may be handwritten in Bengali or English)
- If the image is rotated, read it correctly
- Return a JSON object with the field names as keys
- If you cannot find a value for a field, use null
- Only include the requested fields
- Return ONLY the JSON, no explanation

Example format: {{"field1": "value1", "field2": null}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a data extraction assistant. Extract information from images and return JSON."},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{media_type};base64,{base64_image}",
                    "detail": "high"
                }}
            ]}
        ],
        temperature=0,
        max_tokens=1024
    )

    raw = response.choices[0].message.content.strip()
    print(f"   📝 AI Response: {raw[:200]}{'...' if len(raw) > 200 else ''}")
    
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    
    # Capture token usage
    token_usage = {
        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
        "total_tokens": response.usage.total_tokens if response.usage else 0,
        "model": model
    }
    
    return json.loads(raw), token_usage


def extract_from_image_anthropic(image_path: str, schema: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Extract using Anthropic Claude Vision directly from image."""
    client = get_anthropic_client(api_key)
    fields = ", ".join(schema.keys())
    
    base64_image = encode_image_base64(image_path)
    media_type = get_image_media_type(image_path)
    
    prompt = f"""Look at this image and extract the following fields.

Fields to extract:
{fields}

CRITICAL RULES:
- Return ONLY valid JSON
- Keys must EXACTLY match the field names above
- ONLY extract values that are ACTUALLY WRITTEN in the image
- If a field's value is NOT VISIBLE in the image, you MUST return null
- Do NOT guess, infer, or make up values
- Do NOT hallucinate - if you cannot clearly read the text, return null
- Do NOT add extra keys
- Do NOT use markdown or explanation
- Read ALL handwritten or printed text carefully
- The image may contain text in any language (English, Bengali, Arabic, Hindi, etc.)
- If the image is rotated or upside down, read it correctly

IMPORTANT: Only return what you can actually SEE written in the image. Never invent answers."""

    message = client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64_image
                }},
                {"type": "text", "text": prompt}
            ]}
        ]
    )

    raw = message.content[0].text.strip()
    
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    
    # Capture token usage
    token_usage = {
        "prompt_tokens": message.usage.input_tokens if message.usage else 0,
        "completion_tokens": message.usage.output_tokens if message.usage else 0,
        "total_tokens": (message.usage.input_tokens + message.usage.output_tokens) if message.usage else 0,
        "model": "claude-3-haiku-20240307"
    }
    
    return json.loads(raw), token_usage


def extract_from_image_google(image_path: str, schema: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Extract using Google Gemini Vision directly from image."""
    genai = get_google_client(api_key)
    fields = ", ".join(schema.keys())
    
    # Load image for Gemini
    import PIL.Image
    image = PIL.Image.open(image_path)
    
    prompt = f"""Look at this image and extract the following fields.

Fields to extract:
{fields}

CRITICAL RULES:
- Return ONLY valid JSON
- Keys must EXACTLY match the field names above
- ONLY extract values that are ACTUALLY WRITTEN in the image
- If a field's value is NOT VISIBLE in the image, you MUST return null
- Do NOT guess, infer, or make up values
- Do NOT hallucinate - if you cannot clearly read the text, return null
- Do NOT add extra keys
- Do NOT use markdown or explanation
- Read ALL handwritten or printed text carefully
- The image may contain text in any language (English, Bengali, Arabic, Hindi, etc.)
- If the image is rotated or upside down, read it correctly

IMPORTANT: Only return what you can actually SEE written in the image. Never invent answers."""

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt, image])
    
    raw = response.text.strip()
    
    if raw.startswith("```"):
        raw = raw.replace("```json", "").replace("```", "").strip()
    
    # Capture token usage
    token_usage = {
        "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
        "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
        "total_tokens": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
        "model": "gemini-1.5-flash"
    }
    
    return json.loads(raw), token_usage


def extract_from_image(image_path: str, schema: Dict[str, Any],
                       api_key: Optional[str] = None,
                       provider: str = "openai",
                       custom_endpoint: str = None,
                       custom_model: str = None) -> Dict[str, Any]:
    """
    Extract structured fields directly from image using Vision AI.
    Used for non-English text where OCR struggles.
    
    Args:
        image_path: Path to the image file
        schema: Dictionary defining expected fields
        api_key: API key for the provider
        provider: AI provider (openai, anthropic, google, custom)
        custom_endpoint: Custom API endpoint (for local LLMs)
        custom_model: Custom model name
        
    Returns:
        Tuple of (extracted_data, token_usage)
    """
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key and provider != "custom":
        raise RuntimeError(f"API key not configured for {provider}. Set it in Settings.")

    print(f"   👁️ Using Vision AI ({provider}) for direct image extraction")

    token_usage = None
    
    try:
        if provider == "openai":
            # Use GPT-4o for vision
            model = custom_model if custom_model else "gpt-4o"
            data, token_usage = extract_from_image_openai(image_path, schema, api_key, custom_endpoint, model)
        elif provider == "anthropic":
            data, token_usage = extract_from_image_anthropic(image_path, schema, api_key)
        elif provider == "google":
            data, token_usage = extract_from_image_google(image_path, schema, api_key)
        elif provider == "custom":
            # Custom endpoint - try vision if model supports it
            model = custom_model or "gpt-4o"
            data, token_usage = extract_from_image_openai(image_path, schema, api_key or "not-needed",
                                              base_url=custom_endpoint, model=model)
        else:
            # Default to OpenAI
            data, token_usage = extract_from_image_openai(image_path, schema, api_key)
            
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI returned invalid JSON: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Vision extraction failed ({provider}): {str(e)}")

    # Enforce schema strictly
    output = {}
    for key in schema.keys():
        output[key] = data.get(key)

    return output, token_usage

