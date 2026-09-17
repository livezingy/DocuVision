/**
 * Tables panel (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js. The only non-whitelisted cross-domain dependency is
 * D12's bindTableCardCsvExport (called at the end of updateContentTables); it is
 * injected at boot via the same-name module-scope binding trick, keeping the call
 * site byte-identical. app.js wires `initResultPanelsTables({ bindTableCardCsvExport })`.
 */
import { escapeHtml } from '../utils/dom.js';
import { normalizeTextForDisplay } from '../utils/text.js';
import { tableConfidencePct } from '../utils/csv.js';

let bindTableCardCsvExport = function () {};

/**
 * Wire the cross-domain dependency from D12 export-csv (app.js assembly).
 */
export function initResultPanelsTables(deps = {}) {
    if (typeof deps.bindTableCardCsvExport === 'function') {
        bindTableCardCsvExport = deps.bindTableCardCsvExport;
    }
}

/**
 * Render a single table card with proper merge cell support
 * Only renders table content, not other page content
 */
export function renderTableCard(table, index, total) {
    const tableData = table.data || [];
    const page = table.page || '?';
    const confidencePct = tableConfidencePct(table);
    const tableCaption = String(table.caption || '').trim();
    const tableHtml = table.html || null;
    const htmlStructure = table.html_structure || null;

    let html = '<div class="table-card">';
    html += '<div class="table-card-header">';
    html += `<span class="table-name">Table ${index + 1}${total > 1 ? ` of ${total}` : ''}${page !== '?' ? ` (Page ${page})` : ''}`;
    if (confidencePct > 0) {
        html += ` <span style="font-size: 0.75rem; color: var(--text-tertiary);">Confidence: ${confidencePct}%</span>`;
    }
    html += '</span>';
    if (tableCaption) {
        html += `<span class="table-caption-label" title="${escapeHtml(tableCaption)}" style="font-size:0.75rem;color:var(--text-secondary);font-weight:400;max-width:60%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(tableCaption)}</span>`;
    }
    html += '<div class="table-actions">';
    html += '<button type="button" class="table-action-btn" title="Export CSV">';
    html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">';
    html += '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>';
    html += '<polyline points="7 10 12 15 17 10"></polyline>';
    html += '<line x1="12" y1="15" x2="12" y2="3"></line>';
    html += '</svg></button></div></div>';
    html += '<div class="table-preview" style="overflow-x: auto;">';

    let tableRendered = false;

    // Strategy 1: Use HTML structure if available (most reliable)
    if (!tableRendered && htmlStructure && htmlStructure.rows && htmlStructure.rows.length > 0) {
        html += '<table class="extracted-table">';
        let inThead = false;
        let inTbody = false;

        htmlStructure.rows.forEach((row, rowIdx) => {
            const isHeaderRow = row.cells.some(c => c.is_header);

            if (rowIdx === 0 && isHeaderRow && !inThead) {
                html += '<thead>';
                inThead = true;
            } else if (rowIdx === 0 && !isHeaderRow && !inTbody) {
                html += '<tbody>';
                inTbody = true;
            } else if (rowIdx > 0 && inThead && !isHeaderRow) {
                html += '</thead><tbody>';
                inThead = false;
                inTbody = true;
            } else if (rowIdx > 0 && !inTbody) {
                html += '<tbody>';
                inTbody = true;
            }

            html += '<tr>';
            row.cells.forEach(cell => {
                const tag = cell.is_header ? 'th' : 'td';
                const attrs = [];
                if (cell.rowspan > 1) attrs.push(`rowspan="${cell.rowspan}"`);
                if (cell.colspan > 1) attrs.push(`colspan="${cell.colspan}"`);
                const attrStr = attrs.length > 0 ? ' ' + attrs.join(' ') : '';
                const cellText = normalizeTextForDisplay(cell.text || '');
                html += `<${tag}${attrStr}>${escapeHtml(cellText)}</${tag}>`;
            });
            html += '</tr>';
        });

        if (inThead) html += '</thead>';
        if (inTbody) html += '</tbody>';
        html += '</table>';
        tableRendered = true;
    }

    // Strategy 2: Parse and clean HTML (only extract table element, ignore all other content)
    if (!tableRendered && tableHtml) {
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(tableHtml, 'text/html');
            const tableElement = doc.querySelector('table');
            if (tableElement) {
                // Clone table and add class
                const cleanTable = tableElement.cloneNode(true);
                cleanTable.className = 'extracted-table';
                // Remove any text nodes or elements outside of table cells
                // Only keep tr, th, td elements
                const rows = cleanTable.querySelectorAll('tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td, th');
                    cells.forEach(cell => {
                        // Remove nested tables if any
                        const nestedTables = cell.querySelectorAll('table');
                        nestedTables.forEach(nt => nt.remove());
                        // Normalize text in cells
                        const cellText = cell.textContent || '';
                        const normalizedText = normalizeTextForDisplay(cellText.trim());
                        cell.textContent = normalizedText;
                    });
                });
                html += cleanTable.outerHTML;
                tableRendered = true;
            } else {
                // No table tag found in HTML, this is invalid - skip to data array
                console.warn('Table HTML does not contain <table> tag, using data array instead');
            }
        } catch (e) {
            console.warn('Failed to parse table HTML:', e);
        }
    }

    // Strategy 3: Render from data array (validate it looks like a table)
    if (!tableRendered && tableData.length > 0 && Array.isArray(tableData[0])) {
        // Filter out empty rows and validate table structure
        const validRows = tableData.filter(row => {
            if (!Array.isArray(row)) return false;
            // Check if row has reasonable number of cells (2-20 columns typical for tables)
            const cellCount = row.filter(cell => cell && String(cell).trim()).length;
            return cellCount >= 2 && cellCount <= 20;
        });

        // Additional validation: check if data looks like a table
        // Tables typically have consistent column counts across rows
        if (validRows.length > 0) {
            const firstRowCols = validRows[0].length;
            const consistentRows = validRows.filter(row => {
                const rowCols = row.length;
                // Allow some variation (within 2 columns) for merged cells
                return Math.abs(rowCols - firstRowCols) <= 2;
            });

            // Only render if we have at least 2 rows with consistent structure
            if (consistentRows.length >= 2) {
                html += '<table class="extracted-table">';
                const hasHeaders = consistentRows.length > 1 &&
                    consistentRows[0].every(cell => cell && String(cell).trim()) &&
                    consistentRows[0].length <= 15; // Reasonable header count

                if (hasHeaders && consistentRows.length > 1) {
                    html += '<thead><tr>';
                    consistentRows[0].forEach(cell => {
                        const cellText = normalizeTextForDisplay(String(cell || ''));
                        html += `<th>${escapeHtml(cellText)}</th>`;
                    });
                    html += '</tr></thead><tbody>';
                    consistentRows.slice(1).forEach(row => {
                        if (Array.isArray(row)) {
                            html += '<tr>';
                            row.forEach(cell => {
                                const cellText = normalizeTextForDisplay(String(cell || ''));
                                html += `<td>${escapeHtml(cellText)}</td>`;
                            });
                            html += '</tr>';
                        }
                    });
                    html += '</tbody>';
                } else {
                    html += '<tbody>';
                    consistentRows.forEach(row => {
                        if (Array.isArray(row)) {
                            html += '<tr>';
                            row.forEach(cell => {
                                const cellText = normalizeTextForDisplay(String(cell || ''));
                                html += `<td>${escapeHtml(cellText)}</td>`;
                            });
                            html += '</tr>';
                        }
                    });
                    html += '</tbody>';
                }
                html += '</table>';
                tableRendered = true;
            }
        }
    }

    // If nothing rendered, show empty state
    if (!tableRendered) {
        html += '<div class="empty-state" style="padding: 20px; text-align: center; color: var(--text-tertiary);">No table data available</div>';
    }

    html += '</div></div>';
    return html;
}

/**
 * Normalize table dict for display (core/Lite may use headers+rows without data grid).
 */
export function normalizeTableForDisplay(table) {
    if (!table || typeof table !== 'object') return table;
    const data = table.data;
    if (Array.isArray(data) && data.length > 0) {
        return table;
    }
    const headers = Array.isArray(table.headers) ? table.headers : [];
    const rows = Array.isArray(table.rows) ? table.rows : [];
    if (!headers.length && !rows.length) {
        return table;
    }
    const grid = headers.length ? [headers, ...rows] : rows;
    return { ...table, data: grid };
}

/**
 * Update Content Tables view
 */
export function updateContentTables(result) {
    const contentTableList = document.getElementById('contentTableList');
    if (!contentTableList) return;

    // Render extracted tables (or fallback layout-derived tables) into contentTableList
    let extractedTables = (result.tables || []).map(normalizeTableForDisplay);

    // Fallback: Layout-only mode can contain table HTML in result.layout.elements
    if (extractedTables.length === 0) {
        const layoutTables = (result.layout?.elements || []).filter(el => {
            const t = String(el.type || el.element_type || '').toLowerCase();
            return t === 'table' && !!el.html;
        });

        if (layoutTables.length > 0) {
            extractedTables = layoutTables.map((el, idx) => ({
                id: el.id || el.element_id || `layout_table_${idx + 1}`,
                page: el.page || el.page_number || 1,
                html: el.html,
                data: el.data || [],
                rows: el.rows || 0,
                columns: el.columns || 0,
                confidence: typeof el.confidence === 'number' ? el.confidence : null,
                score: el.score,
                caption: el.caption || el.text || '',
                bbox: el.bbox || null,
            }));
        }
    }

    if (extractedTables.length === 0) {
        contentTableList.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-tertiary);">No tables extracted</div>';
        return;
    }

    // Store tables data globally for navigation
    window.currentTables = extractedTables.map((table, idx) => ({
        id: table.id || `table_${idx + 1}`,
        data: table.data || [],
        html: table.html || null,
        html_structure: table.html_structure || null,
        page: table.page || table.page_number || '?',
        rows: table.rows || 0,
        columns: table.columns || 0,
        confidence: typeof table.confidence === 'number' ? table.confidence : null,
        score: table.score,
        caption: table.caption || ''
    }));

    window.currentTableIndex = 0;

    let html = '';
    if (window.currentTables.length > 1) {
        html += '<div class="table-navigation" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding: 12px; background: var(--bg-tertiary); border-radius: var(--radius-md);">';
        html += '<button class="table-nav-btn" id="contentPrevTableBtn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast);">';
        html += '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="15 18 9 12 15 6"></polyline></svg>';
        html += 'Previous</button>';
        html += `<span style="color: var(--text-primary); font-weight: 500;">Table <span id="contentCurrentTableIndex">1</span> of ${window.currentTables.length}</span>`;
        html += '<button class="table-nav-btn" id="contentNextTableBtn" style="display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: var(--bg-elevated); border: 1px solid var(--border-default); border-radius: var(--radius-sm); color: var(--text-secondary); cursor: pointer; transition: all var(--transition-fast);">';
        html += 'Next<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="9 18 15 12 9 6"></polyline></svg></button>';
        html += '</div>';
    }

    html += renderTableCard(window.currentTables[0], 0, window.currentTables.length);
    contentTableList.innerHTML = html;

    // Add navigation event listeners
    if (window.currentTables.length > 1) {
        const prevBtn = document.getElementById('contentPrevTableBtn');
        const nextBtn = document.getElementById('contentNextTableBtn');
        const currentIndexSpan = document.getElementById('contentCurrentTableIndex');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (window.currentTableIndex > 0) {
                    window.currentTableIndex--;
                    currentIndexSpan.textContent = window.currentTableIndex + 1;
                    const tableCard = contentTableList.querySelector('.table-card');
                    if (tableCard) {
                        tableCard.outerHTML = renderTableCard(window.currentTables[window.currentTableIndex], window.currentTableIndex, window.currentTables.length);
                    }
                    updateContentNavButtons();
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (window.currentTableIndex < window.currentTables.length - 1) {
                    window.currentTableIndex++;
                    currentIndexSpan.textContent = window.currentTableIndex + 1;
                    const tableCard = contentTableList.querySelector('.table-card');
                    if (tableCard) {
                        tableCard.outerHTML = renderTableCard(window.currentTables[window.currentTableIndex], window.currentTableIndex, window.currentTables.length);
                    }
                    updateContentNavButtons();
                }
            });
        }

        function updateContentNavButtons() {
            if (prevBtn) {
                prevBtn.disabled = window.currentTableIndex === 0;
                prevBtn.style.opacity = window.currentTableIndex === 0 ? '0.5' : '1';
                prevBtn.style.cursor = window.currentTableIndex === 0 ? 'not-allowed' : 'pointer';
            }
            if (nextBtn) {
                nextBtn.disabled = window.currentTableIndex === window.currentTables.length - 1;
                nextBtn.style.opacity = window.currentTableIndex === window.currentTables.length - 1 ? '0.5' : '1';
                nextBtn.style.cursor = window.currentTableIndex === window.currentTables.length - 1 ? 'not-allowed' : 'pointer';
            }
        }

        updateContentNavButtons();
    }

    bindTableCardCsvExport(contentTableList);
}
