const { defineConfig } = require('@playwright/test');
const path = require('path');

const phaseUiDir = path.join(__dirname, '..', 'test_data', 'TestResult', 'PhaseUI');

module.exports = defineConfig({
  testDir: './tests/e2e',
  testMatch: '**/*.e2e.js',
  timeout: 120 * 1000,
  retries: 0,
  use: {
    headless: true,
    viewport: { width: 1280, height: 720 },
    baseURL: process.env.PW_BASE_URL || 'http://127.0.0.1:8000/frontend',
  },
  reporter: [
    ['list'],
    ['html', { outputFolder: path.join(phaseUiDir, 'playwright-report'), open: 'never' }],
    ['json', { outputFile: path.join(phaseUiDir, 'results.json') }],
    ['junit', { outputFile: path.join(phaseUiDir, 'junit.xml') }],
  ],
});
