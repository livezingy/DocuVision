/**
 * Shell tools (v1.8.3 B5a) - domain module (D4, tools half).
 *
 * View-level tooling: engine selectors, analysis view wiring, export buttons,
 * the PDF tools page (merge / metadata / split). No cross-half calls into ui.js.
 * The single cross-domain call (D1 refreshActiveEngineFooterLine) is injected at
 * boot; everything else is a whitelist import or a classic-script global
 * (DocuVisionExport from shared/export-ui.js).
 */
import { showNotification } from '../notifications.js';
import { API_BASE_URL, API_ROOT_URL } from '../api-config.js';
import { currentTaskId } from '../preview-state.js';

// --- cross-domain deps, injected at boot ---
let refreshActiveEngineFooterLine = function () {};

/**
 * Wire shell-tools dependencies (app.js assembly).
 */
export function initShellTools(deps = {}) {
    if (typeof deps.refreshActiveEngineFooterLine === 'function') refreshActiveEngineFooterLine = deps.refreshActiveEngineFooterLine;
}

/**
 * Initialize engine selectors
 */
export function initEngineSelectors() {
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
export function initAnalysisView() {
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
export function initExportButtons() {
    DocuVisionExport.init({
        getJobId: () => currentTaskId,
        buildUrl: (jobId, apiFormat) => `${API_BASE_URL}/tasks/${jobId}/export/${apiFormat}`,
        notify: showNotification,
        supportsAzure: true,
    });
}

export function initPdfTools() {
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
