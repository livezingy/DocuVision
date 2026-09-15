/**
 * KIE / table-mapping configuration (v1.8.3 B2 prep) - a registered leaf service.
 *
 * These five values were `const` in app.js (:1462-1466) and are never reassigned
 * (measured 2026-09-15), so they are read-only configuration rather than state: no setter
 * channel is needed, unlike modules/preview-state.js.
 *
 * Why they had to be extracted before B2: the options dialog (D6) and kie-mapping (D7)
 * both read them, and F3 forbids domain-to-domain imports - so the batch that moves the
 * options dialog would have hit an unavoidable D6 -> D7 import. The dependency was
 * invisible until the state-read scan stopped skipping declaration lines (see the B1a
 * follow-up commit).
 *
 * This module imports nothing at all (L1 holds trivially) and mutates nothing, so every
 * domain may import it and nothing can become a hub.
 */

/** Document types the KIE stage accepts (callers lower-case the candidate first). */
export const KIE_DOC_TYPES = new Set(['invoice', 'receipt', 'id_card', 'passport', 'bank_card']);

/** KIE field names must be identifier-like. */
export const KIE_FIELD_NAME_RE = /^[A-Za-z][A-Za-z0-9_]*$/;

/** Processing-mode value that selects the table-mapping template run. */
export const TABLE_MAPPING_MODE = 'table_mapping';

/** Detected file types eligible for a table-mapping run. */
export const TABLE_MAPPING_ELIGIBLE = new Set(['pdf_digital']);

/** Image extensions accepted for a table-mapping run. */
export const TABLE_MAPPING_IMAGE_EXTENSIONS = new Set([
    'png', 'jpg', 'jpeg', 'tif', 'tiff', 'gif', 'bmp', 'webp',
]);
