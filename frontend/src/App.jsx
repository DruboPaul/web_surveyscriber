import { useState, useEffect } from "react";
import {
  uploadImagesChunked,
  extractBatch,
  extractBatchAsync,
  pollJobStatus,
  getExcelDownloadUrl,
  getCsvDownloadUrl
} from "./api/backend";
import SchemaEditor from "./components/SchemaEditor";
import ImageUploader from "./components/ImageUploader";
import Settings from "./components/Settings";
import SetupScreen from "./components/SetupScreen";
import { isSetupComplete, startBackendWithEmbeddedPython } from "./setup";
import "./App.css";

// Dynamic BASE_URL from environment variable (for API calls)
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Detect if running in Tauri environment - check multiple ways
const checkIsTauri = () => {
  // Check for Tauri internals (most reliable for Tauri v2)
  if (typeof window !== 'undefined') {
    if (window.__TAURI_INTERNALS__) return true;
    if (window.__TAURI__) return true;
    if (window.__TAURI_IPC__) return true;
    // Check if Tauri APIs are available
    try {
      // This will throw if not in Tauri
      if ('__TAURI__' in window) return true;
    } catch (e) { }
  }
  return false;
};

const isTauri = checkIsTauri();
console.log("🖥️ [App] Running in Tauri:", isTauri);
console.log("🖥️ [App] window.__TAURI_INTERNALS__:", typeof window !== 'undefined' && !!window.__TAURI_INTERNALS__);


/**
 * Save file with "Save As" dialog using File System Access API
 * Falls back to regular download if not supported
 */
/**
 * Save file with "Save As" dialog
 * Supports:
 * 1. Tauri Native Dialog (Desktop App)
 * 2. File System Access API (Modern Browsers)
 * 3. Legacy Download Link (Fallback)
 */
async function saveWithDialog(url, suggestedName, fileType, defaultFolder = null) {
  try {
    // Fetch the file content
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch file');
    const blob = await response.blob();
    const buffer = await blob.arrayBuffer();
    const uint8Array = new Uint8Array(buffer);

    // 1️⃣ Check for Tauri Environment
    if (isTauri) {
      console.log("📁 [Save Dialog] Using Tauri native save");
      try {
        const { save } = await import('@tauri-apps/plugin-dialog');
        const { invoke } = await import('@tauri-apps/api/core');
        const { join } = await import('@tauri-apps/api/path');

        // If defaultFolder is provided, construct full default path
        let defaultPath = suggestedName;
        if (defaultFolder) {
          defaultPath = await join(defaultFolder, suggestedName);
          console.log("📁 [Save Dialog] Pre-selected path:", defaultPath);
        }

        const filePath = await save({
          defaultPath: defaultPath,
          filters: fileType === 'csv'
            ? [{ name: 'CSV File', extensions: ['csv'] }]
            : [{ name: 'Excel File', extensions: ['xlsx'] }]
        });

        console.log("📁 [Save Dialog] User selected path:", filePath);

        if (filePath) {
          try {
            // Convert to array for Rust command
            const contents = Array.from(uint8Array);

            // Use Rust command for reliable file writing
            await invoke('write_file_bytes', {
              path: filePath,
              contents: contents
            });

            console.log("📁 [Save Dialog] ✅ SUCCESS! File saved to:", filePath);
            alert(`✅ File saved successfully to:\n${filePath}`);
            return true;
          } catch (writeErr) {
            console.error("📁 [Save Dialog] ❌ Save failed:", writeErr);
            alert(`❌ Failed to save file: ${writeErr}\n\nPlease try a different location.`);
            return false;
          }
        }
        console.log("📁 [Save Dialog] User cancelled");
        return false; // User cancelled
      } catch (tauriError) {
        console.error('Tauri dialog/API error:', tauriError);
        alert(`❌ Save error: ${tauriError.message}`);
        return false;
      }
    }

    // 2️⃣ For web browser - Check if File System Access API is available
    if ('showSaveFilePicker' in window) {
      const options = {
        suggestedName: suggestedName,
        types: fileType === 'csv'
          ? [{
            description: 'CSV File',
            accept: { 'text/csv': ['.csv'] }
          }]
          : [{
            description: 'Excel File',
            accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] }
          }]
      };

      const handle = await window.showSaveFilePicker(options);
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return true;
    }

    // 3️⃣ Fallback: Create download link (only for web browser)
    const downloadUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = suggestedName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
    return true;

  } catch (err) {
    if (err.name === 'AbortError') {
      return false;
    }
    console.error('Save failed:', err);
    throw err;
  }
}

// Processing time estimates (seconds per image)
const TIME_PER_IMAGE = {
  upload: 0.5,      // Upload to server
  ocr: 3,           // PaddleOCR processing
  extraction: 2,    // OpenAI API call
};

// System limits
const LIMITS = {
  syncMax: 0,         // Always use async mode (prevents timeout)
  recommended: 500,   // Recommended max with async mode
  warning: 2000,      // Warning threshold
  danger: 5000,       // High risk
};

function App() {
  const [files, setFiles] = useState([]);
  const [schemaFields, setSchemaFields] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState(null);
  const [browserFolderHandle, setBrowserFolderHandle] = useState(null); // For browser File System Access API
  const [error, setError] = useState(null);
  const [customFilename, setCustomFilename] = useState("");
  const [outputFolder, setOutputFolder] = useState(null);
  const [outputFormat, setOutputFormat] = useState("excel");

  // Progress tracking
  const [progress, setProgress] = useState(null);
  const [processingMode, setProcessingMode] = useState("auto");
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Setup state (for first-run)
  const [setupComplete, setSetupComplete] = useState(!isTauri); // Web doesn't need setup
  const [justCompletedSetup, setJustCompletedSetup] = useState(false); // Track fresh setup

  // Timer for elapsed time
  const [startTime, setStartTime] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);

  // Abort controller for cancellation
  const [abortController, setAbortController] = useState(null);

  // Timer effect for elapsed time display
  useEffect(() => {
    let interval = null;
    if (loading && startTime) {
      interval = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
      }, 1000);
    } else {
      setElapsedTime(0);
    }
    return () => clearInterval(interval);
  }, [loading, startTime]);

  // Wait for backend to be ready (Rust starts it on subsequent runs, JS starts on first-run)
  useEffect(() => {
    if (isTauri && setupComplete) {
      const waitForBackend = async () => {
        // If this is a fresh setup completion, start backend immediately from JS
        // (Rust couldn't start it because Python didn't exist yet)
        if (justCompletedSetup) {
          console.log('🚀 First run detected: Starting backend immediately after setup...');
          try {
            await startBackendWithEmbeddedPython();
            console.log('Backend start initiated after first-run setup');
          } catch (err) {
            console.error('Failed to start backend after setup:', err);
          }
          // Reset the flag
          setJustCompletedSetup(false);
        } else {
          console.log('Waiting for backend (Rust should have started it)...');
        }

        // Wait for backend to be ready (with retries)
        // Shorter wait for subsequent runs (Rust starts faster), longer for first run
        const maxRetries = justCompletedSetup ? 20 : 10;
        for (let i = 0; i < maxRetries; i++) {
          try {
            const response = await fetch(`${BASE_URL}/api/settings/raw`);
            if (response.ok) {
              console.log('✅ Backend is ready!');
              return;
            }
          } catch (e) {
            // Backend not ready yet
          }
          await new Promise(resolve => setTimeout(resolve, 1000));
          console.log(`Waiting for backend... (${i + 1}/${maxRetries})`);
        }

        // If backend still not ready after waiting, try starting it from JS as fallback
        console.warn('Backend not responding, attempting JS-side start as fallback...');
        try {
          await startBackendWithEmbeddedPython();
          console.log('Fallback backend start initiated, waiting again...');

          // Wait a bit more after fallback start
          for (let i = 0; i < 15; i++) {
            try {
              const response = await fetch(`${BASE_URL}/api/settings/raw`);
              if (response.ok) {
                console.log('✅ Backend is ready (after fallback start)!');
                return;
              }
            } catch (e) {
              // Backend not ready yet
            }
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
        } catch (fallbackErr) {
          console.error('Fallback start also failed:', fallbackErr);
        }

        console.warn('Backend may not be fully ready, but proceeding...');
      };
      waitForBackend();
    }
  }, [setupComplete]);


  // Format elapsed time as mm:ss
  function formatElapsedTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  // Calculate estimated time based on image count
  function getTimeEstimate(imageCount) {
    if (imageCount === 0) return null;

    const totalSeconds = imageCount * (TIME_PER_IMAGE.upload + TIME_PER_IMAGE.ocr + TIME_PER_IMAGE.extraction);
    const adjustedSeconds = totalSeconds / 3;

    if (adjustedSeconds < 60) {
      return `~${Math.round(adjustedSeconds)} seconds`;
    } else if (adjustedSeconds < 3600) {
      const minutes = Math.round(adjustedSeconds / 60);
      return `~${minutes} minute${minutes > 1 ? 's' : ''}`;
    } else {
      const hours = (adjustedSeconds / 3600).toFixed(1);
      return `~${hours} hours`;
    }
  }

  // Calculate remaining time estimate
  function getRemainingTime(processed, total, elapsedSec) {
    if (processed === 0 || elapsedSec === 0) return null;
    const avgTimePerImage = elapsedSec / processed;
    const remaining = (total - processed) * avgTimePerImage;

    if (remaining < 60) {
      return `~${Math.round(remaining)}s remaining`;
    } else {
      const mins = Math.round(remaining / 60);
      return `~${mins}m remaining`;
    }
  }

  // Get warning level based on image count
  function getWarningLevel(imageCount) {
    if (imageCount >= LIMITS.danger) return 'danger';
    if (imageCount >= LIMITS.warning) return 'warning';
    if (imageCount >= LIMITS.recommended) return 'caution';
    return 'ok';
  }

  // Determine if async mode should be used
  function shouldUseAsync(imageCount) {
    if (processingMode === "sync") return false;
    if (processingMode === "async") return true;
    return imageCount > LIMITS.syncMax;
  }

  // Convert fields array → schema object
  function buildSchema(fields) {
    const schema = {};
    fields.forEach((f) => {
      if (f.trim()) schema[f.trim()] = null;
    });
    return schema;
  }

  // Generate default filename with date and time
  function generateDefaultFilename() {
    const now = new Date();
    const dateStr = now.toISOString().split('T')[0]; // YYYY-MM-DD
    const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '-'); // HH-MM-SS
    return `survey_${dateStr}_${timeStr}`;
  }

  // Handle progress updates from async polling
  function handleProgressUpdate(progressData) {
    setProgress({
      ...progressData,
      backendStage: progressData.stage // Backend sends detailed stage message
    });
    const { processed, total, status: jobStatus } = progressData;

    if (jobStatus === "processing") {
      setStatus(`Processing: ${processed}/${total} images (${progressData.percentage}%)`);
    } else if (jobStatus === "completed") {
      setStatus("✅ Extraction complete!");
    }
  }

  // Helper to auto-save file directly (no dialog)
  async function autoSaveFile(resultData, filename, folderPath, format) {
    console.log("📁 [Auto-save] Called with:", { filename, folderPath, format, isTauri });

    if (!folderPath && !browserFolderHandle) {
      console.log("📁 [Auto-save] Skipped: No folder path/handle selected");
      return null;
    }

    const ext = format === 'csv' ? '.csv' : '.xlsx';
    const url = format === 'csv' ? resultData.csvUrl : resultData.excelUrl;
    const fullFilename = filename + ext;

    try {
      // Fetch file from backend
      const response = await fetch(url);
      if (!response.ok) {
        console.error("📁 [Auto-save] Fetch failed:", response.status, response.statusText);
        return null;
      }

      const blob = await response.blob();

      // 1️⃣ Tauri Desktop Mode
      if (isTauri && folderPath) {
        const { invoke } = await import('@tauri-apps/api/core');
        const { join } = await import('@tauri-apps/api/path');

        const fullPath = await join(folderPath, fullFilename);
        console.log("📁 [Auto-save] Saving to:", fullPath);

        const buffer = await blob.arrayBuffer();
        const uint8Array = new Uint8Array(buffer);
        const contents = Array.from(uint8Array);

        const result = await invoke('write_file_bytes', {
          path: fullPath,
          contents: contents
        });

        console.log("📁 [Auto-save] ✅ SUCCESS:", result);
        return fullPath;
      }

      // 2️⃣ Browser Mode with File System Access API
      if (browserFolderHandle) {
        console.log("📁 [Auto-save] Using browser File System Access API");
        const fileHandle = await browserFolderHandle.getFileHandle(fullFilename, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
        console.log("📁 [Auto-save] ✅ SUCCESS (browser):", fullFilename);
        return fullFilename;
      }

      return null;
    } catch (e) {
      console.error("📁 [Auto-save] ❌ Failed:", e);
      console.error("📁 [Auto-save] Error message:", e.message || e);
      return null;
    }
  }

  // Main extraction workflow
  async function handleExtract() {
    if (files.length === 0) {
      setError("Please upload at least one image");
      return;
    }

    if (schemaFields.filter(f => f.trim()).length === 0) {
      setError("Please define at least one field to extract");
      return;
    }

    setError(null);
    setLoading(true);
    setResult(null);
    setProgress(null);
    setStartTime(Date.now());

    // Create abort controller for this operation
    const controller = new AbortController();
    setAbortController(controller);

    const useAsync = shouldUseAsync(files.length);

    try {
      // Step 1: Upload images
      setProgress({ processed: 0, total: files.length, percentage: 0, stage: 'upload' });
      setStatus(`Uploading ${files.length} images...`);

      const uploadRes = await uploadImagesChunked(files, (uploaded, total) => {
        const pct = Math.round((uploaded / total) * 30); // Upload is 30% of total
        setProgress({ processed: uploaded, total, percentage: pct, stage: 'upload' });
        setStatus(`Uploading: ${uploaded}/${total} images`);
      });

      const schema = buildSchema(schemaFields);
      const filename = customFilename.trim() || generateDefaultFilename();

      let finalResultData = null;

      if (useAsync) {
        // ASYNC MODE: Queue job and poll for progress
        setStatus("Queuing extraction job...");
        setProgress({ processed: 0, total: files.length, percentage: 30, stage: 'extraction', backendStage: 'Initializing... Please wait patiently 🙏' });

        const jobRes = await extractBatchAsync(uploadRes.batch_id, schema, filename);

        setStatus(`Processing: 0/${files.length} images (0%)`);
        setProgress({ processed: 0, total: files.length, percentage: 30, stage: 'extraction', backendStage: 'Starting extraction...' });

        // Poll for completion
        const finalResult = await pollJobStatus(jobRes.job_id, (progressData) => {
          const extractPct = 30 + Math.round((progressData.percentage / 100) * 70);
          setProgress({
            ...progressData,
            percentage: extractPct,
            stage: 'extraction',
            backendStage: progressData.stage // Pass backend stage message
          });
          handleProgressUpdate(progressData);
        });

        finalResultData = {
          rows: finalResult.rows,
          excelUrl: getExcelDownloadUrl(finalResult.excel_path),
          csvUrl: getCsvDownloadUrl(finalResult.csv_path),
          suggestedName: filename,
        };

      } else {
        // SYNC MODE: Original behavior for small batches
        setStatus(`Running OCR + AI extraction on ${files.length} images...`);
        setProgress({ processed: 0, total: files.length, percentage: 30, stage: 'extraction' });

        const extractRes = await extractBatch(uploadRes.batch_id, schema, filename);

        finalResultData = {
          rows: extractRes.rows,
          excelUrl: getExcelDownloadUrl(extractRes.excel_path),
          csvUrl: getCsvDownloadUrl(extractRes.csv_path),
          suggestedName: filename,
        };
      }

      // Auto-save logic
      let savedPath = null;
      if (outputFolder) {
        setStatus("💾 Auto-saving file...");
        savedPath = await autoSaveFile(finalResultData, filename, outputFolder, outputFormat);
      }

      setResult({
        ...finalResultData,
        autoSaved: !!savedPath,
        savedPath: savedPath
      });

      setProgress({ processed: files.length, total: files.length, percentage: 100, stage: 'complete' });
      setStatus("✅ Extraction complete!");

    } catch (err) {
      if (err.name === 'AbortError') {
        setError("⛔ Operation cancelled by user");
        setStatus("Cancelled");
      } else {
        // Categorize error for display
        const errorType = err.errorType || '';
        let icon = '❌';
        let message = err.message || "Something went wrong";

        // Use warning icon for recoverable errors
        if (errorType === 'rate_limit') {
          icon = '⚠️';
        } else if (errorType === 'insufficient_credits') {
          icon = '💳';
        } else if (errorType === 'invalid_key') {
          icon = '🔑';
        } else if (errorType === 'no_valid_data') {
          icon = '📄';
        }

        setError(`${icon} ${message}`);
        setStatus("");
      }
      setProgress(null);
    } finally {
      setLoading(false);
      setStartTime(null);
      setAbortController(null);
    }
  }

  // Terminate/cancel handler
  function handleTerminate() {
    if (abortController) {
      abortController.abort();
      setAbortController(null);
      setLoading(false);
      setStatus("⛔ Operation terminated");
      setProgress(null);
    }
  }

  const timeEstimate = getTimeEstimate(files.length);
  const warningLevel = getWarningLevel(files.length);

  return (
    <>
      {/* Setup Screen (first-run only) */}
      {isTauri && !setupComplete && (
        <SetupScreen onSetupComplete={() => {
          setJustCompletedSetup(true); // Mark as fresh setup for immediate backend start
          setSetupComplete(true);
        }} />
      )}

      {/* Main App (after setup or if not Tauri) */}
      {setupComplete && (
        <div className="app">
          {/* Header */}
          <header className="header">
            <div className="header-content">
              <h1>📋 SurveyScriber</h1>
              <p>Transform handwritten survey forms into structured data</p>
            </div>
          </header>

          {/* Settings Modal */}
          <Settings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

          {/* Main Content */}
          <main className="main-content">
            <div className="workflow-container">

              {/* Upload Section */}
              <section className="step-section">
                <div className="step-header">
                  <h2>📤 Upload Survey Images</h2>
                </div>
                <ImageUploader onBatchReady={(newFiles) => {
                  setFiles(newFiles);
                  // Clear previous result when new files are uploaded
                  if (newFiles.length > 0) {
                    setResult(null);
                    setError(null);
                  }
                }} />

                {/* Time Estimate Display */}
                {files.length > 0 && (
                  <div className={`time-estimate ${warningLevel}`}>
                    <div className="estimate-header">
                      <span className="estimate-icon">⏱️</span>
                      <span className="estimate-label">Estimated Processing Time:</span>
                      <span className="estimate-time">{timeEstimate}</span>
                    </div>

                    {warningLevel === 'caution' && (
                      <p className="estimate-warning">
                        ℹ️ Large batch ({files.length} images). Using background processing for reliability.
                      </p>
                    )}
                    {warningLevel === 'warning' && (
                      <p className="estimate-warning">
                        ⚠️ Very large batch ({files.length} images). Processing will take a while but will complete reliably.
                      </p>
                    )}
                    {warningLevel === 'danger' && (
                      <p className="estimate-warning">
                        ⚠️ Extremely large batch ({files.length} images). Ensure background workers are running.
                      </p>
                    )}
                  </div>
                )}
              </section>

              {/* Define Schema Section */}
              <section className="step-section">
                <div className="step-header">
                  <h2>📝 Define Extraction Fields</h2>
                </div>
                <SchemaEditor onChange={setSchemaFields} />
              </section>

              {/* Extract Section */}
              <section className="step-section">
                <div className="step-header">
                  <h2>🚀 Extract Data</h2>
                </div>

                {/* Output Settings - Always visible BEFORE Extract button */}
                <div className="filename-section">
                  <div className="input-group">
                    <label htmlFor="filename">📁 Output Filename (optional)</label>
                    <div className="filename-input-wrapper">
                      <input
                        id="filename"
                        type="text"
                        className="filename-input"
                        placeholder={generateDefaultFilename()}
                        value={customFilename}
                        onChange={(e) => setCustomFilename(e.target.value)}
                      />
                    </div>
                    <p className="filename-hint">Leave blank for auto-generated name</p>
                  </div>

                  {/* Output Folder Selection (Works in both Browser and Desktop) */}
                  <div className="input-group">
                    <label>📂 Save Location & Format</label>
                    <div className="folder-selection">
                      <button
                        className="select-folder-btn"
                        onClick={async () => {
                          try {
                            // 1️⃣ Tauri Desktop Mode
                            if (isTauri) {
                              const { open } = await import('@tauri-apps/plugin-dialog');
                              const selected = await open({
                                directory: true,
                                multiple: false,
                                defaultPath: outputFolder || undefined
                              });
                              if (selected) {
                                setOutputFolder(selected);
                                setBrowserFolderHandle(null);
                              }
                            }
                            // 2️⃣ Browser Mode with File System Access API
                            else if ('showDirectoryPicker' in window) {
                              const handle = await window.showDirectoryPicker({ mode: 'readwrite' });
                              setBrowserFolderHandle(handle);
                              setOutputFolder(handle.name); // Display folder name
                            }
                            // 3️⃣ Fallback for unsupported browsers
                            else {
                              alert('Folder selection is not supported in this browser. Files will be downloaded directly.');
                            }
                          } catch (e) {
                            if (e.name !== 'AbortError') {
                              console.error("Failed to select folder:", e);
                            }
                          }
                        }}
                      >
                        {outputFolder ? `📁 ${outputFolder.length > 30 ? '...' + outputFolder.slice(-27) : outputFolder}` : "Select Output Folder"}
                      </button>

                      {/* Refresh/Clear button */}
                      {(outputFolder || browserFolderHandle) && (
                        <button
                          className="refresh-folder-btn"
                          onClick={() => {
                            setOutputFolder(null);
                            setBrowserFolderHandle(null);
                          }}
                          title="Clear folder selection"
                          style={{
                            padding: '0.5rem 0.75rem',
                            borderRadius: '6px',
                            border: 'none',
                            background: '#4a5568',
                            color: 'white',
                            cursor: 'pointer',
                            fontSize: '0.9rem'
                          }}
                        >
                          🔄
                        </button>
                      )}

                      <select
                        className="format-select"
                        value={outputFormat}
                        onChange={(e) => setOutputFormat(e.target.value)}
                      >
                        <option value="excel">Excel (.xlsx)</option>
                        <option value="csv">CSV (.csv)</option>
                      </select>
                    </div>
                    <p className="filename-hint">
                      {(outputFolder || browserFolderHandle)
                        ? "✅ Files will be saved automatically here"
                        : "ℹ️ Select a folder to auto-save results (or download manually)"}
                    </p>
                  </div>
                </div>

                <button
                  className={`extract-btn ${loading ? 'loading' : ''}`}
                  onClick={handleExtract}
                  disabled={loading}
                >
                  {loading ? "Processing..." : "🚀 Extract & Generate Files"}
                </button>

                {/* Progress Bar */}
                {loading && progress && (
                  <div className="progress-container">
                    <div className="progress-header">
                      <span className="progress-stage">
                        {progress.stage === 'upload' && '📤 Uploading...'}
                        {progress.stage === 'complete' && '✅ Complete!'}
                        {/* Show detailed stage message from backend if available */}
                        {progress.stage === 'extraction' && (
                          progress.backendStage || '🔍 Processing...'
                        )}
                      </span>
                      <span className="progress-timer">
                        ⏱️ {formatElapsedTime(elapsedTime)}
                        {progress.stage === 'extraction' && progress.processed > 0 && (
                          <span className="remaining-time">
                            {' • '}{getRemainingTime(progress.processed, progress.total, elapsedTime)}
                          </span>
                        )}
                      </span>
                    </div>

                    {/* Detailed status message */}
                    {progress.stage === 'extraction' && progress.backendStage && (
                      <div className="detailed-status" style={{
                        padding: '0.5rem 0.75rem',
                        marginBottom: '0.75rem',
                        background: 'rgba(66, 153, 225, 0.1)',
                        borderRadius: '6px',
                        fontSize: '0.9rem',
                        color: '#90cdf4',
                        textAlign: 'center'
                      }}>
                        {progress.backendStage}
                      </div>
                    )}

                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${progress.percentage}%` }}
                      />
                    </div>
                    <div className="progress-text">
                      {progress.stage === 'upload'
                        ? `${progress.processed} / ${progress.total} files uploaded`
                        : `${progress.processed} / ${progress.total} images processed`
                      }
                      <span className="progress-percent">{progress.percentage}%</span>
                    </div>
                    {/* Terminate Button */}
                    <button
                      className="terminate-btn"
                      onClick={handleTerminate}
                      type="button"
                    >
                      ⛔ Terminate Operation
                    </button>
                  </div>
                )}

                {error && <p className="error-message">❌ {error}</p>}

                {/* Completion message - always show download buttons */}
                {result && (
                  <div className="results-card">
                    <h3>🎉 Extraction is completed</h3>
                    <p><strong>{result.rows}</strong> records extracted successfully</p>

                    {/* Auto-save success message */}
                    {result.autoSaved && (
                      <div className="auto-save-success" style={{ marginBottom: '1rem' }}>
                        <p>✅ File auto-saved to:</p>
                        <code className="path-display">{result.savedPath}</code>
                      </div>
                    )}

                    {/* Always show download buttons */}
                    <div className="download-buttons">
                      <button
                        className="download-btn excel"
                        onClick={() => saveWithDialog(
                          result.excelUrl,
                          (customFilename || result.suggestedName) + '.xlsx',
                          'excel',
                          outputFolder
                        )}
                      >
                        📊 Save Excel (.xlsx)
                      </button>
                      <button
                        className="download-btn csv"
                        onClick={() => saveWithDialog(
                          result.csvUrl,
                          (customFilename || result.suggestedName) + '.csv',
                          'csv',
                          outputFolder
                        )}
                      >
                        📄 Save CSV
                      </button>
                    </div>
                  </div>
                )}
              </section>

              {/* Settings Section at the End */}
              <section className="step-section settings-section">
                <button
                  className="settings-header-btn"
                  onClick={() => setSettingsOpen(true)}
                >
                  <h2>⚙️ Settings</h2>
                  <p className="settings-description">
                    Configure your AI provider, OCR engine, and other preferences.
                  </p>
                </button>
              </section>
            </div>
          </main>

          {/* Footer */}
          <footer className="footer">
            <p>SurveyScriber • Handwritten Survey Data Extraction</p>
            <div className="footer-contact">
              <p className="developer">Developed by <strong>Drubo Paul</strong></p>
              <p className="contact-info">
                <a href="mailto:pdrubo064@gmail.com">pdrubo064@gmail.com</a>
                {' • '}
                <a href="mailto:pauldruboraj064@gmail.com">pauldruboraj064@gmail.com</a>
              </p>
              <p className="contact-info">
                <a href="tel:+8801856365064">+880 1856-365064</a>
                {' • '}
                <a href="tel:+8801757836300">+880 1757-836300</a>
              </p>
            </div>
          </footer>
        </div>
      )}
    </>
  );
}

export default App;
