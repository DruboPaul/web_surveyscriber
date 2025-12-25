/**
 * Secure API Key Storage using localStorage
 * Keys are stored only in the user's browser, never sent to the server for storage
 */

const STORAGE_KEYS = {
    AI_PROVIDER: 'surveyscriber_ai_provider',
    AI_API_KEY: 'surveyscriber_ai_api_key',
    CUSTOM_ENDPOINT: 'surveyscriber_custom_endpoint',
    CUSTOM_MODEL: 'surveyscriber_custom_model',
    OCR_PROVIDER: 'surveyscriber_ocr_provider',
};

/**
 * Get stored AI settings from localStorage
 */
export function getStoredSettings() {
    return {
        ai_provider: localStorage.getItem(STORAGE_KEYS.AI_PROVIDER) || 'openai',
        ai_api_key: localStorage.getItem(STORAGE_KEYS.AI_API_KEY) || '',
        custom_endpoint: localStorage.getItem(STORAGE_KEYS.CUSTOM_ENDPOINT) || '',
        custom_model: localStorage.getItem(STORAGE_KEYS.CUSTOM_MODEL) || '',
        ocr_provider: localStorage.getItem(STORAGE_KEYS.OCR_PROVIDER) || 'none',
    };
}

/**
 * Save AI settings to localStorage
 */
export function saveSettings(settings) {
    if (settings.ai_provider !== undefined) {
        localStorage.setItem(STORAGE_KEYS.AI_PROVIDER, settings.ai_provider);
    }
    if (settings.ai_api_key !== undefined) {
        localStorage.setItem(STORAGE_KEYS.AI_API_KEY, settings.ai_api_key);
    }
    if (settings.custom_endpoint !== undefined) {
        localStorage.setItem(STORAGE_KEYS.CUSTOM_ENDPOINT, settings.custom_endpoint);
    }
    if (settings.custom_model !== undefined) {
        localStorage.setItem(STORAGE_KEYS.CUSTOM_MODEL, settings.custom_model);
    }
    if (settings.ocr_provider !== undefined) {
        localStorage.setItem(STORAGE_KEYS.OCR_PROVIDER, settings.ocr_provider);
    }
}

/**
 * Clear all stored settings
 */
export function clearAllSettings() {
    Object.values(STORAGE_KEYS).forEach(key => localStorage.removeItem(key));
}

/**
 * Check if API key is configured
 */
export function hasApiKey() {
    const key = localStorage.getItem(STORAGE_KEYS.AI_API_KEY);
    return key && key.trim().length > 0;
}

/**
 * Get API key (for sending in request headers)
 */
export function getApiKey() {
    return localStorage.getItem(STORAGE_KEYS.AI_API_KEY) || '';
}

/**
 * Get headers with API credentials for backend requests
 */
export function getAuthHeaders() {
    const settings = getStoredSettings();
    return {
        'Content-Type': 'application/json',
        'X-AI-Provider': settings.ai_provider,
        'X-AI-API-Key': settings.ai_api_key,
        'X-Custom-Endpoint': settings.custom_endpoint,
        'X-Custom-Model': settings.custom_model,
    };
}
