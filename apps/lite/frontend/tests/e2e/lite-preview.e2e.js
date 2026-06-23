const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const INDEX_URL = process.env.PW_LITE_INDEX_URL || 'http://127.0.0.1:8001/lite/lite.html';

function samplePdfPath() {
  const candidate = path.join(
    __dirname,
    '..',
    '..',
    'backend',
    'tests',
    'fixtures',
    'sample_bordered.pdf',
  );
  if (fs.existsSync(candidate)) {
    return candidate;
  }
  throw new Error(`Lite PDF E2E fixture missing: ${candidate}`);
}

test.describe('LITE-UI Preview', () => {
  test('LITE-PREVIEW-01 PDF upload shows server-rendered preview', async ({ page }) => {
    await page.goto(INDEX_URL);
    await page.waitForLoadState('domcontentloaded');

    await page.locator('#fileInput').setInputFiles(samplePdfPath());

    const previewImage = page.locator('#previewImage');
    await expect(previewImage).toBeVisible({ timeout: 30000 });
    await expect
      .poll(async () => previewImage.evaluate((img) => img.naturalWidth))
      .toBeGreaterThan(0);

    await expect(page.locator('#currentPage')).toHaveText('1');
    const totalPages = Number(await page.locator('#totalPages').textContent());
    expect(totalPages).toBeGreaterThanOrEqual(1);

    if (totalPages > 1) {
      await page.locator('#nextPage').click();
      await expect(page.locator('#currentPage')).toHaveText('2');
      await expect(previewImage).toBeVisible();
    }
  });
});
