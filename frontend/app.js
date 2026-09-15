/**
 * DocuVision - Intelligent Document Processing System
 * Frontend Interaction Script
 */

// --- v1.8.3 B0b: extracted pure helpers (see frontend/modules/utils/) ---
import {
    normalizeAnnotationBbox,
    bboxFromPolygon,
    normalizeCoordSpace,
    normalizeBboxToImageMatrix,
    remapBboxToImageSpace,
} from './modules/utils/geometry.js';
import {
    convertToCSV,
    convertToMarkdown,
    tableConfidencePct,
    formatTableCsvBanner,
    excelSafeCell,
    escapeCsvCell,
    buildSingleTableCsv,
    singleTableCsvFilename,
} from './modules/utils/csv.js';
import {
    formatAzureRoleLabel,
    normalizeTextForDisplay,
    normalizePanelParagraphText,
    isLikelyCollapsedText,
    toAzureTypeLabel,
} from './modules/utils/text.js';
import { escapeHtml } from './modules/utils/dom.js';
// --- v1.8.3 B1a: API constants moved to modules/api-config.js (leaf service) ---
import { API_BASE_URL, API_ROOT_URL, HEALTH_URL, ENGINES_URL } from './modules/api-config.js';
// --- v1.8.3 B2 prep: KIE / table-mapping constants moved to modules/kie-config.js ---
import {
    KIE_DOC_TYPES, KIE_FIELD_NAME_RE, TABLE_MAPPING_MODE, TABLE_MAPPING_ELIGIBLE,
    TABLE_MAPPING_IMAGE_EXTENSIONS,
} from './modules/kie-config.js';
// --- v1.8.3 B1a: shared preview/result state lives in modules/preview-state.js; reads stay
// byte-identical through live bindings, writes go through the setters below ---
import {
    // reads: live bindings, every read expression stays byte-identical
    currentOriginalFileUrl, currentTaskId, currentQueueItem, currentPreviewPage,
    currentPageImageUrl, previewPaginationInitialized, lastRenderedAnalysisResult,
    lastFetchedBlocks,
    // writes: the only channel, module code cannot assign to an imported binding
    setOriginalFileUrl, setTaskId, setQueueItem, setPreviewPage, setPageImageUrl,
    setPreviewPaginationInitialized, setLastRenderedAnalysisResult, setLastFetchedBlocks,
    resetPreviewState,
} from './modules/preview-state.js';
// --- v1.8.3 B1b: extracted leaf services + shared api state ---
import { updateStatusBar, updateStatusBarThrottled } from './modules/status-bar.js';
import { showNotification } from './modules/notifications.js';
import { lastHealthPayload } from './modules/api-state.js';
import {
    initializeAPIConnection, checkApiReachable, applyHealthToFooter, refreshActiveEngineFooterLine,
} from './modules/api-base.js';
import { bindTableCardCsvExport } from './modules/export-csv.js';
import { initBatchProcessing } from './modules/batch.js';
import { initHitlReviews, refreshHitlReviews } from './modules/hitl-review.js';
import {
    initAnalysisOptionsDialog, openAnalysisOptionsDialog, getProcessingOptions,
    getSelectedProcessingMode, setSyncProcessingModeUI,
} from './modules/options-dialog.js';
import {
    initKieMapping, clearTableMappingEligibility, updateTableMappingEligibility,
    fetchDocumentProfileForQueueItem, updateDocumentTypeSuggestion, isTableMappingRunBlocked,
    updateKieQueryFieldsAvailability, buildKieQueryFieldsPayload, updateContentFields,
} from './modules/kie-mapping.js';
import {
    initOverlayRender, renderDocumentWithAnnotations, renderTextPreview, highlightResultItem,
} from './modules/overlay-render.js';
import { renderQualityPanelPro, updateContentMappedRows } from './modules/result-panels/quality.js';
import { updateContentText } from './modules/result-panels/text.js';
import { initResultPanelsTables, updateContentTables } from './modules/result-panels/tables.js';
import { initResultPanelsFigures, updateContentFigures } from './modules/result-panels/figures.js';
import { updateEnhancementTabs, updateContentFormulas, updateContentSeals } from './modules/result-panels/enhance.js';
import { updateResultJson } from './modules/result-panels/json.js';
import { updateDemoTransactionViews } from './modules/result-panels/demo-transaction.js';
import {
    initPreviewNav, previewHelpers, resolveResultPageCount, syncPreviewPaginationControls,
    revokeCurrentPageImageUrl, switchToQueueItem, initPreviewPagination,
} from './modules/preview-nav.js';
import {
    initPreviewRender, getPdfPageImage, updatePreviewView, updateDocumentPreview,
    fetchAuthedImage, adjustDocumentSize,
} from './modules/preview-render.js';
import { initPipelineRun, startProcessing } from './modules/pipeline-run.js';
import {
    initPipelineResult, fetchTaskResult, fetchTaskBlocks, completeProcessing, clearResultsDisplay,
} from './modules/pipeline-result.js';
import {
    initUploadQueue, insertInitialSkeleton, initUploadZone, handleFiles, createQueueItem,
    handleQueueItemDeletion, updateQueueCount, resetQueueItemForReprocessing, simulateProcessing,
    processNextInQueue, failProcessing,
} from './modules/upload-queue.js';

// --- v1.8.3 B2: D6 <-> D7 cycle wired at module scope (before any runtime call) ---
initKieMapping({ getSelectedProcessingMode });

// --- v1.8.3 B3/B4: module dependency wiring (all at module scope, before any runtime call).
// Every cross-domain and same-domain-split call passes through these deps; §5.3 is the contract. ---
initOverlayRender({
    previewHelpers, resolveResultPageCount, syncPreviewPaginationControls,
    revokeCurrentPageImageUrl, getPdfPageImage, adjustDocumentSize,
    fetchTaskBlocks, updateContentText, initAnnotationInteractions,
});
initResultPanelsTables({ bindTableCardCsvExport });
initResultPanelsFigures({ fetchAuthedImage });

// D5 preview-paging (nav <-> render halves + D10/D7/mediator)
initPreviewNav({
    renderDocumentWithAnnotations, updateTableMappingEligibility, updateDocumentTypeSuggestion,
    renderResults: (r) => updateResultsDisplay(r),
    adjustDocumentSize, getPdfPageImage, updatePreviewView,
});
initPreviewRender({
    renderDocumentWithAnnotations, renderTextPreview,
    resolveResultPageCount, revokeCurrentPageImageUrl, syncPreviewPaginationControls,
});

// D8 pipeline (run <-> result halves + D1/D3/D5/D6/D7 + mediator)
initPipelineRun({
    checkApiReachable, applyHealthToFooter,
    failProcessing, resetQueueItemForReprocessing, simulateProcessing,
    previewHelpers, switchToQueueItem, getProcessingOptions, isTableMappingRunBlocked,
    clearResultsDisplay, fetchTaskResult,
});
initPipelineResult({
    failProcessing, handleQueueItemDeletion, processNextInQueue,
    previewHelpers, resolveResultPageCount,
    renderResults: (r) => updateResultsDisplay(r),
});

// D3 upload-queue (D5/D7/D8)
initUploadQueue({
    switchToQueueItem, previewHelpers, fetchDocumentProfileForQueueItem,
    clearResultsDisplay, completeProcessing, startProcessing,
});

document.addEventListener('DOMContentLoaded', () => {
    // Clear any existing results on page load
    clearResultsDisplay();

    // Initialize status bar
    updateStatusBar();

    // Check API connection
    initializeAPIConnection();

    initUploadZone();
    initTabs();
    initHelpButton();
    initResultTabs();
    initActionButtons();
    initAnalysisOptionsDialog({ clearTableMappingEligibility, updateKieQueryFieldsAvailability, buildKieQueryFieldsPayload, updateEnhancementTabs });
    initEngineSelectors();
    initAnalysisView();
    initExportButtons();
    initBatchProcessing({ getProcessingOptions });
    initHitlReviews();
    initPdfTools();
    initPreviewPagination();

    // Insert a lightweight skeleton placeholder to avoid initial flash
    if (typeof insertInitialSkeleton === 'function') {
        insertInitialSkeleton();
    }
});



/**
 * Create queue item element
 */
/**
 * Initialize navigation tabs
 */
function initTabs() {
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
function initHelpButton() {
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
function initResultTabs() {
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
function initActionButtons() {
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

/**
 * Initialize engine selectors
 */
function initEngineSelectors() {
    const ocrSelect = document.getElementById('dialogOcrEngineSelect');
    const layoutSelect = document.getElementById('dialogLayoutEngineSelect');

    if (ocrSelect) {
        ocrSelect.addEventListener('change', () => {
            refreshActiveEngineFooterLine();
            const engineNames = {
                paddleocr: 'PaddleOCR',
                tesseract: 'Tesseract 5.x',
                easyocr: 'EasyOCR'
            };
            const base = engineNames[ocrSelect.value] || ocrSelect.value;
            showNotification(`OCR engine changed to ${base}`, 'info');
        });
    }

    if (layoutSelect) {
        layoutSelect.addEventListener('change', () => {
            const engineNames = {
                'ppstructure': 'PP-StructureV3'
            };
            showNotification(`Layout engine changed to ${engineNames[layoutSelect.value]}`, 'info');
        });
    }
}


/**
 * Initialize analysis view
 */
function initAnalysisView() {
    // Start processing button
    const startBtn = document.getElementById('startProcessBtn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            startProcessing();
        });
    }
}

/**
 * Initialize export buttons
 */
function initExportButtons() {
    DocuVisionExport.init({
        getJobId: () => currentTaskId,
        buildUrl: (jobId, apiFormat) => `${API_BASE_URL}/tasks/${jobId}/export/${apiFormat}`,
        notify: showNotification,
        supportsAzure: true,
    });
}


/**
 * Update results display with actual data
 */
async function updateResultsDisplay(result) {
    if (!result) return;

    setLastRenderedAnalysisResult(result);

    // Reset cached blocks so the SVG overlay fetches fresh data.
    setLastFetchedBlocks(null);

    // Update document preview
    await updateDocumentPreview(result);

    // Update Content views
    updateContentText(result);
    updateContentTables(result);
    updateContentMappedRows(result);
    updateContentFigures(result);
    updateContentFormulas((result.view || {}).formulas || []);
    updateContentSeals((result.view || {}).seals || []);
    updateContentFields(result);

    // Update Result JSON view
    updateResultJson(result);

    // Quality, transactions, mapping preview (trial demo)
    renderQualityPanelPro(result);
    await updateDemoTransactionViews(result);
}







// Global tooltip instance
let globalTooltip = null;

/**
 * Initialize global tooltip
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
function initAnnotationInteractions() {
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
 * Initialize panel resize functionality
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
 * Initialize JSON view buttons
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

// Adjust document size on window resize
window.addEventListener('resize', () => {
    setTimeout(adjustDocumentSize, 100);
});



function initPdfTools() {
    const mergeInput = document.getElementById('pdfMergeFileInput');
    const mergeSelectBtn = document.getElementById('pdfMergeSelectBtn');
    const mergeBtn = document.getElementById('pdfMergeBtn');
    const mergeCount = document.getElementById('pdfMergeFileCount');
    const mergeStatus = document.getElementById('pdfMergeStatus');
    let mergeFiles = [];

    if (mergeSelectBtn && mergeInput) {
        mergeSelectBtn.addEventListener('click', () => mergeInput.click());
        mergeInput.addEventListener('change', () => {
            mergeFiles = Array.from(mergeInput.files || []);
            if (mergeCount) {
                mergeCount.textContent = mergeFiles.length
                    ? `${mergeFiles.length} PDF(s) selected`
                    : '';
            }
            if (mergeBtn) mergeBtn.disabled = mergeFiles.length < 2;
        });
    }

    mergeBtn?.addEventListener('click', async () => {
        if (mergeFiles.length < 2) {
            showNotification('Select at least two PDF files', 'warning');
            return;
        }
        try {
            if (mergeStatus) mergeStatus.textContent = 'Merging...';
            const formData = new FormData();
            mergeFiles.forEach(f => formData.append('files', f));
            const response = await fetch(`${API_ROOT_URL}/api/v1/pdf-tools/merge`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'merged.pdf';
            a.click();
            URL.revokeObjectURL(url);
            if (mergeStatus) mergeStatus.textContent = 'Download started: merged.pdf';
            showNotification('PDFs merged', 'success');
        } catch (error) {
            if (mergeStatus) mergeStatus.textContent = '';
            showNotification(`Merge failed: ${error.message}`, 'error');
        }
    });

    const metaInput = document.getElementById('pdfMetaFileInput');
    const metaSelectBtn = document.getElementById('pdfMetaSelectBtn');
    const metaBtn = document.getElementById('pdfMetaBtn');
    const metaCount = document.getElementById('pdfMetaFileCount');
    const metaResult = document.getElementById('pdfMetaResult');
    let metaFile = null;

    if (metaSelectBtn && metaInput) {
        metaSelectBtn.addEventListener('click', () => metaInput.click());
        metaInput.addEventListener('change', () => {
            metaFile = (metaInput.files && metaInput.files[0]) || null;
            if (metaCount) {
                metaCount.textContent = metaFile ? `1 PDF selected: ${metaFile.name}` : '';
            }
            if (metaBtn) metaBtn.disabled = !metaFile;
        });
    }

    metaBtn?.addEventListener('click', async () => {
        if (!metaFile) return;
        try {
            const formData = new FormData();
            formData.append('file', metaFile);
            const response = await fetch(`${API_ROOT_URL}/api/v1/pdf-tools/metadata`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (metaResult) metaResult.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            if (metaResult) metaResult.textContent = `Failed: ${error.message}`;
        }
    });

    const splitInput = document.getElementById('pdfSplitFileInput');
    const splitSelectBtn = document.getElementById('pdfSplitSelectBtn');
    const splitBtn = document.getElementById('pdfSplitBtn');
    const splitCount = document.getElementById('pdfSplitFileCount');
    const splitPageInput = document.getElementById('pdfSplitPageInput');
    let splitFile = null;

    if (splitSelectBtn && splitInput) {
        splitSelectBtn.addEventListener('click', () => splitInput.click());
        splitInput.addEventListener('change', () => {
            splitFile = (splitInput.files && splitInput.files[0]) || null;
            if (splitCount) {
                splitCount.textContent = splitFile ? `1 PDF selected: ${splitFile.name}` : '';
            }
            if (splitBtn) splitBtn.disabled = !splitFile;
        });
    }

    splitBtn?.addEventListener('click', async () => {
        if (!splitFile) return;
        const pageNum = parseInt(splitPageInput?.value || '1', 10) || 1;
        try {
            const formData = new FormData();
            formData.append('file', splitFile);
            formData.append('pages', JSON.stringify([pageNum]));
            const response = await fetch(`${API_ROOT_URL}/api/v1/pdf-tools/split`, {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('application/pdf')) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `page_${pageNum}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
                showNotification('Page downloaded', 'success');
            } else {
                const data = await response.json();
                showNotification(`Split returned ${data.count} page(s) (server paths only)`, 'info');
            }
        } catch (error) {
            showNotification(`Split failed: ${error.message}`, 'error');
        }
    });
}





