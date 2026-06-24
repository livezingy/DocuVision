const { defineConfig } = require('@playwright/test');
const path = require('path');

const repoRoot = path.join(__dirname, '..');
const liteBackendDir = path.join(repoRoot, 'apps', 'lite', 'backend');
const liteE2eDir = path.join(repoRoot, 'apps', 'lite', 'frontend', 'tests', 'e2e');
const liteEntryUrl = process.env.PW_LITE_INDEX_URL || 'http://127.0.0.1:8001/lite/lite.html';
const liteServerCmd = process.platform === 'win32' ? 'python run_lite.py' : 'python3 run_lite.py';
const phaseUiDir = path.join(repoRoot, 'test_data', 'TestResult', 'PhaseUI', 'lite');

module.exports = defineConfig({
  testDir: liteE2eDir,
  testMatch: '**/*.e2e.js',
  timeout: 120 * 1000,
  retries: 0,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    baseURL: 'http://127.0.0.1:8001',
  },
  webServer: process.env.PW_SKIP_LITE_WEBSERVER
    ? undefined
    : {
        command: liteServerCmd,
        cwd: liteBackendDir,
        url: liteEntryUrl,
        reuseExistingServer: true,
        timeout: 120 * 1000,
      },
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(phaseUiDir, 'playwright-report'), open: 'never' }],
    ['json', { outputFile: path.join(phaseUiDir, 'results.json') }],
  ],
});
