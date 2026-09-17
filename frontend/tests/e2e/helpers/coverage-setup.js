/**
 * Clears the runtime-coverage fragments before a run (P-008 gap 2, MVP).
 *
 * Wired as Playwright's globalSetup. Without this, the teardown merged whatever fragments
 * happened to be on disk - a run with `PW_COVERAGE=0`, or a partial run, would report the
 * previous run's data as if it were current. That was the MVP's second defect, found by
 * running the suite rather than by reading the code.
 */

const fs = require('fs');
const path = require('path');

// frontend/tests/e2e/helpers -> repo root
const REPO_ROOT = path.join(__dirname, '..', '..', '..', '..');
const FRAGMENT_DIR = path.join(REPO_ROOT, 'test_data', 'TestResult', 'PhaseUI', 'coverage-fragments');

module.exports = async function globalSetup() {
  fs.rmSync(FRAGMENT_DIR, { recursive: true, force: true });
};
