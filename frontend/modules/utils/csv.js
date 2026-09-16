/**
 * csv.js - Pure CSV / Markdown cell formatting helpers.
 *
 * Extracted verbatim from app.js in v1.8.3 B0b (no behaviour change).
 */

/**
 * Convert to CSV format
 */
export function convertToCSV(data) {
    return data.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
}

/**
 * Convert to Markdown format
 */
export function convertToMarkdown(data) {
    let md = `# ${data.document.name}\n\n`;
    md += `**Processed At**: ${data.document.processedAt}\n\n`;
    md += `**Total Pages**: ${data.document.pages}\n\n`;

    md += `## Document Structure\n\n`;
    md += `- Headers: ${data.layout.headers}\n`;
    md += `- Titles: ${data.layout.titles}\n`;
    md += `- Paragraphs: ${data.layout.paragraphs}\n`;
    md += `- Tables: ${data.layout.tables}\n`;
    md += `- Figures: ${data.layout.figures}\n\n`;

    md += `## Extracted Tables\n\n`;
    if (data.tables.length > 0) {
        const table = data.tables[0];
        md += `### ${table.name}\n\n`;
        md += '| ' + table.data[0].join(' | ') + ' |\n';
        md += '| ' + table.data[0].map(() => '---').join(' | ') + ' |\n';
        table.data.slice(1).forEach(row => {
            md += '| ' + row.join(' | ') + ' |\n';
        });
    }

    md += `\n## Keywords\n\n`;
    md += data.keywords.map(k => `- ${k}`).join('\n');

    return md;
}

/**
 * Table confidence as a 0-100 integer.
 * Prefers table.confidence (layout detector, typically 0-1); falls back to table.score.
 * Values in [0, 1] are ratios; values > 1 are treated as already-percent.
 */
export function tableConfidencePct(table) {
    let raw = table && table.confidence;
    if (raw == null) raw = table && table.score;
    const val = Number(raw);
    if (!Number.isFinite(val)) return 0;
    if (val >= 0 && val <= 1) return Math.round(val * 100);
    return Math.round(val);
}

export function formatTableCsvBanner(index1, table) {
    const page = table && table.page != null ? table.page : '?';
    return `=== Table ${index1} (Page ${page}) confidence=${tableConfidencePct(table)}% ===`;
}

export function excelSafeCell(cell) {
    const s = cell == null ? '' : String(cell);
    if (!s) return s;
    const first = s.charAt(0);
    if (first === '=' || first === '+' || first === '@' || first === '\t' || first === '\r') {
        return "'" + s;
    }
    if (first === '-') {
        const n = Number(s.replace(/,/g, ''));
        if (!Number.isFinite(n)) return "'" + s;
    }
    return s;
}

export function escapeCsvCell(cell) {
    const s = excelSafeCell(cell);
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
}

export function buildSingleTableCsv(table, index1) {
    const lines = [formatTableCsvBanner(index1, table)];
    const cap = table && table.caption ? String(table.caption).trim() : '';
    if (cap) lines.push(escapeCsvCell('Caption: ' + cap));
    const rows = (table && table.data) || [];
    for (let i = 0; i < rows.length; i++) {
        const row = Array.isArray(rows[i]) ? rows[i] : [rows[i]];
        lines.push(row.map(escapeCsvCell).join(','));
    }
    return lines.join('\r\n');
}

export function singleTableCsvFilename(index1, page) {
    const n = String(index1).padStart(2, '0');
    const p = page == null || page === '' ? '?' : page;
    return `table_${n}_p${p}.csv`;
}
