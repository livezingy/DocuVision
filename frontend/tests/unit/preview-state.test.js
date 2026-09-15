/**
 * v1.8.3 B1a - modules/preview-state.js + modules/api-config.js + modules/utils/api-url.js.
 *
 * The expected export surfaces come from scripts/frontend_domain_map.json, so a
 * deliberate change stays a one-line data edit while an accidental one fails here.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as state from '../../modules/preview-state.js';
import {
    normalizeApiBaseUrl,
    resolveApiBaseUrl,
    API_BASE_URL,
    API_ROOT_URL,
    HEALTH_URL,
    ENGINES_URL,
} from '../../modules/api-config.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(here, '..', '..');
const repoRoot = path.resolve(frontendDir, '..');
const domainMap = JSON.parse(
    fs.readFileSync(path.join(repoRoot, 'scripts', 'frontend_domain_map.json'), 'utf8'),
);

const EXPORT_RE = /^export\s+(?:async\s+)?(?:function|const|let|var)\s+([A-Za-z_$][\w$]*)/gm;
const readFile = (rel) => fs.readFileSync(path.join(frontendDir, rel), 'utf8');

const STATE_NAMES = domainMap.shared_modules['frontend/modules/preview-state.js'].filter(
    (name) => !name.startsWith('set') && name !== 'resetPreviewState',
);

describe('shared_modules export surface', () => {
    it('each registered module exports exactly the pinned names', () => {
        for (const [rel, expected] of Object.entries(domainMap.shared_modules)) {
            const moduleRel = rel.replace(/^frontend\//, '');
            const actual = [...readFile(moduleRel).matchAll(EXPORT_RE)].map((match) => match[1]);
            expect(actual.sort(), `${rel} export surface`).toEqual([...expected].sort());
        }
    });

    it('app.js no longer declares any of the shared state values', () => {
        const appJs = readFile('app.js');
        const stillDeclared = STATE_NAMES.filter((name) =>
            new RegExp(`^(?:const|let|var)\\s+${name}\\b`, 'm').test(appJs),
        );
        expect(stillDeclared).toEqual([]);
    });

    it('app.js imports the shared modules and no module uses a default export', () => {
        const appJs = readFile('app.js');
        expect(appJs).toContain("'./modules/preview-state.js'");
        expect(appJs).toContain("'./modules/api-config.js'");
        for (const rel of Object.keys(domainMap.shared_modules)) {
            expect(readFile(rel.replace(/^frontend\//, ''))).not.toMatch(/export\s+default/);
        }
    });
});

describe('preview-state', () => {
    beforeEach(() => {
        state.resetPreviewState();
        state.setPreviewPage(1);
        state.setPageImageUrl(null);
        state.setPreviewPaginationInitialized(false);
        state.setLastRenderedAnalysisResult(null);
    });

    it('setters update the bindings consumers read', () => {
        state.setTaskId('task-1');
        state.setQueueItem({ id: 'q1' });
        state.setOriginalFileUrl('blob:original');
        state.setPreviewPage(3);
        state.setPageImageUrl('blob:page');
        state.setPreviewPaginationInitialized(true);
        state.setLastRenderedAnalysisResult({ document_info: { pages: 3 } });

        expect(state.currentTaskId).toBe('task-1');
        expect(state.currentQueueItem).toEqual({ id: 'q1' });
        expect(state.currentOriginalFileUrl).toBe('blob:original');
        expect(state.currentPreviewPage).toBe(3);
        expect(state.currentPageImageUrl).toBe('blob:page');
        expect(state.previewPaginationInitialized).toBe(true);
        expect(state.lastRenderedAnalysisResult).toEqual({ document_info: { pages: 3 } });
    });

    it('resetPreviewState clears the three document slots only', () => {
        state.setTaskId('task-1');
        state.setQueueItem({ id: 'q1' });
        state.setOriginalFileUrl('blob:original');
        state.setPageImageUrl('blob:page');
        state.setPreviewPaginationInitialized(true);

        state.resetPreviewState();

        expect(state.currentTaskId).toBeNull();
        expect(state.currentQueueItem).toBeNull();
        expect(state.currentOriginalFileUrl).toBeNull();
        // By design the caller revokes page images itself, so this stays untouched.
        expect(state.currentPageImageUrl).toBe('blob:page');
        expect(state.previewPaginationInitialized).toBe(true);
    });
});

describe('api-config', () => {
    it('derives root / health / engines from the base url', () => {
        expect(API_BASE_URL.endsWith('/api/v1')).toBe(true);
        expect(API_ROOT_URL).toBe(API_BASE_URL.replace(/\/api\/v1$/, ''));
        expect(HEALTH_URL).toBe(`${API_BASE_URL}/health`);
        expect(ENGINES_URL).toBe(`${API_BASE_URL}/engines`);
    });
});

describe('api-config url helpers', () => {
    it('normalizes base urls exactly like the original app.js helper', () => {
        expect(normalizeApiBaseUrl('')).toBe('/api/v1');
        expect(normalizeApiBaseUrl('   ')).toBe('/api/v1');
        expect(normalizeApiBaseUrl('https://example.dev')).toBe('https://example.dev/api/v1');
        expect(normalizeApiBaseUrl('https://example.dev/')).toBe('https://example.dev/api/v1');
        expect(normalizeApiBaseUrl('https://example.dev/api/v1')).toBe('https://example.dev/api/v1');
    });

    it('resolves the local development default under jsdom', () => {
        expect(resolveApiBaseUrl()).toBe('http://localhost:8000/api/v1');
    });
});
