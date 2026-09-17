/**
 * Processing pipeline - run half (v1.8.3 B4; sibling-imports per the B-decision) -
 * domain module (D8).
 *
 * D8 is split across pipeline/run.js (this file) and pipeline/result.js because the
 * domain is >500 lines. run -> result calls (clearResultsDisplay / fetchTaskResult)
 * are same-directory sibling imports (one-way, no cycle). All cross-domain deps
 * (D1 / D3 / D5 / D6 / D7) are injected at boot; the mediator updateResultsDisplay
 * stays in app.js and is injected into pipeline/result.js. The same-name
 * module-scope binding keeps every call site byte-identical.
 */
import { showNotification } from '../notifications.js';
import { updateStatusBar, updateStatusBarThrottled } from '../status-bar.js';
import { API_BASE_URL, API_ROOT_URL } from '../api-config.js';
import { lastHealthPayload } from '../api-state.js';
import { currentQueueItem, setTaskId } from '../preview-state.js';
import { clearResultsDisplay, fetchTaskResult } from './result.js';

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

/**
 * Start processing
 */
export async function startProcessing() {
    // Check for pending files first
    let queueItems = document.querySelectorAll('.queue-item.pending');

    // If no pending files, reset a completed item for reprocessing (prefer selected queue item)
    if (queueItems.length === 0) {
        const completedItems = Array.from(
            document.querySelectorAll('.queue-item.completed, .queue-item.cancelled, .queue-item.failed')
        );
        if (completedItems.length === 0) {
            showNotification('No files waiting to be processed', 'warning');
            return;
        }

        const pickReprocess = previewHelpers().pickReprocessTarget;
        const reprocessTarget = typeof pickReprocess === 'function'
            ? pickReprocess(completedItems, currentQueueItem)
            : completedItems[0];

        if (!reprocessTarget || !resetQueueItemForReprocessing(reprocessTarget)) {
            showNotification('No files available for processing. Please upload a new file.', 'warning');
            return;
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
        return;
    }

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
    // If another item is already processing, queue this one instead of starting
    const activeProcessing = document.querySelector('.queue-item.processing');
    if (activeProcessing) {
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
        return;
    }
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

    // Check if we have the actual file
    if (firstPending.file) {
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
    let websocket = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const reconnectDelay = 2000; // 2 seconds

    // Get WebSocket URL (convert http to ws)
    const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
    // Include `since` param (last seen event id) to avoid replaying older events
    const since = item.lastEventId || 0;
    const wsEndpoint = `${wsUrl}/tasks/${taskId}/ws?since=${since}`;

    const connectWebSocket = () => {
        try {
            console.log(`[WebSocket] Connecting to ${wsEndpoint}`);
            websocket = new WebSocket(wsEndpoint);

            websocket.onopen = () => {
                console.log(`[WebSocket] Connection opened for task ${taskId}`);
                reconnectAttempts = 0; // Reset reconnect attempts on successful connection

                // Send ping to keep connection alive
                const pingInterval = setInterval(() => {
                    if (websocket && websocket.readyState === WebSocket.OPEN) {
                        websocket.send('ping');
                    } else {
                        clearInterval(pingInterval);
                    }
                }, 30000); // Ping every 30 seconds

                // Store ping interval for cleanup
                item.pingInterval = pingInterval;
            };

            websocket.onmessage = (event) => {
                try {
                    // Handle pong response
                    if (event.data === 'pong') {
                        return;
                    }

                    const data = JSON.parse(event.data);
                    const eventType = data.type;
                    const message = data.message || '';
                    // (duplicate suppression removed — backend now avoids re-sending current_event)

                    console.log(`[WebSocket] Event received - type: ${eventType}, message: ${message.substring(0, 50)}...`);

                    // Update display based on event type
                    if (eventType === 'log' || (eventType === 'status' && data.status !== 'completed')) {
                        // FINAL FIX: Direct synchronous UI update - no queues, no delays, no async
                        // Update queue item status immediately and synchronously
                        if (status) {
                            const oldText = status.textContent;
                            status.textContent = message;
                            status.style.display = 'block';
                            status.style.visibility = 'visible';
                            void status.offsetHeight; // Force reflow
                            console.log(`[UI-Sync] Queue item updated: "${oldText.substring(0, 30)}..." -> "${message.substring(0, 50)}..."`);
                        } else {
                            console.error('[WebSocket] ERROR: status element is null!', { item, taskId });
                        }

                        // Update status bar immediately and synchronously - direct DOM manipulation
                        const statusProcessingEl = document.getElementById('statusProcessing');
                        if (statusProcessingEl) {
                            statusProcessingEl.style.display = 'flex';
                            statusProcessingEl.style.visibility = 'visible';
                            statusProcessingEl.style.opacity = '1';
                            const stepEl = statusProcessingEl.querySelector('.processing-step');
                            if (stepEl) {
                                const oldStepText = stepEl.textContent;
                                stepEl.textContent = message;
                                void statusProcessingEl.offsetHeight; // Force reflow
                                console.log(`[UI-Sync] Status bar updated: "${oldStepText.substring(0, 30)}..." -> "${message.substring(0, 50)}..."`);
                            } else {
                                console.error('[WebSocket] ERROR: .processing-step element not found!');
                            }
                        } else {
                            console.error('[WebSocket] ERROR: statusProcessing element not found!');
                        }

                        console.log(`[WebSocket] Event processed immediately - type: ${eventType}, message: ${message.substring(0, 50)}...`);
                    } else if (eventType === 'completed') {
                        // Task completed
                        if (item.classList.contains('completed')) {
                            closeWebSocket();
                            return;
                        }

                        if (status) {
                            status.textContent = message || 'Processing completed';
                        }

                        // Update status bar with completed message
                        updateStatusBarThrottled('processing', {
                            step: message || 'Processing completed...'
                        }, true); // Immediate update for completion

                        closeWebSocket();

                        // Fetch full result (this will call completeProcessing which will update status bar)
                        fetchTaskResult(taskId, item);
                    } else if (eventType === 'failed' || eventType === 'cancelled') {
                        // Task failed or cancelled
                        closeWebSocket();

                        if (eventType === 'failed') {
                            failProcessing(item, message || 'Processing failed');
                        } else {
                            item.classList.remove('processing');
                            item.classList.add('cancelled');
                            status.textContent = 'Cancelled';
                            showNotification('Task cancelled', 'warning');
                            updateStatusBar();
                        }
                    }
                } catch (error) {
                    console.error('[WebSocket] Error parsing message:', error);
                }
            };

            websocket.onerror = (error) => {
                console.error(`[WebSocket] Connection error for task ${taskId}:`, error);
            };

            websocket.onclose = (event) => {
                console.log(`[WebSocket] Connection closed for task ${taskId} (code: ${event.code}, reason: ${event.reason})`);

                // Clean up ping interval
                if (item.pingInterval) {
                    clearInterval(item.pingInterval);
                    item.pingInterval = null;
                }

                // Try to reconnect if not a normal closure and task is still processing
                if (event.code !== 1000 && !item.classList.contains('completed') &&
                    !item.classList.contains('failed') && !item.classList.contains('cancelled')) {
                    if (reconnectAttempts < maxReconnectAttempts) {
                        reconnectAttempts++;
                        console.log(`[WebSocket] Attempting to reconnect (${reconnectAttempts}/${maxReconnectAttempts})...`);
                        setTimeout(connectWebSocket, reconnectDelay);
                    } else {
                        console.error(`[WebSocket] Max reconnect attempts reached, falling back to polling`);
                        // Fallback to HTTP polling if WebSocket fails
                        startFallbackPolling();
                    }
                }
            };
        } catch (error) {
            console.error(`[WebSocket] Failed to create WebSocket for task ${taskId}:`, error);
            // Fallback to HTTP polling
            startFallbackPolling();
        }
    };

    const closeWebSocket = () => {
        if (websocket) {
            websocket.close(1000, 'Task completed'); // Normal closure
            websocket = null;
        }
        if (item.pingInterval) {
            clearInterval(item.pingInterval);
            item.pingInterval = null;
        }
    };

    // Fallback polling function (if WebSocket fails)
    const startFallbackPolling = () => {
        console.warn('[WebSocket] Using fallback HTTP polling');
        let pollCount = 0;
        const maxPolls = 600; // 5 minutes

        const poll = async () => {
            pollCount++;
            if (pollCount > maxPolls) {
                failProcessing(item, 'Processing timeout - please check server status');
                return;
            }

            try {
                const response = await fetch(`${API_BASE_URL}/tasks/${taskId}`);
                if (!response.ok) {
                    if (response.status === 404) {
                        failProcessing(item, 'Task not found on server');
                        return;
                    }
                    throw new Error(`Server returned ${response.status}`);
                }

                const task = await response.json();
                const step = task.message || 'Processing...';

                if (status) {
                    status.textContent = step;
                }
                updateStatusBarThrottled('processing', { step: step });

                if (task.status === 'completed') {
                    fetchTaskResult(taskId, item);
                } else if (task.status === 'failed') {
                    failProcessing(item, task.message || 'Processing failed');
                } else {
                    setTimeout(poll, 1000); // Poll every second
                }
            } catch (error) {
                console.error(`[Fallback] Error polling task ${taskId}:`, error);
                setTimeout(poll, 2000); // Retry after 2 seconds on error
            }
        };

        poll();
    };

    // Start WebSocket connection
    connectWebSocket();

    // Store cleanup function on item
    item.cleanupPolling = () => {
        closeWebSocket();
    };
}
