/**
 * Shared API health state (v1.8.3 B1b) - registered shared-state module.
 *
 * Holds the single mutable value that the api-base domain (D1) owns and the pipeline
 * domain (D8) reads. Extracted by mutability from modules/api-config.js (which holds only
 * the immutable constants): this value is re-written after boot - by a 12s KIE-cold retry
 * inside applyHealthToFooter, and by startProcessing's own applyHealthToFooter call - so a
 * "pass it once" injection would go stale. Only a live binding (or a getter) works; the
 * binding keeps every read expression byte-identical. Design rev3 section 4.1.
 */

/** Last successful GET /health JSON (dependencies, kie, api_version). */
export let lastHealthPayload = null;

export function setLastHealthPayload(health) {
    lastHealthPayload = health;
}
