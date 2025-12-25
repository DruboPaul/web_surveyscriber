// Central API client for backend communication

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
// Chunk size for large uploads
const CHUNK_SIZE = 100;

/* ==============================
   1️⃣ Upload Images (Chunked for large batches)
============================== */
export async function uploadImages(files, onProgress = null) {
    const formData = new FormData();

    for (const file of files) {
        formData.append("files", file);
    }

    const response = await fetch(`${BASE_URL}/upload/images`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        throw new Error("Failed to upload images");
    }

    return response.json();
}

/**
 * Upload files in chunks for large batches
 * @param {File[]} files - Array of files to upload
 * @param {Function} onProgress - Callback for progress updates (uploaded, total)
 * @returns {Promise<object>} - Upload result with batch_id
 */
export async function uploadImagesChunked(files, onProgress = null) {
    if (files.length <= CHUNK_SIZE) {
        // Small batch - use regular upload
        return uploadImages(files, onProgress);
    }

    // Large batch - upload in chunks
    let batchId = null;
    const totalFiles = files.length;
    let uploadedCount = 0;

    for (let i = 0; i < files.length; i += CHUNK_SIZE) {
        const chunk = files.slice(i, i + CHUNK_SIZE);
        const formData = new FormData();

        for (const file of chunk) {
            formData.append("files", file);
        }

        // Append batch_id if continuing an existing batch
        if (batchId) {
            formData.append("batch_id", batchId);
        }

        const response = await fetch(`${BASE_URL}/upload/images`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Failed to upload chunk ${Math.floor(i / CHUNK_SIZE) + 1}`);
        }

        const result = await response.json();

        // Get batch_id from first chunk
        if (!batchId) {
            batchId = result.batch_id;
        }

        uploadedCount += chunk.length;

        if (onProgress) {
            onProgress(uploadedCount, totalFiles);
        }
    }

    return { batch_id: batchId, file_count: totalFiles };
}

/* ==============================
   2️⃣ Extract Batch → Excel/CSV (Sync - for small batches)
============================== */
export async function extractBatch(batchId, schema, customFilename = null) {
    const response = await fetch(`${BASE_URL}/extract/batch`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            batch_id: batchId,
            schema: schema,
            custom_filename: customFilename,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to extract batch");
    }

    return response.json();
}

/* ==============================
   3️⃣ Extract Batch Async (Enterprise scale)
============================== */
export async function extractBatchAsync(batchId, schema, customFilename = null) {
    const response = await fetch(`${BASE_URL}/extract/batch/async`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            batch_id: batchId,
            schema: schema,
            custom_filename: customFilename,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to queue extraction job");
    }

    return response.json();
}

/* ==============================
   4️⃣ Get Job Status (for async extraction)
============================== */
export async function getJobStatus(jobId) {
    const response = await fetch(`${BASE_URL}/extract/batch/status/${jobId}`);

    if (!response.ok) {
        if (response.status === 404) {
            return { status: "not_found" };
        }
        throw new Error("Failed to get job status");
    }

    return response.json();
}

/**
 * Poll job status until completion
 * @param {string} jobId - Job ID to poll
 * @param {Function} onProgress - Callback for progress updates
 * @param {number} intervalMs - Polling interval in milliseconds
 * @returns {Promise<object>} - Final job result
 */
export async function pollJobStatus(jobId, onProgress = null, intervalMs = 2000) {
    return new Promise((resolve, reject) => {
        const poll = async () => {
            try {
                const status = await getJobStatus(jobId);

                if (onProgress) {
                    onProgress(status);
                }

                if (status.status === "completed") {
                    resolve(status);
                } else if (status.status?.startsWith("error")) {
                    // Parse error type and create user-friendly message
                    const errorType = status.status.split(":")[1] || "unknown";
                    const errorMessage = status.error_message || getDefaultErrorMessage(errorType);
                    const error = new Error(errorMessage);
                    error.errorType = errorType;
                    reject(error);
                } else if (status.status === "not_found") {
                    reject(new Error("Job not found"));
                } else {
                    // Continue polling
                    setTimeout(poll, intervalMs);
                }
            } catch (error) {
                reject(error);
            }
        };

        poll();
    });
}

/**
 * Get user-friendly error message based on error type
 */
function getDefaultErrorMessage(errorType) {
    const messages = {
        "rate_limit": "API rate limit exceeded. Please wait a moment and try again.",
        "insufficient_credits": "API credits exhausted. Please add credits to your account or switch to a different AI provider in Settings.",
        "invalid_key": "API key is invalid or expired. Please check your API key in Settings.",
        "no_valid_data": "No text could be extracted from the images. Please try with clearer images.",
        "unknown": "An unexpected error occurred during extraction."
    };
    return messages[errorType] || messages["unknown"];
}

/* ==============================
   5️⃣ Build Download URLs
============================== */
export function getExcelDownloadUrl(excelPath) {
    return `${BASE_URL}/${excelPath}`;
}

export function getCsvDownloadUrl(csvPath) {
    return `${BASE_URL}/${csvPath}`;
}

/* ==============================
   6️⃣ Test AI Connection
============================== */
/**
 * Test the currently configured AI provider API key
 * @returns {Promise<{valid: boolean, provider: string, message: string}>}
 */
export async function testAiConnection() {
    const response = await fetch(`${BASE_URL}/api/settings/test-ai`, {
        method: "POST",
        headers: { "Content-Type": "application/json" }
    });

    if (!response.ok) {
        throw new Error("Failed to test AI connection");
    }

    return response.json();
}
