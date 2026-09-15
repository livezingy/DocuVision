/**
 * Floating progress card (v1.8.3 B1b) - domain module (D11).
 *
 * NOTE (2026-09-15): moved verbatim for domain completeness, but `showFloatingProgressCard`
 * and `updateFloatingProgress` currently have no call sites anywhere in frontend/ - the
 * processing flow was switched to the status bar. Kept (not deleted) per the "no extra
 * cleanup in a structure-only version" rule; candidate for v1.9 removal together with the
 * `#floatingProgressCard` markup.
 */
import { API_BASE_URL } from './api-config.js';

/**
 * Show floating progress card
 */
export function showFloatingProgressCard(taskInfo) {
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
export function updateFloatingProgress(progress, step) {
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
export function hideFloatingProgressCard() {
    const card = document.getElementById('floatingProgressCard');
    if (card) {
        card.style.display = 'none';
    }
}
