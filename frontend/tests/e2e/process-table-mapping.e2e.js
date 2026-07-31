const { test, expect } = require('@playwright/test');
const { installProApiMocks } = require('./helpers/mock-pro-api');
const { sampleImagePath, samplePdfPath } = require('./helpers/e2e-fixtures');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';

async function openProcessingOptions(page) {
  await page.locator('#analysisOptionsBtn').click();
  await expect(page.locator('#analysisOptionsModal')).toHaveClass(/active/);
}

async function selectTableMappingMode(page) {
  // The radio input is visually hidden by CSS (.option-item input { display: none })
  // and replaced by a .radio-custom span. .check() requires the input to be
  // visible, so click the wrapping label instead — this toggles the nested
  // radio and mirrors real user interaction.
  await page.locator('label.option-item:has(#optTableMapping)').click();
  await expect(page.locator('#tableMappingSubOptions')).not.toHaveClass(/hidden/);
}

test.describe('UI-TM Table mapping', () => {
  test('UI-TM-01 options dialog exposes table mapping template', async ({ page }) => {
    await installProApiMocks(page);
    await page.goto(INDEX_URL, { waitUntil: 'domcontentloaded' });

    await openProcessingOptions(page);
    await selectTableMappingMode(page);

    await expect(page.locator('#optTableTemplate')).toBeVisible();
    await expect(page.locator('#optTableTemplate')).toHaveValue('bank_statement');
    await expect(page.locator('#tableMappingHint')).toContainText('Mapped rows');
  });

  test('UI-TM-02 digital PDF shows table mapping eligibility hint', async ({ page }) => {
    await installProApiMocks(page, { documentProfileType: 'pdf_digital' });
    await page.goto(INDEX_URL, { waitUntil: 'domcontentloaded' });

    const profileResponse = page.waitForResponse(
      (response) => response.url().includes('/document/profile') && response.ok(),
    );
    await page.locator('#fileInput').setInputFiles(samplePdfPath());
    await profileResponse;
    await expect(page.locator('#queueList .queue-item')).toHaveCount(1);

    await openProcessingOptions(page);
    await selectTableMappingMode(page);

    await expect(page.locator('#tableMappingEligibility')).toBeVisible();
    await expect(page.locator('#tableMappingEligibility')).toHaveText(/Ready for table mapping/i);
  });

  test('UI-TM-03 run analysis renders Mapped rows tab', async ({ page }) => {
    await installProApiMocks(page, {
      pageCount: 1,
      useMappedResult: true,
      documentProfileType: 'pdf_digital',
    });
    await page.goto(INDEX_URL, { waitUntil: 'domcontentloaded' });

    const profileResponse = page.waitForResponse(
      (response) => response.url().includes('/document/profile') && response.ok(),
    );
    await page.locator('#fileInput').setInputFiles(samplePdfPath());
    await profileResponse;
    await openProcessingOptions(page);
    await selectTableMappingMode(page);
    await page.locator('#closeAnalysisOptionsBtn').click();

    await page.locator('#runAnalysisBtn').click();

    const item = page.locator('#queueList .queue-item').first();
    await expect(item).toHaveClass(/completed/, { timeout: 30000 });

    const mappedTab = page.locator('#tabBtnMapped');
    await expect(mappedTab).toBeVisible();
    await mappedTab.click();

    await expect(page.locator('#contentMappedList table.extracted-table')).toBeVisible();
    await expect(page.locator('#contentMappedList')).toContainText('transaction_date');
    await expect(page.locator('#contentMappedList')).toContainText('Wire transfer');
  });

  test('UI-TM-04 image upload blocked for table mapping run', async ({ page }) => {
    await installProApiMocks(page, { documentProfileType: 'image' });
    await page.goto(INDEX_URL, { waitUntil: 'domcontentloaded' });

    await page.locator('#fileInput').setInputFiles(sampleImagePath());
    await openProcessingOptions(page);
    await selectTableMappingMode(page);
    await page.locator('#closeAnalysisOptionsBtn').click();

    await page.locator('#runAnalysisBtn').click();

    await expect(page.locator('.notification')).toContainText(/Table mapping requires a digital PDF/i);
    await expect(page.locator('#queueList .queue-item').first()).toHaveClass(/pending/);
  });
});
