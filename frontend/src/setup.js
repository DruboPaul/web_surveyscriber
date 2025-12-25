/**
 * First-run setup module for SurveyScriber
 * Extracts bundled Python environment on first launch
 */

import { appDataDir, join, resourceDir } from '@tauri-apps/api/path';
import { exists, mkdir } from '@tauri-apps/plugin-fs';
import { Command } from '@tauri-apps/plugin-shell';

const PYTHON_FOLDER_NAME = 'python-embed';
const SETUP_COMPLETE_MARKER = '.setup-complete';

/**
 * Check if first-run setup has been completed
 * Checks BUNDLED Python first, then app_data fallback
 */
export async function isSetupComplete() {
    try {
        const resDir = await resourceDir();
        const appData = await appDataDir();

        // First check: Is Python available in BUNDLED location?
        const bundledPython = await join(resDir, PYTHON_FOLDER_NAME, 'python.exe');
        if (await exists(bundledPython)) {
            console.log('✅ Bundled Python found - no setup needed');
            return true;  // Bundled Python exists, no copy needed
        }

        // Second check: Is Python in app_data? (from previous setup)
        const appdataPython = await join(appData, PYTHON_FOLDER_NAME, 'python.exe');
        if (await exists(appdataPython)) {
            console.log('✅ AppData Python found - setup complete');
            return true;
        }

        // No Python found anywhere
        console.log('⚠️ No Python found - setup required');
        return false;
    } catch (e) {
        console.error('Error checking setup status:', e);
        return false;
    }
}


/**
 * Get the path to the Python executable
 * Checks BUNDLED location first (resource_dir), then falls back to app_data
 */
export async function getPythonPath() {
    const resDir = await resourceDir();
    const appData = await appDataDir();

    // Try bundled Python first (from install location)
    const bundledPython = await join(resDir, PYTHON_FOLDER_NAME, 'python.exe');
    if (await exists(bundledPython)) {
        console.log('[getPythonPath] Using BUNDLED Python:', bundledPython);
        return bundledPython;
    }

    // Fall back to app_data location
    const appdataPython = await join(appData, PYTHON_FOLDER_NAME, 'python.exe');
    console.log('[getPythonPath] Using AppData Python:', appdataPython);
    return appdataPython;
}

/**
 * Get the path to the backend entry script
 */
export async function getBackendEntryPath() {
    const resDir = await resourceDir();

    // Try multiple possible locations
    const possiblePaths = [
        await join(resDir, 'backend_entry.py'),
        await join(resDir, '..', 'backend_entry.py'),
        await join(resDir, '_up_', '_up_', '_up_', 'backend_entry.py'),
    ];

    for (const path of possiblePaths) {
        if (await exists(path)) {
            return path;
        }
    }

    return possiblePaths[0]; // Return first as fallback
}

/**
 * Get the resource directory (where backend folder is located)
 */
export async function getBackendDir() {
    const resDir = await resourceDir();

    // Try multiple possible locations for backend folder
    const possiblePaths = [
        await join(resDir, 'backend'),
        await join(resDir, '..', 'backend'),
        await join(resDir, '_up_', '_up_', '_up_', 'backend'),
    ];

    for (const path of possiblePaths) {
        if (await exists(path)) {
            return path;
        }
    }

    return possiblePaths[0]; // Return first as fallback
}

/**
 * FALLBACK: Download Python from python.org when pre-bundled is not available
 */
async function downloadAndInstallPython(pythonDir, onProgress, onStatus) {
    const PYTHON_URL = 'https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip';
    const REQUIREMENTS = [
        'fastapi', 'uvicorn', 'paddleocr', 'paddlepaddle',
        'openai', 'anthropic', 'google-generativeai',
        'pandas', 'openpyxl', 'pillow', 'sqlalchemy',
        'python-multipart', 'pydantic'
    ];

    try {
        const appData = await appDataDir();
        const tempDir = await join(appData, 'temp');
        const zipPath = await join(tempDir, 'python-embed.zip');

        try { await mkdir(tempDir, { recursive: true }); } catch (e) { }

        onProgress(20);
        onStatus('⬇️ Downloading Python 3.10 (~8MB)...');

        const downloadCmd = Command.create('powershell', [
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
            `Invoke-WebRequest -Uri '${PYTHON_URL}' -OutFile '${zipPath}'`
        ]);
        const downloadResult = await downloadCmd.execute();
        if (downloadResult.code !== 0) return false;

        onProgress(40);
        onStatus('📦 Extracting Python...');

        const extractCmd = Command.create('powershell', [
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
            `Expand-Archive -Path '${zipPath}' -DestinationPath '${pythonDir}' -Force`
        ]);
        const extractResult = await extractCmd.execute();
        if (extractResult.code !== 0) return false;

        onProgress(50);
        onStatus('🔧 Configuring Python for pip...');

        const pthPath = await join(pythonDir, 'python310._pth');
        const pthContent = 'python310.zip\r\n.\r\nLib\\site-packages\r\nimport site\r\n';
        const { invoke } = await import('@tauri-apps/api/core');
        await invoke('write_file_bytes', {
            path: pthPath,
            contents: Array.from(new TextEncoder().encode(pthContent))
        });

        onProgress(55);
        onStatus('📥 Installing pip...');

        const getPipPath = await join(tempDir, 'get-pip.py');
        const pythonExe = await join(pythonDir, 'python.exe');

        const downloadPipCmd = Command.create('powershell', [
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
            `Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '${getPipPath}'`
        ]);
        await downloadPipCmd.execute();

        const installPipCmd = Command.create('cmd', ['/c', pythonExe, getPipPath]);
        await installPipCmd.execute();

        onProgress(60);
        onStatus('📦 Installing packages (5-10 minutes)...');

        for (let i = 0; i < REQUIREMENTS.length; i++) {
            const pkg = REQUIREMENTS[i];
            onStatus(`📦 Installing ${pkg}... (${i + 1}/${REQUIREMENTS.length})`);
            const installCmd = Command.create('cmd', ['/c', pythonExe, '-m', 'pip', 'install', pkg, '--no-cache-dir']);
            await installCmd.execute();
            onProgress(60 + Math.floor((i + 1) / REQUIREMENTS.length * 25));
        }

        return true;
    } catch (error) {
        console.error('Download fallback error:', error);
        return false;
    }
}

/**
 * Run first-time setup - copies or extracts Python environment
 * Now supports BOTH pre-extracted folder AND zip file
 * @param {Function} onProgress - Callback for progress updates (0-100)
 * @param {Function} onStatus - Callback for status message updates
 * @returns {Promise<boolean>} - True if setup successful
 */
export async function runFirstTimeSetup(onProgress = () => { }, onStatus = () => { }) {
    try {
        const appData = await appDataDir();
        const pythonDir = await join(appData, PYTHON_FOLDER_NAME);
        const resDir = await resourceDir();

        console.log('Starting first-time setup...');
        console.log('   App Data:', appData);
        console.log('   Python Dir:', pythonDir);
        console.log('   Resource Dir:', resDir);

        onProgress(5);
        onStatus('Initializing setup...');

        // Create app data directory if needed
        try {
            await mkdir(appData, { recursive: true });
        } catch (e) {
            // Directory might already exist
        }

        onProgress(10);
        onStatus('Locating Python environment...');

        // ===== FIRST: Check for PRE-EXTRACTED python-embed folder =====
        const preExtractedPaths = [
            await join(resDir, 'python-embed'),
            await join(resDir, '..', 'python-embed'),
            await join(appData, '..', 'SurveyScriber', 'python-embed'),
            await join(resDir, '_up_', '_up_', '_up_', 'python-embed'),
        ];

        console.log('Looking for pre-extracted python-embed folder...');
        let preExtractedPath = null;
        for (const path of preExtractedPaths) {
            console.log('   Checking folder:', path);
            try {
                const pythonExe = await join(path, 'python.exe');
                if (await exists(pythonExe)) {
                    preExtractedPath = path;
                    console.log('   ✅ Found pre-extracted at:', path);
                    break;
                }
            } catch (e) {
                console.log('   ❌ Error checking path:', path, e.message);
            }
        }

        // If pre-extracted folder found, COPY it (much faster than extraction)
        if (preExtractedPath) {
            onProgress(15);
            onStatus('Copying pre-installed Python environment...');

            console.log('Copying pre-extracted Python from:', preExtractedPath);

            // Use PowerShell to copy the folder (handles large directories well)
            const copyCommand = Command.create('powershell', [
                '-NoProfile',
                '-ExecutionPolicy', 'Bypass',
                '-Command',
                `Copy-Item -Path '${preExtractedPath}' -Destination '${pythonDir}' -Recurse -Force`
            ]);

            const copyOutput = await copyCommand.execute();
            if (copyOutput.code !== 0) {
                console.error('Copy failed:', copyOutput.stderr);
                throw new Error('Failed to copy Python environment: ' + (copyOutput.stderr || 'Unknown error'));
            }

            console.log('   ✅ Python environment copied successfully');
            onProgress(85);

        } else {
            // ===== FALLBACK: Try to find ZIP file =====
            console.log('No pre-extracted folder found, looking for python-embed.zip...');

            const possibleZipPaths = [
                await join(appData, '..', 'SurveyScriber', 'python-embed.zip'),
                await join(resDir, 'python-embed.zip'),
                await join(resDir, '..', 'python-embed.zip'),
                await join(appData, 'python-embed.zip'),
                await join(resDir, '_up_', '_up_', '_up_', 'python-embed.zip'),
            ];

            let zipPath = null;
            for (const path of possibleZipPaths) {
                console.log('   Checking zip:', path);
                try {
                    if (await exists(path)) {
                        zipPath = path;
                        console.log('   ✅ Found zip at:', path);
                        break;
                    }
                } catch (e) {
                    console.log('   ❌ Error checking path:', path, e.message);
                }
            }

            if (!zipPath) {
                // ===== FINAL FALLBACK: Download Python from internet =====
                console.log('No local Python found! Trying to download from python.org...');
                onProgress(15);
                onStatus('⬇️ Downloading Python from python.org (this requires internet)...');

                try {
                    const downloadSuccess = await downloadAndInstallPython(pythonDir, onProgress, onStatus);
                    if (!downloadSuccess) {
                        throw new Error('Failed to download and install Python');
                    }
                    console.log('   ✅ Python downloaded and installed successfully');
                    onProgress(85);
                } catch (downloadError) {
                    console.error('Download fallback failed:', downloadError);
                    throw new Error('Python environment not found and download failed.\n\nPlease try:\n1. Check your internet connection\n2. Reinstall SurveyScriber\n3. Run as Administrator\n4. Manually install Python 3.10 from python.org');
                }
            } else {

                onProgress(15);
                onStatus('Preparing to extract (~300MB, this takes 2-5 minutes)...');

                // Start a progress simulation that updates during extraction
                let currentProgress = 20;
                const progressInterval = setInterval(() => {
                    // Slowly increment progress from 20 to 85 during extraction
                    if (currentProgress < 85) {
                        currentProgress += 1;
                        onProgress(currentProgress);

                        // Update status messages to show activity
                        if (currentProgress < 40) {
                            onStatus('Extracting Python environment... (this may take a few minutes)');
                        } else if (currentProgress < 60) {
                            onStatus('Extracting packages and dependencies...');
                        } else if (currentProgress < 75) {
                            onStatus('Installing machine learning libraries...');
                        } else {
                            onStatus('Almost done, finalizing extraction...');
                        }
                    }
                }, 3000); // Update every 3 seconds

                try {
                    // Extract ZIP using PowerShell (available on all Windows systems)
                    console.log('Extracting Python environment...');
                    const extractCommand = Command.create('powershell', [
                        '-NoProfile',
                        '-ExecutionPolicy', 'Bypass',
                        '-Command',
                        `Expand-Archive -Path '${zipPath}' -DestinationPath '${pythonDir}' -Force`
                    ]);

                    const output = await extractCommand.execute();

                    // Stop the progress simulation
                    clearInterval(progressInterval);

                    if (output.code !== 0) {
                        console.error('Extraction failed:', output.stderr);
                        const errorMsg = output.stderr || 'Unknown error';

                        // Provide helpful error messages
                        if (errorMsg.includes('Access') || errorMsg.includes('denied')) {
                            throw new Error('Permission denied. Please run as administrator or check antivirus settings.');
                        } else if (errorMsg.includes('disk') || errorMsg.includes('space')) {
                            throw new Error('Not enough disk space. Please free up at least 1GB and try again.');
                        } else {
                            throw new Error('Failed to extract Python environment: ' + errorMsg);
                        }
                    }
                } catch (extractError) {
                    clearInterval(progressInterval);
                    throw extractError;
                }

                onProgress(88);
                onStatus('Verifying installation...');

                // Verify Python was actually extracted
                const pythonExePath = await join(pythonDir, 'python.exe');
                const pythonExists = await exists(pythonExePath);

                if (!pythonExists) {
                    console.error('Python.exe not found after extraction at:', pythonExePath);
                    throw new Error('Python environment extraction incomplete. Your antivirus may have blocked python.exe. Please add an exception for SurveyScriber and try again.');
                }

                onProgress(90);
                onStatus('📦 Installing OCR models (prevents slow downloads later)...');

                // Copy bundled PaddleOCR models to user's .paddlex folder
                // This prevents the 5-20 minute first-time download from China servers
                try {
                    const homeDir = await join(appData, '..', '..');  // Navigate to user home
                    const paddlexDest = await join(homeDir, '.paddlex', 'official_models');

                    // Find the bundled models
                    const possibleModelPaths = [
                        await join(appData, '..', 'SurveyScriber', 'paddlex_models'),
                        await join(resDir, 'paddlex_models'),
                        await join(resDir, '..', 'paddlex_models'),
                    ];

                    let modelsSource = null;
                    for (const path of possibleModelPaths) {
                        console.log('   Checking for models at:', path);
                        if (await exists(path)) {
                            modelsSource = path;
                            console.log('   ✅ Found models at:', path);
                            break;
                        }
                    }

                    if (modelsSource) {
                        console.log('Copying OCR models to:', paddlexDest);

                        // Use PowerShell to copy the models folder
                        const copyCommand = Command.create('powershell', [
                            '-NoProfile',
                            '-ExecutionPolicy', 'Bypass',
                            '-Command',
                            `New-Item -ItemType Directory -Force -Path '${paddlexDest}' | Out-Null; Copy-Item -Path '${modelsSource}\\*' -Destination '${paddlexDest}' -Recurse -Force`
                        ]);

                        const copyOutput = await copyCommand.execute();
                        if (copyOutput.code === 0) {
                            console.log('   ✅ OCR models installed successfully');
                        } else {
                            console.warn('   ⚠️ Model copy warning:', copyOutput.stderr);
                            // Non-fatal - models will download on first use if copy fails
                        }
                    } else {
                        console.warn('   ⚠️ Bundled models not found - will download on first use');
                    }
                } catch (modelError) {
                    console.warn('   ⚠️ Model installation warning:', modelError);
                    // Non-fatal error - models will download on first use if needed
                }

                onProgress(95);
                onStatus('Creating configuration...');

                // Create setup complete marker
                const markerPath = await join(appData, SETUP_COMPLETE_MARKER);
                const { invoke } = await import('@tauri-apps/api/core');
                await invoke('write_file_bytes', {
                    path: markerPath,
                    contents: Array.from(new TextEncoder().encode('setup-complete'))
                });

                onProgress(100);
                onStatus('Setup complete!');
                console.log('First-time setup complete!');

                return true;
            } // Close the else block for ZIP extraction
        } // Close the outer else block
    } catch (e) {
        console.error('Setup failed:', e);
        throw e;
    }
}

/**
 * Start the backend server using the extracted Python
 */
export async function startBackendWithEmbeddedPython() {
    const pythonPath = await getPythonPath();
    const backendEntry = await getBackendEntryPath();
    const backendDir = await getBackendDir();
    const resDir = await resourceDir();

    console.log('Starting backend...');
    console.log('   Python:', pythonPath);
    console.log('   Entry:', backendEntry);
    console.log('   Backend Dir:', backendDir);

    // Check if Python exists
    if (!(await exists(pythonPath))) {
        throw new Error('Python not found. Please run first-time setup.');
    }

    // Check if backend entry exists
    if (!(await exists(backendEntry))) {
        console.error('Backend entry not found at:', backendEntry);
        throw new Error('Backend entry script not found. Please reinstall SurveyScriber.');
    }

    // Start the backend with proper PYTHONPATH
    const command = Command.create('cmd', [
        '/c',
        pythonPath,
        backendEntry
    ], {
        env: {
            PYTHONPATH: `${resDir};${backendDir}`,
            DISABLE_MODEL_SOURCE_CHECK: 'True'
        }
    });

    // Set up output listeners for debugging
    command.stdout.on('data', (data) => {
        console.log('[Backend]', data);
    });

    command.stderr.on('data', (data) => {
        console.error('[Backend Error]', data);
    });

    const child = await command.spawn();
    console.log('Backend started, PID:', child.pid);

    return child;
}
