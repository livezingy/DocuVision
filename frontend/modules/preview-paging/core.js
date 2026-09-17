/**
 * Preview-paging core (v1.8.3 B-decision) - domain-internal base layer (D5).
 *
 * Holds the paging / page-image hub functions that BOTH halves of D5 depend on
 * (nav: goToPreviewPage/uploadFileForPreview; render: updatePreviewView/
 * updateDocumentPreview). Extracting them here is what makes the split a one-way
 * DAG - nav -> render -> core -> (preview-state / api-config) - with no circular
 * import and therefore no ESM TDZ hazard.
 *
 * These functions are NOT leaf services (they own domain semantics: how page
 * counts resolve, how the pagination controls sync) and are deliberately NOT
 * registered in the F3/F5 whitelist - they are reachable only as same-directory
 * siblings.
 */
import * as DocuVisionPreview from '../../shared/queue_preview.js';
import { API_BASE_URL } from '../api-config.js';
import {
    currentPreviewPage, currentPageImageUrl, setPreviewPage, setPageImageUrl,
} from '../preview-state.js';

export function previewHelpers() {
    // B5a: direct ESM import of shared/queue_preview.js (the index.html
    // window.DocuVisionPreview bridge script was removed with it).
    return DocuVisionPreview || {};
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

export async function getPdfPageImage(taskId, pageNum = 1) {
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
 * Wire the freshly rendered preview image to the sizing helper.
 *
 * The templates used to carry `onload="adjustDocumentSize()"`, and the browser evaluates an
 * inline handler in **global scope** - where this module's binding does not exist, so every
 * preview load threw `ReferenceError: adjustDocumentSize is not defined` (P-016, found by the
 * runtime coverage report). render.js had the same problem with an inline `onerror`. Attached
 * as real listeners the calls stay module-scope; `onError` is optional (only render.js has a
 * failure UI). `complete` is checked because a cached image may have fired `load` first.
 */
export function bindDocumentImageLoad(onError) {
    const documentImage = document.getElementById('documentImage');
    if (!documentImage) return;
    documentImage.addEventListener('load', adjustDocumentSize);
    if (onError) documentImage.addEventListener('error', onError);
    if (documentImage.complete) adjustDocumentSize();
}

/**
 * Adjust document size to fit container - show full page without scrollbar
 */
export function adjustDocumentSize() {
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

// Adjust document size on window resize (moved here from app.js in B5a - it was
// left behind when B4 extracted adjustDocumentSize into core.js)
window.addEventListener('resize', () => {
    setTimeout(adjustDocumentSize, 100);
});
