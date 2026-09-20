/**
 * Quality / mapped-rows panels (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js; only imports the utils whitelist.
 */
import { escapeHtml } from '../utils/dom.js';

/**
 * Render quality / warnings for Pro results
 */
export function renderQualityPanelPro(result) {
    const panel = document.getElementById('qualityPanel');
    if (!panel) return;
    if (!result) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
        return;
    }
    const quality = result.quality || {};
    const kieAttempted = quality.kie_attempted === true
        || (quality.kie_stage && !['skipped', 'disabled', ''].includes(String(quality.kie_stage)));
    const backfill = quality.table_backfill;
    const hasBackfill = backfill && backfill.enabled === true && backfill.cells_candidates > 0;

    if (!kieAttempted && !hasBackfill) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
        return;
    }

    // P-007 (v1.9 S1, plan B): summary lines only when confidence was really measured.
    // The orchestrator (document_pipeline_orchestrator.py) guarantees kie_confidence_source
    // is non-empty only on attempted && succeeded, so failure paths (runtime_error /
    // skipped_doc_type, all attempted=True) no longer show a misleading "0%".
    // Gating on kieAttempted alone would keep the "0%" row on those failure paths.
    const hasKieConfidence = String(quality.kie_confidence_source ?? '') !== '';

    // KIE warning blocks stay gated on kieAttempted: failure / skip reasons are useful
    // to the user, but non-KIE layout tasks show no KIE meta at all.
    const warnings = [];
    if (kieAttempted) {
        if (quality.kie_error_message) {
            warnings.push({ code: 'kie_error', message: quality.kie_error_message });
        }
        if (quality.kie_production_hit === false && quality.kie_production_reason) {
            warnings.push({ code: 'kie_production', message: quality.kie_production_reason });
        }
    }

    const summaryParts = [];
    if (hasKieConfidence) {
        const kieScore = quality.kie_confidence_avg != null
            ? `${Math.round(quality.kie_confidence_avg * 100)}%`
            : '—';
        summaryParts.push(`KIE confidence: ${kieScore}`);
        summaryParts.push(`KIE fields: ${quality.kie_fields_count ?? '—'}`);
    }
    const tableCount = (result.view?.tables || []).length;
    if (tableCount > 0) {
        summaryParts.push(`Tables: ${tableCount}`);
    }
    if (hasBackfill) {
        const backfillPct = backfill.backfill_rate != null
            ? `${Math.round(backfill.backfill_rate * 100)}%`
            : '—';
        summaryParts.push(`Backfill: ${backfill.cells_backfilled}/${backfill.cells_candidates} (${backfillPct})`);
    }

    const warnHtml = warnings.map(w =>
        `<div class="quality-warn">⚠ ${escapeHtml(w.code)}: ${escapeHtml(w.message)}</div>`
    ).join('');

    if (!summaryParts.length && !warnHtml) {
        panel.classList.add('hidden');
        panel.innerHTML = '';
        return;
    }

    const summaryHtml = summaryParts.length
        ? `<div class="quality-score">${summaryParts.join(' · ')}</div>`
        : '';
    panel.innerHTML = `${summaryHtml}${warnHtml}`;
    panel.classList.remove('hidden');
}

const TABLE_TEMPLATE_COLUMNS = {
    bank_statement: ['transaction_date', 'description', 'amount', 'balance'],
    invoice_line_items: ['line_description', 'quantity', 'unit_price', 'line_total'],
};

export function renderSchemaTable(containerId, rows, columns, emptyMsg, metaColumns) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    const safeRows = Array.isArray(rows) ? rows : [];
    const safeColumns = Array.isArray(columns) ? columns : [];
    if (!safeRows.length) {
        container.innerHTML = `<p class="empty-state">${escapeHtml(emptyMsg || 'No rows.')}</p>`;
        return;
    }
    const meta = Array.isArray(metaColumns) ? metaColumns : [];
    const headers = [...safeColumns, ...meta];
    const table = document.createElement('table');
    table.className = 'extracted-table';
    const thead = document.createElement('thead');
    const hr = document.createElement('tr');
    headers.forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    safeRows.forEach(row => {
        const tr = document.createElement('tr');
        headers.forEach(h => {
            const td = document.createElement('td');
            const val = row && row[h] != null && String(row[h]).trim() !== '' ? row[h] : '—';
            td.textContent = val;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
}

export function updateContentMappedRows(result) {
    const tabBtn = document.getElementById('tabBtnMapped');
    const rows = Array.isArray(result?.mapped_table_rows) ? result.mapped_table_rows : [];
    const template = String(result?.table_template || '').trim().toLowerCase();
    const hasRows = rows.length > 0;

    if (tabBtn) {
        tabBtn.classList.toggle('hidden', !hasRows);
    }

    const container = document.getElementById('contentMappedList');
    if (!container) return;

    if (!hasRows) {
        renderSchemaTable(
            'contentMappedList',
            [],
            TABLE_TEMPLATE_COLUMNS[template] || [],
            template
                ? 'No mapped rows. Check table headers match the template aliases or enable Table extraction.'
                : 'Select a table vertical template in Analysis Options to map rows to a unified schema.'
        );
        return;
    }

    const columns = TABLE_TEMPLATE_COLUMNS[template];
    const fieldKeys = columns || Object.keys(rows[0] || {}).filter(
        k => !['template', 'source_table_index', 'page', 'row_index', 'file_name'].includes(k)
    );
    container.innerHTML = '';
    if (template) {
        const note = document.createElement('p');
        note.className = 'kie-meta-line';
        note.innerHTML = `Template: <strong>${escapeHtml(template)}</strong> · ${rows.length} row(s)`;
        container.appendChild(note);
    }
    const tableWrap = document.createElement('div');
    tableWrap.id = 'contentMappedTableWrap';
    container.appendChild(tableWrap);
    renderSchemaTable(
        'contentMappedTableWrap',
        rows,
        fieldKeys,
        'No mapped rows.',
        ['page', 'source_table_index']
    );
}
