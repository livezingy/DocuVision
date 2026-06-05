import { describe, it, expect, beforeEach } from 'vitest';
import {
    resolveDocumentPageCount,
    pickProcessingTarget,
    normalizePreviewPage,
    formatCompletedStatus,
    findNextQueueItem,
} from '../../shared/queue_preview.js';

function makeQueueItem(statusClass) {
    const el = document.createElement('div');
    el.className = `queue-item ${statusClass}`;
    return el;
}

describe('resolveDocumentPageCount', () => {
    it('uses document_info.pages when positive', () => {
        expect(resolveDocumentPageCount({ document_info: { pages: 3 } })).toBe(3);
    });

    it('falls back to layout.total_pages when pages is zero', () => {
        expect(resolveDocumentPageCount({
            document_info: { pages: 0 },
            layout: { total_pages: 2 },
        })).toBe(2);
    });

    it('uses preview page count before result is ready', () => {
        expect(resolveDocumentPageCount(null, 5)).toBe(5);
    });

    it('defaults to 1', () => {
        expect(resolveDocumentPageCount({ document_info: { pages: 0 } })).toBe(1);
    });
});

describe('pickProcessingTarget', () => {
    let a;
    let b;

    beforeEach(() => {
        a = makeQueueItem('pending');
        b = makeQueueItem('pending');
    });

    it('prefers currently selected pending item', () => {
        expect(pickProcessingTarget([a, b], b)).toBe(b);
    });

    it('falls back to first pending when selection is not pending', () => {
        const completed = makeQueueItem('completed');
        expect(pickProcessingTarget([a, b], completed)).toBe(a);
    });
});

describe('normalizePreviewPage', () => {
    it('clamps to valid range', () => {
        expect(normalizePreviewPage(0, 3)).toBe(1);
        expect(normalizePreviewPage(2, 3)).toBe(2);
        expect(normalizePreviewPage(9, 3)).toBe(3);
    });
});

describe('formatCompletedStatus', () => {
    it('formats singular and plural labels', () => {
        expect(formatCompletedStatus(1)).toBe('Completed · 1 page');
        expect(formatCompletedStatus(3)).toBe('Completed · 3 pages');
    });
});

describe('findNextQueueItem', () => {
    it('returns queued item before pending', () => {
        const pending = makeQueueItem('pending');
        const queued = makeQueueItem('queued');
        expect(findNextQueueItem([pending, queued])).toBe(queued);
    });

    it('returns null when only pending items remain', () => {
        const completed = makeQueueItem('completed');
        const pending = makeQueueItem('pending');
        expect(findNextQueueItem([completed, pending])).toBeNull();
    });

    it('returns null while another item is processing even if queued exists', () => {
        const processing = makeQueueItem('processing');
        const queued = makeQueueItem('queued');
        expect(findNextQueueItem([processing, queued])).toBe(queued);
    });
});
