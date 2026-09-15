/**
 * Preview rendering (v1.8.3 B4) - domain module (D5, render half).
 *
 * Second half of D5 (see preview-nav.js for the split rationale). The same-domain
 * calls into preview-nav.js (resolveResultPageCount / revokeCurrentPageImageUrl /
 * syncPreviewPaginationControls) are injected at boot, as are the cross-domain ones
 * into D10 (renderDocumentWithAnnotations / renderTextPreview). Same-name
 * module-scope binding keeps every call site byte-identical.
 */
import { showNotification } from './notifications.js';
import { API_BASE_URL } from './api-config.js';
import {
    currentOriginalFileUrl, currentTaskId, currentQueueItem, currentPreviewPage,
    currentPageImageUrl, setPageImageUrl,
} from './preview-state.js';

// --- cross-domain deps (D10 overlay), injected at boot ---
let renderDocumentWithAnnotations = async function () {};
let renderTextPreview = function () {};
// --- same-domain deps from preview-nav.js, injected at boot ---
let resolveResultPageCount = function () { return 1; };
let revokeCurrentPageImageUrl = function () {};
let syncPreviewPaginationControls = function () {};

/**
 * Wire preview-render dependencies (app.js assembly).
 */
export function initPreviewRender(deps = {}) {
    if (typeof deps.renderDocumentWithAnnotations === 'function') renderDocumentWithAnnotations = deps.renderDocumentWithAnnotations;
    if (typeof deps.renderTextPreview === 'function') renderTextPreview = deps.renderTextPreview;
    if (typeof deps.resolveResultPageCount === 'function') resolveResultPageCount = deps.resolveResultPageCount;
    if (typeof deps.revokeCurrentPageImageUrl === 'function') revokeCurrentPageImageUrl = deps.revokeCurrentPageImageUrl;
    if (typeof deps.syncPreviewPaginationControls === 'function') syncPreviewPaginationControls = deps.syncPreviewPaginationControls;
}

/**
 * Get PDF page image from backend
 */
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
 * Update preview view
 */
export async function updatePreviewView(viewType) {
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

export async function updateDocumentPreview(result) {
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

/**
 * Fetch an image URL through the trial-key auth bridge and return an object
 * URL. Falls back to the raw URL on any error so a missing key still shows
 * a broken-image placeholder rather than throwing. The object URL is
 * revoked after the <img> errors or after a generous TTL.
 */
export function fetchAuthedImage(url, imgEl) {
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
