/**
 * Enhancement tabs: formulas / seals (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js; katex stays the pre-existing window global.
 */
import { escapeHtml } from '../utils/dom.js';

/**
 * Show or hide the Formulas/Seals sub-tabs based on enhancement checkbox state.
 * @param {boolean} enableFormula
 * @param {boolean} enableSeal
 */
export function updateEnhancementTabs(enableFormula, enableSeal) {
    const tabFormulas = document.getElementById('tabBtnFormulas');
    const tabSeals = document.getElementById('tabBtnSeals');
    if (tabFormulas) tabFormulas.classList.toggle('hidden', !enableFormula);
    if (tabSeals) tabSeals.classList.toggle('hidden', !enableSeal);
}

/**
 * Render Formulas tab content from view.formulas[].
 * @param {Array} formulas  - view.formulas from the result envelope
 */
export function updateContentFormulas(formulas) {
    const list = document.getElementById('contentFormulasList');
    if (!list) return;

    const items = Array.isArray(formulas) ? formulas : [];
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No formulas detected</div>';
        return;
    }

    let html = '';
    items.forEach((formula, index) => {
        const latex = formula.payload && formula.payload.latex ? formula.payload.latex : null;
        const status = formula.processing_status || '';
        html += '<div class="formula-item">';
        html += `<div class="formula-item-header"><span class="formula-name">Formula ${index + 1}</span>`;
        html += `<span class="formula-status">${escapeHtml(status)}</span></div>`;
        html += '<div class="formula-item-body">';
        if (latex) {
            try {
                html += `<div class="formula-rendered">${katex.renderToString(latex, { throwOnError: false, displayMode: true })}</div>`;
                html += `<div class="formula-latex"><code>${escapeHtml(latex)}</code></div>`;
            } catch (e) {
                html += `<div class="formula-latex"><code>${escapeHtml(latex)}</code></div>`;
            }
        } else {
            html += '<p class="formula-placeholder">Formula region detected — recognition pending</p>';
        }
        html += '</div></div>';
    });

    list.innerHTML = html;
}

/**
 * Render Seals tab content from view.seals[].
 * @param {Array} seals  - view.seals from the result envelope
 */
export function updateContentSeals(seals) {
    const list = document.getElementById('contentSealsList');
    if (!list) return;

    const items = Array.isArray(seals) ? seals : [];
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No seals detected</div>';
        return;
    }

    let html = '';
    items.forEach((seal, index) => {
        const text = seal.payload && seal.payload.text_on_seal ? seal.payload.text_on_seal : null;
        const status = seal.processing_status || '';
        html += '<div class="seal-item">';
        html += `<div class="seal-item-header"><span class="seal-name">Seal ${index + 1}</span>`;
        html += `<span class="seal-status">${escapeHtml(status)}</span></div>`;
        html += '<div class="seal-item-body">';
        if (text) {
            html += `<p class="seal-text">${escapeHtml(text)}</p>`;
        } else {
            html += '<p class="seal-placeholder">Seal region detected — recognition pending</p>';
        }
        html += '</div></div>';
    });

    list.innerHTML = html;
}
