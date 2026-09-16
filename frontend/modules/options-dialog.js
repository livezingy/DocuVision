/**
 * Analysis options dialog (v1.8.3 B2) - domain module (D6).
 *
 * Cross-domain deps are injected at boot because F3 forbids domain->domain imports
 * (this domain both calls into D7 and is called by D7, forming a cycle):
 *   - clearTableMappingEligibility / updateKieQueryFieldsAvailability /
 *     buildKieQueryFieldsPayload  (D7 kie-mapping)
 *   - updateEnhancementTabs       (D9 result-panels, not yet extracted - injected from app.js)
 *   - syncProcessingModeUI        (owned here; D4 initAnalysisView sets it via
 *     setSyncProcessingModeUI at boot)
 * The module-scope "same-name binding" trick keeps every call site byte-identical:
 * the bodies call the local let-bound names and app.js wires the real ones in.
 */
import { showNotification } from './notifications.js';
import { TABLE_MAPPING_MODE, KIE_DOC_TYPES } from './kie-config.js';

let clearTableMappingEligibility = function () {};
let updateKieQueryFieldsAvailability = function () {};
let buildKieQueryFieldsPayload = function () { return '[]'; };
let updateEnhancementTabs = function () {};
let syncProcessingModeUI = function () {};

/**
 * Set the processing-mode UI sync hook (assigned by D4's initAnalysisView).
 */
export function setSyncProcessingModeUI(fn) {
    if (typeof fn === 'function') {
        syncProcessingModeUI = fn;
    }
}

export function initAnalysisOptionsDialog(deps = {}) {
    if (typeof deps.clearTableMappingEligibility === 'function') clearTableMappingEligibility = deps.clearTableMappingEligibility;
    if (typeof deps.updateKieQueryFieldsAvailability === 'function') updateKieQueryFieldsAvailability = deps.updateKieQueryFieldsAvailability;
    if (typeof deps.buildKieQueryFieldsPayload === 'function') buildKieQueryFieldsPayload = deps.buildKieQueryFieldsPayload;
    if (typeof deps.updateEnhancementTabs === 'function') updateEnhancementTabs = deps.updateEnhancementTabs;

    const modal = document.getElementById('analysisOptionsModal');
    const openBtn = document.getElementById('analysisOptionsBtn');
    const closeBtn = document.getElementById('closeAnalysisOptionsBtn');
    const cancelBtn = document.getElementById('cancelOptionsBtn');
    const saveBtn = document.getElementById('saveOptionsBtn');
    const resetBtn = document.getElementById('resetOptionsBtn');
    const modalTabs = document.querySelectorAll('.modal-tab');

    // Tab switching
    modalTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            modalTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.modal-tab-content').forEach(content => {
                content.classList.remove('active');
            });
            const targetContent = document.getElementById(tabName + 'Tab');
            if (targetContent) {
                targetContent.classList.add('active');
            }
        });
    });

    // Close handlers
    const closeModal = () => {
        if (modal) modal.classList.remove('active');
    };

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

    // Click outside to close
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    // Save handler
    if (saveBtn) {
        saveBtn.addEventListener('click', () => {
            saveAnalysisOptions();
            closeModal();
        });
    }

    // Reset handler
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            resetAnalysisOptions();
        });
    }
}

/**
 * Open Analysis Options Dialog
 */
export function openAnalysisOptionsDialog() {
    const modal = document.getElementById('analysisOptionsModal');
    if (modal) {
        modal.classList.add('active');
    }
}

/**
 * Save Analysis Options
 */
export function saveAnalysisOptions() {
    // Options are read dynamically from dialog when needed
    showNotification('Analysis options saved', 'success');
}

/**
 * Reset Analysis Options to defaults
 */
export function resetAnalysisOptions() {
    document.getElementById('optLayout').checked = true;
    const optEnableTable = document.getElementById('optEnableTable');
    if (optEnableTable) optEnableTable.checked = true;
    document.getElementById('optEnableFormula').checked = false;
    document.getElementById('optEnableSeal').checked = false;
    document.getElementById('dialogOcrEngineSelect').value = 'paddleocr';
    document.getElementById('dialogLayoutEngineSelect').value = 'ppstructure';
    const layoutSubOptions = document.getElementById('layoutSubOptions');
    if (layoutSubOptions) {
        layoutSubOptions.classList.remove('hidden');
        layoutSubOptions.classList.remove('sub-options-dimmed');
    }
    const kieNote = document.getElementById('kieNote');
    if (kieNote) kieNote.classList.add('hidden');
    const docTypeSuggestion = document.getElementById('documentTypeSuggestion');
    if (docTypeSuggestion) {
        docTypeSuggestion.textContent = '';
        docTypeSuggestion.classList.add('hidden');
    }
    const kieQueryInput = document.getElementById('optKieQueryFields');
    if (kieQueryInput) kieQueryInput.value = '';
    const optTableTemplate = document.getElementById('optTableTemplate');
    if (optTableTemplate) optTableTemplate.value = 'bank_statement';
    const tableMappingSubOptions = document.getElementById('tableMappingSubOptions');
    if (tableMappingSubOptions) tableMappingSubOptions.classList.add('hidden');
    clearTableMappingEligibility();
    syncProcessingModeUI();
    updateKieQueryFieldsAvailability();
    updateEnhancementTabs(false, false);
    showNotification('Options reset to defaults', 'info');
}

export function getSelectedProcessingMode() {
    return document.querySelector('input[name="processingMode"]:checked')?.value || 'layout';
}

/**
 * Get current processing options from dialog
 */
export function getProcessingOptions() {
    const selectedMode = getSelectedProcessingMode();
    const isLayout = selectedMode === 'layout';
    const isTableMapping = selectedMode === TABLE_MAPPING_MODE;

    const enableKie = (function() {
        const dt = isLayout ? 'auto' : selectedMode;
        return KIE_DOC_TYPES.has(String(dt).toLowerCase());
    })();

    const optTableTemplate = document.getElementById('optTableTemplate');
    const tableTemplate = isTableMapping
        ? String(optTableTemplate?.value || 'bank_statement').trim()
        : '';

    const options = {
        document_type: isTableMapping ? 'general' : (isLayout ? 'auto' : selectedMode),
        enable_layout: isTableMapping ? false : isLayout,
        enable_table: isTableMapping
            ? true
            : (isLayout ? (document.getElementById('optEnableTable')?.checked ?? true) : true),
        enable_formula: isTableMapping
            ? false
            : (isLayout ? (document.getElementById('optEnableFormula')?.checked || false) : false),
        enable_seal: isTableMapping
            ? false
            : (isLayout ? (document.getElementById('optEnableSeal')?.checked || false) : false),
        // Auto-enable KIE when user selects invoice/receipt/id_card processing mode
        enable_kie: isTableMapping ? false : enableKie,
        kie_query_fields: buildKieQueryFieldsPayload(),
        // Ignore stale PDF page specs when KIE is off (layout-only runs on images).
        kie_pages: enableKie
            ? ((document.getElementById('optKiePages')?.value || '').trim() || '1')
            : '1',
        ocr_engine: document.getElementById('dialogOcrEngineSelect')?.value || 'paddleocr',
        layout_engine: document.getElementById('dialogLayoutEngineSelect')?.value || 'ppstructure',
        table_template: tableTemplate,
        validation_passed_only: Boolean(document.getElementById('batchValidationPassedOnly')?.checked),
    };

    return options;
}
