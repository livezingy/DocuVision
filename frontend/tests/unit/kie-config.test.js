/**
 * v1.8.3 B2 prep - modules/kie-config.js.
 *
 * The values are pinned here because they are behaviour-relevant (which document types the
 * KIE stage accepts, which modes/extensions trigger a table-mapping run). The export
 * surface itself is pinned by tests/unit/preview-state.test.js, which walks every entry of
 * domainMap.shared_modules.
 */
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
    KIE_DOC_TYPES,
    KIE_FIELD_NAME_RE,
    TABLE_MAPPING_MODE,
    TABLE_MAPPING_ELIGIBLE,
    TABLE_MAPPING_IMAGE_EXTENSIONS,
} from '../../modules/kie-config.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(here, '..', '..');
const repoRoot = path.resolve(frontendDir, '..');
const domainMap = JSON.parse(
    fs.readFileSync(path.join(repoRoot, 'scripts', 'frontend_domain_map.json'), 'utf8'),
);

describe('kie-config', () => {
    it('keeps the values the app relies on', () => {
        expect([...KIE_DOC_TYPES].sort()).toEqual([
            'bank_card', 'id_card', 'invoice', 'passport', 'receipt',
        ]);
        expect(KIE_FIELD_NAME_RE.test('invoice_no')).toBe(true);
        expect(KIE_FIELD_NAME_RE.test('1bad')).toBe(false);
        expect(KIE_FIELD_NAME_RE.test('has space')).toBe(false);
        expect(TABLE_MAPPING_MODE).toBe('table_mapping');
        expect([...TABLE_MAPPING_ELIGIBLE]).toEqual(['pdf_digital']);
        expect([...TABLE_MAPPING_IMAGE_EXTENSIONS]).toEqual([
            'png', 'jpg', 'jpeg', 'tif', 'tiff', 'gif', 'bmp', 'webp',
        ]);
    });

    it('app.js imports it and no longer declares the constants', () => {
        const appJs = fs.readFileSync(path.join(frontendDir, 'app.js'), 'utf8');
        expect(appJs).toContain("'./modules/kie-config.js'");
        for (const name of domainMap.shared_modules['frontend/modules/kie-config.js']) {
            const declared = new RegExp(`^(?:const|let|var)\\s+${name}\\b`, 'm').test(appJs);
            expect(declared, `app.js still declares ${name}`).toBe(false);
        }
    });
});
