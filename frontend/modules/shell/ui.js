/**
 * Shell UI (v1.8.3 B5a) - domain module (D4, ui half).
 *
 * Shell chrome: navigation tabs, result tabs (incl. the processing-mode radio wiring
 * and the syncModeUI hook), action buttons, annotation tooltip/interactions, panel
 * resize, JSON view buttons. All cross-domain calls (D1/D6/D7/D8/D9/D10/D15) are
 * injected at boot - F3 forbids importing sibling domain modules - via the same-name
 * module-scope binding trick, so every call site stays byte-identical. The classic
 * script globals (window.DOCUVISION_CONFIG / DocuVisionExport / DocuVisionUiFeatures)
 * remain the pre-existing integration points.
 */
import { showNotification } from '../notifications.js';
import { API_ROOT_URL } from '../api-config.js';
import { currentQueueItem } from '../preview-state.js';
import { TABLE_MAPPING_MODE } from '../kie-config.js';

// --- cross-domain deps, injected at boot ---
let startProcessing = async function () {};
let openAnalysisOptionsDialog = function () {};
let clearTableMappingEligibility = function () {};
let updateTableMappingEligibility = function () {};
let updateKieQueryFieldsAvailability = function () {};
let updateEnhancementTabs = function () {};
let refreshHitlReviews = function () {};
let highlightResultItem = function () {};
let setSyncProcessingModeUI = function () {};

/**
 * Wire shell-ui dependencies (app.js assembly).
 */
export function initShellUi(deps = {}) {
    if (typeof deps.startProcessing === 'function') startProcessing = deps.startProcessing;
    if (typeof deps.openAnalysisOptionsDialog === 'function') openAnalysisOptionsDialog = deps.openAnalysisOptionsDialog;
    if (typeof deps.clearTableMappingEligibility === 'function') clearTableMappingEligibility = deps.clearTableMappingEligibility;
    if (typeof deps.updateTableMappingEligibility === 'function') updateTableMappingEligibility = deps.updateTableMappingEligibility;
    if (typeof deps.updateKieQueryFieldsAvailability === 'function') updateKieQueryFieldsAvailability = deps.updateKieQueryFieldsAvailability;
    if (typeof deps.updateEnhancementTabs === 'function') updateEnhancementTabs = deps.updateEnhancementTabs;
    if (typeof deps.refreshHitlReviews === 'function') refreshHitlReviews = deps.refreshHitlReviews;
    if (typeof deps.highlightResultItem === 'function') highlightResultItem = deps.highlightResultItem;
    if (typeof deps.setSyncProcessingModeUI === 'function') setSyncProcessingModeUI = deps.setSyncProcessingModeUI;
}

export function initTabs() {
    const navTabs = document.querySelectorAll('.nav-tab');
    const processView = document.getElementById('processMainView');
    const batchView = document.getElementById('batchMainView');
    const reviewsView = document.getElementById('reviewsMainView');
    const pdfToolsView = document.getElementById('pdfToolsMainView');
    navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            if (tab.disabled) return;
            navTabs.forEach(t => {
                if (!t.disabled) t.classList.remove('active');
            });
            tab.classList.add('active');

            const tabName = tab.dataset.tab;
            if (processView && batchView) {
                processView.classList.add('hidden');
                batchView.classList.add('hidden');
                if (reviewsView) reviewsView.classList.add('hidden');
                if (pdfToolsView) pdfToolsView.classList.add('hidden');
                if (tabName === 'batch') {
                    batchView.classList.remove('hidden');
                } else if (tabName === 'reviews') {
                    if (reviewsView) reviewsView.classList.remove('hidden');
                    refreshHitlReviews();
                } else if (tabName === 'pdftools') {
                    if (pdfToolsView) pdfToolsView.classList.remove('hidden');
                } else {
                    processView.classList.remove('hidden');
                }
            }
        });
    });
}

/**
 * Help opens API docs or configured architecture doc URL.
 */
export function initHelpButton() {
    const btn = document.getElementById('helpBtn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        let url = '';
        if (window.DOCUVISION_CONFIG && typeof window.DOCUVISION_CONFIG.HELP_DOC_URL === 'string') {
            url = window.DOCUVISION_CONFIG.HELP_DOC_URL.trim();
        }
        if (!url) {
            url = `${API_ROOT_URL}/docs`;
        }
        window.open(url, '_blank', 'noopener,noreferrer');
    });
}

/**
 * Initialize result tabs (new structure: Content/Result)
 */
export function initResultTabs() {
    // Main tabs (Content/Result)
    const mainTabs = document.querySelectorAll('.result-main-tab');
    const mainViews = document.querySelectorAll('.result-main-view');

    mainTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.mainTab;

            // Update main tab state
            mainTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update main view
            mainViews.forEach(view => {
                view.classList.remove('active');
                if (view.id === `${targetTab}View`) {
                    view.classList.add('active');
                }
            });
        });
    });

    // Content sub-tabs (Text/Tables/Figures)
    const contentSubTabs = document.querySelectorAll('.content-sub-tab');
    const contentViews = document.querySelectorAll('.content-view');

    contentSubTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetContent = tab.dataset.content;

            // Update sub-tab state
            contentSubTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update content view（可选子视图初始带 .hidden，需去掉否则 display:none !important 盖住 .active）
            contentViews.forEach(view => {
                view.classList.remove('active');
                if (view.id === `content${targetContent.charAt(0).toUpperCase() + targetContent.slice(1)}View`) {
                    view.classList.add('active');
                    view.classList.remove('hidden');
                }
            });
        });
    });

    // Initialize panel resize
    initPanelResize();

    // Initialize JSON view buttons
    initJsonViewButtons();

    // Wire processing mode radios: toggle sub-options panel + enhancement tabs
    const processingModeRadios = document.querySelectorAll('input[name="processingMode"]');
    const layoutSubOptions = document.getElementById('layoutSubOptions');
    const optEnableFormula = document.getElementById('optEnableFormula');
    const optEnableSeal = document.getElementById('optEnableSeal');

    const syncModeUI = () => {
        const selectedMode = document.querySelector('input[name="processingMode"]:checked')?.value || 'layout';
        const isLayout = selectedMode === 'layout';
        const isTableMapping = selectedMode === TABLE_MAPPING_MODE;

        if (layoutSubOptions) {
            layoutSubOptions.classList.toggle('hidden', !isLayout);
            layoutSubOptions.classList.remove('sub-options-dimmed');
        }

        const tableMappingSubOptions = document.getElementById('tableMappingSubOptions');
        if (tableMappingSubOptions) {
            tableMappingSubOptions.classList.toggle('hidden', !isTableMapping);
        }

        const enginesLayoutSection = document.getElementById('enginesLayoutSection');
        if (enginesLayoutSection) {
            enginesLayoutSection.classList.toggle('sub-options-dimmed', isTableMapping);
        }

        const kieNote = document.getElementById('kieNote');
        if (kieNote) kieNote.classList.toggle('hidden', isLayout || isTableMapping);

        if (isLayout) {
            updateEnhancementTabs(
                optEnableFormula ? optEnableFormula.checked : false,
                optEnableSeal ? optEnableSeal.checked : false
            );
        } else {
            updateEnhancementTabs(false, false);
        }

        if (isTableMapping) {
            updateTableMappingEligibility(currentQueueItem);
        } else {
            clearTableMappingEligibility();
        }

        updateKieQueryFieldsAvailability();
    };

    processingModeRadios.forEach(radio => radio.addEventListener('change', syncModeUI));
    setSyncProcessingModeUI(syncModeUI);
    syncModeUI();
    updateKieQueryFieldsAvailability();

    if (optEnableFormula) {
        optEnableFormula.addEventListener('change', () => {
            updateEnhancementTabs(optEnableFormula.checked, optEnableSeal ? optEnableSeal.checked : false);
        });
    }
    if (optEnableSeal) {
        optEnableSeal.addEventListener('change', () => {
            updateEnhancementTabs(optEnableFormula ? optEnableFormula.checked : false, optEnableSeal.checked);
        });
    }

    if (window.DocuVisionUiFeatures) {
        DocuVisionUiFeatures.applyContentTabFeatures();
    }
}

/**
 * Initialize action buttons
 */
export function initActionButtons() {
    const runAnalysisBtn = document.getElementById('runAnalysisBtn');
    const analysisOptionsBtn = document.getElementById('analysisOptionsBtn');

    if (runAnalysisBtn) {
        runAnalysisBtn.addEventListener('click', () => {
            startProcessing();
        });
    }

    if (analysisOptionsBtn) {
        analysisOptionsBtn.addEventListener('click', () => {
            openAnalysisOptionsDialog();
        });
    }

}

// Global tooltip instance
let globalTooltip = null;

/**
 * Initialize global tooltip (module-private: only initAnnotationInteractions uses it)
 */
function initGlobalTooltip() {
    if (!globalTooltip) {
        globalTooltip = document.createElement('div');
        globalTooltip.className = 'annotation-tooltip global-tooltip';
        globalTooltip.style.display = 'none';
        globalTooltip.style.position = 'fixed';
        globalTooltip.style.zIndex = '10000';
        document.body.appendChild(globalTooltip);
    }
}

/**
 * Initialize annotation interactions
 */
export function initAnnotationInteractions() {
    initGlobalTooltip();

    const svg = document.getElementById('annotationSvgOverlay');
    if (!svg) return;

    const rects = svg.querySelectorAll('.svg-annotation');

    const esc = (str) => {
        const d = document.createElement('div');
        d.textContent = String(str == null ? '' : str);
        return d.innerHTML;
    };

    rects.forEach(rect => {
        rect.addEventListener('click', () => {
            rects.forEach(r => r.classList.remove('svg-annotation-active'));
            rect.classList.add('svg-annotation-active');
            highlightResultItem(rect.dataset.elementType, rect.dataset.elementIndex);
        });

        rect.addEventListener('mouseenter', () => {
            if (!globalTooltip) return;
            const raw = rect.dataset.tooltipData;
            if (!raw) return;
            try {
                const d = JSON.parse(raw);
                const readingOrderLine = d.readingOrder
                    ? `<div class="tooltip-line"><strong>Reading order:</strong> ${d.readingOrder}</div>`
                    : '';
                globalTooltip.innerHTML = `
                    <div class="tooltip-line"><strong>Role:</strong> ${esc(d.role)}</div>
                    <div class="tooltip-line"><strong>BBox:</strong> ${esc(d.bbox)}</div>
                    <div class="tooltip-line"><strong>Content:</strong> ${d.displayContent ? esc(d.displayContent) : '(empty)'}</div>
                    <div class="tooltip-line"><strong>Confidence:</strong> ${Number(d.confidence || 0).toFixed(1)}%</div>
                    ${readingOrderLine}
                `;

                const vr = rect.getBoundingClientRect();
                globalTooltip.style.display = 'block';
                globalTooltip.style.left = '0';
                globalTooltip.style.top = '0';
                const tr = globalTooltip.getBoundingClientRect();
                const vw = window.innerWidth;
                const vh = window.innerHeight;

                let left = vr.right + 10;
                let top = vr.top;
                if (left + tr.width > vw - 10) left = Math.max(10, vr.left - tr.width - 10);
                if (top + tr.height > vh - 10) top = Math.max(10, vh - tr.height - 10);

                globalTooltip.style.left = `${Math.max(10, left)}px`;
                globalTooltip.style.top = `${Math.max(10, top)}px`;
            } catch (err) {
                console.error('Tooltip parse error:', err);
                globalTooltip.style.display = 'none';
            }
        });

        rect.addEventListener('mouseleave', () => {
            if (globalTooltip) globalTooltip.style.display = 'none';
        });
    });
}

/**
 * Initialize panel resize functionality (module-private: called by initResultTabs)
 */
function initPanelResize() {
    const rightPanel = document.getElementById('rightPanel');
    const resizeHandle = document.getElementById('panelResizeHandle');

    if (!rightPanel || !resizeHandle) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    resizeHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = rightPanel.offsetWidth;
        resizeHandle.classList.add('resizing');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;

        const diff = startX - e.clientX; // Reverse because we're resizing from left
        const newWidth = startWidth + diff;
        const minWidth = 250;
        const maxWidth = 800;

        if (newWidth >= minWidth && newWidth <= maxWidth) {
            rightPanel.style.width = `${newWidth}px`;
        }
    });

    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

/**
 * Initialize JSON view buttons (module-private: called by initResultTabs)
 */
function initJsonViewButtons() {
    const copyBtn = document.getElementById('copyJsonBtn');
    const downloadBtn = document.getElementById('downloadJsonBtn');

    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const jsonCode = document.getElementById('jsonCode');
            if (jsonCode) {
                navigator.clipboard.writeText(jsonCode.textContent).then(() => {
                    showNotification('JSON copied to clipboard', 'success');
                }).catch(() => {
                    showNotification('Failed to copy JSON', 'error');
                });
            }
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener('click', () => {
            const jsonCode = document.getElementById('jsonCode');
            if (jsonCode) {
                const blob = new Blob([jsonCode.textContent], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `docuvision_result_${Date.now()}.json`;
                a.click();
                URL.revokeObjectURL(url);
                showNotification('JSON downloaded', 'success');
            }
        });
    }
}
