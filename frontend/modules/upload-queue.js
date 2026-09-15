/**
 * Upload queue (v1.8.3 B4) - domain module (D3).
 *
 * Cross-domain deps are injected at boot (D5 preview-paging, D7 kie-mapping, D8 pipeline);
 * the same-name module-scope binding trick keeps every call site byte-identical.
 */
import { showNotification } from './notifications.js';
import { updateStatusBar } from './status-bar.js';
import { API_BASE_URL } from './api-config.js';
import { currentQueueItem, currentOriginalFileUrl, resetPreviewState } from './preview-state.js';

// --- cross-domain deps, injected at boot ---
let switchToQueueItem = async function () {};
let previewHelpers = function () { return {}; };
let fetchDocumentProfileForQueueItem = async function () {};
let clearResultsDisplay = function () {};
let completeProcessing = async function () {};
let startProcessing = async function () {};

/**
 * Wire upload-queue dependencies (app.js assembly).
 */
export function initUploadQueue(deps = {}) {
    if (typeof deps.switchToQueueItem === 'function') switchToQueueItem = deps.switchToQueueItem;
    if (typeof deps.previewHelpers === 'function') previewHelpers = deps.previewHelpers;
    if (typeof deps.fetchDocumentProfileForQueueItem === 'function') fetchDocumentProfileForQueueItem = deps.fetchDocumentProfileForQueueItem;
    if (typeof deps.clearResultsDisplay === 'function') clearResultsDisplay = deps.clearResultsDisplay;
    if (typeof deps.completeProcessing === 'function') completeProcessing = deps.completeProcessing;
    if (typeof deps.startProcessing === 'function') startProcessing = deps.startProcessing;
}

export function insertInitialSkeleton() {
    const container = document.getElementById('documentPage');
    if (!container) return;
    const skeleton = document.createElement('div');
    skeleton.className = 'empty-skeleton';
    skeleton.innerHTML = `
        <div class="s-line title"></div>
        <div class="s-line subtitle"></div>
        <div class="s-block"></div>
    `;
    container.innerHTML = '';
    container.appendChild(skeleton);
}

/**
 * Initialize file upload zone
 */
export function initUploadZone() {
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    // Click to upload
    uploadZone.addEventListener('click', () => {
        fileInput.click();
    });

    // File selection
    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        handleFiles(e.dataTransfer.files);
    });
}

/**
 * Handle uploaded files
 */
export function handleFiles(files) {
    const queueList = document.getElementById('queueList');
    const queueCount = document.querySelector('.queue-count');

    let addedCount = 0;

    Array.from(files).forEach((file, index) => {
        // Validate file type
        const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/tiff'];
        const isValid = validTypes.some(type => file.type.includes(type.split('/')[1])) ||
                        file.name.toLowerCase().endsWith('.pdf') ||
                        file.name.toLowerCase().endsWith('.png') ||
                        file.name.toLowerCase().endsWith('.jpg') ||
                        file.name.toLowerCase().endsWith('.jpeg') ||
                        file.name.toLowerCase().endsWith('.tiff') ||
                        file.name.toLowerCase().endsWith('.tif');

        if (!isValid) {
            showNotification(`File "${file.name}" format not supported`, 'error');
            return;
        }

        // Create queue item
        const queueItem = createQueueItem(file.name, file);
        queueList.appendChild(queueItem);
        fetchDocumentProfileForQueueItem(queueItem);
        addedCount++;

        // Display the first file automatically, or if queue was empty before
        const existingItems = queueList.querySelectorAll('.queue-item');
        if (index === 0 || existingItems.length === 1) {
            // Automatically switch to the first file or newly added file
            switchToQueueItem(queueItem);
        }

        // Update queue count
        const count = queueList.querySelectorAll('.queue-item').length;
        queueCount.textContent = count;
    });

    if (addedCount > 0) {
        showNotification(`Added ${addedCount} file(s) to processing queue`, 'success');
    }
}

/**
 * Create queue item element
 */
export function createQueueItem(fileName, file = null, taskId = null) {
    const item = document.createElement('div');
    item.className = 'queue-item pending';
    item.dataset.fileName = fileName;
    if (file) {
        item.file = file;
    }
    if (taskId) {
        item.dataset.taskId = taskId;
    }

    item.innerHTML = `
        <div class="queue-item-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
        </div>
        <div class="queue-item-info">
            <span class="queue-item-name">${fileName}</span>
            <span class="queue-item-status">Waiting</span>
        </div>
        <button class="queue-item-action" title="Remove">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
        </button>
    `;

    // Add click event to switch documents (except when clicking the action button)
    item.addEventListener('click', (e) => {
        // Don't switch if clicking the action button
        if (e.target.closest('.queue-item-action')) {
            return;
        }

        // Switch to the clicked queue item
        switchToQueueItem(item);
    });

    // Remove/Cancel button event
    const actionBtn = item.querySelector('.queue-item-action');
    if (actionBtn) {
    actionBtn.addEventListener('click', async (e) => {
        e.stopPropagation();

        const isProcessing = item.className.includes('processing');
        const isPending = item.className.includes('pending');
        const isCompleted = item.className.includes('completed');
        const isCancelled = item.className.includes('cancelled');
        const isQueued = item.className.includes('queued');

        if (isProcessing && item.dataset.taskId) {
            // Cancel running task
            try {
                const response = await fetch(`${API_BASE_URL}/tasks/${item.dataset.taskId}/cancel`, {
                    method: 'POST'
                });
                if (response.ok) {
                    showNotification('Task cancelled', 'info');
                    // Stop polling if active
                    if (item.pollInterval) {
                        clearInterval(item.pollInterval);
                        item.pollInterval = null;
                    }
                    // Update UI immediately
                    item.classList.remove('processing');
                    item.classList.add('cancelled');
                    const statusEl = item.querySelector('.queue-item-status');
                        if (statusEl) {
                    statusEl.textContent = 'Cancelled';
                        }
                    const icon = item.querySelector('.queue-item-icon');
                        if (icon) {
                    icon.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="15" y1="9" x2="9" y2="15"></line>
                            <line x1="9" y1="9" x2="15" y2="15"></line>
                        </svg>
                    `;
                        }
                    actionBtn.title = 'Remove';
                    actionBtn.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    `;
                } else {
                    showNotification('Failed to cancel task', 'error');
                }
            } catch (error) {
                console.error('Failed to cancel task:', error);
                showNotification('Failed to cancel task', 'error');
            }
        } else if (isCompleted || isCancelled || isPending || isQueued) {
            // Use centralized deletion handler
            handleQueueItemDeletion(item);
        }
    });
    } else {
        console.warn('Action button not found in queue item');
    }

    return item;
}

/**
 * Handle queue item deletion
 */
export async function handleQueueItemDeletion(item) {
    const isCurrentItem = (item === currentQueueItem);

    // Delete task from server if it has a task ID
    if (item.dataset.taskId) {
        try {
            const response = await fetch(`${API_BASE_URL}/tasks/${item.dataset.taskId}`, {
                method: 'DELETE'
            });
            if (!response.ok) {
                console.warn('Failed to delete task from server');
            }
        } catch (error) {
            console.error('Failed to delete task:', error);
        }
    }

    // Remove from UI
    item.style.animation = 'fadeOut 0.3s ease-out forwards';
    setTimeout(() => {
        item.remove();
        updateQueueCount();

        // Ensure file input can be used again after deletion
        const fileInput = document.getElementById('fileInput');
        if (fileInput) {
            fileInput.value = ''; // Clear file input value to allow re-selecting the same file
        }

        // If deleted item was the current one, switch to another or clear display
        if (isCurrentItem) {
            // Clean up global state
            if (currentOriginalFileUrl) {
                URL.revokeObjectURL(currentOriginalFileUrl);
            }
            resetPreviewState();

            // Find next available queue item
            const queueList = document.getElementById('queueList');
            const remainingItems = queueList.querySelectorAll('.queue-item');

            if (remainingItems.length > 0) {
                // Switch to the first available queue item
                switchToQueueItem(remainingItems[0]);
            } else {
                // No other documents, clear display
                clearResultsDisplay();
                const documentPage = document.getElementById('documentPage');
                if (documentPage) {
                    documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;">No document loaded. Upload and process a file to see results.</div>';
                    delete documentPage.dataset.currentFileName;
                    delete documentPage.dataset.currentResult;
                }
            }
        }
    }, 300);
}

/**
 * Update queue count
 */
export function updateQueueCount() {
    const queueList = document.getElementById('queueList');
    const queueCount = document.querySelector('.queue-count');
    const count = queueList.querySelectorAll('.queue-item').length;
    queueCount.textContent = count;
}

/**
 * Reset a completed/cancelled/failed queue item so Run Analysis can process it again.
 * @param {HTMLElement} item
 * @returns {boolean}
 */
export function resetQueueItemForReprocessing(item) {
    if (!item?.file) {
        return false;
    }

    item.classList.remove('completed', 'cancelled', 'failed', 'queued');
    item.classList.add('pending');

    const status = item.querySelector('.queue-item-status');
    if (status) {
        status.textContent = 'Waiting';
    }

    const icon = item.querySelector('.queue-item-icon');
    if (icon) {
        icon.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
        `;
    }

    delete item.result;
    delete item.dataset.taskId;
    return true;
}

/**
 * Simulate processing (for demo/offline mode)
 */
export function simulateProcessing(item, progressBar, status) {
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
            void completeProcessing(item);
        }

        status.textContent = `Processing · ${Math.floor(progress)}%`;
        progressBar.querySelector('.progress-fill').style.width = `${progress}%`;
    }, 500);
}

/**
 * Start the next queued or pending queue item after the current job finishes.
 */
export function processNextInQueue() {
    const allItems = Array.from(document.querySelectorAll('.queue-item'));
    const findNext = previewHelpers().findNextQueueItem;
    const nextItem = typeof findNext === 'function'
        ? findNext(allItems)
        : document.querySelector('.queue-item.queued, .queue-item.pending');

    if (!nextItem) return;
    if (nextItem.classList.contains('processing')) return;

    if (nextItem.classList.contains('queued')) {
        nextItem.classList.remove('queued');
        nextItem.classList.add('pending');
        const statusEl = nextItem.querySelector('.queue-item-status');
        if (statusEl) statusEl.textContent = 'Waiting';
        showNotification('Queued document is ready; starting processing...', 'info');
    } else {
        showNotification('Starting next document in queue...', 'info');
    }

    setTimeout(() => {
        startProcessing();
    }, 200);
}

/**
 * Fail processing
 */
export function failProcessing(item, message) {
    item.classList.remove('processing');
    item.classList.add('failed');

    // Update status bar
    updateStatusBar('default');

    const icon = item.querySelector('.queue-item-icon');
    icon.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="15" y1="9" x2="9" y2="15"></line>
            <line x1="9" y1="9" x2="15" y2="15"></line>
        </svg>
    `;

    const status = item.querySelector('.queue-item-status');
    status.textContent = `Failed: ${message}`;

    const progressBar = item.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.remove();
    }

    showNotification(`Processing failed: ${message}`, 'error');

    // Update status bar
    updateStatusBar();
    // Start next queued or pending item if any
    processNextInQueue();
}
