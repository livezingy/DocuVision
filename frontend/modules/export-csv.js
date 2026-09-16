/**
 * CSV export (v1.8.3 B1b) - domain module (D12).
 *
 * NOTE (2026-09-15): `exportResults` (the app.js version) currently has no call sites -
 * the export UI uses the classic `shared/export-ui.js` (DocuVisionExport) instead. Kept for
 * domain completeness; candidate for v1.9 review. The other three functions are live via
 * bindTableCardCsvExport (called by the result panels).
 */
import { currentTaskId } from './preview-state.js';
import { API_BASE_URL } from './api-config.js';
import { showNotification } from './notifications.js';
import { buildSingleTableCsv, singleTableCsvFilename } from './utils/csv.js';

/**
 * Export results via backend /tasks/{task_id}/export/{format}
 */
export async function exportResults(format) {
    return DocuVisionExport.exportResults(format, {
        getJobId: () => currentTaskId,
        buildUrl: (jobId, apiFormat) => `${API_BASE_URL}/tasks/${jobId}/export/${apiFormat}`,
        notify: showNotification,
        supportsAzure: true,
    });
}

export function downloadCurrentTableCsv() {
    const tables = window.currentTables || [];
    const idx = typeof window.currentTableIndex === 'number' ? window.currentTableIndex : 0;
    const table = tables[idx];
    if (!table) return;
    const n = idx + 1;
    const csv = buildSingleTableCsv(table, n);
    downloadFile('\uFEFF' + csv, singleTableCsvFilename(n, table.page), 'text/csv;charset=utf-8');
}

export function bindTableCardCsvExport(root) {
    if (!root || root.dataset.csvExportBound === '1') return;
    root.dataset.csvExportBound = '1';
    root.addEventListener('click', function (e) {
        const btn = e.target.closest('.table-action-btn');
        if (!btn) return;
        e.preventDefault();
        downloadCurrentTableCsv();
    });
}

/**
 * Download file
 */
export function downloadFile(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
