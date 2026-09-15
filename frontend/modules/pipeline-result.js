/**
 * Processing pipeline - result half (v1.8.3 B4) - domain module (D8).
 *
 * Second half of D8 (see pipeline-run.js for the split rationale). Cross-domain deps
 * (D3 upload-queue, D5 preview-paging) and the app.js mediator updateResultsDisplay
 * (`renderResults`) are injected at boot; same-name module-scope binding keeps every
 * call site byte-identical.
 */
import { showNotification } from './notifications.js';
import { updateStatusBar } from './status-bar.js';
import { API_BASE_URL } from './api-config.js';

// --- cross-domain deps, injected at boot ---
let failProcessing = function () {};
let handleQueueItemDeletion = async function () {};
let processNextInQueue = function () {};
let previewHelpers = function () { return {}; };
let resolveResultPageCount = function () { return 1; };
let renderResults = async function () {};

/**
 * Wire pipeline-result dependencies (app.js assembly).
 */
export function initPipelineResult(deps = {}) {
    if (typeof deps.failProcessing === 'function') failProcessing = deps.failProcessing;
    if (typeof deps.handleQueueItemDeletion === 'function') handleQueueItemDeletion = deps.handleQueueItemDeletion;
    if (typeof deps.processNextInQueue === 'function') processNextInQueue = deps.processNextInQueue;
    if (typeof deps.previewHelpers === 'function') previewHelpers = deps.previewHelpers;
    if (typeof deps.resolveResultPageCount === 'function') resolveResultPageCount = deps.resolveResultPageCount;
    if (typeof deps.renderResults === 'function') renderResults = deps.renderResults;
}

/**
 * Fetch task result and complete processing
 */
export async function fetchTaskResult(taskId, item) {
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
export async function fetchTaskBlocks(taskId, pageNumber = 1) {
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
 * Complete processing
 */
export async function completeProcessing(item, result = null) {
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
        await renderResults(result);

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
export function clearResultsDisplay(keepDocumentPreview = false) {
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
