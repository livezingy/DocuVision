/**
 * KIE / table-mapping eligibility & fields (v1.8.3 B2) - domain module (D7).
 *
 * The only non-whitelisted cross-domain dependency is D6's getSelectedProcessingMode
 * (called by updateTableMappingEligibility and isTableMappingRunBlocked); it is injected
 * into initKieMapping at boot. The module-scope "same-name binding" trick keeps both call
 * sites byte-identical: app.js wires `initKieMapping({ getSelectedProcessingMode })`.
 */
import { API_BASE_URL } from './api-config.js';
import { currentQueueItem } from './preview-state.js';
import {
    KIE_DOC_TYPES,
    KIE_FIELD_NAME_RE,
    TABLE_MAPPING_MODE,
    TABLE_MAPPING_ELIGIBLE,
    TABLE_MAPPING_IMAGE_EXTENSIONS,
} from './kie-config.js';
import { escapeHtml } from './utils/dom.js';

let getSelectedProcessingMode = function () { return 'layout'; };

/**
 * Wire the cross-domain dependency from D6 options-dialog (app.js assembly).
 */
export function initKieMapping(deps = {}) {
    if (typeof deps.getSelectedProcessingMode === 'function') {
        getSelectedProcessingMode = deps.getSelectedProcessingMode;
    }
}

export function clearTableMappingEligibility() {
    const el = document.getElementById('tableMappingEligibility');
    if (!el) return;
    el.textContent = '';
    el.classList.add('hidden');
}

export function updateTableMappingEligibility(queueItem) {
    const el = document.getElementById('tableMappingEligibility');
    if (!el) return;
    if (getSelectedProcessingMode() !== TABLE_MAPPING_MODE) {
        clearTableMappingEligibility();
        return;
    }

    const detected = queueItem?.documentProfile?.detected_file_type;
    let message = 'Upload a digital PDF for best results.';
    if (detected === 'pdf_digital') {
        message = 'Ready for table mapping.';
    } else if (detected === 'pdf_scan' || detected === 'image') {
        message = 'Scanned documents are not supported for table mapping in v1.4. Use Layout Analysis.';
    }

    el.textContent = message;
    el.classList.remove('hidden');
}

export async function fetchDocumentProfileForQueueItem(queueItem) {
    if (!queueItem?.file) return;
    const formData = new FormData();
    formData.append('file', queueItem.file, queueItem.file.name || queueItem.dataset.fileName || 'upload');
    try {
        const response = await fetch(`${API_BASE_URL}/document/profile`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            queueItem.documentProfile = null;
            return;
        }
        queueItem.documentProfile = await response.json();
        if (currentQueueItem === queueItem) {
            updateTableMappingEligibility(queueItem);
            updateDocumentTypeSuggestion(queueItem);
        }
    } catch (err) {
        console.warn('Document profile pre-scan failed:', err);
        queueItem.documentProfile = null;
    }
}

// Non-binding hint: surface the classifier's suggested document_type so the
// user can pick the right KIE mode. This never auto-applies — it only shows
// text next to the options. Low-confidence or "auto" suggestions are hidden.
export function updateDocumentTypeSuggestion(queueItem) {
    const el = document.getElementById('documentTypeSuggestion');
    if (!el) return;
    const profile = queueItem?.documentProfile;
    const suggested = String(profile?.suggested_document_type || '').toLowerCase();
    const confidence = Number(profile?.classification_confidence || 0);
    if (!suggested || suggested === 'auto' || confidence < 0.4 || !KIE_DOC_TYPES.has(suggested)) {
        el.textContent = '';
        el.classList.add('hidden');
        return;
    }
    const pct = Math.round(confidence * 100);
    el.textContent = `Detected: ${suggested} (${pct}%). Select the matching mode to enable KIE.`;
    el.classList.remove('hidden');
}

export function isTableMappingRunBlocked(queueItem) {
    if (getSelectedProcessingMode() !== TABLE_MAPPING_MODE) {
        return false;
    }

    const fileName = String(queueItem?.dataset?.fileName || queueItem?.file?.name || '').toLowerCase();
    const ext = fileName.includes('.') ? fileName.split('.').pop() : '';
    if (TABLE_MAPPING_IMAGE_EXTENSIONS.has(ext)) {
        return true;
    }

    const detected = queueItem?.documentProfile?.detected_file_type;
    if (detected && !TABLE_MAPPING_ELIGIBLE.has(detected)) {
        return true;
    }

    return false;
}

/**
 * Normalize user-facing labels to API field ids (spaces -> underscores).
 */
export function normalizeKieFieldName(raw) {
    let name = String(raw || '').trim();
    if (!name) return name;
    name = name.replace(/\s+/g, '_').replace(/[^A-Za-z0-9_]/g, '');
    if (/^[0-9]/.test(name)) {
        name = 'Field_' + name;
    }
    return name;
}

export function assertValidKieFieldName(name, sourceLabel) {
    if (!KIE_FIELD_NAME_RE.test(name)) {
        throw new Error(
            'Invalid KIE field name "' +
                sourceLabel +
                '". Use letters, digits, underscore only; must start with a letter (e.g. CustomerName or CUSTOMER_NAME).'
        );
    }
}

/**
 * Enable/disable additional KIE fields input based on processing mode.
 */
export function updateKieQueryFieldsAvailability() {
    const block = document.getElementById('kieQueryFieldsBlock');
    const input = document.getElementById('optKieQueryFields');
    if (!block || !input) return;
    const selectedMode = document.querySelector('input[name="processingMode"]:checked')?.value || 'layout';
    const enabled = KIE_DOC_TYPES.has(String(selectedMode).toLowerCase());
    input.disabled = !enabled;
    block.classList.toggle('kie-query-fields-disabled', !enabled);
}

/**
 * Parse Additional KIE fields textarea into API payload (JSON string of array).
 */
export function buildKieQueryFieldsPayload() {
    const el = document.getElementById('optKieQueryFields');
    if (!el || el.disabled) return '[]';
    const raw = String(el.value || '').trim();
    if (!raw) return '[]';

    if (raw.startsWith('[')) {
        try {
            const parsed = JSON.parse(raw);
            if (!Array.isArray(parsed)) {
                throw new Error('JSON must be an array');
            }
            const out = parsed.map((entry, index) => {
                if (typeof entry === 'string') {
                    const name = normalizeKieFieldName(entry);
                    assertValidKieFieldName(name, entry);
                    return name;
                }
                if (entry && typeof entry === 'object' && entry.name) {
                    const label = String(entry.name);
                    const name = normalizeKieFieldName(label);
                    assertValidKieFieldName(name, label);
                    const item = { name };
                    if (entry.description) {
                        item.description = String(entry.description);
                    }
                    return item;
                }
                throw new Error('JSON entry at index ' + index + ' must be a string or {name, description?}');
            });
            return JSON.stringify(out);
        } catch (e) {
            throw new Error('Invalid JSON for additional KIE fields: ' + e.message);
        }
    }

    const names = raw
        .split(/[,;\n]+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((label) => {
            const name = normalizeKieFieldName(label);
            assertValidKieFieldName(name, label);
            return name;
        });
    return JSON.stringify(names);
}

/**
 * 从任务 result 中取出 KIE 字段映射（与 envelope.view.fields 同源）。
 */
export function pickKieFieldsMap(result) {
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
export function formatKieFieldForExtract(field, depth) {
    const d = depth || 0;
    if (d > 8) {
        try {
            return '<pre class="kie-json">' + escapeHtml(JSON.stringify(field, null, 2)) + '</pre>';
        } catch {
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
    } catch {
        return escapeHtml(String(field));
    }
}

/**
 * 在 Content > Fields 子页签中渲染 KIE 字段。
 * 仅当 result.kie_fields 或 result.view.fields 非空时显示 Fields 按钮，
 * 并在结果加载完成后自动切到该子页签。
 */
export function updateContentFields(result) {
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
        metaBits.push('KIE incomplete');
        if (meta.error_message) {
            metaBits.push(String(meta.error_message));
        } else if (meta.error_code) {
            metaBits.push(String(meta.error_code));
        }
    } else {
        if (meta.confidence_avg != null && !Number.isNaN(Number(meta.confidence_avg))) {
            metaBits.push('Avg confidence ' + Number(meta.confidence_avg).toFixed(2));
        }
        if (meta.items_count != null) {
            metaBits.push('Line items ' + String(meta.items_count));
        }
    }
    fieldsMeta.textContent = metaBits.join(' · ');

    const querySet = new Set(
        (result.quality && result.quality.kie_query_fields_requested) ||
        (meta.kie_query_fields_requested) ||
        []
    );

    let html = '';
    Object.entries(kieFields).forEach(([key, value]) => {
        const isQuery = querySet.has(key);
        html += '<div class="kie-field-card' + (isQuery ? ' kie-field-card-query' : '') + '">';
        html += '<div class="kie-field-card-header">';
        html +=
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M16 3v4"></path><path d="M8 3v4"></path><path d="M3 10h18"></path></svg>';
        html += '<span>' + escapeHtml(key) + '</span>';
        if (isQuery) {
            html += '<span class="kie-field-query-badge">Query</span>';
        }
        html += '</div>';
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
