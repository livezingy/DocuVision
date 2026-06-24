const { defineConfig } = require('@playwright/test');
const path = require('path');

const phaseUiDir = path.join(__dirname, '..', 'test_data', 'TestResult', 'PhaseUI');
const repoRoot = path.join(__dirname, '..');
const e2eEntryUrl = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';
const staticServerCmd = process.platform === 'win32' ? 'python -m http.server 8000' : 'python3 -m http.server 8000';

module.exports = defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.e2e.js',
  testIgnore: '**/lite/**',
  timeout: 120 * 1000,
  retries: 0,
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
