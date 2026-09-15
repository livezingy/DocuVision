/**
 * Human-in-the-loop review (v1.8.3 B1b) - domain module (D15).
 *
 * Moved verbatim with its module-local selection state. Imports only whitelisted targets
 * (api-config / notifications / utils/dom).
 */
import { API_ROOT_URL } from './api-config.js';
import { showNotification } from './notifications.js';
import { escapeHtml } from './utils/dom.js';

let hitlSelectedReviewId = null;
let hitlSelectedTaskId = null;
let hitlCurrentProfile = 'full';
let hitlCurrentSchemaFields = [];

export function initHitlReviews() {
    document.getElementById('hitlRefreshBtn')?.addEventListener('click', refreshHitlReviews);
    document.getElementById('hitlSaveBtn')?.addEventListener('click', saveHitlReviewFields);
    document.getElementById('hitlApproveBtn')?.addEventListener('click', () => resolveHitlReview('approved'));
    document.getElementById('hitlRejectBtn')?.addEventListener('click', () => resolveHitlReview('rejected'));
    document.getElementById('hitlReviewTableBody')?.addEventListener('click', async (event) => {
        const row = event.target.closest('tr[data-review-id]');
        if (!row) return;
        hitlSelectedReviewId = row.dataset.reviewId;
        await loadHitlReviewDetail(hitlSelectedReviewId);
    });
}

export async function refreshHitlReviews() {
    const tbody = document.getElementById('hitlReviewTableBody');
    if (!tbody) return;
    try {
        const response = await fetch(`${API_ROOT_URL}/api/v1/hitl/reviews?limit=50`);
        const data = await response.json();
        const reviews = data.reviews || [];
        tbody.innerHTML = reviews.length
            ? reviews.map((item) => `
                <tr data-review-id="${item.review_id}" style="cursor:pointer;">
                    <td style="padding:8px;">${escapeHtml(item.file_name || '')}</td>
                    <td style="padding:8px;">${escapeHtml(item.reason || '')}</td>
                    <td style="padding:8px;">${escapeHtml(item.created_at || '')}</td>
                </tr>`).join('')
            : '<tr><td colspan="3" style="padding:8px;">No pending reviews.</td></tr>';
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="3" style="padding:8px;">Failed to load reviews: ${escapeHtml(error.message)}</td></tr>`;
    }
}

export async function loadHitlReviewDetail(reviewId) {
    const fieldsContainer = document.getElementById('hitlReviewFields');
    const summary = document.getElementById('hitlReviewSummary');
    const approveBtn = document.getElementById('hitlApproveBtn');
    const rejectBtn = document.getElementById('hitlRejectBtn');
    const saveBtn = document.getElementById('hitlSaveBtn');
    if (!fieldsContainer || !reviewId) return;
    try {
        const response = await fetch(`${API_ROOT_URL}/api/v1/hitl/reviews/${reviewId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const item = await response.json();
        hitlSelectedTaskId = item.task_id || null;
        const payload = item.payload || {};
        const validation = payload.validation || {};
        hitlCurrentProfile = payload.hitl_profile || 'full';
        hitlCurrentSchemaFields = Array.isArray(payload.schema_fields) ? payload.schema_fields : [];
        const fields = payload.fields && typeof payload.fields === 'object' ? payload.fields : {};
        const failed = new Set(
            Object.entries(validation.validation_field_results || {})
                .filter(([, v]) => v && v.valid === false)
                .map(([k]) => k)
        );

        if (summary) {
            const passed = validation.validation_passed ? 'passed' : 'failed';
            summary.textContent = `Profile: ${hitlCurrentProfile} · Validation: ${passed} · Task: ${item.task_id || '—'}`;
        }

        fieldsContainer.innerHTML = '';
        const keys = Object.keys(fields);
        if (!keys.length) {
            fieldsContainer.innerHTML = '<p class="empty-state">No KIE fields in review payload.</p>';
        } else {
            const primaryKeys = hitlCurrentProfile === 'lite' && hitlCurrentSchemaFields.length
                ? hitlCurrentSchemaFields.filter(k => k in fields)
                : keys;
            const secondaryKeys = keys.filter(k => !primaryKeys.includes(k));

            primaryKeys.forEach(key => {
                fieldsContainer.appendChild(buildHitlFieldEditor(key, fields[key], failed.has(key)));
            });
            if (secondaryKeys.length && hitlCurrentProfile === 'lite') {
                const details = document.createElement('details');
                details.style.marginTop = '12px';
                details.innerHTML = `<summary class="upload-hint">Other fields (${secondaryKeys.length})</summary>`;
                secondaryKeys.forEach(key => {
                    details.appendChild(buildHitlFieldEditor(key, fields[key], failed.has(key)));
                });
                fieldsContainer.appendChild(details);
            } else {
                secondaryKeys.forEach(key => {
                    fieldsContainer.appendChild(buildHitlFieldEditor(key, fields[key], failed.has(key)));
                });
            }
        }

        if (approveBtn) approveBtn.disabled = false;
        if (rejectBtn) rejectBtn.disabled = false;
        if (saveBtn) saveBtn.disabled = !hitlSelectedTaskId;
    } catch (error) {
        fieldsContainer.innerHTML = `<p class="empty-state">Failed to load review: ${escapeHtml(error.message)}</p>`;
    }
}

export function buildHitlFieldEditor(key, value, isFailed) {
    const wrap = document.createElement('div');
    wrap.className = 'kie-field-card';
    if (isFailed) wrap.style.borderColor = 'var(--warning, #f59e0b)';
    const label = document.createElement('label');
    label.className = 'kie-field-label';
    label.textContent = key;
    label.setAttribute('for', `hitl-field-${key}`);
    const input = document.createElement('input');
    input.type = 'text';
    input.id = `hitl-field-${key}`;
    input.className = 'kie-field-input';
    input.dataset.fieldKey = key;
    input.value = value == null ? '' : (typeof value === 'object' ? JSON.stringify(value) : String(value));
    wrap.appendChild(label);
    wrap.appendChild(input);
    return wrap;
}

export function collectHitlFieldValues() {
    const out = {};
    document.querySelectorAll('#hitlReviewFields input[data-field-key]').forEach(input => {
        const key = input.dataset.fieldKey;
        if (!key) return;
        out[key] = input.value;
    });
    return out;
}

export async function saveHitlReviewFields() {
    if (!hitlSelectedTaskId) return;
    const fields = collectHitlFieldValues();
    try {
        const response = await fetch(`${API_ROOT_URL}/api/v1/tasks/${hitlSelectedTaskId}/kie-fields`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fields }),
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        const validation = data.kie_validation || {};
        const summary = document.getElementById('hitlReviewSummary');
        if (summary) {
            const passed = validation.validation_passed ? 'passed' : 'failed';
            summary.textContent = `Profile: ${hitlCurrentProfile} · Validation: ${passed} (saved) · Task: ${hitlSelectedTaskId}`;
        }
        showNotification('Fields saved to task', 'success');
    } catch (error) {
        showNotification(`Save failed: ${error.message}`, 'error');
    }
}

export async function resolveHitlReview(status) {
    if (!hitlSelectedReviewId) return;
    const correctedFields = collectHitlFieldValues();
    try {
        const response = await fetch(
            `${API_ROOT_URL}/api/v1/hitl/reviews/${hitlSelectedReviewId}/resolve?status=${encodeURIComponent(status)}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status, corrected_fields: correctedFields }),
            },
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        showNotification(`Review ${status}`, 'success');
        hitlSelectedReviewId = null;
        hitlSelectedTaskId = null;
        document.getElementById('hitlReviewFields').innerHTML = '';
        document.getElementById('hitlReviewSummary').textContent = '';
        document.getElementById('hitlApproveBtn').disabled = true;
        document.getElementById('hitlRejectBtn').disabled = true;
        document.getElementById('hitlSaveBtn').disabled = true;
        await refreshHitlReviews();
    } catch (error) {
        showNotification(`Resolve failed: ${error.message}`, 'error');
    }
}
