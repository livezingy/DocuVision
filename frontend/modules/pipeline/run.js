/**
 * Processing pipeline - run half (v1.8.3 B4; sibling-imports per the B-decision) -
 * domain module (D8).
 *
 * D8 is split across pipeline/run.js (this file), pipeline/result.js and, since v1.9 S2-5,
 * pipeline/task-socket.js (the WebSocket / fallback-polling transport) because the domain
 * is >500 lines. Same-directory sibling imports are one-way and cycle-free. All
 * cross-domain deps (D1 / D3 / D5 / D6 / D7) are injected at boot; the mediator
 * updateResultsDisplay stays in app.js and is injected into pipeline/result.js. The
 * same-name module-scope binding keeps every call site byte-identical - task-socket.js
 * receives failProcessing as an argument instead, since it has no injection of its own.
 */
import { showNotification } from '../notifications.js';
import { updateStatusBarThrottled } from '../status-bar.js';
import { API_BASE_URL, API_ROOT_URL } from '../api-config.js';
import { lastHealthPayload } from '../api-state.js';
import { currentQueueItem, setTaskId } from '../preview-state.js';
import { clearResultsDisplay } from './result.js';
import { createTaskSocket } from './task-socket.js';

// --- cross-domain deps, injected at boot ---
let checkApiReachable = async function () { return { ok: false }; };
let applyHealthToFooter = function () {};
let failProcessing = function () {};
let resetQueueItemForReprocessing = function () { return false; };
let simulateProcessing = function () {};
let previewHelpers = function () { return {}; };
let switchToQueueItem = async function () {};
let getProcessingOptions = function () { return {}; };
let isTableMappingRunBlocked = function () { return false; };

/**
 * Wire pipeline-run dependencies (app.js assembly).
 */
export function initPipelineRun(deps = {}) {
    if (typeof deps.checkApiReachable === 'function') checkApiReachable = deps.checkApiReachable;
    if (typeof deps.applyHealthToFooter === 'function') applyHealthToFooter = deps.applyHealthToFooter;
    if (typeof deps.failProcessing === 'function') failProcessing = deps.failProcessing;
    if (typeof deps.resetQueueItemForReprocessing === 'function') resetQueueItemForReprocessing = deps.resetQueueItemForReprocessing;
    if (typeof deps.simulateProcessing === 'function') simulateProcessing = deps.simulateProcessing;
    if (typeof deps.previewHelpers === 'function') previewHelpers = deps.previewHelpers;
    if (typeof deps.switchToQueueItem === 'function') switchToQueueItem = deps.switchToQueueItem;
    if (typeof deps.getProcessingOptions === 'function') getProcessingOptions = deps.getProcessingOptions;
    if (typeof deps.isTableMappingRunBlocked === 'function') isTableMappingRunBlocked = deps.isTableMappingRunBlocked;
}

/** Pending item to run: a pending one, else a finished one reset for reprocessing (null = stop). */
function pickQueueItemToProcess() {
    // Check for pending files first
    let queueItems = document.querySelectorAll('.queue-item.pending');

    // If no pending files, reset a completed item for reprocessing (prefer selected queue item)
    if (queueItems.length === 0) {
        const completedItems = Array.from(
            document.querySelectorAll('.queue-item.completed, .queue-item.cancelled, .queue-item.failed')
        );
        if (completedItems.length === 0) {
            showNotification('No files waiting to be processed', 'warning');
            return null;
        }

        const pickReprocess = previewHelpers().pickReprocessTarget;
        const reprocessTarget = typeof pickReprocess === 'function'
            ? pickReprocess(completedItems, currentQueueItem)
            : completedItems[0];

        if (!reprocessTarget || !resetQueueItemForReprocessing(reprocessTarget)) {
            showNotification('No files available for processing. Please upload a new file.', 'warning');
            return null;
        }

        showNotification('Document reset for reprocessing', 'info');
        queueItems = document.querySelectorAll('.queue-item.pending');
    }

    const pickTarget = previewHelpers().pickProcessingTarget;
    const firstPending = typeof pickTarget === 'function'
        ? pickTarget(Array.from(queueItems), currentQueueItem)
        : queueItems[0];
    if (!firstPending) {
        showNotification('No files waiting to be processed', 'warning');
        return null;
    }
    return firstPending;
}

/** Single-processing limit: mark the item queued instead of starting (true = caller stops). */
function queuePendingItem(firstPending) {
    // If another item is already processing, queue this one instead of starting
    const activeProcessing = document.querySelector('.queue-item.processing');
    if (!activeProcessing) return false;

    // Mark as queued so we don't start concurrent processing
    firstPending.classList.remove('pending');
    firstPending.classList.add('queued');
    const qStatus = firstPending.querySelector('.queue-item-status');
    if (qStatus) qStatus.textContent = 'Queued — waiting for current task to finish';
    const qIcon = firstPending.querySelector('.queue-item-icon');
    if (qIcon) {
        qIcon.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 6v6l4 2"></path>
                    <circle cx="12" cy="12" r="9"></circle>
                </svg>
            `;
    }
    showNotification('Document queued due to single-processing limit', 'info');
    return true;
}

/** Flip the item into the processing state and return the elements the poller updates. */
async function startItemProcessingUI(firstPending) {
    firstPending.classList.remove('pending');
    firstPending.classList.add('processing');

    // Update current queue item and display the file
    if (currentQueueItem !== firstPending) {
        await switchToQueueItem(firstPending);
    }

    const icon = firstPending.querySelector('.queue-item-icon');
    icon.innerHTML = '<div class="spinner"></div>';

    const status = firstPending.querySelector('.queue-item-status');
    const info = firstPending.querySelector('.queue-item-info');
    const actionBtn = firstPending.querySelector('.queue-item-action');

    // Update action button to Cancel
    actionBtn.title = 'Cancel';
    actionBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>
    `;

    // Add progress bar
    let progressBar = info.querySelector('.progress-bar');
    if (!progressBar) {
        progressBar = document.createElement('div');
        progressBar.className = 'progress-bar';
        progressBar.innerHTML = '<div class="progress-fill" style="width: 0%"></div>';
        info.appendChild(progressBar);
    }

    showNotification('Starting document processing...', 'info');

    return { status, progressBar };
}

/** Map a start-up failure onto the user-facing notification and the item's failed state. */
function handleStartFailure(firstPending, error) {
    console.error('API Error:', error);
    const errorMessage = error.message || 'Connection error';

    // Provide helpful error message
    if (errorMessage.includes('not available') || errorMessage.includes('Failed to fetch')) {
        showNotification(`Cannot connect to API server. Please ensure backend is reachable at ${API_ROOT_URL}`, 'error');
        failProcessing(firstPending, 'API server unavailable');
    } else if (error.name === 'AbortError') {
        showNotification('Request timeout. The server may be slow or unavailable.', 'error');
        failProcessing(firstPending, 'Request timeout');
    } else {
        showNotification(`Processing failed to start: ${errorMessage}`, 'error');
        failProcessing(firstPending, errorMessage);
    }
}

/** Upload the file, prove the API is reachable, then hand the task to the poller. */
async function uploadAndStartTask(firstPending, options, progressBar, status) {
    try {
        // Update status bar (no floating card) - use throttled version to maintain state sync
        updateStatusBarThrottled('processing', {
            step: 'Initializing......'
        }, true); // Immediate update for initialization

        // Upload and process via API
        const formData = new FormData();
        formData.append('file', firstPending.file);

        // Add options as query params or form fields
        // CRITICAL FIX: Convert boolean values to "1"/"0" strings for proper FastAPI parsing
        Object.keys(options).forEach(key => {
            const value = options[key];
            // FastAPI/Form doesn't parse "true"/"false" strings correctly
            // Use "1"/"0" which gets parsed as True/False by FastAPI
            if (typeof value === 'boolean') {
                formData.append(key, value ? '1' : '0');
            } else {
                formData.append(key, value);
            }
        });

        const reachability = await checkApiReachable(8000);
        if (!reachability.ok) {
            throw new Error(
                `API server is not available. Please ensure backend is reachable at ${API_BASE_URL}`
            );
        }
        if (reachability.health) {
            applyHealthToFooter(reachability.health);
        }
        console.log('[Analyze] API probe OK via', reachability.probe);

        // Don't set timeout for upload - let it take as long as needed
        // Layout analysis and other processing can take several minutes
        const response = await fetch(`${API_BASE_URL}/analyze`, {
            method: 'POST',
            body: formData
            // Removed timeout to allow long processing times
        });

        if (response.ok) {
            const task = await response.json();
            firstPending.dataset.taskId = task.task_id;
            setTaskId(task.task_id); // Store taskId for PDF page image API

            // Removed short-lived WS handshake: rely on persistent WS and `since` param.
            // Ensure we have a lastEventId placeholder on the queue item (default 0)
            firstPending.lastEventId = firstPending.lastEventId || 0;

            // Start normal poll/WS handler
            pollTaskStatus(task.task_id, firstPending, progressBar, status);
        } else {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Server returned ${response.status}: ${errorText}`);
        }
    } catch (error) {
        handleStartFailure(firstPending, error);
    }
}

/**
 * Start processing
 */
export async function startProcessing() {
    const firstPending = pickQueueItemToProcess();
    if (!firstPending) return;

    // Clear previous results, but keep document preview visible during processing
    clearResultsDisplay(true);

    let options;
    try {
        options = getProcessingOptions();
    } catch (err) {
        showNotification(err.message || String(err), 'error');
        return;
    }

    if (isTableMappingRunBlocked(firstPending)) {
        showNotification(
            'Table mapping requires a digital PDF. Use Layout Analysis for scanned documents.',
            'error'
        );
        return;
    }

    if (
        options.enable_kie &&
        lastHealthPayload &&
        lastHealthPayload.kie &&
        !lastHealthPayload.kie.model_loaded
    ) {
        showNotification('First KIE run loads the Qwen model and may take tens of seconds. Watch the progress bar.', 'info');
    }

    if (queuePendingItem(firstPending)) return;

    const { status, progressBar } = await startItemProcessingUI(firstPending);

    // Check if we have the actual file
    if (firstPending.file) {
        await uploadAndStartTask(firstPending, options, progressBar, status);
    } else {
        // Simulation mode
        simulateProcessing(firstPending, progressBar, status);
    }
}

/**
 * Poll task status from API using WebSocket
 * This provides real-time event streaming with WebSocket connection
 */
export async function pollTaskStatus(taskId, item, progressBar, status) {
    // Get WebSocket URL (convert http to ws)
    const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    // Include `since` param (last seen event id) to avoid replaying older events
    const since = item.lastEventId || 0;
    const wsEndpoint = `${wsUrl}/tasks/${taskId}/ws?since=${since}`;

    const { connectWebSocket, closeWebSocket } = createTaskSocket(
        wsEndpoint, taskId, item, status, failProcessing
    );

    // Start WebSocket connection
    connectWebSocket();

    // Store cleanup function on item
    item.cleanupPolling = () => {
        closeWebSocket();
    };
}
