/**
 * Pure helpers for Pro queue selection and document preview pagination.
 * Imported by Vitest; exposed on window.DocuVisionPreview via index.html module script.
 */

/**
 * Resolve total page count from API result (fallback chain for legacy payloads).
 * @param {object|null|undefined} result
 * @param {number} [previewPageCount] - from upload preview when result not ready
 * @returns {number}
 */
export function resolveDocumentPageCount(result, previewPageCount = 0) {
    const preview = Number(previewPageCount);
    if (preview > 0) {
        return Math.floor(preview);
    }
    if (!result || typeof result !== 'object') {
        return 1;
    }
    const docInfo = result.document_info || {};
    const pages = Number(docInfo.pages);
    if (pages > 0) {
        return Math.floor(pages);
    }
    const layoutPages = Number((result.layout || {}).total_pages);
    if (layoutPages > 0) {
        return Math.floor(layoutPages);
    }
    const viewPages = (result.view || {}).pages;
    if (Array.isArray(viewPages) && viewPages.length > 0) {
        return viewPages.length;
    }
    const pageCount = Number(result.page_count);
    if (pageCount > 0) {
        return Math.floor(pageCount);
    }
    return 1;
}

/**
 * Pick which pending queue item Run Analysis should process.
 * Prefer the currently selected item when it is still waiting.
 * @param {HTMLElement[]} pendingItems - DOM nodes with class queue-item.pending
 * @param {HTMLElement|null|undefined} currentItem
 * @returns {HTMLElement|null}
 */
export function pickProcessingTarget(pendingItems, currentItem) {
    const list = Array.isArray(pendingItems) ? pendingItems : [];
    if (list.length === 0) {
        return null;
    }
    if (currentItem && list.includes(currentItem)) {
        return currentItem;
    }
    return list[0];
}

/**
 * Clamp page number to [1, totalPages].
 * @param {number} page
 * @param {number} totalPages
 * @returns {number}
 */
export function normalizePreviewPage(page, totalPages) {
    const total = Math.max(1, Math.floor(Number(totalPages) || 1));
    const raw = Math.floor(Number(page) || 1);
    return Math.min(Math.max(1, raw), total);
}

/**
 * Format sidebar completed status line.
 * @param {number} pageCount
 * @returns {string}
 */
export function formatCompletedStatus(pageCount) {
    const n = resolveDocumentPageCount({ document_info: { pages: pageCount } });
    return `Completed · ${n} page${n !== 1 ? 's' : ''}`;
}

/**
 * Find next queue item to auto-start after one job finishes.
 * @param {HTMLElement[]} items - all .queue-item elements
 * @returns {HTMLElement|null}
 */
export function findNextQueueItem(items) {
    const list = Array.isArray(items) ? items : [];
    const queued = list.find((el) => el.classList && el.classList.contains('queued'));
    if (queued) {
        return queued;
    }
    const processing = list.some((el) => el.classList && el.classList.contains('processing'));
    if (processing) {
        return null;
    }
    return list.find((el) => el.classList && el.classList.contains('pending')) || null;
}
