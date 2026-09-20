/**
 * Processing pipeline - task transport half (v1.9 S2-5) - same-directory sibling of
 * pipeline/run.js inside domain D8 (F3 allows sibling imports inside a domain
 * sub-directory; no cross-domain edge is added).
 *
 * Holds the WebSocket lifecycle and the HTTP fallback polling that used to be nested
 * inside run.js's pollTaskStatus. Moved verbatim: the only adaptation is that failProcessing
 * (an injected D3 dependency of run.js) is passed in as an argument instead of read from a
 * module-scope binding, because this file has no boot-time injection of its own.
 */
import { showNotification } from '../notifications.js';
import { updateStatusBar, updateStatusBarThrottled } from '../status-bar.js';
import { API_BASE_URL } from '../api-config.js';
import { fetchTaskResult } from './result.js';

/** Progress events (log / status): synchronous queue-item + status-bar update, no queues. */
function handleTaskProgressEvent(eventType, message, item, taskId, status) {
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
}

/** Terminal events: completed hands over to the result panel, failed / cancelled stop the task. */
function handleTaskTerminalEvent(eventType, message, item, status, taskId, closeWebSocket, failProcessing) {
    if (eventType === 'completed') {
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
    } else {
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
}

/** One WS message: pong, a progress event, or a terminal event (parse errors are logged only). */
function handleTaskSocketMessage(eventData, item, status, taskId, closeWebSocket, failProcessing) {
    try {
        // Handle pong response
        if (eventData === 'pong') {
            return;
        }

        const data = JSON.parse(eventData);
        const eventType = data.type;
        const message = data.message || '';
        // (duplicate suppression removed — backend now avoids re-sending current_event)

        console.log(`[WebSocket] Event received - type: ${eventType}, message: ${message.substring(0, 50)}...`);

        // Update display based on event type
        if (eventType === 'log' || (eventType === 'status' && data.status !== 'completed')) {
            handleTaskProgressEvent(eventType, message, item, taskId, status);
        } else if (eventType === 'completed' || eventType === 'failed' || eventType === 'cancelled') {
            handleTaskTerminalEvent(eventType, message, item, status, taskId, closeWebSocket, failProcessing);
        }
    } catch (error) {
        console.error('[WebSocket] Error parsing message:', error);
    }
}

/** Fallback HTTP polling (used when the WebSocket cannot connect or keeps failing). */
function startFallbackPolling(taskId, item, status, failProcessing) {
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
}

/** One task's WebSocket: connect, ping keep-alive, reconnect budget, cleanup handle. */
export function createTaskSocket(wsEndpoint, taskId, item, status, failProcessing) {
    let websocket = null;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 5;
    const reconnectDelay = 2000; // 2 seconds

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
                handleTaskSocketMessage(event.data, item, status, taskId, closeWebSocket, failProcessing);
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
                        startFallbackPolling(taskId, item, status, failProcessing);
                    }
                }
            };
        } catch (error) {
            console.error(`[WebSocket] Failed to create WebSocket for task ${taskId}:`, error);
            // Fallback to HTTP polling
            startFallbackPolling(taskId, item, status, failProcessing);
        }
    };

    return { connectWebSocket, closeWebSocket };
}
