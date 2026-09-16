/**
 * API connection & health probe (v1.8.3 B1b) - domain module (D1).
 *
 * NOT registered as a leaf service: it calls status-bar (updateStatusBar) and owns mutable
 * infrastructure state (kieHealthRefreshTimer), so it stays a normal domain module. Its
 * immutable config moved to modules/api-config.js (B1a) and its single mutable shared value
 * (lastHealthPayload) moved to modules/api-state.js (this batch, design §4.1).
 */
import { API_BASE_URL, API_ROOT_URL, HEALTH_URL, ENGINES_URL } from './api-config.js';
import { updateStatusBar } from './status-bar.js';
import { lastHealthPayload, setLastHealthPayload } from './api-state.js';

let kieHealthRefreshTimer = null;

/**
 * Probe API reachability (cloud proxies may block /health but allow /api/v1/*).
 * Tries GET /api/v1/health, then GET /api/v1/engines as fallback.
 */
export async function checkApiReachable(timeoutMs = 8000) {
    let lastError = null;

    try {
        const healthResponse = await fetch(HEALTH_URL, {
            method: 'GET',
            signal: AbortSignal.timeout(timeoutMs),
        });
        if (healthResponse.ok) {
            try {
                const healthJson = await healthResponse.json();
                if (healthJson) {
                    return { ok: true, health: healthJson, probe: 'health' };
                }
            } catch (parseErr) {
                lastError = parseErr;
            }
        } else {
            lastError = new Error(`health HTTP ${healthResponse.status}`);
        }
    } catch (err) {
        lastError = err;
        console.warn('[API] Health probe failed:', err);
    }

    try {
        const enginesResponse = await fetch(ENGINES_URL, {
            method: 'GET',
            signal: AbortSignal.timeout(timeoutMs),
        });
        if (enginesResponse.ok) {
            try {
                const enginesJson = await enginesResponse.json();
                if (enginesJson && enginesJson.ocr) {
                    return { ok: true, health: null, probe: 'engines' };
                }
            } catch (parseErr) {
                lastError = parseErr;
            }
        } else {
            lastError = new Error(`engines HTTP ${enginesResponse.status}`);
        }
    } catch (err) {
        lastError = err;
        console.warn('[API] Engines probe failed:', err);
    }

    return { ok: false, health: null, probe: null, error: lastError };
}

export function truncateFooterEngineLine(line) {
    if (!line) return '';
    return line.length > 72 ? `${line.slice(0, 69)}...` : line;
}

/**
 * Keep #activeEngine aligned with last /health dependencies and the OCR engine dropdown.
 */
export function refreshActiveEngineFooterLine() {
    const activeEl = document.getElementById('activeEngine');
    if (!activeEl) return;
    const deps = (lastHealthPayload && lastHealthPayload.dependencies) || {};
    const px = String(deps.paddlex || '').trim() || 'unknown';
    const po = String(deps.paddleocr || '').trim() || 'unknown';
    const ocrSelect = document.getElementById('dialogOcrEngineSelect');

    if (!ocrSelect) {
        activeEl.textContent = truncateFooterEngineLine(`PaddleOCR ${po} · PaddleX ${px}`);
        return;
    }

    const engineNames = {
        paddleocr: 'PaddleOCR',
        tesseract: 'Tesseract 5.x',
        easyocr: 'EasyOCR'
    };
    const val = ocrSelect.value || 'paddleocr';
    const base = engineNames[val] || val;
    const line =
        val === 'paddleocr'
            ? `PaddleOCR ${po} · PaddleX ${px}`
            : `${base} · PaddleX ${px}`;
    activeEl.textContent = truncateFooterEngineLine(line);
}

/**
 * Apply /health payload to footer (Paddle stack version, KIE readiness, API version).
 */
export function applyHealthToFooter(health) {
    if (!health || typeof health !== 'object') return;
    setLastHealthPayload(health);
    refreshActiveEngineFooterLine();
    const kieEl = document.getElementById('kieEngineStatus');
    if (kieEl) {
        if (health.kie && typeof health.kie === 'object') {
            kieEl.textContent = health.kie.model_loaded ? ' · KIE ready' : ' · KIE cold';
            kieEl.title = health.kie.model_id ? `KIE: ${health.kie.model_id}` : '';
        } else {
            kieEl.textContent = '';
            kieEl.title = '';
        }
    }
    const verEl = document.getElementById('apiVersionFooter');
    if (verEl && health.api_version) {
        verEl.textContent = `API v${health.api_version}`;
    }
    if (health.kie && health.kie.model_loaded === false && !kieHealthRefreshTimer) {
        kieHealthRefreshTimer = window.setTimeout(() => {
            kieHealthRefreshTimer = null;
            fetch(HEALTH_URL)
                .then((r) => (r.ok ? r.json() : null))
                .then((h) => {
                    if (h) applyHealthToFooter(h);
                })
                .catch(() => {});
        }, 12000);
    }
}

/**
 * Initialize API connection and check server status
 */
export async function initializeAPIConnection() {
    try {
        console.log('[Init] API_BASE_URL=', API_BASE_URL, 'HEALTH_URL=', HEALTH_URL);

        const reachability = await checkApiReachable(8000);
        if (!reachability.ok) {
            console.warn('[Init] API reachability probe failed');
            updateStatusBar('warning', {
                step: 'Server connection weak - some features may not work properly'
            });
            return;
        }

        if (reachability.health) {
            applyHealthToFooter(reachability.health);
        }

        console.log('[Init] API probe OK via', reachability.probe);

        // Get server info (optional; root / may be blocked on some cloud proxies)
        try {
            const infoResponse = await fetch(API_ROOT_URL, {
                signal: AbortSignal.timeout(5000),
            });
            if (infoResponse.ok) {
                const serverInfo = await infoResponse.json();
                console.log('[Init] Server info:', serverInfo);
                updateStatusBar('success', {
                    step: '✓ API Connected: ' + serverInfo.name + ' v' + serverInfo.version
                });
                return;
            }
        } catch (infoErr) {
            console.warn('[Init] Could not fetch server info:', infoErr);
        }

        updateStatusBar('success', {
            step: '✓ API Connected (' + reachability.probe + ' probe)'
        });

    } catch (error) {
        console.error('[Init] Failed to connect to API:', error);
        updateStatusBar('error', {
            step: `⚠ Server not responding - check backend: ${API_ROOT_URL}`
        });

        // Show alert to user
        const uploadZone = document.getElementById('uploadZone');
        if (uploadZone) {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.3);
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
                color: #ff6b6b;
                padding: 16px;
                text-align: center;
                z-index: 10;
            `;
            overlay.innerHTML = '⚠ Server not responding<br/>Make sure backend is running';
            uploadZone.parentElement.style.position = 'relative';
            uploadZone.parentElement.appendChild(overlay);
        }
    }
}
