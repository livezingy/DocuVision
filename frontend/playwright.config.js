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
  timeout: 120 * 1000,
  // 0 everywhere, including CI (P-008 gap 2, step 2): a retry would hide exactly the flake this
  // job exists to surface, and a flake that only disappears on retry is a real finding. A red CI
  // run ships its trace/report as an artifact, so the diagnosis is not lost - see lint.yml.
  retries: 0,
  // CI runners have fewer cores than the dev host, and over-subscribing is the failure mode the
  // 256-deep accept backlog in scripts/e2e_static_server.py was added for. Only CI is pinned;
  // locally the default (cores / 2) is faster and has been stable at 14/14.
  workers: process.env.CI ? 2 : undefined,
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
