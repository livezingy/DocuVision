/**
 * Preview navigation (v1.8.3 B4) - domain module (D5, nav half).
 *
 * D5 is split across preview-nav.js (this file) and preview-render.js because the
 * domain is >500 lines. The two halves call each other (nav -> render: adjustDocumentSize /
 * getPdfPageImage / updatePreviewView; render -> nav: resolveResultPageCount /
 * revokeCurrentPageImageUrl / syncPreviewPaginationControls), and F3 forbids module-to-module
 * imports, so those six same-domain calls are injected from app.js too - exactly like the
 * cross-domain ones. The same-name module-scope binding trick keeps every call site
 * byte-identical.
 */
import { showNotification } from './notifications.js';
import { API_BASE_URL } from './api-config.js';
import {
    currentOriginalFileUrl, currentTaskId, currentQueueItem, currentPreviewPage,
    currentPageImageUrl, previewPaginationInitialized,
    setOriginalFileUrl, setTaskId, setQueueItem, setPreviewPage, setPageImageUrl,
    setPreviewPaginationInitialized, setLastFetchedBlocks, resetPreviewState,
} from './preview-state.js';

// --- cross-domain deps (D7 / D8 / D10), injected at boot ---
let renderDocumentWithAnnotations = async function () {};
let updateTableMappingEligibility = function () {};
let updateDocumentTypeSuggestion = function () {};
let renderResults = async function () {};
// --- same-domain deps from preview-render.js, injected at boot ---
let adjustDocumentSize = function () {};
let getPdfPageImage = async function () { return null; };
let updatePreviewView = async function () {};

/**
 * Wire preview-nav dependencies (app.js assembly).
 */
export function initPreviewNav(deps = {}) {
    if (typeof deps.renderDocumentWithAnnotations === 'function') renderDocumentWithAnnotations = deps.renderDocumentWithAnnotations;
    if (typeof deps.updateTableMappingEligibility === 'function') updateTableMappingEligibility = deps.updateTableMappingEligibility;
    if (typeof deps.updateDocumentTypeSuggestion === 'function') updateDocumentTypeSuggestion = deps.updateDocumentTypeSuggestion;
    if (typeof deps.renderResults === 'function') renderResults = deps.renderResults;
    if (typeof deps.adjustDocumentSize === 'function') adjustDocumentSize = deps.adjustDocumentSize;
    if (typeof deps.getPdfPageImage === 'function') getPdfPageImage = deps.getPdfPageImage;
    if (typeof deps.updatePreviewView === 'function') updatePreviewView = deps.updatePreviewView;
}

/** Clear inline sizing from adjustDocumentSize so the next task is not clipped by the previous layout. */
export function resetDocumentPageLayoutStyles() {
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

export function previewHelpers() {
    return window.DocuVisionPreview || {};
}

export function resolveResultPageCount(result, queueItem = null) {
    const previewCount = queueItem && queueItem.previewPageCount ? Number(queueItem.previewPageCount) : 0;
    const fn = previewHelpers().resolveDocumentPageCount;
    if (typeof fn === 'function') {
        return fn(result, previewCount);
    }
    const pages = Number((result && result.document_info && result.document_info.pages) || previewCount || 1);
    return pages > 0 ? pages : 1;
}

export function syncPreviewPaginationControls(totalPages, pageNum = currentPreviewPage) {
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

export function revokeCurrentPageImageUrl() {
    if (currentPageImageUrl) {
        URL.revokeObjectURL(currentPageImageUrl);
        setPageImageUrl(null);
    }
}

export async function goToPreviewPage(pageNum) {
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

export function initPreviewPagination() {
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
export async function uploadFileForPreview(file, queueItem) {
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
export async function switchToQueueItem(queueItem) {
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
        await renderResults(queueItem.result);
    } else {
        const previewPages = resolveResultPageCount(null, queueItem);
        syncPreviewPaginationControls(previewPages, 1);
        await updatePreviewView('original');
    }

    updateTableMappingEligibility(queueItem);
    updateDocumentTypeSuggestion(queueItem);
}
