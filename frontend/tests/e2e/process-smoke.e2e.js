const { test, expect } = require('@playwright/test');
const { installProApiMocks } = require('./helpers/mock-pro-api');
const { sampleImagePath } = require('./helpers/e2e-fixtures');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';

test.describe('UI-S Smoke', () => {
  test.beforeEach(async ({ page }) => {
    await installProApiMocks(page);
    await page.goto(INDEX_URL, { waitUntil: 'domcontentloaded' });
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
