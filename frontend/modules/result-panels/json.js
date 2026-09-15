/**
 * Result JSON view (v1.8.3 B3) - result-panels sub-module (D9).
 * Moved verbatim from app.js; no imports.
 */

/**
 * Update Result JSON view
 */
export function updateResultJson(result) {
    const jsonCode = document.getElementById('jsonCode');
    if (!jsonCode) return;

    try {
        // Format JSON with indentation (similar to Azure format)
        const formattedJson = JSON.stringify(result, null, 2);
        jsonCode.textContent = formattedJson;
    } catch (e) {
        jsonCode.textContent = 'Error formatting JSON: ' + e.message;
    }
}
