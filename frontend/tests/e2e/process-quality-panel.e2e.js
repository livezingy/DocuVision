const { test, expect } = require('./helpers/coverage');
const { installProApiMocks } = require('./helpers/mock-pro-api');
const { gotoApp } = require('./helpers/app-boot');
const { samplePdfPath } = require('./helpers/e2e-fixtures');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';

test.describe('UI-QP Quality panel', () => {
  // P-007 (v1.9 S1): a non-KIE run with table backfill must show Tables + Backfill
  // but never KIE meta. Before S1 the mock's quality was always { kie_stage:
  // 'skipped' } with no table_backfill, so the visible render path had 0 e2e coverage.
  test('UI-QP-01 backfill run shows Tables/Backfill but no KIE meta', async ({ page }) => {
    await installProApiMocks(page, {
      pageCount: 1,
      qualityPreset: 'backfill',
      documentProfileType: 'pdf_digital',
    });
    await gotoApp(page, INDEX_URL);

    const profileResponse = page.waitForResponse(
      (response) => response.url().includes('/document/profile') && response.ok(),
    );
    await page.locator('#fileInput').setInputFiles(samplePdfPath());
    await profileResponse;

    await page.locator('#runAnalysisBtn').click();

    const item = page.locator('#queueList .queue-item').first();
    await expect(item).toHaveClass(/completed/, { timeout: 30000 });

    const panel = page.locator('#qualityPanel');
    await expect(panel).toBeVisible();
    await expect(panel).toContainText('Tables: 16');
    await expect(panel).toContainText('Backfill: 89/588 (15%)');
    await expect(panel).not.toContainText('KIE');
  });
});
