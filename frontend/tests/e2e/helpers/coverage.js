/**
 * Runtime coverage recorder for the Pro e2e suite (P-008 gap 2, MVP - 2026-09-17).
 *
 * Re-exports Playwright's `test` with a `page` fixture that installs a recorder *before* any
 * page script runs, so a spec only swaps its import line. What it answers - and no static
 * gate can: which modules actually loaded, which modules registered DOM listeners and how
 * many of those ever fired, and which runtime errors occurred. F7 proves reachability and C9
 * proves the deps are injected; neither can tell whether a feature is ever *exercised* (the
 * two registered orphans are the standing example).
 *
 * Deliberately non-blocking: nothing here can fail a run (see PENDING P-008 gap 2 - the
 * enforcement venue is still open). Per-test fragments land in
 * `test_data/TestResult/PhaseUI/coverage-fragments/` (already gitignored) and are merged by
 * `coverage-report.js`, which runs as Playwright's globalTeardown.
 */

const fs = require('fs');
const path = require('path');

const base = require('@playwright/test');

// frontend/tests/e2e/helpers -> repo root
const REPO_ROOT = path.join(__dirname, '..', '..', '..', '..');
const OUT_DIR = path.join(REPO_ROOT, 'test_data', 'TestResult', 'PhaseUI');
const FRAGMENT_DIR = path.join(OUT_DIR, 'coverage-fragments');

/** Injected into the page before any script: records registrations and invocations. */
function recorder() {
  const coverage = { listeners: [] };
  window.__dvCoverage = coverage;
  const MODULE_RE = /\/frontend\/((?:modules|shared)\/[\w./-]+\.js|app\.js)/;
  const MAX_RECORDS = 4000;

  // The caller of addEventListener is the module that registered it; the first /frontend/
  // frame in the stack is the best available attribution for a listener.
  function registrationSite() {
    const stack = String((new Error()).stack || '');
    for (const line of stack.split('\n')) {
      const match = MODULE_RE.exec(line);
      if (match) return match[1];
    }
    return '(inline or unknown)';
  }

  function describe(target) {
    if (target === window) return 'window';
    if (target === document) return 'document';
    if (!target || !target.tagName) return 'unknown';
    const tag = target.tagName.toLowerCase();
    if (target.id) return `${tag}#${target.id}`;
    const cls = typeof target.className === 'string' ? target.className.trim().split(/\s+/)[0] : '';
    return cls ? `${tag}.${cls}` : tag;
  }

  const add = EventTarget.prototype.addEventListener;
  const remove = EventTarget.prototype.removeEventListener;
  // original listener -> target -> type -> wrapper. Two reasons for the full key:
  // removeEventListener(type, original) must still detach, and re-registering the same
  // (target, type, listener) must reuse one wrapper so the browser's own de-duplication
  // keeps working (two wrappers would deliver every event twice).
  const wrappers = new Map();

  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (typeof listener !== 'function' || coverage.listeners.length >= MAX_RECORDS) {
      return add.call(this, type, listener, options);
    }
    let byTarget = wrappers.get(listener);
    if (!byTarget) {
      byTarget = new Map();
      wrappers.set(listener, byTarget);
    }
    let byType = byTarget.get(this);
    if (!byType) {
      byType = new Map();
      byTarget.set(this, byType);
    }
    let wrapped = byType.get(type);
    if (!wrapped) {
      const record = { event: type, module: registrationSite(), target: describe(this), fired: 0 };
      coverage.listeners.push(record);
      wrapped = function (...args) {
        record.fired += 1;
        return listener.apply(this, args);
      };
      byType.set(type, wrapped);
    }
    return add.call(this, type, wrapped, options);
  };

  EventTarget.prototype.removeEventListener = function (type, listener, options) {
    const byTarget = wrappers.get(listener);
    const byType = byTarget && byTarget.get(this);
    const wrapped = byType && byType.get(type);
    return remove.call(this, type, wrapped || listener, options);
  };
}

// Kill switch: `PW_COVERAGE=0 npm run test:e2e` runs the suite untouched. A report must be
// dismissible without editing code, and an A/B run is how the recorder itself gets validated.
// It also disables the runtime-error assertion below (the escape hatch has to be total).
const ENABLED = process.env.PW_COVERAGE !== '0';

/**
 * Runtime errors that are *expected* on this suite - RegExp matched against the
 * `pageerror: <msg>` / `console.error: <msg>` lines the fixture collects.
 *
 * Empty on purpose (2026-09-17): the first full run measured **0** errors, so this starts at
 * zero rather than at "a few we agreed to live with" - the same rule the ESLint gate was wired
 * under. Every entry weakens the signal this assertion exists to provide, so an entry needs
 * the reason it is expected next to it.
 */
const EXPECTED_ERRORS = [];

function fragmentName(file, title) {
  const stem = `${path.basename(file, '.e2e.js')}-${title}`;
  let hash = 0;
  for (const char of stem) hash = (hash * 31 + char.charCodeAt(0)) % 100000;
  return `${stem.replace(/[^A-Za-z0-9_.-]+/g, '-').slice(0, 80)}-${hash}.json`;
}

const test = base.test.extend({
  page: async ({ page }, use, testInfo) => {
    const errors = [];
    // Instrumentation problems are reported, never fatal: they are about the recorder, not the
    // application (a page that closed early must not look like a product bug).
    const notes = [];
    page.on('pageerror', (err) => errors.push(`pageerror: ${err.message}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(`console.error: ${msg.text()}`);
    });
    if (ENABLED) await page.addInitScript(recorder);
    await use(page);
    if (!ENABLED) return;

    let snapshot = { listeners: [], loaded: [] };
    try {
      snapshot = await page.evaluate(() => ({
        listeners: (window.__dvCoverage || {}).listeners || [],
        loaded: performance.getEntriesByType('resource').map((entry) => entry.name),
      }));
    } catch (err) {
      notes.push(`coverage snapshot unavailable: ${err.message}`);
    }
    // Fragment first: the assertion below must not cost us the coverage data it is about.
    try {
      fs.mkdirSync(FRAGMENT_DIR, { recursive: true });
      fs.writeFileSync(
        path.join(FRAGMENT_DIR, fragmentName(testInfo.file, testInfo.title)),
        JSON.stringify({
          title: testInfo.title,
          file: path.relative(REPO_ROOT, testInfo.file),
          errors,
          notes,
          ...snapshot,
        }),
        'utf8',
      );
    } catch (err) {
      console.log(`[coverage] fragment not written: ${err.message}`);
    }
    for (const note of notes) console.log(`[coverage] note (${testInfo.title}): ${note}`);

    // P-008 gap 2, step 1 (2026-09-17): a report depends on someone reading it; this assertion
    // does not. It is what would have caught P-016 (8 pageerrors behind a 14/14 green suite).
    // Local-only by design - it needs no CI change and no branch protection to be useful.
    const unexpected = errors.filter((line) => !EXPECTED_ERRORS.some((re) => re.test(line)));
    if (unexpected.length) {
      throw new Error(
        `${unexpected.length} runtime error(s) during this test:`
        + `\n  ${unexpected.join('\n  ')}`
        + '\nThe app threw or logged an error while this scenario ran. Fix the cause; only if it'
        + ' is genuinely expected, add a pattern *with its reason* to EXPECTED_ERRORS in'
        + ' frontend/tests/e2e/helpers/coverage.js (or run with PW_COVERAGE=0 to skip entirely).',
      );
    }
  },
});

module.exports = { test, expect: base.expect, OUT_DIR, FRAGMENT_DIR };
