/**
 * Status bar throttling and filtering with queue mechanism (v1.8.3 B1b) - leaf service.
 *
 * Moved verbatim out of app.js (functions + their presentation-only state). No imports:
 * it touches only the DOM and the timers, so L1 holds trivially and any domain may import
 * updateStatusBar / updateStatusBarThrottled without coupling. Its state is throttling
 * bookkeeping (queue, last message) and is never read by another domain.
 */

let statusUpdateQueue = [];
let isProcessingQueue = false;
let lastStatusMessage = '';
const STATUS_UPDATE_MIN_INTERVAL = 100; // Minimum 100ms between status updates (reduced for real-time updates)

/**
 * Check if a status message should be displayed
 * Show all processing steps and completions for real-time feedback
 */
export function shouldDisplayStatus(message) {
    if (!message) return false;

    const msg = message.toLowerCase();

    // Always show key statuses
    if (msg.includes('initializing')) return true;
    if (msg.includes('trying')) return true;
    if (msg.includes('completed')) return true; // Show all completions
    if (msg.includes('processing')) return true;
    if (msg.includes('failed')) return true;
    if (msg.includes('cancelled')) return true;

    // Show everything else by default (changed from false to true)
    // This ensures all processing steps are visible in real-time
    return true;
}

/**
 * Process status update queue
 * Ensures each key status is displayed with proper timing
 */
export function processStatusQueue() {
    if (statusUpdateQueue.length === 0) {
        isProcessingQueue = false;
        return;
    }

    isProcessingQueue = true;
    const { status, data, message, isImmediate } = statusUpdateQueue.shift();

    // Update status bar immediately
    updateStatusBar(status, data);

    // Update tracking variables
    lastStatusMessage = message;

    // Schedule next item
    if (statusUpdateQueue.length > 0) {
        // Use shorter delay for faster updates
        const delay = isImmediate ? 100 : STATUS_UPDATE_MIN_INTERVAL;
        setTimeout(() => {
            processStatusQueue();
        }, delay);
    } else {
        isProcessingQueue = false;
    }
}

/**
 * Throttled status bar update with queue mechanism
 * Ensures all key statuses are displayed in order without being lost
 */
export function updateStatusBarThrottled(status, data, isImmediate = false) {
    const message = data.step || '';

    // Check if this is a key status that should be displayed
    if (!shouldDisplayStatus(message)) {
        return; // Skip non-key statuses
    }

    // If same as last displayed message, skip (unless it's immediate)
    // But allow different messages even if they contain similar content
    if (message === lastStatusMessage && !isImmediate) {
        return;
    }

    // Don't skip if message is already in queue - allow updates even if similar
    // This ensures all processing steps are visible

    // Add to queue
    statusUpdateQueue.push({ status, data, message, isImmediate });

    // Debug log
    console.log(`[Queue] Added to queue: ${message.substring(0, 50)}... (Queue length: ${statusUpdateQueue.length}, Processing: ${isProcessingQueue})`);

    // Start processing queue if not already processing
    // CRITICAL FIX: Process first item immediately, don't wait
    // This ensures the first status is shown right away
    if (!isProcessingQueue) {
        console.log(`[Queue] Starting queue processing...`);
        processStatusQueue();
    }
}

/**
 * Clear status update queue
 * Used when we need to reset the queue (e.g., on error)
 */
export function clearStatusQueue() {
    statusUpdateQueue = [];
    isProcessingQueue = false;
}

/**
 * Update status bar
 */
export function updateStatusBar(status = 'default', data = {}) {
    const statusDefault = document.getElementById('statusDefault');
    const statusProcessing = document.getElementById('statusProcessing');
    const statusCompleted = document.getElementById('statusCompleted');

    // Hide all states
    if (statusDefault) statusDefault.style.display = 'none';
    if (statusProcessing) statusProcessing.style.display = 'none';
    if (statusCompleted) statusCompleted.style.display = 'none';

    switch (status) {
        case 'processing':
            if (statusProcessing) {
                // Force show the element
                statusProcessing.style.display = 'flex';
                statusProcessing.style.visibility = 'visible';
                statusProcessing.style.opacity = '1';

                const stepEl = statusProcessing.querySelector('.processing-step');

                // Only update step text (server terminal output)
                if (stepEl && data.step) {
                    stepEl.textContent = data.step;
                    // Force immediate reflow and repaint to ensure the update is visible
                    void statusProcessing.offsetHeight;
                    // Use requestAnimationFrame to ensure browser renders the update immediately
                    requestAnimationFrame(() => {
                        if (stepEl && data.step) {
                            stepEl.textContent = data.step; // Update again in next frame to force render
                        }
                    });
                    console.log(`[StatusBar] Updated processing step: ${data.step.substring(0, 50)}...`);
                    console.log(`[StatusBar] Element display: ${statusProcessing.style.display}, visibility: ${statusProcessing.style.visibility}`);
                } else {
                    if (!stepEl) {
                        console.warn('[StatusBar] .processing-step element not found');
                    }
                    if (!data.step) {
                        console.warn('[StatusBar] No step data provided');
                    }
                }
            } else {
                console.warn('[StatusBar] statusProcessing element not found');
            }
            break;
        case 'completed':
            if (statusCompleted) {
                statusCompleted.style.display = 'flex';
                const completedText = statusCompleted.querySelector('.completed-text');
                if (completedText && data.summary) {
                    completedText.textContent = data.summary;
                }
            }
            break;
        default:
            if (statusDefault) {
                statusDefault.style.display = 'block';
            }
            break;
    }
}
