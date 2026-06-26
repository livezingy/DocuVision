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

function mockResult(pageCount) {
  return {
    document_info: { pages: pageCount, file_name: 'sample.pdf' },
    layout: { total_pages: pageCount },
    text_blocks: [{ content: 'Hello world', page: 1 }],
    tables: [],
    view: { fields: {} },
    quality: { kie_stage: 'skipped' },
  };
}

function mockHealthPayload() {
  return {
    status: 'ok',
    api_version: '1.2.0',
    layout: { ready: true },
    table: { ready: true, strategy: 'layout_first' },
    kie: { model_loaded: false },
  };
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {object} [options]
 */
async function installProApiMocks(page, options = {}) {
  const pageCount = options.pageCount ?? 1;
  const tasks = new Map();

  // Pro app.js calls GET /api/v1/health (and legacy GET /health on direct :8000).
  await page.route(/\/api\/v1\/health$/i, async (route) => {
    await route.fulfill(jsonResponse(mockHealthPayload()));
  });
  await page.route(/\/health$/i, async (route) => {
    await route.fulfill(jsonResponse(mockHealthPayload()));
  });

  await page.route(/http:\/\/(127\.0\.0\.1|localhost):8000\/?(\?.*)?$/, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill(jsonResponse({ name: 'DocuVision', version: '1.2.0' }));
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
    tasks.set(taskId, { status: 'completed' });
    await route.fulfill(jsonResponse({ task_id: taskId, status: 'processing' }));
  });

  await page.routeWebSocket(`${API_PREFIX}/tasks/**/ws**`, (ws) => {
    const completed = JSON.stringify({
      type: 'completed',
      message: 'Processing completed',
      progress: 100,
    });
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      ws.send(completed);
      ws.close();
    };

    ws.onMessage((message) => {
      if (message === 'ping') {
        ws.send('pong');
        return;
      }
      finish();
    });

    // Defer so the client attaches onmessage before the completed payload arrives.
    setTimeout(finish, 0);
  });

  await page.route(/\/api\/v1\/tasks\//, async (route) => {
    const url = route.request().url();
    if (url.includes('/result')) {
      await route.fulfill(jsonResponse(mockResult(pageCount)));
      return;
    }
    if (url.includes('/blocks')) {
      await route.fulfill(jsonResponse({ blocks: [] }));
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
        status: state.status,
        progress: 100,
        message: 'Done',
      }),
    );
  });
}

module.exports = { installProApiMocks, jsonResponse, API_PREFIX };
