const { test, expect } = require('./helpers/coverage');
const { installProApiMocks } = require('./helpers/mock-pro-api');
const { gotoApp } = require('./helpers/app-boot');
const { samplePdfPath } = require('./helpers/e2e-fixtures');

const INDEX_URL = process.env.PW_INDEX_URL || 'http://127.0.0.1:8000/frontend/index.html';
const BATCH_ID = 'batch-e2e-mapping';

// R-003/P-042 AC1 (frontend half): the customer mapping is configured ONCE in
// the Analysis Options dialog and the whole batch runs under it — the UI proof
// is the POST /api/v1/batch create payload carrying the configured
// table_template for every task of the batch, followed by the batch lifecycle
// completing all tasks (backend endpoints mocked; no GPU / no live analyze).

function extractOptionsField(postDataBuffer) {
  // multipart/form-data: parts are appended name -> files... -> options
  // (frontend/modules/batch.js createBatch). latin1 keeps bytes 1:1 so the
  // binary file parts cannot shift the boundary search; the options field is
  // the last part, so the next CRLF boundary after its header ends it.
  const body = postDataBuffer.toString('latin1');
  const marker = 'name="options"';
  const markerIndex = body.lastIndexOf(marker);
  const start = body.indexOf('\r\n\r\n', markerIndex) + 4;
  const end = body.indexOf('\r\n--', start);
  return JSON.parse(body.slice(start, end));
}

function batchTask(taskId, fileName, status) {
  return {
    task_id: taskId,
    file_name: fileName,
    status,
    error: '',
    result:
      status === 'completed'
        ? { quality: { kie_production_hit: true } }
        : null,
  };
}

function batchPayload(status, tasks) {
  return {
    batch_id: BATCH_ID,
    name: 'Batch job',
    status,
    total_tasks: tasks.length,
    completed_tasks: tasks.filter((t) => t.status === 'completed').length,
    failed_tasks: 0,
    progress: status === 'completed' ? 100 : 0,
    tasks,
  };
}

test.describe('UI-BM Batch table mapping', () => {
  test('UI-BM-01 mapping configured once applies to the whole batch', async ({ page }) => {
    await installProApiMocks(page, { documentProfileType: 'pdf_digital' });

    const pendingTasks = [
      batchTask('bt-1', 'order-a.pdf', 'pending'),
      batchTask('bt-2', 'order-b.pdf', 'pending'),
    ];
    const completedTasks = [
      batchTask('bt-1', 'order-a.pdf', 'completed'),
      batchTask('bt-2', 'order-b.pdf', 'completed'),
    ];

    let createOptions = null;
    await page.route('**/api/v1/batch', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.continue();
        return;
      }
      createOptions = extractOptionsField(route.request().postDataBuffer());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(batchPayload('pending', pendingTasks)),
      });
    });
    await page.route(`**/api/v1/batch/${BATCH_ID}/start`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Batch started', batch_id: BATCH_ID }),
      });
    });
    await page.route(`**/api/v1/batch/${BATCH_ID}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(batchPayload('completed', completedTasks)),
      });
    });

    await gotoApp(page, INDEX_URL);

    // 1) Configure the mapping ONCE in the options dialog (one config).
    await page.locator('#analysisOptionsBtn').click();
    await expect(page.locator('#analysisOptionsModal')).toHaveClass(/active/);
    await page.locator('label.option-item:has(#optTableMapping)').click();
    await expect(page.locator('#tableMappingSubOptions')).not.toHaveClass(/hidden/);
    await page.locator('#optTableTemplate').selectOption('invoice_line_items');
    await page.locator('#closeAnalysisOptionsBtn').click();

    // 2) Batch tab: select two orders and create the batch under that config.
    await page.locator('.nav-tab[data-tab="batch"]').click();
    await expect(page.locator('#batchMainView')).toBeVisible();
    await page.locator('#batchFileInput').setInputFiles([samplePdfPath(), samplePdfPath()]);
    const createResponse = page.waitForResponse(
      (response) => response.url().includes('/api/v1/batch') && response.request().method() === 'POST',
    );
    await page.locator('#batchCreateBtn').click();
    await createResponse;
    expect(createOptions).not.toBeNull();
    // the one dialog config reaches the batch create payload verbatim — every
    // task of this batch is processed under this single mapping config.
    expect(createOptions.table_template).toBe('invoice_line_items');
    expect(createOptions.enable_table).toBe(true);

    await expect(page.locator('.notification').filter({ hasText: 'created with 2 files' })).toBeVisible();
    await expect(page.locator('#batchStartBtn')).toBeEnabled();
    await expect(page.locator('#batchTaskTableBody tr')).toHaveCount(2);

    // 3) Start: the whole batch completes under the one mapping config.
    await page.locator('#batchStartBtn').click();

    await expect(page.locator('#batchStatusText')).toContainText('Status: completed | 2/2 done', {
      timeout: 30000,
    });
    await expect(page.locator('#batchTaskTableBody tr')).toHaveCount(2);
    await expect(page.locator('#batchTaskTableBody tr').first()).toContainText('order-a.pdf');
    await expect(page.locator('#batchTaskTableBody tr').first()).toContainText('completed');
    await expect(page.locator('#batchTaskTableBody tr').nth(1)).toContainText('order-b.pdf');
    await expect(page.locator('#batchTaskTableBody tr').nth(1)).toContainText('completed');
    await expect(
      page.locator('.notification').filter({ hasText: 'Batch completed: 2/2 completed' }),
    ).toBeVisible();
  });
});
