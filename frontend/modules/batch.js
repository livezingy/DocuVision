/**
 * Batch processing (v1.8.3 B1b) - domain module (D14).
 *
 * The only non-whitelisted cross-domain dependency is D6's getProcessingOptions (used by
 * createBatch); it is injected into initBatchProcessing at boot, keeping createBatch's call
 * site byte-identical. The module-scope "same-name binding" trick lets the body call
 * `getProcessingOptions()` with zero edits; app.js wires `initBatchProcessing({ getProcessingOptions })`.
 */
import { API_BASE_URL } from './api-config.js';
import { showNotification } from './notifications.js';
import { escapeHtml } from './utils/dom.js';

let getProcessingOptions = function () { return {}; };

/**
 * Initialize batch processing features
 */
export function initBatchProcessing(deps = {}) {
    if (typeof deps.getProcessingOptions === 'function') {
        getProcessingOptions = deps.getProcessingOptions;
    }

    window.batchState = {
        batches: [],
        currentBatch: null,
        selectedFiles: [],
        pollTimer: null
    };

    const fileInput = document.getElementById('batchFileInput');
    const selectBtn = document.getElementById('batchSelectFilesBtn');
    const fileCount = document.getElementById('batchFileCount');

    if (selectBtn && fileInput) {
        selectBtn.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', () => {
            window.batchState.selectedFiles = Array.from(fileInput.files || []);
            if (fileCount) {
                fileCount.textContent = window.batchState.selectedFiles.length
                    ? `${window.batchState.selectedFiles.length} file(s) selected`
                    : '';
            }
        });
    }

    document.getElementById('batchCreateBtn')?.addEventListener('click', async () => {
        const name = document.getElementById('batchNameInput')?.value || 'Batch job';
        const files = window.batchState.selectedFiles || [];
        if (!files.length) {
            showNotification('Select files first', 'warning');
            return;
        }
        const batch = await createBatch(name, files);
        if (batch) {
            window.batchState.currentBatch = batch;
            setBatchControlsForBatch(batch);
            updateBatchUI(batch);
        }
    });

    document.getElementById('batchStartBtn')?.addEventListener('click', async () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) await startBatch(id);
    });
    document.getElementById('batchPauseBtn')?.addEventListener('click', async () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) await pauseBatch(id);
    });
    document.getElementById('batchResumeBtn')?.addEventListener('click', async () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) await resumeBatch(id);
    });
    document.getElementById('batchCancelBtn')?.addEventListener('click', async () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) await cancelBatch(id);
    });
    document.getElementById('batchRetryBtn')?.addEventListener('click', async () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (!id) return;
        try {
            const r = await fetch(`${API_BASE_URL}/batch/${id}/retry`, { method: 'POST' });
            if (r.ok) {
                showNotification('Failed tasks reset; click Start to retry', 'info');
                await startBatch(id);
            }
        } catch (e) {
            showNotification(`Retry failed: ${e.message}`, 'error');
        }
    });
    document.getElementById('batchDownloadCsvBtn')?.addEventListener('click', () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) downloadBatchExport(id, 'csv');
    });
    document.getElementById('batchDownloadJsonBtn')?.addEventListener('click', () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) downloadBatchExport(id, 'json');
    });
    document.getElementById('batchDownloadXlsxBtn')?.addEventListener('click', () => {
        const id = window.batchState.currentBatch?.batch_id;
        if (id) downloadBatchExport(id, 'xlsx');
    });
}

/**
 * Fetch batch export and trigger a file download (not an in-browser tab).
 */
export async function downloadBatchExport(batchId, kind) {
    const validationOnly = document.getElementById('batchValidationPassedOnly')?.checked;
    const validationQuery = validationOnly ? '&validation_passed_only=true' : '';
    const paths = {
        csv: `/batch/${batchId}/export.csv?mode=kie${validationQuery}`,
        json: `/batch/${batchId}/export.json`,
        xlsx: `/batch/${batchId}/export.xlsx?mode=all`,
    };
    const filenames = {
        csv: `batch_${batchId}_kie.csv`,
        json: `batch_${batchId}.json`,
        xlsx: `batch_${batchId}.xlsx`,
    };
    const mimeTypes = {
        csv: 'text/csv;charset=utf-8',
        json: 'application/json',
        xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    };
    const path = paths[kind];
    if (!path) return;

    try {
        const response = await fetch(`${API_BASE_URL}${path}`);
        if (!response.ok) {
            const detail = await response.text().catch(() => '');
            throw new Error(detail || `HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const objectUrl = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = objectUrl;
        anchor.download = filenames[kind];
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(objectUrl);
        showNotification(`${kind.toUpperCase()} downloaded`, 'success');
    } catch (error) {
        showNotification(`Download failed: ${error.message}`, 'error');
    }
}

export function setBatchControlsForBatch(batch) {
    const hasBatch = Boolean(batch?.batch_id);
    const terminal = ['completed', 'failed', 'cancelled'].includes(batch?.status);
    const processing = batch?.status === 'processing';
    const paused = batch?.status === 'paused';
    const hasPending = Array.isArray(batch.tasks) && batch.tasks.some(t => t.status === 'pending');

    const set = (id, on) => {
        const el = document.getElementById(id);
        if (el) el.disabled = !on;
    };
    set('batchStartBtn', hasBatch && !processing && (batch.status === 'pending' || hasPending));
    set('batchPauseBtn', hasBatch && processing);
    set('batchResumeBtn', hasBatch && paused);
    set('batchCancelBtn', hasBatch && !terminal);
    set('batchRetryBtn', hasBatch && terminal);
    set('batchDownloadCsvBtn', hasBatch && (terminal || processing));
    set('batchDownloadJsonBtn', hasBatch && (terminal || processing));
    set('batchDownloadXlsxBtn', hasBatch && (terminal || processing));
}

/**
 * Create a new batch job
 */
export async function createBatch(name, files) {
    try {
        const formData = new FormData();
        formData.append('name', name);

        files.forEach(file => {
            formData.append('files', file);
        });

        formData.append('options', JSON.stringify(getProcessingOptions()));

        const response = await fetch(`${API_BASE_URL}/batch`, {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const batch = await response.json();
            window.batchState.currentBatch = batch;
            setBatchControlsForBatch(batch);
            showNotification(`Batch "${name}" created with ${batch.total_tasks} files`, 'success');
            return batch;
        } else {
            throw new Error('Failed to create batch');
        }
    } catch (error) {
        showNotification(`Batch creation failed: ${error.message}`, 'error');
        return null;
    }
}

/**
 * Start batch processing
 */
export async function startBatch(batchId) {
    try {
        const response = await fetch(`${API_BASE_URL}/batch/${batchId}/start`, {
            method: 'POST'
        });

        if (response.ok) {
            showNotification('Batch processing started', 'success');
            pollBatchStatus(batchId);
            return true;
        }
        return false;
    } catch (error) {
        showNotification(`Failed to start batch: ${error.message}`, 'error');
        return false;
    }
}

/**
 * Poll batch status
 */
export async function pollBatchStatus(batchId) {
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/batch/${batchId}`);
            const batch = await response.json();

            updateBatchUI(batch);

            if (batch.status === 'completed' || batch.status === 'failed' || batch.status === 'cancelled') {
                clearInterval(pollInterval);
                showNotification(`Batch ${batch.status}: ${batch.completed_tasks}/${batch.total_tasks} completed`,
                    batch.status === 'completed' ? 'success' : 'warning');
            }
        } catch (error) {
            clearInterval(pollInterval);
        }
    }, 2000);
}

/**
 * Update batch UI
 */
export function updateBatchUI(batch) {
    if (!batch) return;
    window.batchState.currentBatch = batch;
    setBatchControlsForBatch(batch);

    const statusText = document.getElementById('batchStatusText');
    const progressText = document.getElementById('batchProgressText');
    if (statusText) {
        statusText.textContent = `Status: ${batch.status} | ${batch.completed_tasks}/${batch.total_tasks} done`;
    }
    if (progressText) {
        progressText.textContent = batch.progress != null ? `Progress: ${batch.progress}%` : '';
    }

    const tbody = document.getElementById('batchTaskTableBody');
    if (!tbody || !Array.isArray(batch.tasks)) return;
    tbody.innerHTML = '';
    batch.tasks.forEach(task => {
        const tr = document.createElement('tr');
        const kieHit = task.result?.quality?.kie_production_hit ?? '';
        const err = task.error || task.result?.kie_meta?.error_message || '';
        tr.innerHTML = `
            <td style="padding:8px;">${escapeHtml(task.file_name || '')}</td>
            <td style="padding:8px;">${escapeHtml(task.status || '')}</td>
            <td style="padding:8px;">${kieHit === true ? 'yes' : kieHit === false ? 'no' : ''}</td>
            <td style="padding:8px;">${escapeHtml(String(err).slice(0, 120))}</td>
        `;
        tbody.appendChild(tr);
    });
}

/**
 * Pause batch
 */
export async function pauseBatch(batchId) {
    try {
        const response = await fetch(`${API_BASE_URL}/batch/${batchId}/pause`, {
            method: 'POST'
        });
        if (response.ok) {
            showNotification('Batch paused', 'info');
        }
    } catch (error) {
        showNotification(`Failed to pause: ${error.message}`, 'error');
    }
}

/**
 * Resume batch
 */
export async function resumeBatch(batchId) {
    try {
        const response = await fetch(`${API_BASE_URL}/batch/${batchId}/resume`, {
            method: 'POST'
        });
        if (response.ok) {
            showNotification('Batch resumed', 'success');
            pollBatchStatus(batchId);
        }
    } catch (error) {
        showNotification(`Failed to resume: ${error.message}`, 'error');
    }
}

/**
 * Cancel batch
 */
export async function cancelBatch(batchId) {
    try {
        const response = await fetch(`${API_BASE_URL}/batch/${batchId}/cancel`, {
            method: 'POST'
        });
        if (response.ok) {
            showNotification('Batch cancelled', 'warning');
        }
    } catch (error) {
        showNotification(`Failed to cancel: ${error.message}`, 'error');
    }
}

/**
 * Get batch results
 */
export async function getBatchResults(batchId) {
    try {
        const response = await fetch(`${API_BASE_URL}/batch/${batchId}/results`);
        if (response.ok) {
            return await response.json();
        }
        return null;
    } catch (error) {
        showNotification(`Failed to get results: ${error.message}`, 'error');
        return null;
    }
}
