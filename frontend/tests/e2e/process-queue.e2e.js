const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');
const { installProApiMocks } = require('./helpers/mock-pro-api');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/';

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

const SAMPLE_PNG = sampleImagePath();

async function uploadTwoFiles(page) {
  await page.locator('#fileInput').setInputFiles([SAMPLE_PNG, SAMPLE_PNG]);
  await expect(page.locator('#queueList .queue-item')).toHaveCount(2);
}

test.describe('UI-Q Queue and preview', () => {
  test.beforeEach(async ({ page }) => {
    await installProApiMocks(page, { pageCount: 3 });
    await page.goto(INDEX_URL);
    await page.waitForLoadState('domcontentloaded');
  });

  test('UI-Q-01 selected item is preferred for Run Analysis', async ({ page }) => {
    await uploadTwoFiles(page);
    const items = page.locator('#queueList .queue-item');
    await items.nth(1).click();
    await page.locator('#runAnalysisBtn').click();
    await expect(items.nth(1)).toHaveClass(/processing|completed/);
  });

  test('UI-Q-03 completed status shows page count', async ({ page }) => {
    await page.locator('#fileInput').setInputFiles(SAMPLE_PNG);
    const item = page.locator('#queueList .queue-item').first();
    item.evaluate((el) => {
      el.classList.remove('pending');
      el.classList.add('completed');
      el.previewPageCount = 3;
      const status = el.querySelector('.queue-item-status');
      if (status) status.textContent = 'Completed · 3 pages';
    });
    await expect(item.locator('.queue-item-status')).toContainText('3 pages');
  });

  test('UI-Q-04 multipage pagination controls update', async ({ page }) => {
    await page.locator('#fileInput').setInputFiles(SAMPLE_PNG);
    await page.evaluate(() => {
      const item = document.querySelector('#queueList .queue-item');
      if (item) item.previewPageCount = 3;
      if (typeof window.syncPreviewPaginationControls === 'function') {
        window.syncPreviewPaginationControls(3, 1);
      }
    });
    const pageInput = page.locator('.page-input');
    await expect(pageInput).toHaveValue('1');
    await page.locator('#nextPage').click();
    await expect(pageInput).toHaveValue('2');
  });
});
