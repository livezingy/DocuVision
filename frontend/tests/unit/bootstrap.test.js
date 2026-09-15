/**
 * Assembly / extraction guards for v1.8.3 B0b.
 *
 * This is the STATIC half of FRONT-U5 (design rev2 section 7): it asserts the boot
 * sequence order, that every booted function still exists, the exact export surface of
 * the extracted utils modules, and that index.html loads app.js as the only module
 * entry. The DYNAMIC half (DOM readiness after boot) needs a real browser and is
 * covered by the Playwright pass + the cloud walkthrough, not here.
 *
 * The expected shapes come from scripts/frontend_domain_map.json, so a deliberate
 * change is a one-line data edit and an accidental change fails the test.
 */
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(here, '..', '..');
const repoRoot = path.resolve(frontendDir, '..');

const appJs = fs.readFileSync(path.join(frontendDir, 'app.js'), 'utf8');
const indexHtml = fs.readFileSync(path.join(frontendDir, 'index.html'), 'utf8');
const domainMap = JSON.parse(
    fs.readFileSync(path.join(repoRoot, 'scripts', 'frontend_domain_map.json'), 'utf8'),
);

const CALL_KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'return', 'typeof', 'catch', 'do', 'else']);

function bootCalls(text) {
    const lines = text.split('\n');
    const start = lines.findIndex((line) => line.includes('DOMContentLoaded'));
    if (start < 0) return [];
    const calls = [];
    for (let i = start + 1; i < lines.length; i += 1) {
        const stripped = lines[i].trim();
        if (stripped === '});') break;
        if (!stripped || stripped.startsWith('//')) continue;
        const match = /^([A-Za-z_$][\w$]*)\s*\(/.exec(stripped);
        if (match && !CALL_KEYWORDS.has(match[1])) calls.push(match[1]);
    }
    return calls;
}

function exportedFunctions(text) {
    return [...text.matchAll(/^export\s+(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)]
        .map((match) => match[1]);
}

function declaredFunctions(text) {
    return new Set(
        [...text.matchAll(/^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/gm)].map((m) => m[1]),
    );
}

describe('boot sequence', () => {
    it('runs the pinned steps in the pinned order', () => {
        expect(bootCalls(appJs)).toEqual(domainMap.boot_sequence);
    });

    it('only calls top-level functions that still exist in app.js', () => {
        const declared = declaredFunctions(appJs);
        const missing = bootCalls(appJs).filter((name) => !declared.has(name));
        expect(missing).toEqual([]);
    });
});

describe('extracted utils modules', () => {
    it('each module exports exactly the pinned function set', () => {
        for (const [moduleKey, expected] of Object.entries(domainMap.utils_modules)) {
            const file = path.join(frontendDir, 'modules', `${moduleKey}.js`);
            expect(fs.existsSync(file), `${moduleKey} missing`).toBe(true);
            expect(exportedFunctions(fs.readFileSync(file, 'utf8')).sort()).toEqual([...expected].sort());
        }
    });

    it('app.js no longer declares any extracted function', () => {
        const declared = declaredFunctions(appJs);
        const stillDeclared = Object.values(domainMap.utils_modules)
            .flat()
            .filter((name) => declared.has(name));
        expect(stillDeclared).toEqual([]);
    });

    it('app.js imports every extracted module', () => {
        for (const moduleKey of Object.keys(domainMap.utils_modules)) {
            expect(appJs).toContain(`'./modules/${moduleKey}.js'`);
        }
    });
});

describe('index.html assembly', () => {
    it('loads app.js exactly once as a module', () => {
        const scriptTags = [...indexHtml.matchAll(/<script\b([^>]*)>/gi)].map((m) => m[1]);
        const sources = scriptTags
            .map((attrs) => /\bsrc\s*=\s*["']([^"']+)["']/i.exec(attrs))
            .filter(Boolean)
            .map((m) => m[1]);
        const entries = sources.filter((src) => src.split('?')[0].replace(/^\.\//, '') === 'app.js');
        expect(entries).toHaveLength(1);
        const entryAttrs = scriptTags.find((attrs) => /app\.js/.test(attrs)) || '';
        expect(entryAttrs).toMatch(/type\s*=\s*["']module["']/i);
    });

    it('never loads a modules/ file directly', () => {
        expect(indexHtml).not.toMatch(/src\s*=\s*["'][^"']*modules\//i);
    });
});
