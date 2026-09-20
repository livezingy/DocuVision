/**
 * Static frontend configuration (v1.8.3 B1a) - a registered leaf service.
 *
 * The four values below were `const` in app.js (:57/:58/:63/:64) and are never
 * reassigned after load (measured 2026-09-15), so consumers import them instead of
 * receiving them through dependency injection.
 *
 * The two URL helpers that build them moved here too, verbatim from app.js (:33-55).
 * They deliberately do NOT live in modules/utils/: the C0 gate (C6) asserts that every
 * utils function has zero `document`/`window.` references - the "utils are pure"
 * invariant that gives the geometry/csv/text modules their unit-test value - and
 * resolveApiBaseUrl reads window.location / window.DOCUVISION_CONFIG (7 refs, measured).
 * Keeping them private to this module also means api-config imports nothing at all, so
 * L1 holds trivially and the api-base domain module never has to import it back
 * (api-base calls status-bar, which would conflict with L1, so it cannot be a
 * whitelist target itself).
 *
 * Consumers: api-base, export-csv, hitl-review, overlay, shell-init,
 * pipeline - they import the constants and keep every call site byte-identical.
 */

export function normalizeApiBaseUrl(baseUrl) {
    const trimmed = (baseUrl || '').trim().replace(/\/+$/, '');
    if (!trimmed) return '/api/v1';
    return trimmed.endsWith('/api/v1') ? trimmed : `${trimmed}/api/v1`;
}

export function resolveApiBaseUrl() {
    // Optional override via global config: window.DOCUVISION_CONFIG.API_BASE_URL
    if (window.DOCUVISION_CONFIG && typeof window.DOCUVISION_CONFIG.API_BASE_URL === 'string') {
        return normalizeApiBaseUrl(window.DOCUVISION_CONFIG.API_BASE_URL);
    }

    const hostname = window.location.hostname;
    const isLocal = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';
    if (isLocal) {
        return 'http://localhost:8000/api/v1';
    }

    // Cloud/staging friendly: infer proxy prefix from current path when '/frontend' is present.
    const path = window.location.pathname || '/';
    const prefix = path.includes('/frontend') ? path.split('/frontend')[0] : '';
    return `${window.location.origin}${prefix}/api/v1`;
}

// API Base URL (auto-adapt for local and cloud deployments)
export const API_BASE_URL = resolveApiBaseUrl();
export const API_ROOT_URL = API_BASE_URL.replace(/\/api\/v1$/, '');
/** Prefer /api/v1/health (works on Baidu AI Studio api_serving); /health kept for direct :8000 access. */
export const HEALTH_URL = `${API_BASE_URL}/health`;
export const ENGINES_URL = `${API_BASE_URL}/engines`;
