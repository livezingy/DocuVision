/**
 * DocuVision - Intelligent Document Processing System
 * Frontend Interaction Script
 */

// --- v1.8.3 B0b: extracted pure helpers (see frontend/modules/utils/) ---
import {
    normalizeAnnotationBbox,
    bboxFromPolygon,
    normalizeCoordSpace,
    normalizeBboxToImageMatrix,
    remapBboxToImageSpace,
} from './modules/utils/geometry.js';
import {
    convertToCSV,
    convertToMarkdown,
    tableConfidencePct,
    formatTableCsvBanner,
    excelSafeCell,
    escapeCsvCell,
    buildSingleTableCsv,
    singleTableCsvFilename,
} from './modules/utils/csv.js';
import {
    formatAzureRoleLabel,
    normalizeTextForDisplay,
    normalizePanelParagraphText,
    isLikelyCollapsedText,
    toAzureTypeLabel,
} from './modules/utils/text.js';
import { escapeHtml } from './modules/utils/dom.js';
// --- v1.8.3 B1a: API constants moved to modules/api-config.js (leaf service) ---
import { API_BASE_URL, API_ROOT_URL, HEALTH_URL, ENGINES_URL } from './modules/api-config.js';
// --- v1.8.3 B2 prep: KIE / table-mapping constants moved to modules/kie-config.js ---
import {
    KIE_DOC_TYPES, KIE_FIELD_NAME_RE, TABLE_MAPPING_MODE, TABLE_MAPPING_ELIGIBLE,
    TABLE_MAPPING_IMAGE_EXTENSIONS,
} from './modules/kie-config.js';
// --- v1.8.3 B1a: shared preview/result state lives in modules/preview-state.js; reads stay
// byte-identical through live bindings, writes go through the setters below ---
import {
    // reads: live bindings, every read expression stays byte-identical
    currentOriginalFileUrl, currentTaskId, currentQueueItem, currentPreviewPage,
    currentPageImageUrl, previewPaginationInitialized, lastRenderedAnalysisResult,
    lastFetchedBlocks,
    // writes: the only channel, module code cannot assign to an imported binding
    setOriginalFileUrl, setTaskId, setQueueItem, setPreviewPage, setPageImageUrl,
    setPreviewPaginationInitialized, setLastRenderedAnalysisResult, setLastFetchedBlocks,
    resetPreviewState,
} from './modules/preview-state.js';
// --- v1.8.3 B1b: extracted leaf services + shared api state ---
import { updateStatusBar, updateStatusBarThrottled } from './modules/status-bar.js';
import { showNotification } from './modules/notifications.js';
import { lastHealthPayload } from './modules/api-state.js';
import {
    initializeAPIConnection, checkApiReachable, applyHealthToFooter, refreshActiveEngineFooterLine,
} from './modules/api-base.js';
import { bindTableCardCsvExport } from './modules/export-csv.js';
import { initBatchProcessing } from './modules/batch.js';
import { initHitlReviews, refreshHitlReviews } from './modules/hitl-review.js';
import {
    initAnalysisOptionsDialog, openAnalysisOptionsDialog, getProcessingOptions,
    getSelectedProcessingMode, setSyncProcessingModeUI,
} from './modules/options-dialog.js';
import {
    initKieMapping, clearTableMappingEligibility, updateTableMappingEligibility,
    fetchDocumentProfileForQueueItem, updateDocumentTypeSuggestion, isTableMappingRunBlocked,
    updateKieQueryFieldsAvailability, buildKieQueryFieldsPayload, updateContentFields,
} from './modules/kie-mapping.js';
import {
    initOverlayRender, renderDocumentWithAnnotations, renderTextPreview, highlightResultItem,
} from './modules/overlay-render.js';
import { renderQualityPanelPro, updateContentMappedRows } from './modules/result-panels/quality.js';
import { updateContentText } from './modules/result-panels/text.js';
import { initResultPanelsTables, updateContentTables } from './modules/result-panels/tables.js';
import { initResultPanelsFigures, updateContentFigures } from './modules/result-panels/figures.js';
import { updateEnhancementTabs, updateContentFormulas, updateContentSeals } from './modules/result-panels/enhance.js';
import { updateResultJson } from './modules/result-panels/json.js';
import { updateDemoTransactionViews } from './modules/result-panels/demo-transaction.js';

// --- v1.8.3 B2: D6 <-> D7 cycle wired at module scope (before any runtime call) ---
initKieMapping({ getSelectedProcessingMode });

// --- v1.8.3 B3: D10 overlay deps (D5/D8/D9/D4 still live here; B4 re-points the D5/D8
// wiring to the preview-nav.js / preview-render.js / pipeline-result.js exports) ---
initOverlayRender({
    previewHelpers, resolveResultPageCount, syncPreviewPaginationControls,
    revokeCurrentPageImageUrl, getPdfPageImage, adjustDocumentSize,
    fetchTaskBlocks, updateContentText, initAnnotationInteractions,
});

// --- v1.8.3 B3: result-panels cross-domain deps (D5/D12 still live here; B4 re-points
// fetchAuthedImage to preview-render.js, D12 is already extracted) ---
initResultPanelsTables({ bindTableCardCsvExport });
initResultPanelsFigures({ fetchAuthedImage });

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
    initAnalysisOptionsDialog({ clearTableMappingEligibility, updateKieQueryFieldsAvailability, buildKieQueryFieldsPayload, updateEnhancementTabs });
    initEngineSelectors();
    initAnalysisView();
    initExportButtons();
    initBatchProcessing({ getProcessingOptions });
    initHitlReviews();
    initPdfTools();
    initPreviewPagination();

    // Insert a lightweight skeleton placeholder to avoid initial flash
    if (typeof insertInitialSkeleton === 'function') {
        insertInitialSkeleton();
    }
});



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
    const processView = document.getElementById('processMainView');
    const batchView = document.getElementById('batchMainView');
    const reviewsView = document.getElementById('reviewsMainView');
    const pdfToolsView = document.getElementById('pdfToolsMainView');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.disabled) return;
            navTabs.forEach(t => {
                if (!t.disabled) t.classList.remove('active');
            });
            tab.classList.add('active');

            const tabName = tab.dataset.tab;
            if (processView && batchView) {
                processView.classList.add('hidden');
                batchView.classList.add('hidden');
                if (reviewsView) reviewsView.classList.add('hidden');
                if (pdfToolsView) pdfToolsView.classList.add('hidden');
                if (tabName === 'batch') {
                    batchView.classList.remove('hidden');
                } else if (tabName === 'reviews') {
                    if (reviewsView) reviewsView.classList.remove('hidden');
                    refreshHitlReviews();
                } else if (tabName === 'pdftools') {
                    if (pdfToolsView) pdfToolsView.classList.remove('hidden');
                } else {
                    processView.classList.remove('hidden');
                }
            }
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
        const selectedMode = document.querySelector('input[name="processingMode"]:checked')?.value || 'layout';
        const isLayout = selectedMode === 'layout';
        const isTableMapping = selectedMode === TABLE_MAPPING_MODE;

        if (layoutSubOptions) {
            layoutSubOptions.classList.toggle('hidden', !isLayout);
            layoutSubOptions.classList.remove('sub-options-dimmed');
        }

        const tableMappingSubOptions = document.getElementById('tableMappingSubOptions');
        if (tableMappingSubOptions) {
            tableMappingSubOptions.classList.toggle('hidden', !isTableMapping);
        }

        const enginesLayoutSection = document.getElementById('enginesLayoutSection');
        if (enginesLayoutSection) {
            enginesLayoutSection.classList.toggle('sub-options-dimmed', isTableMapping);
        }

        const kieNote = document.getElementById('kieNote');
        if (kieNote) kieNote.classList.toggle('hidden', isLayout || isTableMapping);

        if (isLayout) {
            updateEnhancementTabs(
                optEnableFormula ? optEnableFormula.checked : false,
                optEnableSeal ? optEnableSeal.checked : false
            );
        } else {
            updateEnhancementTabs(false, false);
        }

        if (isTableMapping) {
            updateTableMappingEligibility(currentQueueItem);
        } else {
            clearTableMappingEligibility();
        }

        updateKieQueryFieldsAvailability();
    };

    processingModeRadios.forEach(radio => radio.addEventListener('change', syncModeUI));
    setSyncProcessingModeUI(syncModeUI);
    syncModeUI();
    updateKieQueryFieldsAvailability();

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

    if (window.DocuVisionUiFeatures) {
        DocuVisionUiFeatures.applyContentTabFeatures();
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

function previewHelpers() {
    return window.DocuVisionPreview || {};
}

function resolveResultPageCount(result, queueItem = null) {
    const previewCount = queueItem && queueItem.previewPageCount ? Number(queueItem.previewPageCount) : 0;
    const fn = previewHelpers().resolveDocumentPageCount;
    if (typeof fn === 'function') {
        return fn(result, previewCount);
    }
    const pages = Number((result && result.document_info && result.document_info.pages) || previewCount || 1);
    return pages > 0 ? pages : 1;
}

function syncPreviewPaginationControls(totalPages, pageNum = currentPreviewPage) {
    const total = Math.max(1, Number(totalPages) || 1);
    const normalize = previewHelpers().normalizePreviewPage;
    const page = typeof normalize === 'function' ? normalize(pageNum, total) : Math.min(Math.max(1, pageNum), total);
    setPreviewPage(page);

    const pageInput = document.querySelector('.page-input');
    const pageTotal = document.querySelector('.page-total');
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');

    if (pageInput) {
        pageInput.min = 1;
        pageInput.max = total;
        pageInput.value = page;
    }
    if (pageTotal) {
        pageTotal.textContent = ` / ${total}`;
    }
    if (prevBtn) {
        prevBtn.disabled = page <= 1;
    }
    if (nextBtn) {
        nextBtn.disabled = page >= total;
    }
}

function revokeCurrentPageImageUrl() {
    if (currentPageImageUrl) {
        URL.revokeObjectURL(currentPageImageUrl);
        setPageImageUrl(null);
    }
}

async function goToPreviewPage(pageNum) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    let totalPages = 1;
    const resultJson = documentPage.dataset.currentResult;
    if (resultJson) {
        try {
            const result = JSON.parse(resultJson);
            totalPages = resolveResultPageCount(result, currentQueueItem);
        } catch (e) {
            totalPages = resolveResultPageCount(null, currentQueueItem);
        }
    } else {
        totalPages = resolveResultPageCount(null, currentQueueItem);
    }

    const normalize = previewHelpers().normalizePreviewPage;
    const page = typeof normalize === 'function'
        ? normalize(pageNum, totalPages)
        : Math.min(Math.max(1, pageNum), totalPages);

    syncPreviewPaginationControls(totalPages, page);

    const fileName = documentPage.dataset.currentFileName
        || (currentQueueItem && currentQueueItem.dataset.fileName)
        || '';
    const fileExt = fileName.toLowerCase().split('.').pop();
    const isPdf = fileExt === 'pdf';

    if (resultJson && currentTaskId) {
        try {
            const result = JSON.parse(resultJson);
            await renderDocumentWithAnnotations(result, page);
            return;
        } catch (e) {
            console.warn('[Preview] Failed to parse stored result for page switch:', e);
        }
    }

    if (isPdf && currentTaskId) {
        const documentImage = document.getElementById('documentImage');
        try {
            revokeCurrentPageImageUrl();
            setPageImageUrl(await getPdfPageImage(currentTaskId, page));
            if (documentImage) {
                documentImage.src = currentPageImageUrl;
            } else {
                let html = '<div class="document-preview-content">';
                html += `<img id="documentImage" src="${currentPageImageUrl}" style="width: auto; height: auto; object-fit: contain; border: none; border-radius: 8px; display: block;" alt="Document" onload="adjustDocumentSize()">`;
                html += '</div>';
                documentPage.innerHTML = html;
            }
            setTimeout(() => adjustDocumentSize(), 100);
        } catch (error) {
            console.error('Failed to load PDF page:', error);
            showNotification('Failed to load PDF page preview', 'warning');
        }
        return;
    }

    if (!isPdf && currentOriginalFileUrl) {
        syncPreviewPaginationControls(1, 1);
    }
}

function initPreviewPagination() {
    if (previewPaginationInitialized) return;
    setPreviewPaginationInitialized(true);

    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    const pageInput = document.querySelector('.page-input');

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            void goToPreviewPage(currentPreviewPage - 1);
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            void goToPreviewPage(currentPreviewPage + 1);
        });
    }
    if (pageInput) {
        pageInput.addEventListener('change', () => {
            void goToPreviewPage(Number(pageInput.value) || 1);
        });
    }
}

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
        const pageCount = Number(result.page_count) || 0;

        // Store taskId
        setTaskId(taskId);
        if (queueItem) {
            queueItem.dataset.taskId = taskId;
            if (pageCount > 0) {
                queueItem.previewPageCount = pageCount;
                syncPreviewPaginationControls(pageCount, 1);
            }
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
    setQueueItem(queueItem);

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
    setOriginalFileUrl(URL.createObjectURL(file));
    setTaskId(taskId || null);
    setPreviewPage(1);
    setLastFetchedBlocks(null);

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
            setTaskId(newTaskId);
            await updatePreviewView('original');
        }).catch((error) => {
            console.error('Failed to upload file for preview:', error);
            if (documentPage) {
                documentPage.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: #6b7280;"><p style="margin-bottom: 8px; color: #f43f5e;">⚠️ Preview unavailable</p><p style="font-size: 0.875rem; color: #94a3b8;">PDF uploaded but preview failed.</p></div>';
            }
        });
    } else if (queueItem.result) {
        // Completed item: render once (avoids racing updatePreviewView vs renderDocumentWithAnnotations on PDF page-image).
        syncPreviewPaginationControls(resolveResultPageCount(queueItem.result, queueItem), 1);
        await updateResultsDisplay(queueItem.result);
    } else {
        const previewPages = resolveResultPageCount(null, queueItem);
        syncPreviewPaginationControls(previewPages, 1);
        await updatePreviewView('original');
    }

    updateTableMappingEligibility(queueItem);
    updateDocumentTypeSuggestion(queueItem);
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

                        const previewPages = resolveResultPageCount(null, currentQueueItem);
                        syncPreviewPaginationControls(previewPages, currentPreviewPage);

                        let html = '<div class="document-preview-content">';
                        revokeCurrentPageImageUrl();
                        setPageImageUrl(await getPdfPageImage(currentTaskId, currentPreviewPage));
                        html += `<img id="documentImage" src="${currentPageImageUrl}" style="width: auto; height: auto; object-fit: contain; border: none; border-radius: 8px; display: block;" alt="Document" onload="adjustDocumentSize()" onerror="this.parentElement.innerHTML=\'<div class=\\\'empty-state\\\' style=\\\'padding: 40px; text-align: center; color: #f43f5e;\\\'>Failed to load PDF image. Please try again.</div>\'">`;
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
                    syncPreviewPaginationControls(1, 1);
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
                'ppstructure': 'PP-StructureV3'
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
    DocuVisionExport.init({
        getJobId: () => currentTaskId,
        buildUrl: (jobId, apiFormat) => `${API_BASE_URL}/tasks/${jobId}/export/${apiFormat}`,
        notify: showNotification,
        supportsAzure: true,
    });
}


/**
 * Reset a completed/cancelled/failed queue item so Run Analysis can process it again.
 * @param {HTMLElement} item
 * @returns {boolean}
 */
function resetQueueItemForReprocessing(item) {
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
 * Start processing
 */
async function startProcessing() {
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
async function fetchTaskBlocks(taskId, pageNumber = 1) {
    try {
        const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/blocks?page_number=${pageNumber}`);
        if (!response.ok) return null;
        return await response.json();
    } catch (e) {
        console.warn('[Blocks] Failed to fetch blocks:', e);
        return null;
    }
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
    const pageCount = resolveResultPageCount(result, item);
    item.previewPageCount = pageCount;
    const formatStatus = previewHelpers().formatCompletedStatus;
    status.textContent = typeof formatStatus === 'function'
        ? formatStatus(pageCount)
        : `Completed · ${pageCount} page${pageCount !== 1 ? 's' : ''}`;

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

    // After finishing, start the next queued or pending item
    processNextInQueue();
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
 * Start the next queued or pending queue item after the current job finishes.
 */
function processNextInQueue() {
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
 * Update results display with actual data
 */
async function updateResultsDisplay(result) {
    if (!result) return;

    setLastRenderedAnalysisResult(result);

    // Reset cached blocks so the SVG overlay fetches fresh data.
    setLastFetchedBlocks(null);

    // Update document preview
    await updateDocumentPreview(result);

    // Update Content views
    updateContentText(result);
    updateContentTables(result);
    updateContentMappedRows(result);
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
 * Update document preview
 */
async function updateDocumentPreview(result) {
    const documentPage = document.getElementById('documentPage');
    if (!documentPage) return;

    const docInfo = result.document_info || {};
    const fileName = docInfo.file_name || 'Document';
    const pages = resolveResultPageCount(result, currentQueueItem);

    syncPreviewPaginationControls(pages, currentPreviewPage);

    // Store current result for preview switching
    documentPage.dataset.currentResult = JSON.stringify(result);


    // Always prioritize showing source image when available.
    // Annotation data may come from layout, OCR, or table-only paths.
    if (currentOriginalFileUrl) {
        await renderDocumentWithAnnotations(result, currentPreviewPage);
    } else {
        // Fallback to text preview only when source image is unavailable.
        renderTextPreview(result);
    }
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
                const readingOrderLine = d.readingOrder
                    ? `<div class="tooltip-line"><strong>Reading order:</strong> ${d.readingOrder}</div>`
                    : '';
                globalTooltip.innerHTML = `
                    <div class="tooltip-line"><strong>Role:</strong> ${esc(d.role)}</div>
                    <div class="tooltip-line"><strong>BBox:</strong> ${esc(d.bbox)}</div>
                    <div class="tooltip-line"><strong>Content:</strong> ${d.displayContent ? esc(d.displayContent) : '(empty)'}</div>
                    <div class="tooltip-line"><strong>Confidence:</strong> ${Number(d.confidence || 0).toFixed(1)}%</div>
                    ${readingOrderLine}
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
    // Start next queued or pending item if any
    processNextInQueue();
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
 * Fetch an image URL through the trial-key auth bridge and return an object
 * URL. Falls back to the raw URL on any error so a missing key still shows
 * a broken-image placeholder rather than throwing. The object URL is
 * revoked after the <img> errors or after a generous TTL.
 */
function fetchAuthedImage(url, imgEl) {
    if (!url) return Promise.resolve(null);
    return fetch(url)
        .then(function (res) {
            if (!res.ok) return null;
            return res.blob();
        })
        .then(function (blob) {
            if (!blob) return null;
            const objUrl = URL.createObjectURL(blob);
            if (imgEl) {
                imgEl.dataset.objUrl = objUrl;
                imgEl.addEventListener('error', function () {
                    if (imgEl.dataset.objUrl) {
                        URL.revokeObjectURL(imgEl.dataset.objUrl);
                        delete imgEl.dataset.objUrl;
                    }
                }, { once: true });
            }
            return objUrl;
        })
        .catch(function () { return null; });
}

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



function initPdfTools() {
    const mergeInput = document.getElementById('pdfMergeFileInput');
    const mergeSelectBtn = document.getElementById('pdfMergeSelectBtn');
    const mergeBtn = document.getElementById('pdfMergeBtn');
    const mergeCount = document.getElementById('pdfMergeFileCount');
    const mergeStatus = document.getElementById('pdfMergeStatus');
    let mergeFiles = [];

    if (mergeSelectBtn && mergeInput) {
        mergeSelectBtn.addEventListener('click', () => mergeInput.click());
        mergeInput.addEventListener('change', () => {
            mergeFiles = Array.from(mergeInput.files || []);
            if (mergeCount) {
                mergeCount.textContent = mergeFiles.length
                    ? `${mergeFiles.length} PDF(s) selected`
                    : '';
            }
            if (mergeBtn) mergeBtn.disabled = mergeFiles.length < 2;
        });
    }

    mergeBtn?.addEventListener('click', async () => {
        if (mergeFiles.length < 2) {
            showNotification('Select at least two PDF files', 'warning');
            return;
        }
        try {
            if (mergeStatus) mergeStatus.textContent = 'Merging...';
            const formData = new FormData();
            mergeFiles.forEach(f => formData.append('files', f));
            const response = await fetch(`${API_ROOT_URL}/api/v1/pdf-tools/merge`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'merged.pdf';
            a.click();
            URL.revokeObjectURL(url);
            if (mergeStatus) mergeStatus.textContent = 'Download started: merged.pdf';
            showNotification('PDFs merged', 'success');
        } catch (error) {
            if (mergeStatus) mergeStatus.textContent = '';
            showNotification(`Merge failed: ${error.message}`, 'error');
        }
    });

    const metaInput = document.getElementById('pdfMetaFileInput');
    const metaSelectBtn = document.getElementById('pdfMetaSelectBtn');
    const metaBtn = document.getElementById('pdfMetaBtn');
    const metaCount = document.getElementById('pdfMetaFileCount');
    const metaResult = document.getElementById('pdfMetaResult');
    let metaFile = null;

    if (metaSelectBtn && metaInput) {
        metaSelectBtn.addEventListener('click', () => metaInput.click());
        metaInput.addEventListener('change', () => {
            metaFile = (metaInput.files && metaInput.files[0]) || null;
            if (metaCount) {
                metaCount.textContent = metaFile ? `1 PDF selected: ${metaFile.name}` : '';
            }
            if (metaBtn) metaBtn.disabled = !metaFile;
        });
    }

    metaBtn?.addEventListener('click', async () => {
        if (!metaFile) return;
        try {
            const formData = new FormData();
            formData.append('file', metaFile);
            const response = await fetch(`${API_ROOT_URL}/api/v1/pdf-tools/metadata`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (metaResult) metaResult.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            if (metaResult) metaResult.textContent = `Failed: ${error.message}`;
        }
    });

    const splitInput = document.getElementById('pdfSplitFileInput');
    const splitSelectBtn = document.getElementById('pdfSplitSelectBtn');
    const splitBtn = document.getElementById('pdfSplitBtn');
    const splitCount = document.getElementById('pdfSplitFileCount');
    const splitPageInput = document.getElementById('pdfSplitPageInput');
    let splitFile = null;

    if (splitSelectBtn && splitInput) {
        splitSelectBtn.addEventListener('click', () => splitInput.click());
        splitInput.addEventListener('change', () => {
            splitFile = (splitInput.files && splitInput.files[0]) || null;
            if (splitCount) {
                splitCount.textContent = splitFile ? `1 PDF selected: ${splitFile.name}` : '';
            }
            if (splitBtn) splitBtn.disabled = !splitFile;
        });
    }

    splitBtn?.addEventListener('click', async () => {
        if (!splitFile) return;
        const pageNum = parseInt(splitPageInput?.value || '1', 10) || 1;
        try {
            const formData = new FormData();
            formData.append('file', splitFile);
            formData.append('pages', JSON.stringify([pageNum]));
            const response = await fetch(`${API_ROOT_URL}/api/v1/pdf-tools/split`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/pdf')) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `page_${pageNum}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
                showNotification('Page downloaded', 'success');
            } else {
                const data = await response.json();
                showNotification(`Split returned ${data.count} page(s) (server paths only)`, 'info');
            }
        } catch (error) {
            showNotification(`Split failed: ${error.message}`, 'error');
        }
    });
}





