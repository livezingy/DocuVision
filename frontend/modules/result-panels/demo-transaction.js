/**
 * Demo transaction table (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js; no imports (the DocuVisionDemo / window.DocuVisionUiFeatures
 * globals are the pre-existing integration points).
 */

export function renderDemoTransactionTable(containerId, rows, emptyMsg) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    if (!rows || !rows.length) {
        container.innerHTML = `<p class="empty-state">${emptyMsg}</p>`;
        return;
    }
    const headers = ['date', 'description', 'amount', 'internal_code', 'internal_label'];
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
    rows.forEach(tx => {
        const tr = document.createElement('tr');
        headers.forEach(h => {
            const td = document.createElement('td');
            td.textContent = tx[h] ?? '—';
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
}

export async function updateDemoTransactionViews(result) {
    const features = window.DocuVisionUiFeatures;
    if (
        !features
        || (!features.isContentTabEnabled('transactions') && !features.isContentTabEnabled('mapped'))
    ) {
        return;
    }
    if (!window.DocuVisionDemo || !result) {
        if (features.isContentTabEnabled('transactions')) {
            renderDemoTransactionTable('contentTransactionsList', [], 'No transactions.');
        }
        if (features.isContentTabEnabled('mapped')) {
            renderDemoTransactionTable('contentMappedList', [], 'No mapped transactions.');
        }
        return;
    }
    try {
        const enriched = await DocuVisionDemo.enrichResult(result);
        if (features.isContentTabEnabled('transactions')) {
            renderDemoTransactionTable('contentTransactionsList', enriched.transactions, 'No transaction rows detected.');
        }
        if (features.isContentTabEnabled('mapped')) {
            renderDemoTransactionTable('contentMappedList', enriched.mapped_transactions, 'No mapped transactions.');
        }
    } catch (error) {
        console.warn('[Demo] Transaction preview failed:', error);
        if (features.isContentTabEnabled('transactions')) {
            renderDemoTransactionTable('contentTransactionsList', [], 'No transaction rows detected.');
        }
        if (features.isContentTabEnabled('mapped')) {
            renderDemoTransactionTable('contentMappedList', [], 'No mapped transactions.');
        }
    }
}
