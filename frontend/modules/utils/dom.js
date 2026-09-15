/**
 * dom.js - DOM helper (single function). The document.createElement trick is kept as-is:
 *
 * v1.8.3 D6 forbids behaviour changes while extracting.
 * Extracted verbatim from app.js in v1.8.3 B0b.
 */

/**
 * Escape HTML to prevent XSS
 */
export function escapeHtml(text) {
    // Handle null, undefined, or non-string types
    if (text == null) {
        return '';
    }
    if (typeof text !== 'string') {
        text = String(text);
    }
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
