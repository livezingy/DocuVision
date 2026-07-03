const { test, expect } = require('@playwright/test');
const { installProApiMocks } = require('./helpers/mock-pro-api');
const { samplePdfPath } = require('./helpers/e2e-fixtures');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';

async function openPdfToolsTab(page) {
  await page.locator('.nav-tab[data-tab="pdftools"]').click();
  await expect(page.locator('#pdfToolsMainView')).not.toHaveClass(/hidden/);
  await expect(page.locator('#pdfToolsMainView')).toContainText('PDF Tools');
}

test.describe('UI-PT PDF Tools', () => {
  test.beforeEach(async ({ page }) => {
    await installProApiMocks(page);
    await page.goto(INDEX_URL, { waitUntil: 'domcontentloaded' });
    await openPdfToolsTab(page);
  });

  test('UI-PT-01 pdf tools tab shows merge and metadata sections', async ({ page }) => {
    await expect(page.locator('#pdfMergeSelectBtn')).toBeVisible();
    await expect(page.locator('#pdfMetaSelectBtn')).toBeVisible();
    await expect(page.locator('#pdfSplitSelectBtn')).toBeVisible();
    await expect(page.locator('#pdfMergeBtn')).toBeDisabled();
  });

  test('UI-PT-02 merge two PDFs triggers download', async ({ page }) => {
    const pdf = samplePdfPath();

    await page.locator('#pdfMergeFileInput').setInputFiles([pdf, pdf]);
    await expect(page.locator('#pdfMergeFileCount')).toContainText('2 PDF(s) selected');
    await expect(page.locator('#pdfMergeBtn')).toBeEnabled();

    const downloadPromise = page.waitForEvent('download');
    await page.locator('#pdfMergeBtn').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe('merged.pdf');
    await expect(page.locator('#pdfMergeStatus')).toContainText('merged.pdf');
  });

  test('UI-PT-03 read metadata renders JSON', async ({ page }) => {
    await page.locator('#pdfMetaFileInput').setInputFiles(samplePdfPath());
    await expect(page.locator('#pdfMetaBtn')).toBeEnabled();

    await page.locator('#pdfMetaBtn').click();

    await expect(page.locator('#pdfMetaResult')).toContainText('Mock bank statement');
    await expect(page.locator('#pdfMetaResult')).toContainText('page_count');
  });

  test('UI-PT-04 split page triggers download', async ({ page }) => {
    await page.locator('#pdfSplitFileInput').setInputFiles(samplePdfPath());
    await expect(page.locator('#pdfSplitBtn')).toBeEnabled();

    const downloadPromise = page.waitForEvent('download');
    await page.locator('#pdfSplitBtn').click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toMatch(/\.pdf$/i);
  });
});
