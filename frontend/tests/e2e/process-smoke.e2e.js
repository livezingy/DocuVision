const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const { installProApiMocks } = require('./helpers/mock-pro-api');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';

function sampleImagePath() {
  const candidate = path.join(__dirname, '..', '..', '..', 'test_data', 'testfiles', 'invoices', 'sample-invoice.png');
  if (fs.existsSync(candidate)) {
    return candidate;
  }
  const fallback = path.join(__dirname, 'fixtures', 'tiny.png');
  if (!fs.existsSync(path.dirname(fallback))) {
    fs.mkdirSync(path.dirname(fallback), { recursive: true });
  }
  if (!fs.existsSync(fallback)) {
    fs.writeFileSync(
      fallback,
      Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
        'base64',
      ),
    );
  }
  return fallback;
}

test.describe('UI-S Smoke', () => {
  test.beforeEach(async ({ page }) => {
    await installProApiMocks(page);
    await page.goto(INDEX_URL);
    await page.waitForLoadState('domcontentloaded');
  });

  test('UI-S-01 page loads with health-driven status', async ({ page }) => {
    await expect(page.locator('.logo-text')).toHaveText('DocuVision');
    await expect(page.locator('#runAnalysisBtn')).toBeVisible();
  });

  test('UI-S-02 upload adds queue item', async ({ page }) => {
    const sample = sampleImagePath();
    const fileInput = page.locator('#fileInput');
    await fileInput.setInputFiles(sample);
    await expect(page.locator('#queueList .queue-item')).toHaveCount(1);
  });

  test('UI-S-04 Content and Result tabs switch', async ({ page }) => {
    await page.locator('[data-main-tab="content"]').click();
    await expect(page.locator('#contentView')).toHaveClass(/active/);
    await page.locator('[data-main-tab="result"]').click();
    await expect(page.locator('#resultView')).toHaveClass(/active/);
  });
});
