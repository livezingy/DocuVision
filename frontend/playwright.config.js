const { defineConfig } = require('@playwright/test');
const path = require('path');

const phaseUiDir = path.join(__dirname, '..', 'test_data', 'TestResult', 'PhaseUI');
const repoRoot = path.join(__dirname, '..');
const e2eEntryUrl = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';
// scripts/e2e_static_server.py is a stdlib ThreadingHTTPServer with a 256-deep accept
// backlog. The default `python -m http.server` backlog is 5 and refuses connections once
// Playwright's cores/2 default worker count has several pages loading at once (app.js then
// fails to load and the tests report misleading assertion failures) - see the script header.
const staticServerCmd = process.platform === 'win32'
  ? 'python scripts/e2e_static_server.py 8000'
  : 'python3 scripts/e2e_static_server.py 8000';

module.exports = defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.e2e.js',
  testIgnore: '**/lite/**',
  timeout: 120 * 1000,
  retries: 0,
  // P-008 gap 2 (MVP): clear stale fragments before the run and merge this run's into
  // test_data/TestResult/PhaseUI/coverage-<date>.md. A report, not a gate - see the header.
  globalSetup: path.join(__dirname, 'tests', 'e2e', 'helpers', 'coverage-setup.js'),
  globalTeardown: path.join(__dirname, 'tests', 'e2e', 'helpers', 'coverage-report.js'),
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    baseURL: process.env.PW_BASE_URL || 'http://127.0.0.1:8000/frontend',
  },
  webServer: process.env.PW_SKIP_WEBSERVER
    ? undefined
    : {
        command: staticServerCmd,
        cwd: repoRoot,
        url: e2eEntryUrl,
        reuseExistingServer: true,
        timeout: 120 * 1000,
      },
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(phaseUiDir, 'playwright-report'), open: 'never' }],
    ['json', { outputFile: path.join(phaseUiDir, 'results.json') }],
    ['junit', { outputFile: path.join(phaseUiDir, 'junit.xml') }],
  ],
});
