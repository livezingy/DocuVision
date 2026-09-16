/**
 * Boot readiness helper for the UI E2E suite (FRONT-U1).
 *
 * Why this exists: the specs used to click straight after
 * `page.goto(url, { waitUntil: 'domcontentloaded' })`, so nothing guaranteed the app had
 * booted. When a page load failed (see below) the tests clicked at a half-initialised
 * document and failed with a misleading assertion - "the options dialog never opened"
 * rather than "the app never loaded".
 *
 * Root cause of that flakiness (measured 2026-09-15): the Playwright webServer was the
 * default `python -m http.server`, whose accept backlog is 5. With ~12 files per page and
 * Playwright defaulting to cores/2 workers (10 on this host) the kernel refused
 * connections, so index.html loaded but app.js did not - in the failing pages
 * `#documentPage` still held the raw index.html placeholder comment. That is fixed in
 * scripts/e2e_static_server.py; this helper stays because a test should never click before
 * boot, and because it turns any future load failure into an explicit "boot never
 * finished" error instead of a misleading one.
 *
 * The signal is the last boot step's DOM side effect: insertInitialSkeleton() (step 17)
 * paints `<div class="empty-skeleton">` into #documentPage. Waiting for it means every
 * earlier init has already run, so this stays a test-only change - no application code,
 * no new global, nothing to keep in sync.
 */

const DEFAULT_INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';
const BOOT_MARKER = '#documentPage .empty-skeleton';

/**
 * Wait until the boot sequence has finished (idempotent, safe to call after navigation).
 *
 * @param {import('@playwright/test').Page} page
 * @param {number} [timeout]
 */
async function waitForAppBoot(page, timeout = 15000) {
  await page.waitForSelector(BOOT_MARKER, { state: 'attached', timeout });
}

/**
 * Navigate to the app and wait for it to boot.
 *
 * @param {import('@playwright/test').Page} page
 * @param {string} [url]
 */
async function gotoApp(page, url = DEFAULT_INDEX_URL) {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await waitForAppBoot(page);
}

module.exports = { gotoApp, waitForAppBoot, BOOT_MARKER, DEFAULT_INDEX_URL };
