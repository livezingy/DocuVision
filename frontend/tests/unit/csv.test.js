/**
 * Unit tests for modules/utils/csv.js (v1.8.3 B0b extraction).
 *
 * Locks the CSV/Markdown formatting contract: Excel-safe prefixes, RFC4180 quoting,
 * single-table assembly and the sidebar banner format consumed by the export UI.
 */
import { describe, it, expect } from 'vitest';
import {
    convertToCSV,
    convertToMarkdown,
    tableConfidencePct,
    formatTableCsvBanner,
    excelSafeCell,
    escapeCsvCell,
    buildSingleTableCsv,
    singleTableCsvFilename,
} from '../../modules/utils/csv.js';

describe('convertToCSV', () => {
    it('quotes every cell and joins rows with newlines', () => {
        expect(convertToCSV([['a', 'b'], ['c', 'd']])).toBe('"a","b"\n"c","d"');
    });
});

describe('tableConfidencePct', () => {
    it('treats 0-1 ratios as percentages', () => {
        expect(tableConfidencePct({ confidence: 0.87 })).toBe(87);
        expect(tableConfidencePct({ confidence: 1 })).toBe(100);
    });

    it('treats values above 1 as already-percent and falls back to score', () => {
        expect(tableConfidencePct({ confidence: 87 })).toBe(87);
        expect(tableConfidencePct({ score: 42 })).toBe(42);
    });

    it('returns 0 for missing or non-numeric input', () => {
        expect(tableConfidencePct({})).toBe(0);
        expect(tableConfidencePct(null)).toBe(0);
        expect(tableConfidencePct({ confidence: 'x' })).toBe(0);
    });
});

describe('formatTableCsvBanner', () => {
    it('renders the banner with page and confidence', () => {
        expect(formatTableCsvBanner(1, { page: 2, confidence: 0.87 }))
            .toBe('=== Table 1 (Page 2) confidence=87% ===');
    });

    it('falls back to ? when the page is unknown', () => {
        expect(formatTableCsvBanner(3, { confidence: 1 }))
            .toBe('=== Table 3 (Page ?) confidence=100% ===');
    });
});

describe('excelSafeCell', () => {
    it('prefixes formula-like cells with an apostrophe', () => {
        expect(excelSafeCell('=SUM(A1)')).toBe("'=SUM(A1)");
        expect(excelSafeCell('+1')).toBe("'+1");
        expect(excelSafeCell('@x')).toBe("'@x");
    });

    it('keeps negative numbers but escapes non-numeric minus text', () => {
        expect(excelSafeCell('-1')).toBe('-1');
        expect(excelSafeCell('-1,2')).toBe('-1,2');
        expect(excelSafeCell('-abc')).toBe("'-abc");
    });

    it('returns an empty string for null', () => {
        expect(excelSafeCell(null)).toBe('');
    });
});

describe('escapeCsvCell', () => {
    it('quotes cells containing separators and doubles inner quotes', () => {
        expect(escapeCsvCell('a,b')).toBe('"a,b"');
        expect(escapeCsvCell('say "hi"')).toBe('"say ""hi"""');
        expect(escapeCsvCell('plain')).toBe('plain');
    });
});

describe('buildSingleTableCsv', () => {
    it('emits the banner, the optional caption and CRLF-joined rows', () => {
        const csv = buildSingleTableCsv({
            data: [['h1', 'h2'], ['v1', 'v2']],
            page: 1,
            confidence: 1,
            caption: 'Cap',
        }, 2);
        expect(csv).toBe([
            '=== Table 2 (Page 1) confidence=100% ===',
            'Caption: Cap',
            'h1,h2',
            'v1,v2',
        ].join('\r\n'));
    });
});

describe('singleTableCsvFilename', () => {
    it('zero-pads the table index and embeds the page', () => {
        expect(singleTableCsvFilename(1, 3)).toBe('table_01_p3.csv');
    });

    it('uses ? when the page is unknown', () => {
        expect(singleTableCsvFilename(2, null)).toBe('table_02_p?.csv');
    });
});

describe('convertToMarkdown', () => {
    it('renders document metadata, the first table and keywords', () => {
        const md = convertToMarkdown({
            document: { name: 'Doc', processedAt: 'when', pages: 2 },
            layout: { headers: 1, titles: 2, paragraphs: 3, tables: 1, figures: 0 },
            tables: [{ name: 'T1', data: [['a', 'b'], ['1', '2']] }],
            keywords: ['k1'],
        });
        expect(md).toContain('# Doc');
        expect(md).toContain('**Processed At**: when');
        expect(md).toContain('### T1');
        expect(md).toContain('| a | b |');
        expect(md).toContain('| --- | --- |');
        expect(md).toContain('- k1');
    });
});
