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
    initPreviewNav, switchToQueueItem, initPreviewPagination,
} from './modules/preview-paging/nav.js';
import {
    initPreviewRender, updateDocumentPreview, fetchAuthedImage,
} from './modules/preview-paging/render.js';
import {
    previewHelpers, resolveResultPageCount, syncPreviewPaginationControls,
    revokeCurrentPageImageUrl, getPdfPageImage, adjustDocumentSize,
} from './modules/preview-paging/core.js';
import { initPipelineRun, startProcessing } from './modules/pipeline/run.js';
import {
    initPipelineResult, fetchTaskBlocks, completeProcessing, clearResultsDisplay,
} from './modules/pipeline/result.js';
import {
    initUploadQueue, insertInitialSkeleton, initUploadZone, handleFiles, createQueueItem,
    handleQueueItemDeletion, updateQueueCount, resetQueueItemForReprocessing, simulateProcessing,
    processNextInQueue, failProcessing,
} from './modules/upload-queue.js';
import {
    initShellUi, initTabs, initHelpButton, initResultTabs, initActionButtons,
    initAnnotationInteractions,
} from './modules/shell/ui.js';
import {
    initShellTools, initEngineSelectors, initAnalysisView, initExportButtons, initPdfTools,
} from './modules/shell/tools.js';

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

// D5 preview-paging (nav / render halves over the shared core base + D10/D7/mediator;
// same-domain deps are same-directory sibling imports, not injections)
initPreviewNav({
    renderDocumentWithAnnotations, updateTableMappingEligibility, updateDocumentTypeSuggestion,
    renderResults: (r) => updateResultsDisplay(r),
});
initPreviewRender({ renderDocumentWithAnnotations, renderTextPreview });

// D8 pipeline (run / result halves + D1/D3/D5/D6/D7 + mediator; run -> result is a
// same-directory sibling import)
initPipelineRun({
    checkApiReachable, applyHealthToFooter,
    failProcessing, resetQueueItemForReprocessing, simulateProcessing,
    previewHelpers, switchToQueueItem, getProcessingOptions, isTableMappingRunBlocked,
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

// D4 shell (ui / tools halves; every D1/D6/D7/D8/D9/D10/D15 call is injected - the
// shell modules may not import sibling domain modules, and D6-D10 are all extracted)
initShellUi({
    startProcessing, openAnalysisOptionsDialog,
    clearTableMappingEligibility, updateTableMappingEligibility, updateKieQueryFieldsAvailability,
    updateEnhancementTabs, refreshHitlReviews, highlightResultItem, setSyncProcessingModeUI,
});
initShellTools({ refreshActiveEngineFooterLine });

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
