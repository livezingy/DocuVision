/**
 * Mock Pro API routes for UI E2E (no GPU / no live analyze required).
 */

const API_PREFIX = '**/api/v1';

function jsonResponse(body, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {object} [options]
 */
async function installProApiMocks(page, options = {}) {
  const pageCount = options.pageCount ?? 1;
  const tasks = new Map();

  await page.route(`${API_PREFIX}/health`, async (route) => {
    await route.fulfill(
      jsonResponse({
        status: 'ok',
        api_version: '1.2.0',
        layout: { ready: true },
        table: { ready: true, strategy: 'layout_first' },
        kie: { model_loaded: false },
      }),
    );
  });

  await page.route(`${API_PREFIX}/upload`, async (route) => {
    const taskId = `task-${tasks.size + 1}`;
    tasks.set(taskId, { status: 'uploaded', page_count: pageCount });
    await route.fulfill(
      jsonResponse({
        task_id: taskId,
        page_count: pageCount,
        file_name: 'sample.pdf',
      }),
    );
  });

  await page.route(`${API_PREFIX}/analyze`, async (route) => {
    const taskId = `analyze-${Date.now()}`;
    tasks.set(taskId, { status: 'processing' });
    setTimeout(() => tasks.set(taskId, { status: 'completed' }), 50);
    await route.fulfill(jsonResponse({ task_id: taskId, status: 'processing' }));
  });

  await page.route(`${API_PREFIX}/tasks/*`, async (route) => {
    const url = route.request().url();
    if (url.includes('/result')) {
      await route.fulfill(
        jsonResponse({
          document_info: { pages: pageCount, file_name: 'sample.pdf' },
          layout: { total_pages: pageCount },
          text_blocks: [{ content: 'Hello world', page: 1 }],
          tables: [],
          view: { fields: {} },
          quality: { kie_stage: 'skipped' },
        }),
      );
      return;
    }
    if (url.includes('/page-image/')) {
      const png = Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
        'base64',
      );
      await route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: png,
      });
      return;
    }
    if (url.includes('/cancel')) {
      await route.fulfill(jsonResponse({ status: 'cancelled' }));
      return;
    }
    const taskId = url.split('/tasks/')[1]?.split('/')[0] || 'task-1';
    const state = tasks.get(taskId) || { status: 'completed' };
    await route.fulfill(
      jsonResponse({
        task_id: taskId,
        status: state.status === 'processing' ? 'completed' : state.status,
        progress: 100,
        message: 'Done',
      }),
    );
  });
}

module.exports = { installProApiMocks, jsonResponse, API_PREFIX };
