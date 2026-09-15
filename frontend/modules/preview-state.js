/**
 * Shared preview / result state (v1.8.3 B1a) - registered shared-state module.
 *
 * Moved out of app.js (:199 and :921-926) so the preview-paging, overlay, result-panel,
 * export, batch and shell domains can read it through ESM live bindings while it lives in
 * exactly one place.
 *
 * Contract (design rev3 section 4):
 *  1. reads are zero-change - consumers `import { currentTaskId }` and every read
 *     expression stays byte-identical; live bindings always yield the latest value;
 *  2. writes go through the setters below (19 call sites converted in B1a). Module code
 *     is strict mode, so assigning to an imported binding is a TypeError - a harder
 *     guard than any lint rule;
 *  3. revokes stay at the call sites. `revokeCurrentPageImageUrl()`,
 *     `switchToQueueItem()` and `handleQueueItemDeletion()` keep their explicit
 *     `URL.revokeObjectURL(...)` before the write, so the original statement order is
 *     preserved verbatim. The setters stay deliberately dumb: absorbing the revoke would
 *     move `URL.createObjectURL(file)` ahead of it, and would move the page-image revoke
 *     across an `await` - not byte-identical, so it is not done in this version.
 *  4. caching an old value across an `await` is not fixed here (the original `let` had
 *     the same behaviour) - registered as v1.9 input.
 */

// --- preview-paging (D5) ---
export let currentOriginalFileUrl = null;
export let currentTaskId = null;
export let currentQueueItem = null; // Track currently selected queue item
export let currentPreviewPage = 1;
export let currentPageImageUrl = null;
export let previewPaginationInitialized = false;

// --- pipeline (D8) state that other domains read ---
/** Last rendered analysis result; read by renderDocumentWithAnnotations (D10) and updateContentText (D9). */
export let lastRenderedAnalysisResult = null;

// --- the single write channel (setters) ---
export function setOriginalFileUrl(url) { currentOriginalFileUrl = url; } // :1136 (+ reset)
export function setTaskId(id) { currentTaskId = id; } // :1091 :1137 :1159 :1925 (+ reset)
export function setQueueItem(item) { currentQueueItem = item; } // :1120 (+ reset)
export function setPreviewPage(page) { currentPreviewPage = page; } // :946 :1138 :2812
export function setPageImageUrl(url) { currentPageImageUrl = url; } // :972 :1020 :1252 :2822
export function setPreviewPaginationInitialized(value) { previewPaginationInitialized = value; } // :1044
export function setLastRenderedAnalysisResult(result) { lastRenderedAnalysisResult = result; } // :2424 :2804

/**
 * Clear the three "currently displayed document" slots (original app.js :685-687).
 * The caller keeps its own `if (currentOriginalFileUrl) URL.revokeObjectURL(...)` right
 * before this call, exactly as before.
 */
export function resetPreviewState() {
    currentOriginalFileUrl = null;
    currentTaskId = null;
    currentQueueItem = null;
}
