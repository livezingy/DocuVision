/**
 * DocuVision - Intelligent Document Processing System
 * Frontend Interaction Script
 */

// API Base URL (auto-adapt for local and cloud deployments)
function normalizeApiBaseUrl(baseUrl) {
    const trimmed = (baseUrl || '').trim().replace(/\/+$/, '');
    if (!trimmed) return '/api/v1';
    return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
}

function resolveApiBaseUrl() {
    // Optional override via global config: window.DOCUVISION_CONFIG.API_BASE_URL
    if (window.DOCUVISION_CONFIG && typeof window.DOCUVISION_CONFIG.API_BASE_URL === 'string') {
        return normalizeApiBaseUrl(window.DOCUVISION_CONFIG.API_BASE_URL);
    }

    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';
    if (isLocal) {
        return 'http://localhost:8000/api/v1';
    }

    // Cloud/staging friendly: infer proxy prefix from current path when '/frontend' is present.
    const path = window.location.pathname || '/';
    const prefix = path.includes('/frontend') ? path.split('/frontend')[0] : '';
    return `${window.location.origin}${prefix}/api/v1`;
}

const API_BASE_URL = resolveApiBaseUrl();
const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1$/, '');

/** Last successful GET /health JSON (dependencies, kie, api_version). */
let lastHealthPayload = null;
let kieHealthRefreshTimer = null;

function truncateFooterEngineLine(line) {
    if (!line) return '';
    return line.length > 72 ? `${line.slice(0, 69)}...` : line;
}

/**
 * Keep #activeEngine aligned with last /health dependencies and the OCR engine dropdown.
 */
function refreshActiveEngineFooterLine() {
    const activeEl = document.getElementById('activeEngine');
    if (!activeEl) return;
    const deps = (lastHealthPayload && lastHealthPayload.dependencies) || {};
    const px = String(deps.paddlex || '').trim() || 'unknown';
    const po = String(deps.paddleocr || '').trim() || 'unknown';
    const ocrSelect = document.getElementById('dialogOcrEngineSelect');

    if (!ocrSelect) {
        activeEl.textContent = truncateFooterEngineLine(`PaddleOCR ${po} · PaddleX ${px}`);
        return;
    }

    const engineNames = {
        paddleocr: 'PaddleOCR',
        tesseract: 'Tesseract 5.x',
        easyocr: 'EasyOCR'
    };
    const val = ocrSelect.value || 'paddleocr';
    const base = engineNames[val] || val;
    const line =
        val === 'paddleocr'
            ? `PaddleOCR ${po} · PaddleX ${px}`
            : `${base} · PaddleX ${px}`;
    activeEl.textContent = truncateFooterEngineLine(line);
}

/**
 * Apply /health payload to footer (Paddle stack version, KIE readiness, API version).
 */
function applyHealthToFooter(health) {
    if (!health || typeof health !== 'object') return;
    lastHealthPayload = health;
    refreshActiveEngineFooterLine();
    const kieEl = document.getElementById('kieEngineStatus');
    if (kieEl) {
        if (health.kie && typeof health.kie === 'object') {
            kieEl.textContent = health.kie.model_loaded ? ' · KIE ready' : ' · KIE cold';
            kieEl.title = health.kie.model_id ? `KIE: ${health.kie.model_id}` : '';
        } else {
            kieEl.textContent = '';
            kieEl.title = '';
        }
    }
    const verEl = document.getElementById('apiVersionFooter');
    if (verEl && health.api_version) {
        verEl.textContent = `API v${health.api_version}`;
    }
    if (health.kie && health.kie.model_loaded === false && !kieHealthRefreshTimer) {
        kieHealthRefreshTimer = window.setTimeout(() => {
            kieHealthRefreshTimer = null;
            fetch(`${API_ROOT_URL}/health`)
                .then((r) => (r.ok ? r.json() : null))
                .then((h) => {
                    if (h) applyHealthToFooter(h);
                })
                .catch(() => {});
        }, 12000);
    }
}

// Status bar throttling and filtering with queue mechanism
let statusUpdateQueue = [];
let isProcessingQueue = false;
let lastStatusMessage = '';
let lastStatusUpdateTime = 0;
const STATUS_UPDATE_MIN_INTERVAL = 100; // Minimum 100ms between status updates (reduced for real-time updates)
let lastRenderedAnalysisResult = null;
let lastFetchedBlocks = null;

/** Clear inline sizing from adjustDocumentSize so the next task is not clipped by the previous layout. */
function resetDocumentPageLayoutStyles() {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;
    documentPage.style.width = '';
    documentPage.style.height = '';
    documentPage.style.maxWidth = '';
    documentPage.style.maxHeight = '';
    documentPage.style.overflow = '';
    const previewContent = documentPage.querySelector('.document-preview-content');
    if (previewContent) {
        previewContent.style.width = '';
        previewContent.style.height = '';
        previewContent.style.maxWidth = '';
        previewContent.style.maxHeight = '';
        previewContent.style.overflow = '';
    }
}
let enableOverlaySha256Validation = false;
let forcePureLayoutBboxOverlay = false;
const overlayLayerVisibility = {
    text: true,
    table: true,
    figure: true,
    header_footer: true,
    list: true,
};

/**
 * Check if a status message should be displayed
 * Show all processing steps and completions for real-time feedback
 */
function shouldDisplayStatus(message) {
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
function processStatusQueue() {
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
    lastStatusUpdateTime = Date.now();

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
function updateStatusBarThrottled(status, data, isImmediate = false) {
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
function clearStatusQueue() {
    statusUpdateQueue = [];
    isProcessingQueue = false;
}

document.addEventListener('DOMContentLoaded', () => {
    // Clear any existing results on page load
    clearResultsDisplay();

    // Initialize status bar
    updateStatusBar();

    // Check API connection
    initializeAPIConnection();

    initUploadZone();
    initTabs();
    initHelpButton();
    initResultTabs();
    initActionButtons();
    initAnalysisOptionsDialog();
    initEngineSelectors();
    initAnalysisView();
    initExportButtons();
    initBatchProcessing();

    // Insert a lightweight skeleton placeholder to avoid initial flash
    if (typeof insertInitialSkeleton === 'function') {
        insertInitialSkeleton();
    }
});



/**
 * Initialize API connection and check server status
 */
async function initializeAPIConnection() {
    try {
        console.log('[Init] Checking API connection to:', API_BASE_URL);

        // First check the health endpoint
        const healthResponse = await fetch(API_ROOT_URL + '/health', {
            timeout: 3000
        });

        if (!healthResponse.ok) {
            console.warn('[Init] Health check failed with status:', healthResponse.status);
            updateStatusBar('warning', {
                step: 'Server connection weak - some features may not work properly'
            });
            return;
        }

        const healthJson = await healthResponse.json();
        applyHealthToFooter(healthJson);

        // Get server info
        const infoResponse = await fetch(API_ROOT_URL, {
            timeout: 3000
        });

        if (!infoResponse.ok) {
            console.warn('[Init] Could not fetch server info');
            updateStatusBar('warning', {
                step: 'Server connection established but version info unavailable'
            });
            return;
        }

        const serverInfo = await infoResponse.json();
        console.log('[Init] Server info:', serverInfo);
        console.log('[Init] ✓ API connection successful - ' + serverInfo.name + ' v' + serverInfo.version);

        // Show brief success message
        updateStatusBar('success', {
            step: '✓ API Connected: ' + serverInfo.name + ' v' + serverInfo.version
        });

    } catch (error) {
        console.error('[Init] Failed to connect to API:', error);
        updateStatusBar('error', {
            step: `⚠ Server not responding - check backend: ${API_ROOT_URL}`
        });

        // Show alert to user
        const uploadZone = document.getElementById('uploadZone');
        if (uploadZone) {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.3);
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                color: #ff6b6b;
                padding: 16px;
                text-align: center;
                z-index: 10;
            `;
            overlay.innerHTML = '⚠ Server not responding<br/>Make sure backend is running';
            uploadZone.parentElement.style.position = 'relative';
            uploadZone.parentElement.appendChild(overlay);
        }
    }
}

function insertInitialSkeleton() {
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
function initUploadZone() {
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
function handleFiles(files) {
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
function createQueueItem(fileName, file = null, taskId = null) {
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
async function handleQueueItemDeletion(item) {
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
            currentOriginalFileUrl = null;
            currentTaskId = null;
            currentQueueItem = null;

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
function updateQueueCount() {
    const queueList = document.getElementById('queueList');
    const queueCount = document.querySelector('.queue-count');
    const count = queueList.querySelectorAll('.queue-item').length;
    queueCount.textContent = count;
}

/**
 * Initialize navigation tabs
 */
function initTabs() {
    const navTabs = document.querySelectorAll('.nav-tab');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.disabled) return;
            navTabs.forEach(t => {
                if (!t.disabled) t.classList.remove('active');
            });
            tab.classList.add('active');

            const tabName = tab.dataset.tab;
            showNotification(`Switched to ${tab.textContent.trim()} view`, 'info');
        });
    });
}

/**
 * Help opens API docs or configured architecture doc URL.
 */
function initHelpButton() {
    const btn = document.getElementById('helpBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        let url = '';
        if (window.DOCUVISION_CONFIG && typeof window.DOCUVISION_CONFIG.HELP_DOC_URL === 'string') {
            url = window.DOCUVISION_CONFIG.HELP_DOC_URL.trim();
        }
        if (!url) {
            url = `${API_ROOT_URL}/docs`;
        }
        window.open(url, '_blank', 'noopener,noreferrer');
    });
}

/**
 * Initialize result tabs (new structure: Content/Result)
 */
function initResultTabs() {
    // Main tabs (Content/Result)
    const mainTabs = document.querySelectorAll('.result-main-tab');
    const mainViews = document.querySelectorAll('.result-main-view');

    mainTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.mainTab;

            // Update main tab state
            mainTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update main view
            mainViews.forEach(view => {
                view.classList.remove('active');
                if (view.id === `${targetTab}View`) {
                    view.classList.add('active');
                }
            });
        });
    });

    // Content sub-tabs (Text/Tables/Figures)
    const contentSubTabs = document.querySelectorAll('.content-sub-tab');
    const contentViews = document.querySelectorAll('.content-view');

    contentSubTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetContent = tab.dataset.content;

            // Update sub-tab state
            contentSubTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update content view（可选子视图初始带 .hidden，需去掉否则 display:none !important 盖住 .active）
            contentViews.forEach(view => {
                view.classList.remove('active');
                if (view.id === `content${targetContent.charAt(0).toUpperCase() + targetContent.slice(1)}View`) {
                    view.classList.add('active');
                    view.classList.remove('hidden');
                }
            });
        });
    });

    // Initialize panel resize
    initPanelResize();

    // Initialize JSON view buttons
    initJsonViewButtons();

    // Wire processing mode radios: toggle sub-options panel + enhancement tabs
    const processingModeRadios = document.querySelectorAll('input[name="processingMode"]');
    const layoutSubOptions = document.getElementById('layoutSubOptions');
    const optEnableFormula = document.getElementById('optEnableFormula');
    const optEnableSeal = document.getElementById('optEnableSeal');

    const syncModeUI = () => {
        const isLayout = document.querySelector('input[name="processingMode"]:checked')?.value === 'layout';
        // Always show sub-options; dim them when a KIE mode is active to show layout runs automatically.
        if (layoutSubOptions) {
            layoutSubOptions.classList.remove('hidden');
            layoutSubOptions.classList.toggle('sub-options-dimmed', !isLayout);
        }
        const kieNote = document.getElementById('kieNote');
        if (kieNote) kieNote.classList.toggle('hidden', isLayout);
        if (!isLayout) updateEnhancementTabs(false, false);
        else {
            updateEnhancementTabs(
                optEnableFormula ? optEnableFormula.checked : false,
                optEnableSeal ? optEnableSeal.checked : false
            );
        }
    };

    processingModeRadios.forEach(radio => radio.addEventListener('change', syncModeUI));

    if (optEnableFormula) {
        optEnableFormula.addEventListener('change', () => {
            updateEnhancementTabs(optEnableFormula.checked, optEnableSeal ? optEnableSeal.checked : false);
        });
    }
    if (optEnableSeal) {
        optEnableSeal.addEventListener('change', () => {
            updateEnhancementTabs(optEnableFormula ? optEnableFormula.checked : false, optEnableSeal.checked);
        });
    }
}

/**
 * Initialize action buttons
 */
function initActionButtons() {
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const analysisOptionsBtn = document.getElementById('analysisOptionsBtn');

    if (runAnalysisBtn) {
        runAnalysisBtn.addEventListener('click', () => {
            startProcessing();
        });
    }

    if (analysisOptionsBtn) {
        analysisOptionsBtn.addEventListener('click', () => {
            openAnalysisOptionsDialog();
        });
    }

}

// Store original file URL for display
let currentOriginalFileUrl = null;
let currentTaskId = null;
let currentQueueItem = null; // Track currently selected queue item

/**
 * Upload file to backend for preview (PDF only)
 * Returns taskId for immediate preview without processing
 */
async function uploadFileForPreview(file, queueItem) {
    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Upload failed: ${response.status} ${errorText}`);
        }

        const result = await response.json();
        const taskId = result.task_id;

        // Store taskId
        currentTaskId = taskId;
        if (queueItem) {
            queueItem.dataset.taskId = taskId;
        }

        return taskId;
    } catch (error) {
        console.error('Error uploading file for preview:', error);
        throw error;
    }
}

/**
 * Switch to a different queue item and display its document
 */
async function switchToQueueItem(queueItem) {
    if (!queueItem) return;

    // Remove active class from all queue items
    document.querySelectorAll('.queue-item').forEach(item => {
        item.classList.remove('active');
    });

    // Mark current item as active
    queueItem.classList.add('active');
    currentQueueItem = queueItem;

    // Get file information
    const file = queueItem.file;
    const fileName = queueItem.dataset.fileName;
    const taskId = queueItem.dataset.taskId;

    if (!file) {
        showNotification('File data not available', 'warning');
        return;
    }

    // Update global state
    if (currentOriginalFileUrl) {
        URL.revokeObjectURL(currentOriginalFileUrl);
    }
    currentOriginalFileUrl = URL.createObjectURL(file);
    currentTaskId = taskId || null;

    // Update document page
    const documentPage = document.getElementById('documentPage');
    if (documentPage) {
        documentPage.dataset.currentFileName = fileName;
        // Clear result if switching to a different file
        delete documentPage.dataset.currentResult;
        resetDocumentPageLayoutStyles();
    }

    // Display file
    const fileExt = fileName.toLowerCase().split('.').pop();
    if (fileExt === 'pdf' && !taskId) {
        // PDF file needs to be uploaded first to get taskId
        if (documentPage) {
            documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;"><div class="spinner" style="margin: 0 auto 16px; width: 32px; height: 32px; border: 3px solid rgba(99, 102, 241, 0.2); border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite;"></div><p style="margin-top: 16px; font-size: 0.875rem;">Uploading PDF for preview...</p></div>';
        }

        uploadFileForPreview(file, queueItem).then(async (newTaskId) => {
            currentTaskId = newTaskId;
            await updatePreviewView('original');
        }).catch((error) => {
            console.error('Failed to upload file for preview:', error);
            if (documentPage) {
                documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;"><p style="margin-bottom: 8px; color: #f43f5e;">⚠️ Preview unavailable</p><p style="font-size: 0.875rem; color: #94a3b8;">PDF uploaded but preview failed.</p></div>';
            }
        });
    } else if (queueItem.result) {
        // Completed item: render once (avoids racing updatePreviewView vs renderDocumentWithAnnotations on PDF page-image).
        await updateResultsDisplay(queueItem.result);
    } else {
        await updatePreviewView('original');
    }
}

/**
 * Get PDF page image from backend
 */
async function getPdfPageImage(taskId, pageNum = 1) {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/page-image/${pageNum}`);
        if (!response.ok) {
            throw new Error(`Failed to get page image: ${response.statusText}`);
        }
        const blob = await response.blob();
        return URL.createObjectURL(blob);
    } catch (error) {
        console.error('Error getting PDF page image:', error);
        throw error;
    }
}

/**
 * Update preview view
 */
async function updatePreviewView(viewType) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    switch (viewType) {
        case 'original':
            // Display original document (PDF or image) - can show even without result
            if (currentOriginalFileUrl) {
                // Try to get file name from result or queue item
                let fileName = 'Document';
                const resultJson = documentPage.dataset.currentResult;
                if (resultJson) {
                    try {
                        const result = JSON.parse(resultJson);
                        const docInfo = result.document_info || {};
                        fileName = docInfo.file_name || 'Document';
                    } catch (e) {
                        // Use default
                    }
                } else {
                    // Try to get from documentPage dataset or queue item
                    if (documentPage.dataset.currentFileName) {
                        fileName = documentPage.dataset.currentFileName;
                    } else {
                        const queueItem = document.querySelector('.queue-item.pending, .queue-item.processing, .queue-item.completed');
                        if (queueItem) {
                            fileName = queueItem.dataset.fileName || queueItem.querySelector('.queue-item-name')?.textContent || 'Document';
                        }
                    }
                }

                const fileExt = fileName.toLowerCase().split('.').pop();

                // For PDF files, we need taskId to get the image
                if (fileExt === 'pdf') {
                    if (!currentTaskId) {
                        // Show loading state while uploading
                        documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;"><div class="spinner" style="margin: 0 auto 16px; width: 32px; height: 32px; border: 3px solid rgba(99, 102, 241, 0.2); border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite;"></div><p style="margin-top: 16px; font-size: 0.875rem;">Preparing PDF preview...</p></div>';
                        return;
                    }

                    // Get PDF page image from backend
                    try {
                        // Show loading state while fetching image
                        documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;"><div class="spinner" style="margin: 0 auto 16px; width: 32px; height: 32px; border: 3px solid rgba(99, 102, 241, 0.2); border-top-color: #6366f1; border-radius: 50%; animation: spin 0.8s linear infinite;"></div><p style="margin-top: 16px; font-size: 0.875rem;">Loading PDF page...</p></div>';

                        let html = '<div class="document-preview-content">';
                        const imageUrl = await getPdfPageImage(currentTaskId, 1);
                        html += `<img id="documentImage" src="${imageUrl}" style="width: auto; height: auto; object-fit: contain; border: none; border-radius: 8px; display: block;" alt="Document" onload="adjustDocumentSize()" onerror="this.parentElement.innerHTML=\'<div class=\\\'empty-state\\\' style=\\\'padding: 40px; text-align: center; color: #f43f5e;\\\'>Failed to load PDF image. Please try again.</div>\'">`;
                        html += '</div>';
                        documentPage.innerHTML = html;

                        // Adjust document size after rendering
                        setTimeout(() => {
                            adjustDocumentSize();
                        }, 100);
                    } catch (error) {
                        console.error('Failed to get PDF page image:', error);
                        documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;"><p style="margin-bottom: 8px; color: #f43f5e;">⚠️ Failed to load PDF preview</p><p style="font-size: 0.875rem; color: #94a3b8;">Please try running analysis or refresh the page.</p></div>';
                    }
                } else {
                    // For image files, display directly
                    let html = '<div class="document-preview-content">';
                    html += `<img id="documentImage" src="${currentOriginalFileUrl}" style="width: auto; height: auto; object-fit: contain; border: none; border-radius: 8px; display: block;" alt="Document" onload="adjustDocumentSize()">`;
                    html += '</div>';
                    documentPage.innerHTML = html;

                    // Adjust document size after rendering
                    setTimeout(() => {
                        adjustDocumentSize();
                    }, 100);
                }
            } else {
                documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;">Original document not available. Please upload a document first.</div>';
            }
            break;
        case 'analyzed':
            // Display extracted text and analysis results
            const resultJson = documentPage.dataset.currentResult;
            if (resultJson) {
                try {
                    const result = JSON.parse(resultJson);
                    await updateDocumentPreview(result);
                    // Add visual highlights for analyzed regions if available
                    setTimeout(() => {
                        const regions = documentPage.querySelectorAll('.analyzed-region');
                        regions.forEach(r => {
                            const type = r.dataset.type;
                            const colors = {
                                header: '#8b5cf6',
                                title: '#3b82f6',
                                paragraph: '#10b981',
                                table: '#f59e0b',
                                list: '#06b6d4',
                                figure: '#ec4899',
                                footer: '#6b7280'
                            };
                            r.style.outline = `2px solid ${colors[type] || '#6366f1'}`;
                            r.style.outlineOffset = '4px';
                        });
                    }, 100);
                } catch (e) {
                    documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;">Analysis results not available yet. Processing in progress...</div>';
                }
            } else {
                documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;">Analysis results not available yet. Processing in progress...</div>';
            }
            break;
        case 'compare':
            showNotification('Compare view coming soon...', 'info');
            break;
    }
}

/**
 * Initialize engine selectors
 */
function initEngineSelectors() {
    const ocrSelect = document.getElementById('dialogOcrEngineSelect');
    const layoutSelect = document.getElementById('dialogLayoutEngineSelect');

    if (ocrSelect) {
        ocrSelect.addEventListener('change', () => {
            refreshActiveEngineFooterLine();
            const engineNames = {
                paddleocr: 'PaddleOCR',
                tesseract: 'Tesseract 5.x',
                easyocr: 'EasyOCR'
            };
            const base = engineNames[ocrSelect.value] || ocrSelect.value;
            showNotification(`OCR engine changed to ${base}`, 'info');
        });
    }

    if (layoutSelect) {
        layoutSelect.addEventListener('change', () => {
            const engineNames = {
                'ppstructure': 'PP-StructureV2',
                'layoutparser': 'LayoutParser'
            };
            showNotification(`Layout engine changed to ${engineNames[layoutSelect.value]}`, 'info');
        });
    }
}


/**
 * Initialize analysis view
 */
function initAnalysisView() {
    // Start processing button
    const startBtn = document.getElementById('startProcessBtn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            startProcessing();
        });
    }
}

/**
 * Initialize export buttons
 */
function initExportButtons() {
    const exportBtns = document.querySelectorAll('.export-btn');
    exportBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const format = btn.dataset.format || btn.textContent.trim();
            exportResults(format);
        });
    });
}

/**
 * Initialize Analysis Options Dialog
 */
function initAnalysisOptionsDialog() {
    const modal = document.getElementById('analysisOptionsModal');
    const openBtn = document.getElementById('analysisOptionsBtn');
    const closeBtn = document.getElementById('closeAnalysisOptionsBtn');
    const cancelBtn = document.getElementById('cancelOptionsBtn');
    const saveBtn = document.getElementById('saveOptionsBtn');
    const resetBtn = document.getElementById('resetOptionsBtn');
    const modalTabs = document.querySelectorAll('.modal-tab');

    // Tab switching
    modalTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            modalTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.modal-tab-content').forEach(content => {
                content.classList.remove('active');
            });
            const targetContent = document.getElementById(tabName + 'Tab');
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // Close handlers
    const closeModal = () => {
        if (modal) modal.classList.remove('active');
    };

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    // Click outside to close
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    // Save handler
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            saveAnalysisOptions();
            closeModal();
        });
    }

    // Reset handler
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            resetAnalysisOptions();
        });
    }
}

/**
 * Open Analysis Options Dialog
 */
function openAnalysisOptionsDialog() {
    const modal = document.getElementById('analysisOptionsModal');
    if (modal) {
        modal.classList.add('active');
    }
}

/**
 * Save Analysis Options
 */
function saveAnalysisOptions() {
    // Options are read dynamically from dialog when needed
    showNotification('Analysis options saved', 'success');
}

/**
 * Reset Analysis Options to defaults
 */
function resetAnalysisOptions() {
    document.getElementById('optLayout').checked = true;
    const optEnableTable = document.getElementById('optEnableTable');
    if (optEnableTable) optEnableTable.checked = true;
    document.getElementById('optEnableFormula').checked = false;
    const optEnableChart = document.getElementById('optEnableChart');
    if (optEnableChart) optEnableChart.checked = false;
    document.getElementById('optEnableSeal').checked = false;
    document.getElementById('dialogOcrEngineSelect').value = 'paddleocr';
    document.getElementById('dialogLayoutEngineSelect').value = 'ppstructure';
    const layoutSubOptions = document.getElementById('layoutSubOptions');
    if (layoutSubOptions) {
        layoutSubOptions.classList.remove('hidden');
        layoutSubOptions.classList.remove('sub-options-dimmed');
    }
    const kieNote = document.getElementById('kieNote');
    if (kieNote) kieNote.classList.add('hidden');
    updateEnhancementTabs(false, false);
    showNotification('Options reset to defaults', 'info');
}

/**
 * Get current processing options from dialog
 */
function getProcessingOptions() {
    const selectedMode = document.querySelector('input[name="processingMode"]:checked')?.value || 'layout';
    const isLayout = selectedMode === 'layout';

    const options = {
        document_type: isLayout ? 'auto' : selectedMode,
        enable_layout: true,
        // Layout mode text extraction comes from PP-StructureV3 block content, not OCRService.
        enable_ocr: false,
        enable_table: isLayout ? (document.getElementById('optEnableTable')?.checked ?? true) : true,
        enable_formula: isLayout ? (document.getElementById('optEnableFormula')?.checked || false) : false,
        enable_chart: isLayout ? (document.getElementById('optEnableChart')?.checked || false) : false,
        enable_seal: isLayout ? (document.getElementById('optEnableSeal')?.checked || false) : false,
        // Auto-enable KIE when user selects invoice/receipt/id_card processing mode
        enable_kie: (function() {
            const dt = isLayout ? 'auto' : selectedMode;
            const kieTypes = new Set(['invoice', 'receipt', 'id_card', 'passport', 'bank_card']);
            return kieTypes.has(String(dt).toLowerCase());
        })(),
        ocr_engine: document.getElementById('dialogOcrEngineSelect')?.value || 'paddleocr',
        layout_engine: document.getElementById('dialogLayoutEngineSelect')?.value || 'ppstructure'
    };

    return options;
}

/**
 * Start processing
 */
async function startProcessing() {
    // Check for pending files first
    let queueItems = document.querySelectorAll('.queue-item.pending');

    // If no pending files, check for completed or cancelled files that can be reprocessed
    if (queueItems.length === 0) {
        const completedItems = document.querySelectorAll('.queue-item.completed, .queue-item.cancelled, .queue-item.failed');
        if (completedItems.length > 0) {
            // Ask user if they want to reprocess
            const firstItem = completedItems[0];
            if (firstItem.file) {
                // Reset the item to pending state
                firstItem.classList.remove('completed', 'cancelled', 'failed');
                firstItem.classList.add('pending');

                // Reset status
                const status = firstItem.querySelector('.queue-item-status');
                if (status) {
                    status.textContent = 'Waiting';
                }

                // Reset icon
                const icon = firstItem.querySelector('.queue-item-icon');
                if (icon) {
                    icon.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                    `;
                }

                // Clear previous result
                delete firstItem.result;
                delete firstItem.dataset.taskId;

                showNotification('Document reset for reprocessing', 'info');
                queueItems = document.querySelectorAll('.queue-item.pending');
            } else {
                showNotification('No files available for processing. Please upload a new file.', 'warning');
                return;
            }
        } else {
            showNotification('No files waiting to be processed', 'warning');
            return;
        }
    }

    // Clear previous results, but keep document preview visible during processing
    clearResultsDisplay(true);

    const options = getProcessingOptions();
    if (
        options.enable_kie &&
        lastHealthPayload &&
        lastHealthPayload.kie &&
        !lastHealthPayload.kie.model_loaded
    ) {
        showNotification('首次 KIE 将加载 Qwen 模型，可能需数十秒，请耐心等待进度。', 'info');
    }

    // Process first pending file
    const firstPending = queueItems[0];
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

            // Check API availability first (with timeout for health check only)
            let apiAvailable = false;
            try {
                const healthCheck = await fetch(`${API_ROOT_URL}/health`, {
                    method: 'GET',
                    signal: AbortSignal.timeout(5000) // 5 second timeout for health check only
                });
                if (healthCheck && healthCheck.ok) {
                    apiAvailable = true;
                }
            } catch (e) {
                console.warn('Health check failed:', e);
            }

            if (!apiAvailable) {
                throw new Error(`API server is not available. Please ensure backend is reachable at ${API_ROOT_URL}`);
            }

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
                currentTaskId = task.task_id; // Store taskId for PDF page image API

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
async function pollTaskStatus(taskId, item, progressBar, status) {
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
                    const progress = data.progress !== undefined ? Math.floor(data.progress) : undefined;
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


/**
 * Fetch task result and complete processing
 */
async function fetchTaskResult(taskId, item) {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/result`);
        if (!response.ok) {
            throw new Error(`Failed to fetch result: ${response.status}`);
        }

        const result = await response.json();
        console.log('Task completed successfully:', taskId);
        showNotification('Document processing completed successfully!', 'success');
        await completeProcessing(item, result);
    } catch (error) {
        console.error('Error fetching task result:', error);
        showNotification('Document processing completed, but result fetch failed', 'warning');
        failProcessing(item, `Failed to fetch result: ${error.message}`);
    }
}

/**
 * Fetch flat blocks from the /blocks endpoint for SVG overlay rendering.
 */
async function fetchTaskBlocks(taskId) {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/blocks`);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        console.warn('[Blocks] Failed to fetch blocks:', e);
        return null;
    }
}

/**
 * Return SVG stroke/fill colors for a given block type.
 */
function getSvgAnnotationColors(type) {
    const colorMap = {
        title:       { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.10)' },
        subtitle:    { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.10)' },
        heading:     { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.10)' },
        paragraph:   { stroke: '#10b981', fill: 'rgba(16,185,129,0.08)' },
        text:        { stroke: '#10b981', fill: 'rgba(16,185,129,0.08)' },
        text_block:  { stroke: '#10b981', fill: 'rgba(16,185,129,0.08)' },
        table:       { stroke: '#f59e0b', fill: 'rgba(245,158,11,0.10)' },
        figure:      { stroke: '#ec4899', fill: 'rgba(236,72,153,0.10)' },
        image:       { stroke: '#ec4899', fill: 'rgba(236,72,153,0.10)' },
        header:      { stroke: '#8b5cf6', fill: 'rgba(139,92,246,0.08)' },
        page_header: { stroke: '#8b5cf6', fill: 'rgba(139,92,246,0.08)' },
        footer:      { stroke: '#6b7280', fill: 'rgba(107,114,128,0.08)' },
        page_footer: { stroke: '#6b7280', fill: 'rgba(107,114,128,0.08)' },
        list:        { stroke: '#06b6d4', fill: 'rgba(6,182,212,0.08)'  },
        list_item:   { stroke: '#06b6d4', fill: 'rgba(6,182,212,0.08)'  },
    };
    return colorMap[type] || { stroke: '#6b7280', fill: 'rgba(107,114,128,0.08)' };
}

/**
 * Simulate processing (for demo/offline mode)
 */
function simulateProcessing(item, progressBar, status) {
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
 * Complete processing
 */
async function completeProcessing(item, result = null) {
    // 防止重复调用
    if (item.classList.contains('completed')) {
        console.log('Already completed, skipping duplicate call');
        return;
    }

    item.classList.remove('processing');
    item.classList.add('completed');

    const icon = item.querySelector('.queue-item-icon');
    icon.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
            <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
    `;

    const status = item.querySelector('.queue-item-status');
    const pageCount = result?.document_info?.pages || 0;
    status.textContent = `Completed · ${pageCount} page${pageCount !== 1 ? 's' : ''}`;

    // Store result on item
    if (result) {
        item.result = result;
        // Update UI with results
        await updateResultsDisplay(result);

        // Generate completion summary
        const layout = result.layout || {};
        const elements = layout.elements || [];
        const titleCount = elements.filter(e => e.type === 'title' || e.type === 'heading').length;
        const tableCount = elements.filter(e => e.type === 'table').length;
        const imageCount = elements.filter(e => e.type === 'figure' || e.type === 'image').length;

        const summaryParts = [];
        if (titleCount > 0) summaryParts.push(`${titleCount} title${titleCount !== 1 ? 's' : ''}`);
        if (tableCount > 0) summaryParts.push(`${tableCount} table${tableCount !== 1 ? 's' : ''}`);
        if (imageCount > 0) summaryParts.push(`${imageCount} image${imageCount !== 1 ? 's' : ''}`);

        const summary = summaryParts.length > 0
            ? `Completed: ${summaryParts.join(', ')} detected`
            : 'Processing completed';

        // Update status bar with summary (but keep showing processing steps until then)
        // Don't immediately switch to completed - let the last processing step show for a moment
        setTimeout(() => {
            updateStatusBar('completed', { summary: summary });

            // Auto-hide summary after 5 seconds
            setTimeout(() => {
                updateStatusBar('default');
            }, 5000);
        }, 1000); // Wait 1 second before showing completed status
    }

    const progressBar = item.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.remove();
    }

    const action = item.querySelector('.queue-item-action');
    if (action) {
        action.title = 'Delete';
        action.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
        `;

        // Remove existing event listeners by cloning the button
        const newAction = action.cloneNode(true);
        action.parentNode.replaceChild(newAction, action);

        // Add delete event handler
        newAction.addEventListener('click', async (e) => {
            e.stopPropagation();
            // Use centralized deletion handler
            handleQueueItemDeletion(item);
        });
    } else {
        console.warn('Action button not found in completed queue item');
    }

    showNotification('Document processing completed!', 'success');

    // Don't reset status bar here - let it show the completed status from updateStatusBar('completed')
    // The status bar will be reset to default after 5 seconds (already handled above)

    // After finishing, promote any queued item to pending and start it
    promoteNextQueued();
}

/**
 * Clear results display
 * @param {boolean} keepDocumentPreview - If true, keep document preview visible, only clear result data
 */
function clearResultsDisplay(keepDocumentPreview = false) {
    // Clear document preview only if not keeping it
    if (!keepDocumentPreview) {
        const documentPage = document.getElementById('documentPage');
        if (documentPage) {
            documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;">No document loaded. Upload and process a file to see results.</div>';
        }
    }

    // Reset Content > Fields sub-tab (hide button + view, clear renderings)
    const fieldsBtn = document.getElementById('tabBtnFields');
    const fieldsView = document.getElementById('contentFieldsView');
    const fieldsList = document.getElementById('contentFieldsList');
    const fieldsMeta = document.getElementById('contentFieldsMeta');
    if (fieldsBtn) fieldsBtn.classList.add('hidden');
    if (fieldsView) fieldsView.classList.add('hidden');
    if (fieldsList) fieldsList.innerHTML = '';
    if (fieldsMeta) fieldsMeta.textContent = '';
}

/**
 * Promote the next queued item (if any) to pending and start processing it.
 */
function promoteNextQueued() {
    const nextQueued = document.querySelector('.queue-item.queued');
    if (!nextQueued) return;

    // Convert queued -> pending
    nextQueued.classList.remove('queued');
    nextQueued.classList.add('pending');
    const statusEl = nextQueued.querySelector('.queue-item-status');
    if (statusEl) statusEl.textContent = 'Waiting';

    showNotification('Queued document is ready; starting processing...', 'info');

    // Slight delay to allow UI updates, then trigger processing
    setTimeout(() => {
        startProcessing();
    }, 200);
}

/**
 * Update results display with actual data
 */
async function updateResultsDisplay(result) {
    if (!result) return;

    lastRenderedAnalysisResult = result;

    // Reset cached blocks so the SVG overlay fetches fresh data.
    lastFetchedBlocks = null;
    clearCanvasLayoutOverlay();

    // Update document preview
    await updateDocumentPreview(result);

    // Update Content views
    updateContentText(result);
    updateContentTables(result);
    updateContentFigures(result);
    updateContentFormulas((result.view || {}).formulas || []);
    updateContentSeals((result.view || {}).seals || []);
    updateContentFields(result);

    // Update Result JSON view
    updateResultJson(result);

    // Quality, transactions, mapping preview (trial demo)
    renderQualityPanelPro(result);
    await updateDemoTransactionViews(result);
}

/**
 * Render quality / warnings for Pro results
 */
function renderQualityPanelPro(result) {
    const panel = document.getElementById('qualityPanel');
    if (!panel) return;
    if (!result) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
        return;
    }
    const quality = result.quality || {};
    const warnings = [];
    if (quality.kie_error_message) {
        warnings.push({ code: 'kie_error', message: quality.kie_error_message });
    }
    if (quality.kie_production_hit === false && quality.kie_production_reason) {
        warnings.push({ code: 'kie_production', message: quality.kie_production_reason });
    }
    const score = quality.kie_confidence_avg != null
        ? `${Math.round(quality.kie_confidence_avg * 100)}%`
        : (quality.overall_confidence != null ? `${Math.round(quality.overall_confidence * 100)}%` : '—');
    const warnHtml = warnings.map(w =>
        `<div class="quality-warn">⚠ ${escapeHtml(w.code)}: ${escapeHtml(w.message)}</div>`
    ).join('');
    panel.innerHTML = `
        <div class="quality-score">Confidence: ${score} · KIE fields: ${quality.kie_fields_count ?? '—'} · Tables: ${(result.view?.tables || []).length}</div>
        ${warnHtml}`;
    panel.classList.remove('hidden');
}

function renderDemoTransactionTable(containerId, rows, emptyMsg) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    if (!rows || !rows.length) {
        container.innerHTML = `<p class="empty-state">${emptyMsg}</p>`;
        return;
    }
    const headers = ['date', 'description', 'amount', 'internal_code', 'internal_label'];
    const table = document.createElement('table');
    table.className = 'extracted-table';
    const thead = document.createElement('thead');
    const hr = document.createElement('tr');
    headers.forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    rows.forEach(tx => {
        const tr = document.createElement('tr');
        headers.forEach(h => {
            const td = document.createElement('td');
            td.textContent = tx[h] ?? '—';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);

    const txTab = document.getElementById('tabBtnTransactions');
    const mappedTab = document.getElementById('tabBtnMapped');
    if (txTab) txTab.classList.remove('hidden');
    if (mappedTab) mappedTab.classList.remove('hidden');
}

async function updateDemoTransactionViews(result) {
    if (!window.DocuVisionDemo || !result) {
        renderDemoTransactionTable('contentTransactionsList', [], 'No transactions.');
        renderDemoTransactionTable('contentMappedList', [], 'No mapped transactions.');
        return;
    }
    const enriched = await DocuVisionDemo.enrichResult(result);
    renderDemoTransactionTable('contentTransactionsList', enriched.transactions, 'No transaction rows detected.');
    renderDemoTransactionTable('contentMappedList', enriched.mapped_transactions, 'No mapped transactions.');
}

/**
 * Remove legacy canvas-based layout overlay to keep hover behavior consistent.
 */
function clearCanvasLayoutOverlay() {
    const canvas = document.getElementById('layoutAnnotationCanvas');
    if (canvas && canvas.parentElement) {
        canvas.parentElement.removeChild(canvas);
    }

    const controlPanel = document.getElementById('layoutControlPanel');
    if (controlPanel && controlPanel.parentElement) {
        controlPanel.parentElement.removeChild(controlPanel);
    }
}

function formatAzureRoleLabel(type) {
    const normalized = String(type || 'paragraph').toLowerCase();
    const roleMap = {
        doc_title: 'Title',
        paragraph_title: 'SectionHeading',
        abstract_title: 'SectionHeading',
        reference_title: 'SectionHeading',
        content_title: 'SectionHeading',
        figure_table_chart_title: 'FigureCaption',
        page_header: 'PageHeader',
        page_footer: 'PageFooter',
        section_header: 'SectionHeading',
        table_header: 'TableHeader',
        figure_caption: 'FigureCaption',
        list_item: 'ListItem',
        text_block: 'Paragraph',
        text: 'Paragraph',
        paragraph: 'Paragraph',
        title: 'Title',
        subtitle: 'Subtitle',
        table: 'Table',
        figure: 'Figure',
        image: 'Figure',
        header: 'PageHeader',
        footer: 'PageFooter',
        reference: 'Reference',
        equation: 'Formula',
        list: 'ListItem'
    };

    if (roleMap[normalized]) {
        return roleMap[normalized];
    }

    return normalized
        .split('_')
        .map(p => p ? p.charAt(0).toUpperCase() + p.slice(1) : '')
        .join('');
}

/**
 * Update document preview
 */
async function updateDocumentPreview(result) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    const docInfo = result.document_info || {};
    const fileName = docInfo.file_name || 'Document';
    const pages = docInfo.pages || result.layout?.total_pages || result.page_count || 1;

    // Update pagination controls with actual page count
    const pageInput = document.querySelector('.page-input');
    const pageTotal = document.querySelector('.page-total');
    if (pageInput) {
        pageInput.max = pages;
        pageInput.value = 1;
    }
    if (pageTotal) {
        pageTotal.textContent = ` / ${pages}`;
    }

    // Store current result for preview switching
    documentPage.dataset.currentResult = JSON.stringify(result);


    // Always prioritize showing source image when available.
    // Annotation data may come from layout, OCR, or table-only paths.
    if (currentOriginalFileUrl) {
        await renderDocumentWithAnnotations(result);
    } else {
        // Fallback to text preview only when source image is unavailable.
        renderTextPreview(result);
    }
}

function normalizeAnnotationBbox(bbox) {
    if (!bbox) return { x: 0, y: 0, width: 0, height: 0 };

    if (Array.isArray(bbox) && bbox.length >= 4) {
        return {
            x: Number(bbox[0]) || 0,
            y: Number(bbox[1]) || 0,
            width: Math.max((Number(bbox[2]) || 0) - (Number(bbox[0]) || 0), 0),
            height: Math.max((Number(bbox[3]) || 0) - (Number(bbox[1]) || 0), 0)
        };
    }

    if (typeof bbox === 'object') {
        if ('x' in bbox || 'y' in bbox || 'width' in bbox || 'height' in bbox) {
            return {
                x: Number(bbox.x) || 0,
                y: Number(bbox.y) || 0,
                width: Number(bbox.width) || 0,
                height: Number(bbox.height) || 0
            };
        }
        if ('x1' in bbox || 'y1' in bbox || 'x2' in bbox || 'y2' in bbox) {
            const x1 = Number(bbox.x1) || 0;
            const y1 = Number(bbox.y1) || 0;
            const x2 = Number(bbox.x2) || 0;
            const y2 = Number(bbox.y2) || 0;
            return { x: x1, y: y1, width: Math.max(x2 - x1, 0), height: Math.max(y2 - y1, 0) };
        }
    }

    return { x: 0, y: 0, width: 0, height: 0 };
}

function bboxFromPolygon(polygon) {
    if (!Array.isArray(polygon) || polygon.length === 0) return null;

    let points = [];
    if (Array.isArray(polygon[0])) {
        points = polygon.filter(p => Array.isArray(p) && p.length >= 2).map(p => [Number(p[0]) || 0, Number(p[1]) || 0]);
    } else {
        for (let i = 0; i < polygon.length - 1; i += 2) {
            points.push([Number(polygon[i]) || 0, Number(polygon[i + 1]) || 0]);
        }
    }

    if (points.length === 0) return null;
    const xs = points.map(p => p[0]);
    const ys = points.map(p => p[1]);
    const x1 = Math.min(...xs);
    const y1 = Math.min(...ys);
    const x2 = Math.max(...xs);
    const y2 = Math.max(...ys);
    return { x: x1, y: y1, width: Math.max(0, x2 - x1), height: Math.max(0, y2 - y1) };
}

function normalizeCoordSpace(value) {
    const v = String(value || '').trim().toLowerCase();
    if (v === 'image_abs_px') return 'image_abs_px';
    if (v === 'image_norm') return 'image_norm';
    return '';
}

function normalizeBboxToImageMatrix(matrix, coordSpace, imageWidth, imageHeight) {
    const srcSpace = normalizeCoordSpace(coordSpace);

    if (matrix && typeof matrix === 'object') {
        const sx = Number(matrix.scale_x);
        const sy = Number(matrix.scale_y);
        const ox = Number(matrix.offset_x);
        const oy = Number(matrix.offset_y);
        if ([sx, sy, ox, oy].every(Number.isFinite)) {
            return {
                src_space: String(matrix.src_space || srcSpace || 'image_abs_px').toLowerCase(),
                dst_space: String(matrix.dst_space || 'image_abs_px').toLowerCase(),
                scale_x: sx,
                scale_y: sy,
                offset_x: ox,
                offset_y: oy,
            };
        }
    }

    if (srcSpace === 'image_norm' && imageWidth > 0 && imageHeight > 0) {
        return {
            src_space: 'image_norm',
            dst_space: 'image_abs_px',
            scale_x: imageWidth,
            scale_y: imageHeight,
            offset_x: 0,
            offset_y: 0,
        };
    }

    return {
        src_space: srcSpace || 'image_abs_px',
        dst_space: 'image_abs_px',
        scale_x: 1,
        scale_y: 1,
        offset_x: 0,
        offset_y: 0,
    };
}

function remapBboxToImageSpace(x, y, width, height, matrix) {
    const sx = Number(matrix?.scale_x ?? 1);
    const sy = Number(matrix?.scale_y ?? 1);
    const ox = Number(matrix?.offset_x ?? 0);
    const oy = Number(matrix?.offset_y ?? 0);

    const x1 = sx * x + ox;
    const y1 = sy * y + oy;
    const x2 = sx * (x + width) + ox;
    const y2 = sy * (y + height) + oy;

    const left = Math.min(x1, x2);
    const top = Math.min(y1, y2);
    const w = Math.max(Math.abs(x2 - x1), 0);
    const h = Math.max(Math.abs(y2 - y1), 0);

    return {
        x: left,
        y: top,
        width: w,
        height: h,
    };
}

function getPageImageMeta(result, pageNum = 1) {
    const docInfo = (result && result.document_info) ? result.document_info : {};
    const meta = docInfo.page_image_meta;
    if (!meta || typeof meta !== 'object') return null;

    if (Array.isArray(meta.pages)) {
        const match = meta.pages.find(p => Number(p.page || 1) === Number(pageNum));
        return match || null;
    }

    return meta;
}

async function computeImageSha256Hex(image) {
    const src = image?.currentSrc || image?.src || '';
    if (!src || !window.crypto || !window.crypto.subtle) return '';

    const response = await fetch(src, { cache: 'no-store' });
    if (!response.ok) return '';

    const buffer = await response.arrayBuffer();
    const digest = await window.crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

async function validateImageCoordinateBinding(image, result, pageNum = 1) {
    if (!image || !result) return true;

    const expected = getPageImageMeta(result, pageNum);
    if (!expected) return true;

    const expectedWidth = Number(expected.width_px || 0);
    const expectedHeight = Number(expected.height_px || 0);
    if (expectedWidth <= 0 || expectedHeight <= 0) return true;

    const actualWidth = Number(image.naturalWidth || 0);
    const actualHeight = Number(image.naturalHeight || 0);

    if (actualWidth !== expectedWidth || actualHeight !== expectedHeight) {
        console.error(
            `[Layout] Image binding mismatch: expected ${expectedWidth}x${expectedHeight}, got ${actualWidth}x${actualHeight}`,
            expected
        );
        showNotification('Image size does not match coordinate metadata. Skipping overlays to avoid offset.', 'warning');
        return false;
    }

    if (!enableOverlaySha256Validation) {
        return true;
    }

    const expectedSha = String(expected.sha256 || '').trim().toLowerCase();
    if (!expectedSha) {
        return true;
    }

    try {
        const actualSha = (await computeImageSha256Hex(image)).toLowerCase();
        if (!actualSha) {
            showNotification('Unable to compute image SHA256. Skipping SHA verification.', 'info');
            return true;
        }
        if (actualSha !== expectedSha) {
            console.error(`[Layout] Image SHA256 mismatch: expected=${expectedSha}, actual=${actualSha}`);
            showNotification('Image SHA256 mismatch with coordinate metadata. Skipping overlays.', 'warning');
            return false;
        }
    } catch (error) {
        console.warn('[Layout] SHA256 verification failed:', error);
        showNotification('SHA256 verification failed. Proceeding with size validation only.', 'info');
    }

    return true;
}

function getOverlayLayerType(type) {
    const normalized = String(type || '').toLowerCase();
    if (['table'].includes(normalized)) return 'table';
    if (['figure', 'image', 'chart', 'figure_title', 'figure_caption', 'table_caption', 'figure_table_chart_title'].includes(normalized)) return 'figure';
    if (['header', 'footer', 'page_header', 'page_footer'].includes(normalized)) return 'header_footer';
    if (['list', 'list_item'].includes(normalized)) return 'list';
    return 'text';
}

function shouldRenderOverlayType(type) {
    const layerType = getOverlayLayerType(type);
    return overlayLayerVisibility[layerType] !== false;
}

/**
 * Render document with annotations overlay
 */
async function renderDocumentWithAnnotations(result) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    lastRenderedAnalysisResult = result;

    const docInfo = result.document_info || {};
    const fileName = docInfo.file_name || 'Document';

    let imageUrl = currentOriginalFileUrl;
    if (currentTaskId) {
        try {
            // Always use backend page-image endpoint after analysis so the displayed
            // image stays in the same coordinate space as /blocks bboxes.
            imageUrl = await getPdfPageImage(currentTaskId, 1);
        } catch (error) {
            console.error('Failed to get backend page image:', error);
            imageUrl = `${API_BASE_URL}/tasks/${currentTaskId}/page-image/1`;
        }
    }

    const html = `
        <div class="document-preview-content">
            <div class="svg-annotation-wrapper">
                <img id="documentImage" src="${imageUrl || ''}"
                     style="display:block; max-width:100%; height:auto; border-radius:8px;"
                     alt="Document">
                <svg id="annotationSvgOverlay"
                     style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;"
                     preserveAspectRatio="none"></svg>
            </div>
        </div>`;

    documentPage.innerHTML = html;

    const image = document.getElementById('documentImage');
    if (!image) return;

    const renderBlocks = async () => {
        adjustDocumentSize();
        if (!currentTaskId) return;

        const blocks = lastFetchedBlocks || await fetchTaskBlocks(currentTaskId);
        if (!blocks || !Array.isArray(blocks.blocks) || blocks.blocks.length === 0) return;
        lastFetchedBlocks = blocks;

        const svg = document.getElementById('annotationSvgOverlay');
        if (!svg) return;

        const imgW = Number(blocks.image_width) || image.naturalWidth || 1;
        const imgH = Number(blocks.image_height) || image.naturalHeight || 1;
        svg.setAttribute('viewBox', `0 0 ${imgW} ${imgH}`);

        const svgNS = 'http://www.w3.org/2000/svg';
        blocks.blocks.forEach((block, idx) => {
            const bbox = block.bbox || [];
            const x1 = Number(bbox[0] || 0);
            const y1 = Number(bbox[1] || 0);
            const x2 = Number(bbox[2] || 0);
            const y2 = Number(bbox[3] || 0);
            const w = Math.max(0, x2 - x1);
            const h = Math.max(0, y2 - y1);
            if (w <= 0 || h <= 0) return;

            const type = String(block.type || block.role || 'paragraph').toLowerCase();
            if (!shouldRenderOverlayType(type)) return;

            const colors = getSvgAnnotationColors(type);
            const role = formatAzureRoleLabel(type);
            const text = String(block.text || block.content || '');
            const displayContent = text.length > 100 ? text.substring(0, 100) + '...' : text;
            const rawConf = Number(block.confidence || 0);
            const confidencePercent = rawConf > 1 ? rawConf : rawConf * 100;
            const bboxStr = `${x1.toFixed(0)}, ${y1.toFixed(0)}, ${w.toFixed(0)} × ${h.toFixed(0)}`;

            const tooltipData = { role, content: text, displayContent, bbox: bboxStr, confidence: confidencePercent };

            const rect = document.createElementNS(svgNS, 'rect');
            rect.setAttribute('x', x1);
            rect.setAttribute('y', y1);
            rect.setAttribute('width', w);
            rect.setAttribute('height', h);
            rect.setAttribute('fill', colors.fill);
            rect.setAttribute('stroke', colors.stroke);
            rect.setAttribute('stroke-width', '2');
            rect.setAttribute('rx', '3');
            rect.classList.add('svg-annotation');
            rect.dataset.tooltipData = JSON.stringify(tooltipData);
            rect.dataset.elementType = type;
            rect.dataset.elementIndex = String(idx);
            rect.style.pointerEvents = 'auto';
            rect.style.cursor = 'pointer';
            svg.appendChild(rect);
        });

        if (lastRenderedAnalysisResult) {
            updateContentText(lastRenderedAnalysisResult);
        }
        initAnnotationInteractions();
    };

    if (image.complete && image.naturalWidth > 0) {
        await renderBlocks();
    } else {
        image.addEventListener('load', renderBlocks, { once: true });
    }
}

/**
 * Adjust annotation positions — SVG viewBox handles coordinate scaling
 * automatically; this keeps legacy call sites working.
 */
function adjustAnnotationPositions() {
    adjustDocumentSize();
}

/**
 * Handle window resize — just re-adjust document size.
 */
function handleResizeForAnnotations() {
    adjustDocumentSize();
}
/**
 * Render text preview (fallback)
 */
function renderTextPreview(result) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    const docInfo = result.document_info || {};
    const fileName = docInfo.file_name || 'Document';
    const pages = docInfo.pages || result.layout?.total_pages || result.page_count || 1;

    // Get text content for preview (Analysis view)
    const textBlocks = result.text_blocks || [];
    const fullText = result.full_text || '';
    const layout = result.layout || {};
    const elements = layout.elements || [];

    // Try to get text from various sources
    let previewText = '';
    if (fullText) {
        previewText = fullText.substring(0, 2000); // Limit preview length
    } else if (textBlocks.length > 0) {
        previewText = textBlocks.slice(0, 10).map(b => b.text || '').join('\n\n').substring(0, 2000);
    } else if (elements.length > 0) {
        const textElements = elements.filter(el => el.text && el.type !== 'table').slice(0, 10);
        previewText = textElements.map(el => el.text).join('\n\n').substring(0, 2000);
    }

    // Create document preview with extracted text content (Analysis view)
    let html = '<div class="document-preview-content">';
    html += '<div class="preview-header-info" style="margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #e5e7eb;">';
    html += `<h3 style="margin: 0 0 8px 0; color: #1f2937; font-size: 18px;">${escapeHtml(fileName)} (Text Preview)</h3>`;
    html += `<p style="margin: 0; color: #6b7280; font-size: 14px;">${pages} page${pages !== 1 ? 's' : ''} · Extracted Text</p>`;
    html += '</div>';

    if (previewText) {
        html += '<div class="preview-text-content" style="padding: 20px; background: #f9fafb; border-radius: 8px; max-height: 600px; overflow-y: auto;">';
        html += '<div style="white-space: pre-wrap; line-height: 1.6; color: #374151; font-size: 14px;">';
        html += escapeHtml(previewText);
        if ((fullText && fullText.length > 2000) || (textBlocks.length > 10) || (elements.length > 10)) {
            html += '<p style="margin-top: 15px; color: #6b7280; font-style: italic;">...</p>';
            html += '<p style="color: #6b7280; font-size: 12px;">(Preview truncated. Use the Text tab to view full content.)</p>';
        }
        html += '</div>';
        html += '</div>';
    } else {
        html += '<div class="preview-text-preview" style="padding: 40px; text-align: center; color: #6b7280;">';
        html += '<p>No text content available for preview</p>';
        html += '<p style="font-size: 14px; margin-top: 10px;">Use the tabs above to view structure, text, and tables</p>';
        html += '</div>';
    }

    html += '</div>';
    documentPage.innerHTML = html;
}

// Global tooltip instance
let globalTooltip = null;

/**
 * Initialize global tooltip
 */
function initGlobalTooltip() {
    if (!globalTooltip) {
        globalTooltip = document.createElement('div');
        globalTooltip.className = 'annotation-tooltip global-tooltip';
        globalTooltip.style.display = 'none';
        globalTooltip.style.position = 'fixed';
        globalTooltip.style.zIndex = '10000';
        document.body.appendChild(globalTooltip);
    }
}

/**
 * Initialize annotation interactions
 */
function initAnnotationInteractions() {
    initGlobalTooltip();

    const svg = document.getElementById('annotationSvgOverlay');
    if (!svg) return;

    const rects = svg.querySelectorAll('.svg-annotation');

    const esc = (str) => {
        const d = document.createElement('div');
        d.textContent = String(str == null ? '' : str);
        return d.innerHTML;
    };

    rects.forEach(rect => {
        rect.addEventListener('click', () => {
            rects.forEach(r => r.classList.remove('svg-annotation-active'));
            rect.classList.add('svg-annotation-active');
            highlightResultItem(rect.dataset.elementType, rect.dataset.elementIndex);
        });

        rect.addEventListener('mouseenter', () => {
            if (!globalTooltip) return;
            const raw = rect.dataset.tooltipData;
            if (!raw) return;
            try {
                const d = JSON.parse(raw);
                globalTooltip.innerHTML = `
                    <div class="tooltip-line"><strong>Role:</strong> ${esc(d.role)}</div>
                    <div class="tooltip-line"><strong>BBox:</strong> ${esc(d.bbox)}</div>
                    <div class="tooltip-line"><strong>Content:</strong> ${d.displayContent ? esc(d.displayContent) : '(empty)'}</div>
                    <div class="tooltip-line"><strong>Confidence:</strong> ${Number(d.confidence || 0).toFixed(1)}%</div>
                `;

                const vr = rect.getBoundingClientRect();
                globalTooltip.style.display = 'block';
                globalTooltip.style.left = '0';
                globalTooltip.style.top = '0';
                const tr = globalTooltip.getBoundingClientRect();
                const vw = window.innerWidth;
                const vh = window.innerHeight;

                let left = vr.right + 10;
                let top = vr.top;
                if (left + tr.width > vw - 10) left = Math.max(10, vr.left - tr.width - 10);
                if (top + tr.height > vh - 10) top = Math.max(10, vh - tr.height - 10);

                globalTooltip.style.left = `${Math.max(10, left)}px`;
                globalTooltip.style.top = `${Math.max(10, top)}px`;
            } catch (err) {
                console.error('Tooltip parse error:', err);
                globalTooltip.style.display = 'none';
            }
        });

        rect.addEventListener('mouseleave', () => {
            if (globalTooltip) globalTooltip.style.display = 'none';
        });
    });
}

/**
 * Highlight corresponding item in results panel
 */
function highlightResultItem(elementType, elementIndex) {
    // This would scroll to and highlight the corresponding item in the structure view
    // Implementation depends on structure view structure
    console.log('Highlighting:', elementType, elementIndex);
}


/**
 * Normalize text to ensure proper spacing between words
 */
function normalizeTextForDisplay(text) {
    if (!text) return text;

    // Add space between lowercase letter and uppercase letter (word boundary)
    text = text.replace(/([a-z])([A-Z])/g, '$1 $2');

    // Add space between letter and number (if not already spaced)
    text = text.replace(/([a-zA-Z])(\d)/g, '$1 $2');
    text = text.replace(/(\d)([a-zA-Z])/g, '$1 $2');

    // Clean up multiple spaces
    text = text.replace(/ +/g, ' ');

    return text.trim();
}

function normalizePanelParagraphText(text) {
    const value = normalizeTextForDisplay(text || '');
    if (!value) return value;

    // Flatten OCR line breaks for panel readability while keeping sentence spacing.
    return value
        .replace(/\r\n/g, '\n')
        .replace(/[ \t]*\n[ \t]*/g, ' ')
        .replace(/ +/g, ' ')
        .trim();
}

function isLikelyCollapsedText(text) {
    const value = String(text || '');
    if (!value) return false;

    const noSpaceLength = value.replace(/\s+/g, '').length;
    const spaceCount = (value.match(/\s/g) || []).length;

    // Long text with almost no spaces is usually collapsed OCR text.
    if (noSpaceLength >= 40 && spaceCount <= 1) {
        return true;
    }

    // Long alpha chunks without spacing are suspicious.
    if (/[A-Za-z]{25,}/.test(value)) {
        return true;
    }

    return false;
}

function toAzureTypeLabel(type) {
    const normalized = String(type || 'paragraph').toLowerCase();
    const map = {
        doc_title: 'Title',
        paragraph_title: 'SectionHeading',
        abstract_title: 'SectionHeading',
        reference_title: 'SectionHeading',
        content_title: 'SectionHeading',
        figure_table_chart_title: 'FigureCaption',
        table_caption: 'FigureCaption',
        page_header: 'PageHeader',
        page_footer: 'PageFooter',
        section_header: 'SectionHeading',
        table_header: 'TableHeader',
        figure_caption: 'FigureCaption',
        list_item: 'ListItem',
        text: 'Paragraph',
        paragraph: 'Paragraph',
        text_block: 'Paragraph',
        title: 'Title',
        subtitle: 'Subtitle',
        table: 'Table',
        figure: 'Figure',
        image: 'Figure',
        header: 'PageHeader',
        footer: 'PageFooter',
        equation: 'Formula',
        list: 'ListItem',
        reference: 'Reference'
    };

    return map[normalized] || normalized
        .split('_')
        .map(p => p ? p.charAt(0).toUpperCase() + p.slice(1) : '')
        .join('');
}

/**
 * Render a single table card with proper merge cell support
 * Only renders table content, not other page content
 */
function renderTableCard(table, index, total) {
    const tableData = table.data || [];
    const rows = table.rows || tableData.length || 0;
    const columns = table.columns || (tableData[0] ? tableData[0].length : 0);
    const page = table.page || '?';
    const confidence = table.confidence || 0;
    const tableHtml = table.html || null;
    const htmlStructure = table.html_structure || null;

    let html = '<div class="table-card">';
    html += '<div class="table-card-header">';
    html += `<span class="table-name">Table ${index + 1}${total > 1 ? ` of ${total}` : ''}${page !== '?' ? ` (Page ${page})` : ''}`;
    if (confidence > 0) {
        html += ` <span style="font-size: 0.75rem; color: var(--text-tertiary);">Confidence: ${(confidence * 100).toFixed(1)}%</span>`;
    }
    html += '</span>';
    html += '<div class="table-actions">';
    html += '<button class="table-action-btn" title="Export CSV">';
    html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">';
    html += '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>';
    html += '<polyline points="7 10 12 15 17 10"></polyline>';
    html += '<line x1="12" y1="15" x2="12" y2="3"></line>';
    html += '</svg></button></div></div>';
    html += '<div class="table-preview" style="overflow-x: auto;">';

    let tableRendered = false;

    // Strategy 1: Use HTML structure if available (most reliable)
    if (!tableRendered && htmlStructure && htmlStructure.rows && htmlStructure.rows.length > 0) {
        html += '<table class="extracted-table">';
        let inThead = false;
        let inTbody = false;

        htmlStructure.rows.forEach((row, rowIdx) => {
            const isHeaderRow = row.cells.some(c => c.is_header);

            if (rowIdx === 0 && isHeaderRow && !inThead) {
                html += '<thead>';
                inThead = true;
            } else if (rowIdx === 0 && !isHeaderRow && !inTbody) {
                html += '<tbody>';
                inTbody = true;
            } else if (rowIdx > 0 && inThead && !isHeaderRow) {
                html += '</thead><tbody>';
                inThead = false;
                inTbody = true;
            } else if (rowIdx > 0 && !inTbody) {
                html += '<tbody>';
                inTbody = true;
            }

            html += '<tr>';
            row.cells.forEach(cell => {
                const tag = cell.is_header ? 'th' : 'td';
                const attrs = [];
                if (cell.rowspan > 1) attrs.push(`rowspan="${cell.rowspan}"`);
                if (cell.colspan > 1) attrs.push(`colspan="${cell.colspan}"`);
                const attrStr = attrs.length > 0 ? ' ' + attrs.join(' ') : '';
                const cellText = normalizeTextForDisplay(cell.text || '');
                html += `<${tag}${attrStr}>${escapeHtml(cellText)}</${tag}>`;
            });
            html += '</tr>';
        });

        if (inThead) html += '</thead>';
        if (inTbody) html += '</tbody>';
        html += '</table>';
        tableRendered = true;
    }

    // Strategy 2: Parse and clean HTML (only extract table element, ignore all other content)
    if (!tableRendered && tableHtml) {
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(tableHtml, 'text/html');
            const tableElement = doc.querySelector('table');
            if (tableElement) {
                // Clone table and add class
                const cleanTable = tableElement.cloneNode(true);
                cleanTable.className = 'extracted-table';
                // Remove any text nodes or elements outside of table cells
                // Only keep tr, th, td elements
                const rows = cleanTable.querySelectorAll('tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td, th');
                    cells.forEach(cell => {
                        // Remove nested tables if any
                        const nestedTables = cell.querySelectorAll('table');
                        nestedTables.forEach(nt => nt.remove());
                        // Normalize text in cells
                        const cellText = cell.textContent || '';
                        const normalizedText = normalizeTextForDisplay(cellText.trim());
                        cell.textContent = normalizedText;
                    });
                });
                html += cleanTable.outerHTML;
                tableRendered = true;
            } else {
                // No table tag found in HTML, this is invalid - skip to data array
                console.warn('Table HTML does not contain <table> tag, using data array instead');
            }
        } catch (e) {
            console.warn('Failed to parse table HTML:', e);
        }
    }

    // Strategy 3: Render from data array (validate it looks like a table)
    if (!tableRendered && tableData.length > 0 && Array.isArray(tableData[0])) {
        // Filter out empty rows and validate table structure
        const validRows = tableData.filter(row => {
            if (!Array.isArray(row)) return false;
            // Check if row has reasonable number of cells (2-20 columns typical for tables)
            const cellCount = row.filter(cell => cell && String(cell).trim()).length;
            return cellCount >= 2 && cellCount <= 20;
        });

        // Additional validation: check if data looks like a table
        // Tables typically have consistent column counts across rows
        if (validRows.length > 0) {
            const firstRowCols = validRows[0].length;
            const consistentRows = validRows.filter(row => {
                const rowCols = row.length;
                // Allow some variation (within 2 columns) for merged cells
                return Math.abs(rowCols - firstRowCols) <= 2;
            });

            // Only render if we have at least 2 rows with consistent structure
            if (consistentRows.length >= 2) {
                html += '<table class="extracted-table">';
                const hasHeaders = consistentRows.length > 1 &&
                    consistentRows[0].every(cell => cell && String(cell).trim()) &&
                    consistentRows[0].length <= 15; // Reasonable header count

                if (hasHeaders && consistentRows.length > 1) {
                    html += '<thead><tr>';
                    consistentRows[0].forEach(cell => {
                        const cellText = normalizeTextForDisplay(String(cell || ''));
                        html += `<th>${escapeHtml(cellText)}</th>`;
                    });
                    html += '</tr></thead><tbody>';
                    consistentRows.slice(1).forEach(row => {
                        if (Array.isArray(row)) {
                            html += '<tr>';
                            row.forEach(cell => {
                                const cellText = normalizeTextForDisplay(String(cell || ''));
                                html += `<td>${escapeHtml(cellText)}</td>`;
                            });
                            html += '</tr>';
                        }
                    });
                    html += '</tbody>';
                } else {
                    html += '<tbody>';
                    consistentRows.forEach(row => {
                        if (Array.isArray(row)) {
                            html += '<tr>';
                            row.forEach(cell => {
                                const cellText = normalizeTextForDisplay(String(cell || ''));
                                html += `<td>${escapeHtml(cellText)}</td>`;
                            });
                            html += '</tr>';
                        }
                    });
                    html += '</tbody>';
                }
                html += '</table>';
                tableRendered = true;
            }
        }
    }

    // If nothing rendered, show empty state
    if (!tableRendered) {
        html += '<div class="empty-state" style="padding: 20px; text-align: center; color: var(--text-tertiary);">No table data available</div>';
    }

    html += '</div></div>';
    return html;
}

/**
 * 从任务 result 中取出 KIE 字段映射（与 envelope.view.fields 同源）。
 */
function pickKieFieldsMap(result) {
    const view = result.view || {};
    const k = result.kie_fields;
    const vf = view.fields;
    if (k && typeof k === 'object' && !Array.isArray(k)) {
        return k;
    }
    if (vf && typeof vf === 'object' && !Array.isArray(vf)) {
        return vf;
    }
    return {};
}

/**
 * 将 Azure 风格 KIE 字段（dict / BaseField）格式化为可放入 innerHTML 的安全 HTML。
 */
function formatKieFieldForExtract(field, depth) {
    const d = depth || 0;
    if (d > 8) {
        try {
            return '<pre class="kie-json">' + escapeHtml(JSON.stringify(field, null, 2)) + '</pre>';
        } catch (e) {
            return escapeHtml(String(field));
        }
    }
    if (field == null) {
        return '';
    }
    if (typeof field !== 'object') {
        return escapeHtml(String(field));
    }
    if (Array.isArray(field)) {
        if (field.length === 0) {
            return '<span class="kie-empty">—</span>';
        }
        return (
            '<ul class="kie-array">' +
            field.map((item) => '<li>' + formatKieFieldForExtract(item, d + 1) + '</li>').join('') +
            '</ul>'
        );
    }

    const t = field.type;
    if (t === 'string') {
        const s = field.valueString != null ? field.valueString : field.content;
        return escapeHtml(s != null ? String(s) : '');
    }
    if (t === 'date') {
        const s = field.valueDate != null ? field.valueDate : field.content;
        return escapeHtml(s != null ? String(s) : '');
    }
    if (t === 'number') {
        const n = field.valueNumber != null ? field.valueNumber : field.content;
        return escapeHtml(String(n));
    }
    if (t === 'currency' && field.valueCurrency && typeof field.valueCurrency === 'object') {
        const c = field.valueCurrency;
        const amt = c.amount != null ? String(c.amount) : '';
        const code = c.currencyCode != null ? String(c.currencyCode) : '';
        const joined = [code, amt].filter(Boolean).join(' ').trim();
        return escapeHtml(joined || (field.content != null ? String(field.content) : ''));
    }
    if (t === 'address' && field.valueAddress && typeof field.valueAddress === 'object') {
        const a = field.valueAddress;
        const parts = [a.streetAddress, a.city, a.state, a.postalCode, a.countryRegion].filter(Boolean);
        return escapeHtml(parts.join(', '));
    }
    if (t === 'object' && field.valueObject && typeof field.valueObject === 'object') {
        const rows = Object.entries(field.valueObject).map(([k, v]) => {
            return (
                '<div class="kie-subrow"><span class="kie-subk">' +
                escapeHtml(k) +
                '</span>: ' +
                formatKieFieldForExtract(v, d + 1) +
                '</div>'
            );
        });
        return '<div class="kie-object">' + rows.join('') + '</div>';
    }
    if (t === 'array' && Array.isArray(field.valueArray)) {
        return formatKieFieldForExtract(field.valueArray, d + 1);
    }

    if (field.relations && typeof field.relations === 'object') {
        const rows = Object.entries(field.relations).map(([k, arr]) => {
            const label = String(k).split('|')[0];
            let val = '';
            if (Array.isArray(arr) && arr[0] && arr[0].text != null) {
                val = String(arr[0].text);
            }
            return (
                '<div class="kie-subrow"><span class="kie-subk">' +
                escapeHtml(label) +
                '</span>: ' +
                escapeHtml(val) +
                '</div>'
            );
        });
        return '<div class="kie-object">' + rows.join('') + '</div>';
    }

    if (field.content != null && field.content !== '') {
        return escapeHtml(String(field.content));
    }
    try {
        return '<pre class="kie-json">' + escapeHtml(JSON.stringify(field, null, 2)) + '</pre>';
    } catch (e) {
        return escapeHtml(String(field));
    }
}

/**
 * 在 Content > Fields 子页签中渲染 KIE 字段。
 * 仅当 result.kie_fields 或 result.view.fields 非空时显示 Fields 按钮，
 * 并在结果加载完成后自动切到该子页签。
 */
function updateContentFields(result) {
    const fieldsBtn = document.getElementById('tabBtnFields');
    const fieldsView = document.getElementById('contentFieldsView');
    const fieldsList = document.getElementById('contentFieldsList');
    const fieldsMeta = document.getElementById('contentFieldsMeta');

    if (!fieldsBtn || !fieldsView || !fieldsList || !fieldsMeta) {
        return;
    }

    const kieFields = pickKieFieldsMap(result || {});
    const hasKie = Object.keys(kieFields).length > 0;

    if (!hasKie) {
        fieldsList.innerHTML = '';
        fieldsMeta.textContent = '';
        fieldsBtn.classList.add('hidden');
        fieldsView.classList.add('hidden');
        if (fieldsBtn.classList.contains('active')) {
            const fallback = document.querySelector('.content-sub-tab[data-content="text"]');
            if (fallback) fallback.click();
        }
        return;
    }

    const meta = result.kie_meta || {};
    const metaBits = [];
    if (meta.succeeded === false) {
        metaBits.push('KIE 未完成');
        if (meta.error_message) {
            metaBits.push(String(meta.error_message));
        } else if (meta.error_code) {
            metaBits.push(String(meta.error_code));
        }
    } else {
        if (meta.confidence_avg != null && !Number.isNaN(Number(meta.confidence_avg))) {
            metaBits.push('平均置信度 ' + Number(meta.confidence_avg).toFixed(2));
        }
        if (meta.items_count != null) {
            metaBits.push('明细行 ' + String(meta.items_count));
        }
    }
    fieldsMeta.textContent = metaBits.join(' · ');

    let html = '';
    Object.entries(kieFields).forEach(([key, value]) => {
        html += '<div class="kie-field-card">';
        html += '<div class="kie-field-card-header">';
        html +=
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M16 3v4"></path><path d="M8 3v4"></path><path d="M3 10h18"></path></svg>';
        html += '<span>' + escapeHtml(key) + '</span></div>';
        html += '<div class="kie-field-card-value">' + formatKieFieldForExtract(value, 0) + '</div>';
        html += '</div>';
    });
    fieldsList.innerHTML = html;

    fieldsBtn.classList.remove('hidden');
    fieldsView.classList.remove('hidden');
    if (!fieldsBtn.classList.contains('active')) {
        fieldsBtn.click();
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    // Handle null, undefined, or non-string types
    if (text == null) {
        return '';
    }
    if (typeof text !== 'string') {
        text = String(text);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show floating progress card
 */
function showFloatingProgressCard(taskInfo) {
    const card = document.getElementById('floatingProgressCard');
    if (!card) return;

    const fileNameEl = card.querySelector('.floating-card-filename');
    const stepEl = card.querySelector('.floating-card-step');
    const progressFill = card.querySelector('#floatingCardProgressFill');
    const progressText = card.querySelector('#floatingCardProgressText');

    if (fileNameEl && taskInfo.fileName) {
        fileNameEl.textContent = taskInfo.fileName;
    }
    if (stepEl && taskInfo.step) {
        stepEl.textContent = taskInfo.step;
    }
    if (progressFill && taskInfo.progress !== undefined) {
        progressFill.style.width = `${taskInfo.progress}%`;
    }
    if (progressText && taskInfo.progress !== undefined) {
        progressText.textContent = `${taskInfo.progress}%`;
    }

    card.style.display = 'block';

    // Setup cancel button
    const cancelBtn = document.getElementById('cancelFloatingCardBtn');
    if (cancelBtn) {
        cancelBtn.onclick = () => {
            // Find the processing item and cancel it
            const processingItem = document.querySelector('.queue-item.processing');
            if (processingItem && processingItem.dataset.taskId) {
                fetch(`${API_BASE_URL}/tasks/${processingItem.dataset.taskId}/cancel`, {
                    method: 'POST'
                }).catch(console.error);
            }
        };
    }

    // Setup close button
    const closeBtn = document.getElementById('closeFloatingCardBtn');
    if (closeBtn) {
        closeBtn.onclick = () => {
            hideFloatingProgressCard();
        };
    }
}

/**
 * Update floating progress
 */
function updateFloatingProgress(progress, step) {
    const card = document.getElementById('floatingProgressCard');
    if (!card || card.style.display === 'none') return;

    const stepEl = card.querySelector('.floating-card-step');
    const progressFill = card.querySelector('#floatingCardProgressFill');
    const progressText = card.querySelector('#floatingCardProgressText');

    if (stepEl && step) {
        stepEl.textContent = step;
    }
    if (progressFill && progress !== undefined) {
        progressFill.style.width = `${progress}%`;
    }
    if (progressText && progress !== undefined) {
        progressText.textContent = `${progress}%`;
    }
}

/**
 * Hide floating progress card
 */
function hideFloatingProgressCard() {
    const card = document.getElementById('floatingProgressCard');
    if (card) {
        card.style.display = 'none';
    }
}

/**
 * Fail processing
 */
function failProcessing(item, message) {
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
    // Promote next queued item if any
    promoteNextQueued();
}

/**
 * Update status bar
 */
function updateStatusBar(status = 'default', data = {}) {
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

/**
 * Export results via backend /tasks/{task_id}/export/{format}
 */
async function exportResults(format) {
    if (!currentTaskId) {
        showNotification('No completed task to export. Run analysis first.', 'error');
        return;
    }

    format = (format || '').toLowerCase();
    const apiFormat = format === 'word' ? 'docx' : format;

    try {
        const response = await fetch(
            `${API_BASE_URL}/tasks/${currentTaskId}/export/${apiFormat}`
        );

        if (!response.ok) {
            let detail = response.statusText;
            try {
                const errBody = await response.json();
                detail = errBody.detail || detail;
            } catch (_) { /* ignore */ }
            showNotification(`Export failed: ${detail}`, 'error');
            return;
        }

        const contentType = response.headers.get('content-type') || '';

        if (contentType.includes('application/json') && (apiFormat === 'markdown' || apiFormat === 'md')) {
            const payload = await response.json();
            const md = payload.markdown || '';
            downloadFile(md, `${currentTaskId}_result.md`, 'text/markdown');
        } else if (contentType.includes('application/json') && apiFormat === 'azure') {
            const payload = await response.json();
            downloadFile(
                JSON.stringify(payload, null, 2),
                `${currentTaskId}_azure.json`,
                'application/json'
            );
        } else {
            const blob = await response.blob();
            const disposition = response.headers.get('content-disposition') || '';
            const match = disposition.match(/filename="?([^";\n]+)"?/i);
            const filename = match ? match[1] : `${currentTaskId}_export.${apiFormat}`;
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        showNotification(`Exported ${format.toUpperCase()} successfully`, 'success');
    } catch (err) {
        console.error('[Export]', err);
        showNotification(`Export failed: ${err.message}`, 'error');
    }
}

/**
 * Convert to CSV format
 */
function convertToCSV(data) {
    return data.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
}

/**
 * Convert to Markdown format
 */
function convertToMarkdown(data) {
    let md = `# ${data.document.name}\n\n`;
    md += `**Processed At**: ${data.document.processedAt}\n\n`;
    md += `**Total Pages**: ${data.document.pages}\n\n`;

    md += `## Document Structure\n\n`;
    md += `- Headers: ${data.layout.headers}\n`;
    md += `- Titles: ${data.layout.titles}\n`;
    md += `- Paragraphs: ${data.layout.paragraphs}\n`;
    md += `- Tables: ${data.layout.tables}\n`;
    md += `- Figures: ${data.layout.figures}\n\n`;

    md += `## Extracted Tables\n\n`;
    if (data.tables.length > 0) {
        const table = data.tables[0];
        md += `### ${table.name}\n\n`;
        md += '| ' + table.data[0].join(' | ') + ' |\n';
        md += '| ' + table.data[0].map(() => '---').join(' | ') + ' |\n';
        table.data.slice(1).forEach(row => {
            md += '| ' + row.join(' | ') + ' |\n';
        });
    }

    md += `\n## Keywords\n\n`;
    md += data.keywords.map(k => `- ${k}`).join('\n');

    return md;
}

/**
 * Download file
 */
function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * Show notification
 */
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existing = document.querySelector('.notification');
    if (existing) {
        existing.remove();
    }

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-icon">
            ${getNotificationIcon(type)}
        </div>
        <div class="notification-message">${message}</div>
    `;

    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 20px;
        background: ${getNotificationColor(type)};
        border-radius: 10px;
        color: white;
        font-size: 14px;
        font-weight: 500;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(notification);

    // Auto remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out forwards';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Get notification icon
 */
function getNotificationIcon(type) {
    const icons = {
        success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
        error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
        warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
        info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
    };
    return icons[type] || icons.info;
}

/**
 * Get notification color
 */
function getNotificationColor(type) {
    const colors = {
        success: 'linear-gradient(135deg, #22c55e, #16a34a)',
        error: 'linear-gradient(135deg, #f43f5e, #e11d48)',
        warning: 'linear-gradient(135deg, #f59e0b, #d97706)',
        info: 'linear-gradient(135deg, #6366f1, #4f46e5)'
    };
    return colors[type] || colors.info;
}

// ============================================
// P2 Features: Batch Processing
// ============================================

/**
 * Initialize batch processing features
 */
function initBatchProcessing() {
    // Batch processing state
    window.batchState = {
        batches: [],
        currentBatch: null
    };
}

/**
 * Create a new batch job
 */
async function createBatch(name, files) {
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
async function startBatch(batchId) {
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
async function pollBatchStatus(batchId) {
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
function updateBatchUI(batch) {
    // Update progress display if on batch tab
    console.log('Batch status:', batch.status, 'Progress:', batch.progress);
}

/**
 * Pause batch
 */
async function pauseBatch(batchId) {
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
async function resumeBatch(batchId) {
    try {
        const response = await fetch(`${API_BASE_URL}/batch/${batchId}/resume`, {
            method: 'POST'
        });
        if (response.ok) {
            showNotification('Batch resumed', 'success');
        }
    } catch (error) {
        showNotification(`Failed to resume: ${error.message}`, 'error');
    }
}

/**
 * Cancel batch
 */
async function cancelBatch(batchId) {
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
async function getBatchResults(batchId) {
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

/**
 * Initialize panel resize functionality
 */
function initPanelResize() {
    const rightPanel = document.getElementById('rightPanel');
    const resizeHandle = document.getElementById('panelResizeHandle');

    if (!rightPanel || !resizeHandle) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    resizeHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = rightPanel.offsetWidth;
        resizeHandle.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const diff = startX - e.clientX; // Reverse because we're resizing from left
        const newWidth = startWidth + diff;
        const minWidth = 250;
        const maxWidth = 800;

        if (newWidth >= minWidth && newWidth <= maxWidth) {
            rightPanel.style.width = `${newWidth}px`;
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

/**
 * Initialize JSON view buttons
 */
function initJsonViewButtons() {
    const copyBtn = document.getElementById('copyJsonBtn');
    const downloadBtn = document.getElementById('downloadJsonBtn');

    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const jsonCode = document.getElementById('jsonCode');
            if (jsonCode) {
                navigator.clipboard.writeText(jsonCode.textContent).then(() => {
                    showNotification('JSON copied to clipboard', 'success');
                }).catch(() => {
                    showNotification('Failed to copy JSON', 'error');
                });
            }
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const jsonCode = document.getElementById('jsonCode');
            if (jsonCode) {
                const blob = new Blob([jsonCode.textContent], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `docuvision_result_${Date.now()}.json`;
                a.click();
                URL.revokeObjectURL(url);
                showNotification('JSON downloaded', 'success');
            }
        });
    }
}

/**
 * Collect text-bearing elements from Phase1-style result.view.pages[].elements (payload.text).
 */
function collectViewPageTextElements(view) {
    if (!view || !Array.isArray(view.pages)) return [];
    const out = [];
    for (const page of view.pages) {
        const pageNum = page.page_num || page.page || 1;
        const elements = page.elements || [];
        let i = 0;
        for (const elem of elements) {
            if (!elem || typeof elem !== 'object') continue;
            const payload = elem.payload || {};
            const text = (typeof payload.text === 'string' ? payload.text : '').trim();
            if (!text) continue;
            const kind = String(elem.kind || elem.type || 'paragraph').toLowerCase();
            out.push({
                id: elem.id || `view_${pageNum}_${i++}`,
                type: kind,
                text,
                confidence: payload.confidence ?? elem.confidence,
                page: pageNum
            });
        }
    }
    return out;
}

/**
 * Update Content Text view
 */
function updateContentText(result) {
    const contentTextContent = document.getElementById('contentTextContent');
    if (!contentTextContent) return;

    // Prefer flat /blocks data when already fetched; fall back to result fields.
    const blocksData = lastFetchedBlocks;
    const textBlocks = result.text_blocks || [];
    let semanticTextBlocks;
    if (blocksData) {
        semanticTextBlocks = blocksData.blocks.filter(b => {
              const t = String(b.type || b.role || '').toLowerCase();
              return [
                  'doc_title', 'paragraph_title', 'abstract_title', 'reference_title', 'content_title',
                  'figure_table_chart_title', 'table_caption',
                  'title', 'subtitle', 'paragraph', 'text', 'text_block', 'section_header',
                  'header', 'footer', 'page_header', 'page_footer', 'reference',
                  'reference_content', 'abstract', 'content', 'algorithm',
                  'list_item', 'list', 'equation', 'figure_caption', 'aside_text',
                  'number', 'formula_number'
              ].includes(t)
                  && !!(b.text || b.content);
          }).map((b, i) => ({
              id: b.id || `block_${i}`,
              type: String(b.type || b.role || 'paragraph').toLowerCase(),
              text: b.text || b.content || '',
              confidence: b.confidence,
              page: b.page || 1
          }));
    } else {
        const fromView = collectViewPageTextElements(result.view || {});
        semanticTextBlocks = fromView.length ? fromView : (result.semantic_text_blocks || []);
    }
    const fullText = result.full_text || '';
    const layout = result.layout || {};
    const elements = layout.elements || [];

    // Keep type richness closer to Azure (Title/SectionHeading/Paragraph/...) and
    // prioritize semantic blocks (backend-aggregated) over OCR text lines.
    const textLikeTypes = new Set([
        'doc_title', 'paragraph_title', 'abstract_title', 'reference_title', 'content_title',
        'figure_table_chart_title',
        'title', 'subtitle', 'text', 'paragraph', 'text_block',
        'section_header', 'header', 'footer', 'page_header', 'page_footer',
        'reference', 'reference_content', 'abstract', 'content', 'algorithm',
        'list_item', 'list', 'equation', 'figure_caption', 'table_caption',
        'aside_text', 'number', 'formula_number'
    ]);

    const layoutTextElements = elements.filter(el => {
        const type = String(el.type || el.type_name || '').toLowerCase();
        const textValue =
            (typeof el.text === 'string' ? el.text : '') ||
            (typeof el.content === 'string' ? el.content : '');
        return !!textValue && textLikeTypes.has(type);
    });

    const semanticElements = semanticTextBlocks
        .filter(el => el && typeof el === 'object')
        .map((el, idx) => ({
            id: el.id || `semantic_${idx}`,
            type: String(el.type || 'paragraph').toLowerCase(),
            text: (typeof el.text === 'string' ? el.text : '') || (typeof el.content === 'string' ? el.content : ''),
            confidence: el.confidence,
            page: el.page
        }))
        .filter(el => !!el.text);

    const textElements = semanticElements.length > 0 ? semanticElements : layoutTextElements.map(el => ({
        type: String(el.type || el.type_name || 'paragraph').toLowerCase(),
        text: (typeof el.text === 'string' ? el.text : '') || (typeof el.content === 'string' ? el.content : ''),
        confidence: el.confidence,
        page: el.page
    }));

    const ocrCandidates = textBlocks
        .map(b => normalizePanelParagraphText(b.text || ''))
        .filter(Boolean)
        .sort((a, b) => b.length - a.length);

    // Fixed type display order for the Text panel
    const TYPE_DISPLAY_ORDER = [
        'PageHeader', 'Title', 'SectionHeading', 'FigureCaption',
        'Paragraph', 'Reference', 'Formula', 'ListItem', 'PageFooter'
    ];

    let html = '';

    if (textElements.length > 0) {
        // --- Group by page first, then by type label ---
        const pageMap = {};
        textElements.forEach(el => {
            const pageNum = el.page || 1;
            const rawType = String(el.type || el.type_name || 'paragraph').toLowerCase();
            const typeLabel = toAzureTypeLabel(rawType);

            if (!pageMap[pageNum]) pageMap[pageNum] = {};
            if (!pageMap[pageNum][typeLabel]) pageMap[pageNum][typeLabel] = [];

            let rawText = String(el.text || el.content || '');
            if (isLikelyCollapsedText(rawText) && ocrCandidates.length > 0) {
                const better = ocrCandidates.find(candidate => candidate.length >= rawText.length * 0.65);
                if (better) rawText = better;
            }

            pageMap[pageNum][typeLabel].push({
                text: normalizePanelParagraphText(rawText),
                confidence: el.confidence
            });
        });

        const sortedPages = Object.keys(pageMap).map(Number).sort((a, b) => a - b);
        const multiPage = sortedPages.length > 1;

        sortedPages.forEach(pageNum => {
            if (multiPage) {
                html += `<div class="text-page-section">`;
                html += `<h3 class="text-page-title">Page ${pageNum}</h3>`;
            }

            const groups = pageMap[pageNum];
            const allTypes = Object.keys(groups);
            const sortedTypes = [
                ...TYPE_DISPLAY_ORDER.filter(t => allTypes.includes(t)),
                ...allTypes.filter(t => !TYPE_DISPLAY_ORDER.includes(t)).sort()
            ];

            sortedTypes.forEach(typeLabel => {
                html += '<div class="text-section">';
                html += `<h4 class="text-section-title">${escapeHtml(typeLabel)}</h4>`;

                groups[typeLabel].forEach((item) => {
                    html += '<div class="text-block">';
                    html += '<div class="text-block-header">';
                    html += `<span class="block-type">${escapeHtml(typeLabel)}</span>`;
                    if (item.confidence !== undefined && item.confidence !== null) {
                        const confidence = Number(item.confidence || 0);
                        const confidencePercent = confidence > 1 ? confidence : confidence * 100;
                        if (confidencePercent > 0) {
                            html += `<span class="block-confidence">Confidence: ${confidencePercent.toFixed(1)}%</span>`;
                        }
                    }
                    html += '</div>';
                    html += `<p class="text-block-content" style="white-space: pre-wrap;">${escapeHtml(item.text)}</p>`;
                    html += '</div>';
                });

                html += '</div>';
            });

            if (multiPage) {
                html += '</div>';
            }
        });
    } else if (textBlocks.length > 0) {
        textBlocks.slice(0, 50).forEach((block, index) => {
            const normalizedText = normalizeTextForDisplay(block.text || '');
            html += '<div class="text-block">';
            html += '<div class="text-block-header">';
            html += `<span class="block-type">Text Block ${index + 1}</span>`;
            if (block.confidence !== undefined) {
                html += `<span class="block-confidence">Confidence: ${(block.confidence * 100).toFixed(1)}%</span>`;
            }
            html += '</div>';
            html += `<p class="text-block-content" style="white-space: pre-wrap;">${escapeHtml(normalizedText)}</p>`;
            html += '</div>';
        });
    } else if (fullText) {
        const normalizedText = normalizeTextForDisplay(fullText);
        html += '<div class="text-block">';
        html += '<div class="text-block-header">';
        html += '<span class="block-type">Full Text</span>';
        html += '</div>';
        const displayText = normalizedText.length > 10000 ? normalizedText.substring(0, 10000) + '...' : normalizedText;
        html += `<p class="text-block-content" style="white-space: pre-wrap;">${escapeHtml(displayText)}</p>`;
        html += '</div>';
    }

    if (!html) {
        html = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No text extracted</div>';
    }

    contentTextContent.innerHTML = html;
}

/**
 * Update Content Tables view
 */
function updateContentTables(result) {
    const contentTableList = document.getElementById('contentTableList');
    if (!contentTableList) return;

    // Render extracted tables (or fallback layout-derived tables) into contentTableList
    let extractedTables = result.tables || [];

    // Fallback: Layout-only mode can contain table HTML in result.layout.elements
    if (extractedTables.length === 0) {
        const layoutTables = (result.layout?.elements || []).filter(el => {
            const t = String(el.type || el.element_type || '').toLowerCase();
            return t === 'table' && !!el.html;
        });

        if (layoutTables.length > 0) {
            extractedTables = layoutTables.map((el, idx) => ({
                id: el.id || el.element_id || `layout_table_${idx + 1}`,
                page: el.page || el.page_number || 1,
                html: el.html,
                data: el.data || [],
                rows: el.rows || 0,
                columns: el.columns || 0,
                confidence: typeof el.confidence === 'number' ? el.confidence : 0,
                bbox: el.bbox || null,
            }));
        }
    }

    if (extractedTables.length === 0) {
        contentTableList.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No tables extracted</div>';
        return;
    }

    // Store tables data globally for navigation
    window.currentTables = extractedTables.map((table, idx) => ({
        id: table.id || `table_${idx + 1}`,
        data: table.data || [],
        html: table.html || null,
        html_structure: table.html_structure || null,
        page: table.page || table.page_number || '?',
        rows: table.rows || 0,
        columns: table.columns || 0,
        confidence: table.confidence || 0
    }));

    window.currentTableIndex = 0;

    let html = '';
    if (window.currentTables.length > 1) {
        html += '<div class="table-navigation" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding: 12px; background: var(--bg-tertiary); border-radius: var(--radius-md);">';
        html += '<button class="table-nav-btn" id="contentPrevTableBtn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast);">';
        html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        html += 'Previous</button>';
        html += `<span style="color: var(--text-primary); font-weight: 500;">Table <span id="contentCurrentTableIndex">1</span> of ${window.currentTables.length}</span>`;
        html += '<button class="table-nav-btn" id="contentNextTableBtn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast);">';
        html += 'Next<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="9 18 15 12 9 6"></polyline></svg></button>';
        html += '</div>';
    }

    html += renderTableCard(window.currentTables[0], 0, window.currentTables.length);
    contentTableList.innerHTML = html;

    // Add navigation event listeners
    if (window.currentTables.length > 1) {
        const prevBtn = document.getElementById('contentPrevTableBtn');
        const nextBtn = document.getElementById('contentNextTableBtn');
        const currentIndexSpan = document.getElementById('contentCurrentTableIndex');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (window.currentTableIndex > 0) {
                    window.currentTableIndex--;
                    currentIndexSpan.textContent = window.currentTableIndex + 1;
                    const tableCard = contentTableList.querySelector('.table-card');
                    if (tableCard) {
                        tableCard.outerHTML = renderTableCard(window.currentTables[window.currentTableIndex], window.currentTableIndex, window.currentTables.length);
                    }
                    updateContentNavButtons();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (window.currentTableIndex < window.currentTables.length - 1) {
                    window.currentTableIndex++;
                    currentIndexSpan.textContent = window.currentTableIndex + 1;
                    const tableCard = contentTableList.querySelector('.table-card');
                    if (tableCard) {
                        tableCard.outerHTML = renderTableCard(window.currentTables[window.currentTableIndex], window.currentTableIndex, window.currentTables.length);
                    }
                    updateContentNavButtons();
                }
            });
        }

        function updateContentNavButtons() {
            if (prevBtn) {
                prevBtn.disabled = window.currentTableIndex === 0;
                prevBtn.style.opacity = window.currentTableIndex === 0 ? '0.5' : '1';
                prevBtn.style.cursor = window.currentTableIndex === 0 ? 'not-allowed' : 'pointer';
            }
            if (nextBtn) {
                nextBtn.disabled = window.currentTableIndex === window.currentTables.length - 1;
                nextBtn.style.opacity = window.currentTableIndex === window.currentTables.length - 1 ? '0.5' : '1';
                nextBtn.style.cursor = window.currentTableIndex === window.currentTables.length - 1 ? 'not-allowed' : 'pointer';
            }
        }

        updateContentNavButtons();
    }
}

/**
 * Update Content Figures view
 */
function updateContentFigures(result) {
    const contentFiguresList = document.getElementById('contentFiguresList');
    if (!contentFiguresList) return;

    const layout = result.layout || {};
    const elements = layout.elements || [];
    const figures = elements.filter(el => el.type === 'figure' || el.type === 'figure_caption');

    if (figures.length === 0) {
        contentFiguresList.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No figures detected</div>';
        return;
    }

    let html = '';
    figures.forEach((figure, index) => {
        html += '<div class="figure-card">';
        html += '<div class="figure-card-header">';
        html += `<span class="figure-name">Figure ${index + 1}${figure.page ? ` (Page ${figure.page})` : ''}</span>`;
        if (figure.confidence !== undefined) {
            html += `<span style="font-size: 0.75rem; color: var(--text-tertiary);">Confidence: ${(figure.confidence * 100).toFixed(1)}%</span>`;
        }
        html += '</div>';
        html += '<div class="figure-preview">';
        if (figure.text) {
            html += `<p style="color: var(--text-secondary); font-style: italic;">${escapeHtml(normalizeTextForDisplay(figure.text))}</p>`;
        } else {
            html += '<p style="color: var(--text-tertiary);">Figure detected (no caption available)</p>';
        }
        html += '</div>';
        html += '</div>';
    });

    contentFiguresList.innerHTML = html;
}

/**
 * Show or hide the Formulas/Seals sub-tabs based on enhancement checkbox state.
 * @param {boolean} enableFormula
 * @param {boolean} enableSeal
 */
function updateEnhancementTabs(enableFormula, enableSeal) {
    const tabFormulas = document.getElementById('tabBtnFormulas');
    const tabSeals = document.getElementById('tabBtnSeals');
    if (tabFormulas) tabFormulas.classList.toggle('hidden', !enableFormula);
    if (tabSeals) tabSeals.classList.toggle('hidden', !enableSeal);
}

/**
 * Render Formulas tab content from view.formulas[].
 * @param {Array} formulas  - view.formulas from the result envelope
 */
function updateContentFormulas(formulas) {
    const list = document.getElementById('contentFormulasList');
    if (!list) return;

    const items = Array.isArray(formulas) ? formulas : [];
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No formulas detected</div>';
        return;
    }

    let html = '';
    items.forEach((formula, index) => {
        const latex = formula.payload && formula.payload.latex ? formula.payload.latex : null;
        const status = formula.processing_status || '';
        html += '<div class="formula-item">';
        html += `<div class="formula-item-header"><span class="formula-name">Formula ${index + 1}</span>`;
        html += `<span class="formula-status">${escapeHtml(status)}</span></div>`;
        html += '<div class="formula-item-body">';
        if (latex) {
            try {
                html += `<div class="formula-rendered">${katex.renderToString(latex, { throwOnError: false, displayMode: true })}</div>`;
                html += `<div class="formula-latex"><code>${escapeHtml(latex)}</code></div>`;
            } catch (e) {
                html += `<div class="formula-latex"><code>${escapeHtml(latex)}</code></div>`;
            }
        } else {
            html += '<p class="formula-placeholder">Formula region detected — recognition pending</p>';
        }
        html += '</div></div>';
    });

    list.innerHTML = html;
}

/**
 * Render Seals tab content from view.seals[].
 * @param {Array} seals  - view.seals from the result envelope
 */
function updateContentSeals(seals) {
    const list = document.getElementById('contentSealsList');
    if (!list) return;

    const items = Array.isArray(seals) ? seals : [];
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No seals detected</div>';
        return;
    }

    let html = '';
    items.forEach((seal, index) => {
        const text = seal.payload && seal.payload.text_on_seal ? seal.payload.text_on_seal : null;
        const status = seal.processing_status || '';
        html += '<div class="seal-item">';
        html += `<div class="seal-item-header"><span class="seal-name">Seal ${index + 1}</span>`;
        html += `<span class="seal-status">${escapeHtml(status)}</span></div>`;
        html += '<div class="seal-item-body">';
        if (text) {
            html += `<p class="seal-text">${escapeHtml(text)}</p>`;
        } else {
            html += '<p class="seal-placeholder">Seal region detected — recognition pending</p>';
        }
        html += '</div></div>';
    });

    list.innerHTML = html;
}

/**
 * Update Result JSON view
 */
function updateResultJson(result) {
    const jsonCode = document.getElementById('jsonCode');
    if (!jsonCode) return;

    try {
        // Format JSON with indentation (similar to Azure format)
        const formattedJson = JSON.stringify(result, null, 2);
        jsonCode.textContent = formattedJson;
    } catch (e) {
        jsonCode.textContent = 'Error formatting JSON: ' + e.message;
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(100px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }

    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100px);
        }
    }

    @keyframes fadeOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(-20px);
        }
    }

    .queue-item.failed .queue-item-icon {
        color: #f43f5e;
    }

    .option-badge.new {
        background: linear-gradient(135deg, #06b6d4, #0891b2);
    }
`;
document.head.appendChild(style);

/**
 * Adjust document size to fit container - show full page without scrollbar
 */
function adjustDocumentSize() {
    const documentImage = document.getElementById('documentImage');
    const previewContainer = document.querySelector('.preview-container');
    const documentPage = document.getElementById('documentPage');
    const documentPreviewContent = document.querySelector('.document-preview-content');

    if (!previewContainer) return;

    // Calculate available space (account for padding: 8px on each side = 16px total)
    const containerWidth = previewContainer.clientWidth - 16;
    const containerHeight = previewContainer.clientHeight - 16;

    // Ensure container dimensions are valid
    if (containerWidth <= 0 || containerHeight <= 0) {
        setTimeout(adjustDocumentSize, 100);
        return;
    }

    if (documentImage) {
        // Adjust image size to fit container exactly
        // Use natural dimensions if available, otherwise wait for image to load
        if (documentImage.complete && documentImage.naturalWidth > 0) {
            const imgWidth = documentImage.naturalWidth;
            const imgHeight = documentImage.naturalHeight;

            // Calculate scale to fit container (maintain aspect ratio)
            const scaleX = containerWidth / imgWidth;
            const scaleY = containerHeight / imgHeight;
            const scale = Math.min(scaleX, scaleY); // Fit to container, can scale down

            const displayWidth = imgWidth * scale;
            const displayHeight = imgHeight * scale;

            // Set image size to fit exactly within container
            documentImage.style.width = `${displayWidth}px`;
            documentImage.style.height = `${displayHeight}px`;
            documentImage.style.maxWidth = `${containerWidth}px`;
            documentImage.style.maxHeight = `${containerHeight}px`;
            documentImage.style.objectFit = 'contain';
            documentImage.style.display = 'block';

            // Set container sizes to match image size (not container size) to eliminate whitespace
            if (documentPage) {
                documentPage.style.width = `${displayWidth}px`;
                documentPage.style.height = `${displayHeight}px`;
                documentPage.style.maxWidth = `${containerWidth}px`;
                documentPage.style.maxHeight = `${containerHeight}px`;
                documentPage.style.overflow = 'hidden';
            }

            if (documentPreviewContent) {
                documentPreviewContent.style.width = `${displayWidth}px`;
                documentPreviewContent.style.height = `${displayHeight}px`;
                documentPreviewContent.style.maxWidth = `${containerWidth}px`;
                documentPreviewContent.style.maxHeight = `${containerHeight}px`;
                documentPreviewContent.style.overflow = 'hidden';
            }
        } else {
            // Image not loaded yet, wait for it
            const img = new Image();
            img.onload = function() {
                const imgWidth = this.naturalWidth || this.width;
                const imgHeight = this.naturalHeight || this.height;

                if (imgWidth <= 0 || imgHeight <= 0) return;

                // Calculate scale to fit container (maintain aspect ratio)
                const scaleX = containerWidth / imgWidth;
                const scaleY = containerHeight / imgHeight;
                const scale = Math.min(scaleX, scaleY); // Fit to container, can scale down

                const displayWidth = imgWidth * scale;
                const displayHeight = imgHeight * scale;

                // Set image size to fit exactly within container
                documentImage.style.width = `${displayWidth}px`;
                documentImage.style.height = `${displayHeight}px`;
                documentImage.style.maxWidth = `${containerWidth}px`;
                documentImage.style.maxHeight = `${containerHeight}px`;
                documentImage.style.objectFit = 'contain';
                documentImage.style.display = 'block';

                // Set container sizes to match image size (not container size) to eliminate whitespace
                if (documentPage) {
                    documentPage.style.width = `${displayWidth}px`;
                    documentPage.style.height = `${displayHeight}px`;
                    documentPage.style.maxWidth = `${containerWidth}px`;
                    documentPage.style.maxHeight = `${containerHeight}px`;
                    documentPage.style.overflow = 'hidden';
                }

                if (documentPreviewContent) {
                    documentPreviewContent.style.width = `${displayWidth}px`;
                    documentPreviewContent.style.height = `${displayHeight}px`;
                    documentPreviewContent.style.maxWidth = `${containerWidth}px`;
                    documentPreviewContent.style.maxHeight = `${containerHeight}px`;
                    documentPreviewContent.style.overflow = 'hidden';
                }
            };
            img.src = documentImage.src;
        }
    }
}

// Adjust document size on window resize
window.addEventListener('resize', () => {
    setTimeout(adjustDocumentSize, 100);
});

/**
 * Load and display unified layout analysis with canvas annotation
 */
async function loadUnifiedLayoutAnalysis() {
    try {
        if (!currentTaskId) {
            console.log('[Layout] No task ID available for layout analysis');
            return;
        }

        console.log(`[Layout] Fetching unified layout analysis for task: ${currentTaskId}`);

        // Fetch unified layout analysis
        const response = await fetch(`${API_BASE_URL}/tasks/${currentTaskId}/layout`);
        if (!response.ok) {
            console.error(`[Layout] ❌ Failed to fetch: ${response.status} ${response.statusText}`);
            try {
                const errText = await response.text();
                console.error('[Layout] Error response:', errText);
            } catch (e) {}
            return;
        }

        const layoutResult = await response.json();
        console.log('[Layout] Response received:', layoutResult);

        // Validate response structure
        if (!layoutResult) {
            console.error('[Layout] ❌ Empty layout result');
            return;
        }

        if (!layoutResult.elements || !Array.isArray(layoutResult.elements)) {
            console.warn('[Layout] ⚠️ Invalid layout result structure: no elements array');
            console.log('[Layout] Response structure:', Object.keys(layoutResult));
            return;
        }

        if (layoutResult.elements.length === 0) {
            console.log('[Layout] No layout elements in result (empty layout)');
            return;
        }

        console.log(`[Layout] ✓ Found ${layoutResult.elements.length} layout elements`);

        // Wait for documentImage to be ready
        console.log('[Layout] Waiting for image element...');
        let documentImage = document.getElementById('documentImage');

        if (!documentImage) {
            // Wait up to 3 seconds for image to appear
            console.log('[Layout] Image not found immediately, waiting...');
            for (let i = 0; i < 30; i++) {
                await new Promise(r => setTimeout(r, 100));
                documentImage = document.getElementById('documentImage');
                if (documentImage) {
                    console.log('[Layout] ✓ Image element found');
                    break;
                }
            }
        }

        if (!documentImage) {
            console.error('[Layout] ❌ Document image element not found after waiting');
            return;
        }

        // Wait for image to load
        if (!documentImage.complete || !documentImage.naturalWidth) {
            console.log('[Layout] Image not loaded yet, waiting for load event...');
            await new Promise((resolve) => {
                if (documentImage.complete && documentImage.naturalWidth > 0) {
                    resolve();
                } else {
                    documentImage.onload = () => {
                        console.log('[Layout] ✓ Image loaded');
                        resolve();
                    };
                    documentImage.onerror = () => {
                        console.error('[Layout] ❌ Image failed to load');
                        resolve();
                    };
                }
            });
        } else {
            console.log(`[Layout] ✓ Image already loaded: ${documentImage.naturalWidth}x${documentImage.naturalHeight}`);
        }

        if (!documentImage.naturalWidth || !documentImage.naturalHeight) {
            console.error('[Layout] ❌ Image has invalid dimensions');
            return;
        }

        // Create canvas overlay if it doesn't exist
        console.log('[Layout] Setting up canvas overlay...');
        let canvas = document.getElementById('layoutAnnotationCanvas');
        if (!canvas) {
            const documentPage = document.getElementById('documentPage');
            if (!documentPage) {
                console.error('[Layout] ❌ Document page container not found');
                return;
            }

            console.log('[Layout] Creating canvas wrapper...');

            // Get or create wrapper
            let wrapper = documentPage.querySelector('.canvas-wrapper');
            if (!wrapper) {
                wrapper = document.createElement('div');
                wrapper.className = 'canvas-wrapper';
                wrapper.style.cssText = `
                    position: relative;
                    display: inline-block;
                    width: 100%;
                    max-width: 100%;
                `;

                // Move image into wrapper if not already there
                if (documentImage.parentElement !== wrapper) {
                    const originalParent = documentImage.parentElement;
                    originalParent.insertBefore(wrapper, documentImage);
                    wrapper.appendChild(documentImage);
                }
            }

            console.log('[Layout] Creating canvas element...');
            canvas = document.createElement('canvas');
            canvas.id = 'layoutAnnotationCanvas';
            canvas.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                z-index: 100;
                cursor: crosshair;
                display: block;
            `;
            wrapper.appendChild(canvas);
        }

        if (!canvas) {
            console.error('[Layout] ❌ Failed to create canvas for annotations');
            return;
        }

        console.log('[Layout] ✓ Canvas element ready:', canvas.id);

        // Initialize the LayoutAnnotator (defensive)
        console.log('[Layout] Initializing LayoutAnnotator...');
        let annotator = null;
        try {
            annotator = new LayoutAnnotator('layoutAnnotationCanvas', 'documentImage', {
                drawBbox: true,
                showLabels: true,
                showConfidence: true,
                highlightHover: true,
                enableInteraction: true,
                labelOffset: 12,
                borderWidth: 2
            });
            console.log('[Layout] ✓ LayoutAnnotator created');
        } catch (e) {
            console.error('[Layout] Failed to create LayoutAnnotator:', e);
            return;
        }

        // Resize canvas to match image with a small delay (defensive)
        console.log('[Layout] Resizing canvas...');
        setTimeout(() => {
            try {
                if (annotator && typeof annotator.resizeCanvasToImage === 'function') {
                    annotator.resizeCanvasToImage();
                    console.log(`[Layout] ✓ Canvas resized to ${annotator.canvas?.width}x${annotator.canvas?.height} (internal) / ${annotator.canvas?.offsetWidth}x${annotator.canvas?.offsetHeight} (CSS)`);
                }
            } catch (e) {
                console.error('[Layout] Error resizing canvas:', e);
            }
        }, 50);

        // Load the layout analysis result
        console.log('[Layout] Loading layout analysis result...');
        try {
            annotator.loadLayoutAnalysis(layoutResult);
            console.log(`[Layout] ✓ Layout loaded with ${layoutResult.elements.length} elements`);
        } catch (e) {
            console.error('[Layout] Error loading layout into annotator:', e, layoutResult);
        }

        // Create control panel if it doesn't exist
        let controlPanel = document.getElementById('layoutControlPanel');
        if (!controlPanel) {
            console.log('[Layout] Creating control panel...');
            // Find a suitable container for the control panel
            const rightSidebar = document.querySelector('.right-sidebar') ||
                                  document.querySelector('.sidebar-content') ||
                                  document.querySelector('[class*="results"]') ||
                                  document.querySelector('[class*="panel"]');

            if (rightSidebar) {
                controlPanel = document.createElement('div');
                controlPanel.id = 'layoutControlPanel';
                controlPanel.style.cssText = `
                    padding: 15px;
                    border-top: 1px solid #e5e7eb;
                    overflow-y: auto;
                    max-height: 300px;
                `;

                // Try to insert at the beginning or end of the sidebar
                if (rightSidebar.firstChild) {
                    rightSidebar.insertBefore(controlPanel, rightSidebar.firstChild);
                } else {
                    rightSidebar.appendChild(controlPanel);
                }

                // Initialize control panel
                new LayoutControlPanel('layoutControlPanel', annotator);
                console.log('[Layout] ✓ Control panel initialized');
            } else {
                console.warn('[Layout] ⚠️ Right sidebar not found, control panel not created');
            }
        } else {
            console.log('[Layout] Control panel already exists');
        }

        // Listen for element selection events
        canvas.addEventListener('elementSelected', (e) => {
            const element = e.detail;
            console.log('[Layout] Element selected:', element);
        });

        console.log('[Layout] ✅ Unified Layout Analysis initialized successfully!');

    } catch (error) {
        console.error('[Layout] ❌ Error loading unified layout analysis:', error);
        console.error('[Layout] Stack:', error.stack);
    }
}

