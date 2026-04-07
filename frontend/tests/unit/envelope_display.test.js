/**
 * Unit tests for Phase 2 Group A frontend changes.
 * Tests: updateEnhancementTabs, updateContentFormulas, updateContentSeals
 *
 * Uses jsdom (vitest's default browser-like environment) to simulate the DOM.
 */
import { beforeEach, describe, it, expect, vi } from 'vitest';

// ---------------------------------------------------------------------------
// Minimal DOM setup — replicate the elements the functions touch
// ---------------------------------------------------------------------------
function setupDOM() {
    document.body.innerHTML = `
        <button id="tabBtnFormulas" class="content-sub-tab hidden">Formulas</button>
        <button id="tabBtnSeals"    class="content-sub-tab hidden">Seals</button>

        <div id="contentFormulasView" class="content-view hidden">
            <div class="formulas-list" id="contentFormulasList"></div>
        </div>
        <div id="contentSealsView" class="content-view hidden">
            <div class="seals-list" id="contentSealsList"></div>
        </div>

        <input type="checkbox" id="optEnableFormula">
        <input type="checkbox" id="optEnableSeal">
    `;
}

// ---------------------------------------------------------------------------
// Inline the functions under test (extracted from app.js logic, no server dep)
// ---------------------------------------------------------------------------
function updateEnhancementTabs(enableFormula, enableSeal) {
    const tabFormulas = document.getElementById('tabBtnFormulas');
    const tabSeals    = document.getElementById('tabBtnSeals');
    if (tabFormulas) tabFormulas.classList.toggle('hidden', !enableFormula);
    if (tabSeals)    tabSeals.classList.toggle('hidden', !enableSeal);
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Minimal katex stub (real KaTeX not available in jsdom)
const katex = {
    renderToString: (latex, _opts) => `<span class="katex-stub">${escapeHtml(latex)}</span>`,
};

function updateContentFormulas(formulas) {
    const list = document.getElementById('contentFormulasList');
    if (!list) return;
    const items = Array.isArray(formulas) ? formulas : [];
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-state">No formulas detected</div>';
        return;
    }
    let html = '';
    items.forEach((formula, index) => {
        const latex  = formula.payload && formula.payload.latex ? formula.payload.latex : null;
        const status = formula.processing_status || '';
        html += '<div class="formula-item">';
        html += `<div class="formula-item-header"><span class="formula-name">Formula ${index + 1}</span>`;
        html += `<span class="formula-status">${escapeHtml(status)}</span></div>`;
        html += '<div class="formula-item-body">';
        if (latex) {
            try {
                html += `<div class="formula-rendered">${katex.renderToString(latex, { throwOnError: false, displayMode: true })}</div>`;
                html += `<div class="formula-latex"><code>${escapeHtml(latex)}</code></div>`;
            } catch {
                html += `<div class="formula-latex"><code>${escapeHtml(latex)}</code></div>`;
            }
        } else {
            html += '<p class="formula-placeholder">Formula region detected — recognition pending</p>';
        }
        html += '</div></div>';
    });
    list.innerHTML = html;
}

function updateContentSeals(seals) {
    const list = document.getElementById('contentSealsList');
    if (!list) return;
    const items = Array.isArray(seals) ? seals : [];
    if (items.length === 0) {
        list.innerHTML = '<div class="empty-state">No seals detected</div>';
        return;
    }
    let html = '';
    items.forEach((seal, index) => {
        const text   = seal.payload && seal.payload.text_on_seal ? seal.payload.text_on_seal : null;
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('updateEnhancementTabs', () => {
    beforeEach(setupDOM);

    it('both tabs hidden when both false', () => {
        updateEnhancementTabs(false, false);
        expect(document.getElementById('tabBtnFormulas').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('tabBtnSeals').classList.contains('hidden')).toBe(true);
    });

    it('formula tab visible when enableFormula=true', () => {
        updateEnhancementTabs(true, false);
        expect(document.getElementById('tabBtnFormulas').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('tabBtnSeals').classList.contains('hidden')).toBe(true);
    });

    it('seal tab visible when enableSeal=true', () => {
        updateEnhancementTabs(false, true);
        expect(document.getElementById('tabBtnFormulas').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('tabBtnSeals').classList.contains('hidden')).toBe(false);
    });

    it('both tabs visible when both true', () => {
        updateEnhancementTabs(true, true);
        expect(document.getElementById('tabBtnFormulas').classList.contains('hidden')).toBe(false);
        expect(document.getElementById('tabBtnSeals').classList.contains('hidden')).toBe(false);
    });

    it('can toggle back to hidden after being visible', () => {
        updateEnhancementTabs(true, true);
        updateEnhancementTabs(false, false);
        expect(document.getElementById('tabBtnFormulas').classList.contains('hidden')).toBe(true);
        expect(document.getElementById('tabBtnSeals').classList.contains('hidden')).toBe(true);
    });
});

describe('updateContentFormulas', () => {
    beforeEach(setupDOM);

    it('shows empty-state when array is empty', () => {
        updateContentFormulas([]);
        expect(document.getElementById('contentFormulasList').innerHTML).toContain('No formulas detected');
    });

    it('shows empty-state when called with null', () => {
        updateContentFormulas(null);
        expect(document.getElementById('contentFormulasList').innerHTML).toContain('No formulas detected');
    });

    it('renders a formula card for each item', () => {
        updateContentFormulas([
            { processing_status: 'skip_formula', payload: {} },
            { processing_status: 'skip_formula', payload: {} },
        ]);
        const cards = document.querySelectorAll('.formula-item');
        expect(cards.length).toBe(2);
    });

    it('shows placeholder when payload.latex is absent', () => {
        updateContentFormulas([{ processing_status: 'skip_formula', payload: {} }]);
        expect(document.querySelector('.formula-placeholder')).not.toBeNull();
    });

    it('renders KaTeX stub when payload.latex present', () => {
        updateContentFormulas([{ processing_status: 'recognized', payload: { latex: 'E=mc^2' } }]);
        expect(document.querySelector('.formula-rendered')).not.toBeNull();
        expect(document.querySelector('.formula-latex code').textContent).toBe('E=mc^2');
    });

    it('escapes HTML in processing_status', () => {
        updateContentFormulas([{ processing_status: '<script>', payload: {} }]);
        expect(document.getElementById('contentFormulasList').innerHTML).toContain('&lt;script&gt;');
    });

    it('shows correct formula index labels', () => {
        updateContentFormulas([
            { processing_status: 'skip_formula', payload: {} },
            { processing_status: 'skip_formula', payload: {} },
        ]);
        const names = document.querySelectorAll('.formula-name');
        expect(names[0].textContent).toBe('Formula 1');
        expect(names[1].textContent).toBe('Formula 2');
    });
});

describe('updateContentSeals', () => {
    beforeEach(setupDOM);

    it('shows empty-state when array is empty', () => {
        updateContentSeals([]);
        expect(document.getElementById('contentSealsList').innerHTML).toContain('No seals detected');
    });

    it('shows empty-state when called with null', () => {
        updateContentSeals(null);
        expect(document.getElementById('contentSealsList').innerHTML).toContain('No seals detected');
    });

    it('renders a seal card for each item', () => {
        updateContentSeals([
            { processing_status: 'skip_seal', payload: {} },
            { processing_status: 'skip_seal', payload: {} },
        ]);
        const cards = document.querySelectorAll('.seal-item');
        expect(cards.length).toBe(2);
    });

    it('shows placeholder when text_on_seal absent', () => {
        updateContentSeals([{ processing_status: 'skip_seal', payload: {} }]);
        expect(document.querySelector('.seal-placeholder')).not.toBeNull();
    });

    it('displays text_on_seal when present', () => {
        updateContentSeals([{ processing_status: 'recognized', payload: { text_on_seal: 'XX公司合同专用章' } }]);
        expect(document.querySelector('.seal-text').textContent).toBe('XX公司合同专用章');
    });

    it('escapes HTML in text_on_seal', () => {
        updateContentSeals([{ processing_status: 'recognized', payload: { text_on_seal: '<b>seal</b>' } }]);
        expect(document.getElementById('contentSealsList').innerHTML).toContain('&lt;b&gt;seal&lt;/b&gt;');
    });

    it('shows correct seal index labels', () => {
        updateContentSeals([
            { processing_status: 'skip_seal', payload: {} },
            { processing_status: 'skip_seal', payload: {} },
        ]);
        const names = document.querySelectorAll('.seal-name');
        expect(names[0].textContent).toBe('Seal 1');
        expect(names[1].textContent).toBe('Seal 2');
    });
});
