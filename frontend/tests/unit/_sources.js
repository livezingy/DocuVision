/**
 * Shared structural-test helper (P-010).
 *
 * Not a test file: `vitest.config.js` collects only `tests/unit/**\/*.test.js` (same
 * convention as `backend/tests/_sample_paths.py`).
 *
 * Why it exists: the extraction guards used to assert "app.js imports module X". After
 * the v1.8.3 split app.js stopped consuming the pure utils and the shared constants, so
 * those imports had become dead - `no-unused-vars` reported them and the P-010 cleanup
 * removed them (2026-09-17). The invariant worth pinning is "X is imported by a
 * consumer" (app.js or a module), which is what `importedBySomeSource` checks.
 */
import fs from 'node:fs';
import path from 'node:path';

function walk(dir) {
    const out = [];
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) out.push(...walk(full));
        else if (entry.name.endsWith('.js')) out.push(full);
    }
    return out;
}

/** Import specifiers of every frontend ESM source (app.js + modules/** + shared/**). */
export function importSpecifiers(frontendDir) {
    const files = [
        path.join(frontendDir, 'app.js'),
        ...walk(path.join(frontendDir, 'modules')),
        ...walk(path.join(frontendDir, 'shared')),
    ];
    const specs = new Set();
    for (const file of files) {
        const text = fs.readFileSync(file, 'utf8');
        for (const match of text.matchAll(/from\s*["']([^"']+)["']|\bimport\s*["']([^"']+)["']/g)) {
            specs.add(match[1] || match[2]);
        }
    }
    return specs;
}

/** True when some frontend source imports the module whose path ends with `suffix.js`. */
export function importedBySomeSource(frontendDir, suffix) {
    return [...importSpecifiers(frontendDir)].some((spec) => spec.endsWith(`${suffix}.js`));
}
