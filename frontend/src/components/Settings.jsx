import { useState, useEffect } from 'react';
import { testAiConnection } from '../api/backend';
import './Settings.css';

// Dynamic import for Tauri save dialog (only works in Tauri environment)
const downloadUsageReport = async (period) => {
    try {
        const BASE_URL = "http://localhost:8000";
        const response = await fetch(`${BASE_URL}/api/usage/report/download?period=${period}`);

        if (!response.ok) {
            throw new Error('Failed to fetch report');
        }

        const blob = await response.blob();
        const filename = `usage_report_${period}_${new Date().toISOString().split('T')[0]}.csv`;

        // Try Tauri save dialog first
        try {
            const { save } = await import('@tauri-apps/plugin-dialog');
            const { writeFile } = await import('@tauri-apps/plugin-fs');

            const filePath = await save({
                defaultPath: filename,
                filters: [{ name: 'CSV Files', extensions: ['csv'] }]
            });

            if (filePath) {
                const arrayBuffer = await blob.arrayBuffer();
                await writeFile(filePath, new Uint8Array(arrayBuffer));
                alert(`Report saved to: ${filePath}`);
            }
        } catch (tauriError) {
            // Fallback for browser: trigger download
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
    } catch (error) {
        alert('Failed to download report: ' + error.message);
    }
};

const BASE_URL = "http://localhost:8000";

// AI Provider definitions
const AI_PROVIDERS = [
    {
        id: 'openai',
        name: 'OpenAI',
        icon: '🟢',
        desc: 'GPT-4, GPT-3.5 Turbo',
        placeholder: 'sk-...',
        helpUrl: 'https://platform.openai.com/api-keys',
        helpText: 'OpenAI Dashboard'
    },
    {
        id: 'anthropic',
        name: 'Anthropic Claude',
        icon: '🟠',
        desc: 'Claude 3 Opus, Sonnet, Haiku',
        placeholder: 'sk-ant-...',
        helpUrl: 'https://console.anthropic.com/settings/keys',
        helpText: 'Anthropic Console'
    },
    {
        id: 'google',
        name: 'Google Gemini',
        icon: '🔵',
        desc: 'Gemini Pro, Gemini Flash',
        placeholder: 'AIza...',
        helpUrl: 'https://aistudio.google.com/app/apikey',
        helpText: 'Google AI Studio'
    },
    {
        id: 'custom',
        name: 'Custom / Local LLM',
        icon: '⚙️',
        desc: 'OpenAI-compatible API (Ollama, LM Studio, etc.)',
        placeholder: 'Enter API key if required...',
        helpUrl: null,
        helpText: null,
        needsEndpoint: true
    }
];

export default function Settings({ isOpen, onClose }) {
    const [activeTab, setActiveTab] = useState('ai');
    const [loading, setLoading] = useState(false);
    const [saved, setSaved] = useState(false);
    const [error, setError] = useState(null);

    // AI Provider settings
    const [aiProvider, setAiProvider] = useState('openai');
    const [aiApiKey, setAiApiKey] = useState('');
    const [showAiKey, setShowAiKey] = useState(false);
    const [customEndpoint, setCustomEndpoint] = useState('');
    const [customModel, setCustomModel] = useState('');

    // Track which keys are already saved (won't show actual value)
    const [aiKeyIsSaved, setAiKeyIsSaved] = useState(false);
    const [googleKeyIsSaved, setGoogleKeyIsSaved] = useState(false);
    const [azureKeyIsSaved, setAzureKeyIsSaved] = useState(false);

    // API Key test state
    const [testingAi, setTestingAi] = useState(false);
    const [aiTestResult, setAiTestResult] = useState(null);

    // OCR Provider settings
    const [ocrProvider, setOcrProvider] = useState('none');
    const [googleVisionKey, setGoogleVisionKey] = useState('');
    const [showGoogleKey, setShowGoogleKey] = useState(false);
    const [azureOcrKey, setAzureOcrKey] = useState('');
    const [azureOcrEndpoint, setAzureOcrEndpoint] = useState('');
    const [showAzureKey, setShowAzureKey] = useState(false);
    // Custom OCR settings
    const [customOcrEndpoint, setCustomOcrEndpoint] = useState('');
    const [customOcrKey, setCustomOcrKey] = useState('');
    const [showCustomOcrKey, setShowCustomOcrKey] = useState(false);
    // Local OCR settings
    const [localOcrPath, setLocalOcrPath] = useState('');
    // Vision AI settings (for OCR fallback)
    const [visionAiProvider, setVisionAiProvider] = useState('same');
    const [visionAiKey, setVisionAiKey] = useState('');
    const [customOcrKeyIsSaved, setCustomOcrKeyIsSaved] = useState(false);

    // Python Runtime settings
    const [pythonPath, setPythonPath] = useState('');
    const [detectedPythons, setDetectedPythons] = useState([]);
    const [detectingPython, setDetectingPython] = useState(false);

    // Database settings
    const [databaseUrl, setDatabaseUrl] = useState('');
    const [enableHistory, setEnableHistory] = useState(true);
    const [dbTestResult, setDbTestResult] = useState(null);
    const [testingDb, setTestingDb] = useState(false);

    // Load settings on mount
    useEffect(() => {
        if (isOpen) {
            loadSettings();
        }
    }, [isOpen]);

    async function loadSettings() {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch(`${BASE_URL}/api/settings/raw`);
            if (response.ok) {
                const data = await response.json();
                setAiProvider(data.ai_provider || 'openai');
                setAiApiKey('');
                setAiKeyIsSaved(Boolean(data.ai_api_key || data.openai_api_key));
                setCustomEndpoint(data.custom_endpoint || '');
                setCustomModel(data.custom_model || '');
                // OCR settings
                setOcrProvider(data.ocr_provider || 'none');
                setGoogleVisionKey('');
                setGoogleKeyIsSaved(Boolean(data.google_vision_key));
                setAzureOcrKey('');
                setAzureKeyIsSaved(Boolean(data.azure_ocr_key));
                setAzureOcrEndpoint(data.azure_ocr_endpoint || '');
                // Custom OCR
                setCustomOcrEndpoint(data.custom_ocr_endpoint || '');
                setCustomOcrKey('');
                setCustomOcrKeyIsSaved(Boolean(data.custom_ocr_key));
                // Local OCR
                setLocalOcrPath(data.local_ocr_path || '');
                // Vision AI
                setVisionAiProvider(data.vision_ai_provider || 'same');
                setVisionAiKey('');
                // Python Runtime
                setPythonPath(data.python_path || '');
                // Database settings
                setDatabaseUrl(data.database_url || '');
                setEnableHistory(data.enable_history !== false);
            }
        } catch (err) {
            console.log('Settings not available yet');
        }
        setLoading(false);
    }

    async function handleSave() {
        setLoading(true);
        setError(null);
        try {
            const payload = {
                ai_provider: aiProvider,
                custom_endpoint: customEndpoint,
                custom_model: customModel,
                ocr_provider: ocrProvider,
                azure_ocr_endpoint: azureOcrEndpoint,
                custom_ocr_endpoint: customOcrEndpoint,
                local_ocr_path: localOcrPath,
                vision_ai_provider: visionAiProvider,
                python_path: pythonPath,
                database_url: databaseUrl,
                enable_history: enableHistory
            };

            // Only include keys if user entered a new one
            if (aiApiKey.trim()) {
                payload.ai_api_key = aiApiKey;
                payload.openai_api_key = aiProvider === 'openai' ? aiApiKey : '';
            }
            if (googleVisionKey.trim()) {
                payload.google_vision_key = googleVisionKey;
            }
            if (azureOcrKey.trim()) {
                payload.azure_ocr_key = azureOcrKey;
            }
            if (customOcrKey.trim()) {
                payload.custom_ocr_key = customOcrKey;
            }
            if (visionAiKey.trim()) {
                payload.vision_ai_key = visionAiKey;
            }

            const response = await fetch(`${BASE_URL}/api/settings`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                // Clear key inputs after successful save (keys are now hidden)
                if (aiApiKey.trim()) {
                    setAiKeyIsSaved(true);
                    setAiApiKey('');
                }
                if (googleVisionKey.trim()) {
                    setGoogleKeyIsSaved(true);
                    setGoogleVisionKey('');
                }
                if (azureOcrKey.trim()) {
                    setAzureKeyIsSaved(true);
                    setAzureOcrKey('');
                }

                setSaved(true);
                setTimeout(() => setSaved(false), 2000);
            } else {
                throw new Error('Failed to save settings');
            }
        } catch (err) {
            setError('Failed to save settings. Make sure the backend is running.');
        }
        setLoading(false);
    }

    function handleClearAll() {
        setAiProvider('openai');
        setAiApiKey('');
        setAiKeyIsSaved(false);
        setCustomEndpoint('');
        setCustomModel('');
        setGoogleVisionKey('');
        setGoogleKeyIsSaved(false);
        setAzureOcrKey('');
        setAzureKeyIsSaved(false);
        setAzureOcrEndpoint('');
        setOcrProvider('paddle');
        setDatabaseUrl('');
        setEnableHistory(true);
        setDbTestResult(null);
        localStorage.removeItem('openai_api_key');
    }

    async function handleTestDatabase() {
        setTestingDb(true);
        setDbTestResult(null);
        try {
            const response = await fetch(`${BASE_URL}/api/database/test`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ database_url: databaseUrl })
            });
            const result = await response.json();
            setDbTestResult(result);
        } catch (err) {
            setDbTestResult({ success: false, message: 'Failed to test connection' });
        }
        setTestingDb(false);
    }

    const currentAiProvider = AI_PROVIDERS.find(p => p.id === aiProvider) || AI_PROVIDERS[0];

    if (!isOpen) return null;

    return (
        <div className="settings-overlay" onClick={onClose}>
            <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
                <div className="settings-header">
                    <h2>⚙️ Settings</h2>
                    <button className="close-btn" onClick={onClose}>✕</button>
                </div>

                {/* Tab Navigation */}
                <div className="settings-tabs">
                    <button
                        className={`settings-tab ${activeTab === 'ai' ? 'active' : ''}`}
                        onClick={() => setActiveTab('ai')}
                    >
                        🤖 AI Provider
                    </button>
                    <button
                        className={`settings-tab ${activeTab === 'ocr' ? 'active' : ''}`}
                        onClick={() => setActiveTab('ocr')}
                    >
                        📷 OCR Provider
                    </button>
                    <button
                        className={`settings-tab ${activeTab === 'database' ? 'active' : ''}`}
                        onClick={() => setActiveTab('database')}
                    >
                        💾 Database
                    </button>
                    <button
                        className={`settings-tab ${activeTab === 'python' ? 'active' : ''}`}
                        onClick={() => setActiveTab('python')}
                    >
                        🐍 Python
                    </button>
                </div>

                <div className="settings-content">
                    {error && <div className="settings-error">{error}</div>}

                    {/* AI Provider Tab */}
                    {activeTab === 'ai' && (
                        <div className="setting-group">
                            {/* API Key Status Banner */}
                            {aiKeyIsSaved ? (
                                <div style={{
                                    padding: '0.75rem 1rem',
                                    marginBottom: '1rem',
                                    borderRadius: '8px',
                                    background: 'linear-gradient(135deg, rgba(72, 187, 120, 0.15), rgba(56, 161, 105, 0.1))',
                                    border: '1px solid rgba(72, 187, 120, 0.3)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}>
                                    <span style={{ fontSize: '1.2rem' }}>✅</span>
                                    <span style={{ color: '#48bb78', fontWeight: '500' }}>
                                        API Key is saved and ready to use
                                    </span>
                                </div>
                            ) : (
                                <div style={{
                                    padding: '0.75rem 1rem',
                                    marginBottom: '1rem',
                                    borderRadius: '8px',
                                    background: 'linear-gradient(135deg, rgba(245, 101, 101, 0.15), rgba(229, 62, 62, 0.1))',
                                    border: '1px solid rgba(245, 101, 101, 0.3)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}>
                                    <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                                    <span style={{ color: '#fc8181', fontWeight: '500' }}>
                                        API Key is missing. Please enter an API key below to use the extraction feature.
                                    </span>
                                </div>
                            )}

                            <label>🤖 Select AI Provider</label>
                            <p className="setting-description">
                                Choose your preferred AI/LLM provider for data extraction.
                            </p>

                            <div className="ai-provider-options">
                                {AI_PROVIDERS.map(provider => (
                                    <label key={provider.id} className="provider-option">
                                        <input
                                            type="radio"
                                            name="ai-provider"
                                            value={provider.id}
                                            checked={aiProvider === provider.id}
                                            onChange={(e) => {
                                                setAiProvider(e.target.value);
                                                setAiApiKey(''); // Clear key when switching
                                            }}
                                        />
                                        <div className="provider-info">
                                            <span className="provider-name">{provider.icon} {provider.name}</span>
                                            <span className="provider-desc">{provider.desc}</span>
                                        </div>
                                    </label>
                                ))}
                            </div>

                            {/* API Key Input */}
                            <div className="provider-config">
                                <label htmlFor="ai-key">
                                    🔑 {currentAiProvider.name} API Key
                                    {aiKeyIsSaved && <span style={{ marginLeft: '0.5rem', color: '#48bb78', fontSize: '0.85rem' }}>✓ Saved</span>}
                                </label>
                                <div className="api-key-input-group">
                                    <input
                                        id="ai-key"
                                        type={showAiKey ? "text" : "password"}
                                        value={aiApiKey}
                                        onChange={(e) => {
                                            setAiApiKey(e.target.value);
                                            setAiTestResult(null); // Clear test result when key changes
                                        }}
                                        placeholder={aiKeyIsSaved ? "••••••••••••• (enter new key to replace)" : currentAiProvider.placeholder}
                                        className="api-key-input"
                                    />
                                    <button
                                        type="button"
                                        className="toggle-visibility-btn"
                                        onClick={() => setShowAiKey(!showAiKey)}
                                    >
                                        {showAiKey ? "🙈" : "👁️"}
                                    </button>
                                </div>

                                {/* Test API Key Button */}
                                <div style={{ marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                    <button
                                        type="button"
                                        className="test-api-btn"
                                        onClick={async () => {
                                            setTestingAi(true);
                                            setAiTestResult(null);
                                            try {
                                                // If user entered a new key, save it first
                                                if (aiApiKey.trim()) {
                                                    await fetch(`${BASE_URL}/api/settings`, {
                                                        method: 'PUT',
                                                        headers: { 'Content-Type': 'application/json' },
                                                        body: JSON.stringify({ ai_provider: aiProvider, ai_api_key: aiApiKey })
                                                    });
                                                }
                                                const result = await testAiConnection();
                                                setAiTestResult(result);
                                            } catch (err) {
                                                setAiTestResult({ valid: false, message: 'Connection test failed. Check if backend is running.' });
                                            }
                                            setTestingAi(false);
                                        }}
                                        disabled={testingAi || (!aiKeyIsSaved && !aiApiKey.trim())}
                                        style={{
                                            padding: '0.5rem 1rem',
                                            borderRadius: '6px',
                                            border: 'none',
                                            background: testingAi ? '#4a5568' : '#3182ce',
                                            color: 'white',
                                            cursor: testingAi ? 'wait' : 'pointer',
                                            fontSize: '0.9rem',
                                            opacity: (!aiKeyIsSaved && !aiApiKey.trim()) ? 0.5 : 1
                                        }}
                                    >
                                        {testingAi ? '⏳ Testing...' : '🔌 Test API Key'}
                                    </button>

                                    {aiTestResult && (
                                        <span style={{
                                            color: aiTestResult.valid ? '#48bb78' : '#fc8181',
                                            fontSize: '0.9rem'
                                        }}>
                                            {aiTestResult.valid ? '✅' : '❌'} {aiTestResult.message}
                                        </span>
                                    )}
                                </div>

                                {currentAiProvider.helpUrl && (
                                    <p className="setting-hint">
                                        Get your API key from{' '}
                                        <a href={currentAiProvider.helpUrl} target="_blank" rel="noopener noreferrer">
                                            {currentAiProvider.helpText}
                                        </a>
                                    </p>
                                )}

                                {/* Custom endpoint for local LLMs */}
                                {aiProvider === 'custom' && (
                                    <>
                                        <label htmlFor="custom-endpoint" style={{ marginTop: '1rem', display: 'block' }}>
                                            🌐 API Endpoint URL
                                        </label>
                                        <input
                                            id="custom-endpoint"
                                            type="text"
                                            value={customEndpoint}
                                            onChange={(e) => setCustomEndpoint(e.target.value)}
                                            placeholder="http://localhost:11434/v1 (Ollama)"
                                            className="api-key-input"
                                            style={{ marginBottom: '1rem' }}
                                        />

                                        <label htmlFor="custom-model">
                                            🧠 Model Name
                                        </label>
                                        <input
                                            id="custom-model"
                                            type="text"
                                            value={customModel}
                                            onChange={(e) => setCustomModel(e.target.value)}
                                            placeholder="llama3, mistral, etc."
                                            className="api-key-input"
                                        />

                                        <p className="setting-hint" style={{ marginTop: '0.5rem' }}>
                                            Works with any OpenAI-compatible API: Ollama, LM Studio, vLLM, etc.
                                        </p>
                                    </>
                                )}
                            </div>
                        </div>
                    )}

                    {/* OCR Provider Tab */}
                    {activeTab === 'ocr' && (
                        <div className="setting-group">
                            <label>📷 OCR / Text Extraction Method</label>
                            <p className="setting-description">
                                Choose how to extract text from images. AI Vision is recommended for most use cases.
                            </p>

                            <div className="ocr-provider-options">
                                <label className="provider-option">
                                    <input
                                        type="radio"
                                        name="ocr-provider"
                                        value="none"
                                        checked={ocrProvider === 'none'}
                                        onChange={(e) => setOcrProvider(e.target.value)}
                                    />
                                    <div className="provider-info">
                                        <span className="provider-name">🤖 AI Vision Only</span>
                                        <span className="provider-desc">No OCR - AI directly reads images (recommended)</span>
                                    </div>
                                </label>

                                <label className="provider-option">
                                    <input
                                        type="radio"
                                        name="ocr-provider"
                                        value="google"
                                        checked={ocrProvider === 'google'}
                                        onChange={(e) => setOcrProvider(e.target.value)}
                                    />
                                    <div className="provider-info">
                                        <span className="provider-name">☁️ Google Cloud Vision</span>
                                        <span className="provider-desc">Cloud OCR, high accuracy, requires API key</span>
                                    </div>
                                </label>

                                <label className="provider-option">
                                    <input
                                        type="radio"
                                        name="ocr-provider"
                                        value="azure"
                                        checked={ocrProvider === 'azure'}
                                        onChange={(e) => setOcrProvider(e.target.value)}
                                    />
                                    <div className="provider-info">
                                        <span className="provider-name">🔷 Azure Computer Vision</span>
                                        <span className="provider-desc">Enterprise cloud OCR, requires API key</span>
                                    </div>
                                </label>

                                <label className="provider-option">
                                    <input
                                        type="radio"
                                        name="ocr-provider"
                                        value="custom"
                                        checked={ocrProvider === 'custom'}
                                        onChange={(e) => setOcrProvider(e.target.value)}
                                    />
                                    <div className="provider-info">
                                        <span className="provider-name">🔌 Custom OCR API</span>
                                        <span className="provider-desc">Connect your own OCR service via REST API</span>
                                    </div>
                                </label>

                                <label className="provider-option">
                                    <input
                                        type="radio"
                                        name="ocr-provider"
                                        value="local"
                                        checked={ocrProvider === 'local'}
                                        onChange={(e) => setOcrProvider(e.target.value)}
                                    />
                                    <div className="provider-info">
                                        <span className="provider-name">💻 Local/Desktop OCR</span>
                                        <span className="provider-desc">Use installed OCR software (Tesseract, etc.)</span>
                                    </div>
                                </label>
                            </div>


                            {/* Google Vision API Key */}
                            {ocrProvider === 'google' && (
                                <div className="provider-config">
                                    <label htmlFor="google-key">
                                        Google Cloud API Key
                                        {googleKeyIsSaved && <span style={{ marginLeft: '0.5rem', color: '#48bb78', fontSize: '0.85rem' }}>✓ Saved</span>}
                                    </label>
                                    <div className="api-key-input-group">
                                        <input
                                            id="google-key"
                                            type={showGoogleKey ? "text" : "password"}
                                            value={googleVisionKey}
                                            onChange={(e) => setGoogleVisionKey(e.target.value)}
                                            placeholder={googleKeyIsSaved ? "••••••••••••• (enter new key to replace)" : "AIza..."}
                                            className="api-key-input"
                                        />
                                        <button
                                            type="button"
                                            className="toggle-visibility-btn"
                                            onClick={() => setShowGoogleKey(!showGoogleKey)}
                                        >
                                            {showGoogleKey ? "🙈" : "👁️"}
                                        </button>
                                    </div>
                                    <p className="setting-hint">
                                        Get your key from{' '}
                                        <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer">
                                            Google Cloud Console
                                        </a>
                                    </p>
                                </div>
                            )}

                            {/* Azure OCR Configuration */}
                            {ocrProvider === 'azure' && (
                                <div className="provider-config">
                                    <label htmlFor="azure-endpoint">Azure Endpoint URL</label>
                                    <input
                                        id="azure-endpoint"
                                        type="text"
                                        value={azureOcrEndpoint}
                                        onChange={(e) => setAzureOcrEndpoint(e.target.value)}
                                        placeholder="https://YOUR_RESOURCE.cognitiveservices.azure.com"
                                        className="api-key-input"
                                        style={{ marginBottom: '1rem' }}
                                    />

                                    <label htmlFor="azure-key">
                                        Azure API Key
                                        {azureKeyIsSaved && <span style={{ marginLeft: '0.5rem', color: '#48bb78', fontSize: '0.85rem' }}>✓ Saved</span>}
                                    </label>
                                    <div className="api-key-input-group">
                                        <input
                                            id="azure-key"
                                            type={showAzureKey ? "text" : "password"}
                                            value={azureOcrKey}
                                            onChange={(e) => setAzureOcrKey(e.target.value)}
                                            placeholder={azureKeyIsSaved ? "••••••••••••• (enter new key to replace)" : "Enter your Azure key..."}
                                            className="api-key-input"
                                        />
                                        <button
                                            type="button"
                                            className="toggle-visibility-btn"
                                            onClick={() => setShowAzureKey(!showAzureKey)}
                                        >
                                            {showAzureKey ? "🙈" : "👁️"}
                                        </button>
                                    </div>
                                    <p className="setting-hint">
                                        Get credentials from{' '}
                                        <a href="https://portal.azure.com/" target="_blank" rel="noopener noreferrer">
                                            Azure Portal
                                        </a>
                                    </p>
                                </div>
                            )}

                            {/* Custom OCR API Configuration */}
                            {ocrProvider === 'custom' && (
                                <div className="provider-config">
                                    <label htmlFor="custom-ocr-endpoint">OCR API Endpoint URL</label>
                                    <input
                                        id="custom-ocr-endpoint"
                                        type="text"
                                        value={customOcrEndpoint}
                                        onChange={(e) => setCustomOcrEndpoint(e.target.value)}
                                        placeholder="https://your-ocr-api.com/extract"
                                        className="api-key-input"
                                        style={{ marginBottom: '1rem' }}
                                    />

                                    <label htmlFor="custom-ocr-key">
                                        API Key (if required)
                                        {customOcrKeyIsSaved && <span style={{ marginLeft: '0.5rem', color: '#48bb78', fontSize: '0.85rem' }}>✓ Saved</span>}
                                    </label>
                                    <div className="api-key-input-group">
                                        <input
                                            id="custom-ocr-key"
                                            type={showCustomOcrKey ? "text" : "password"}
                                            value={customOcrKey}
                                            onChange={(e) => setCustomOcrKey(e.target.value)}
                                            placeholder={customOcrKeyIsSaved ? "••••••••••••• (enter new key to replace)" : "Enter API key if required..."}
                                            className="api-key-input"
                                        />
                                        <button
                                            type="button"
                                            className="toggle-visibility-btn"
                                            onClick={() => setShowCustomOcrKey(!showCustomOcrKey)}
                                        >
                                            {showCustomOcrKey ? "🙈" : "👁️"}
                                        </button>
                                    </div>
                                    <p className="setting-hint">
                                        Expected API format: POST image (base64) → returns text
                                    </p>
                                </div>
                            )}

                            {/* Local OCR Configuration */}
                            {ocrProvider === 'local' && (
                                <div className="provider-config">
                                    <label htmlFor="local-ocr-path">OCR Executable Path</label>
                                    <input
                                        id="local-ocr-path"
                                        type="text"
                                        value={localOcrPath}
                                        onChange={(e) => setLocalOcrPath(e.target.value)}
                                        placeholder="C:\Program Files\Tesseract-OCR\tesseract.exe"
                                        className="api-key-input"
                                    />
                                    <p className="setting-hint">
                                        Full path to your OCR executable (Tesseract, PaddleOCR, etc.)
                                    </p>
                                </div>
                            )}

                            {/* OCR Fallback Info */}
                            {ocrProvider !== 'none' && (
                                <div style={{
                                    marginTop: '1.5rem',
                                    padding: '0.75rem',
                                    borderRadius: '8px',
                                    background: 'rgba(66, 153, 225, 0.1)',
                                    border: '1px solid rgba(66, 153, 225, 0.3)'
                                }}>
                                    <p style={{ margin: 0, fontSize: '0.9rem', color: '#90cdf4' }}>
                                        ℹ️ If OCR fails, the app will automatically use AI Vision as fallback.
                                    </p>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Database Tab */}
                    {activeTab === 'database' && (
                        <div className="setting-group">
                            <label>💾 Extraction History Database</label>
                            <p className="setting-description">
                                Track all extractions in a database. SQLite is used by default (no setup needed).
                            </p>

                            {/* Enable History Toggle */}
                            <div className="toggle-option" style={{ marginBottom: '1.5rem', marginTop: '1rem' }}>
                                <label className="toggle-label">
                                    <input
                                        type="checkbox"
                                        checked={enableHistory}
                                        onChange={(e) => setEnableHistory(e.target.checked)}
                                    />
                                    <span className="toggle-text">
                                        {enableHistory ? '✅ History tracking enabled' : '⏸️ History tracking disabled'}
                                    </span>
                                </label>
                            </div>

                            {enableHistory && (
                                <div className="provider-config">
                                    <label htmlFor="db-url">
                                        🔗 Database URL (optional)
                                    </label>
                                    <input
                                        id="db-url"
                                        type="text"
                                        value={databaseUrl}
                                        onChange={(e) => {
                                            setDatabaseUrl(e.target.value);
                                            setDbTestResult(null);
                                        }}
                                        placeholder="Leave empty for SQLite (recommended)"
                                        className="api-key-input"
                                    />

                                    <div style={{ marginTop: '0.75rem', marginBottom: '0.75rem' }}>
                                        <button
                                            type="button"
                                            className="test-db-btn"
                                            onClick={handleTestDatabase}
                                            disabled={testingDb}
                                            style={{
                                                padding: '0.5rem 1rem',
                                                borderRadius: '6px',
                                                border: 'none',
                                                background: '#4a5568',
                                                color: 'white',
                                                cursor: testingDb ? 'wait' : 'pointer',
                                                fontSize: '0.9rem'
                                            }}
                                        >
                                            {testingDb ? '⏳ Testing...' : '🔌 Test Connection'}
                                        </button>

                                        {dbTestResult && (
                                            <span style={{
                                                marginLeft: '1rem',
                                                color: dbTestResult.success ? '#48bb78' : '#fc8181'
                                            }}>
                                                {dbTestResult.success ? '✅' : '❌'} {dbTestResult.message}
                                            </span>
                                        )}
                                    </div>

                                    <div className="setting-hint" style={{ marginTop: '1rem' }}>
                                        <strong>Examples:</strong>
                                        <ul style={{ margin: '0.5rem 0', paddingLeft: '1.5rem' }}>
                                            <li><code style={{ fontSize: '0.85rem' }}>Empty</code> → SQLite (automatic, recommended)</li>
                                            <li><code style={{ fontSize: '0.85rem' }}>postgresql://user:pass@host:5432/db</code></li>
                                            <li><code style={{ fontSize: '0.85rem' }}>mysql://user:pass@host:3306/db</code></li>
                                        </ul>
                                    </div>
                                </div>
                            )}

                            {/* API Usage Reports */}
                            <div style={{ marginTop: '2rem', paddingTop: '1.5rem', borderTop: '1px solid #4a5568' }}>
                                <label style={{ display: 'block', marginBottom: '0.75rem' }}>📊 API Token Usage Reports</label>
                                <p className="setting-description" style={{ marginBottom: '1rem' }}>
                                    Download reports of your API token usage to track costs.
                                </p>

                                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                                    <button
                                        type="button"
                                        onClick={() => downloadUsageReport('weekly')}
                                        style={{
                                            padding: '0.5rem 1rem',
                                            borderRadius: '6px',
                                            border: 'none',
                                            background: 'linear-gradient(135deg, #48bb78, #38a169)',
                                            color: 'white',
                                            cursor: 'pointer',
                                            fontSize: '0.85rem',
                                            fontWeight: '500'
                                        }}
                                    >
                                        📥 Weekly
                                    </button>

                                    <button
                                        type="button"
                                        onClick={() => downloadUsageReport('monthly')}
                                        style={{
                                            padding: '0.5rem 1rem',
                                            borderRadius: '6px',
                                            border: 'none',
                                            background: 'linear-gradient(135deg, #4299e1, #3182ce)',
                                            color: 'white',
                                            cursor: 'pointer',
                                            fontSize: '0.85rem',
                                            fontWeight: '500'
                                        }}
                                    >
                                        📥 Monthly
                                    </button>

                                    <button
                                        type="button"
                                        onClick={() => downloadUsageReport('all')}
                                        style={{
                                            padding: '0.5rem 1rem',
                                            borderRadius: '6px',
                                            border: '1px solid #4a5568',
                                            background: 'transparent',
                                            color: '#a0aec0',
                                            cursor: 'pointer',
                                            fontSize: '0.85rem'
                                        }}
                                    >
                                        📥 All Time
                                    </button>
                                </div>

                                {/* Clear History */}
                                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #3a4556' }}>
                                    <button
                                        type="button"
                                        onClick={async () => {
                                            if (window.confirm('Are you sure you want to clear ALL usage history? This cannot be undone.')) {
                                                try {
                                                    const res = await fetch(`${BASE_URL}/api/usage/clear?period=all`, { method: 'DELETE' });
                                                    const data = await res.json();
                                                    alert(data.message);
                                                } catch (err) {
                                                    alert('Failed to clear history: ' + err.message);
                                                }
                                            }
                                        }}
                                        style={{
                                            padding: '0.5rem 1rem',
                                            borderRadius: '6px',
                                            border: '1px solid #e53e3e',
                                            background: 'transparent',
                                            color: '#fc8181',
                                            cursor: 'pointer',
                                            fontSize: '0.85rem'
                                        }}
                                    >
                                        🗑️ Clear All History
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Python Runtime Tab */}
                    {activeTab === 'python' && (
                        <div className="setting-group">
                            <label>🐍 Python Runtime Configuration</label>
                            <p className="setting-description">
                                Configure which Python installation to use for the backend server.
                                Leave empty to auto-detect from system PATH.
                            </p>

                            {/* Auto-detect Button */}
                            <div style={{ marginBottom: '1.5rem' }}>
                                <button
                                    type="button"
                                    onClick={async () => {
                                        setDetectingPython(true);
                                        try {
                                            const res = await fetch(`${BASE_URL}/api/detect-python`);
                                            const data = await res.json();
                                            setDetectedPythons(data.pythons || []);
                                            if (data.recommended && !pythonPath) {
                                                setPythonPath(data.recommended);
                                            }
                                        } catch (err) {
                                            console.error('Failed to detect Python:', err);
                                        }
                                        setDetectingPython(false);
                                    }}
                                    disabled={detectingPython}
                                    style={{
                                        padding: '0.75rem 1.25rem',
                                        borderRadius: '8px',
                                        border: 'none',
                                        background: 'linear-gradient(135deg, #4c7dcc, #3a6bc2)',
                                        color: 'white',
                                        cursor: detectingPython ? 'wait' : 'pointer',
                                        fontSize: '0.95rem',
                                        fontWeight: '500'
                                    }}
                                >
                                    {detectingPython ? '🔍 Detecting...' : '🔍 Auto-Detect Python'}
                                </button>
                            </div>

                            {/* Detected Pythons List */}
                            {detectedPythons.length > 0 && (
                                <div style={{ marginBottom: '1.5rem' }}>
                                    <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                                        Found Python Installations:
                                    </label>
                                    <div style={{
                                        background: 'rgba(26, 32, 44, 0.6)',
                                        borderRadius: '8px',
                                        padding: '0.75rem',
                                        maxHeight: '150px',
                                        overflowY: 'auto'
                                    }}>
                                        {detectedPythons.map((py, idx) => (
                                            <div
                                                key={idx}
                                                onClick={() => setPythonPath(py.path)}
                                                style={{
                                                    padding: '0.5rem 0.75rem',
                                                    marginBottom: '0.25rem',
                                                    borderRadius: '6px',
                                                    cursor: 'pointer',
                                                    background: pythonPath === py.path ? 'rgba(66, 153, 225, 0.3)' : 'transparent',
                                                    border: pythonPath === py.path ? '1px solid #4299e1' : '1px solid transparent'
                                                }}
                                            >
                                                <div style={{ fontWeight: '500', color: '#e2e8f0' }}>{py.version}</div>
                                                <div style={{ fontSize: '0.8rem', color: '#a0aec0', wordBreak: 'break-all' }}>{py.path}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Manual Path Input */}
                            <div className="provider-config">
                                <label htmlFor="python-path">Python Executable Path</label>
                                <input
                                    id="python-path"
                                    type="text"
                                    value={pythonPath}
                                    onChange={(e) => setPythonPath(e.target.value)}
                                    placeholder="C:\Python311\python.exe (or leave empty for auto-detect)"
                                    className="api-key-input"
                                />
                                <p className="setting-hint">
                                    Full path to python.exe. Leave empty to use system Python from PATH.
                                </p>
                            </div>

                            {/* Requirements Info */}
                            <div style={{
                                marginTop: '1.5rem',
                                padding: '1rem',
                                borderRadius: '8px',
                                background: 'rgba(237, 137, 54, 0.1)',
                                border: '1px solid rgba(237, 137, 54, 0.3)'
                            }}>
                                <p style={{ margin: 0, fontSize: '0.9rem', color: '#fbd38d' }}>
                                    ⚠️ <strong>Important:</strong> The Python installation must have all required packages installed.
                                    Run <code style={{ background: 'rgba(0,0,0,0.3)', padding: '0.1rem 0.3rem', borderRadius: '4px' }}>pip install -r requirements.txt</code> in the app directory.
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer Actions */}
                <div className="settings-footer">
                    <button className="clear-btn" onClick={handleClearAll}>
                        🗑️ Clear All
                    </button>
                    <button
                        className="save-btn"
                        onClick={handleSave}
                        disabled={loading}
                    >
                        {loading ? '⏳ Saving...' : saved ? '✅ Saved!' : '💾 Save Settings'}
                    </button>
                </div>
            </div>
        </div>
    );
}
