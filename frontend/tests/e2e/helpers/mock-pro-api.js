/**
 * Mock Pro API routes for UI E2E (no GPU / no live analyze required).
 */

const { TINY_PDF_BYTES } = require('./e2e-fixtures');

const API_PREFIX = '**/api/v1';

function jsonResponse(body, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  };
}

function mockResult(pageCount, options = {}) {
  const base = {
    document_info: { pages: pageCount, file_name: 'sample.pdf' },
    layout: { total_pages: pageCount },
    text_blocks: [{ content: 'Hello world', page: 1 }],
    tables: [],
    view: { fields: {} },
    quality: { kie_stage: 'skipped' },
  };

  if (options.useMappedResult) {
    const template = options.tableTemplate || 'bank_statement';
    return {
      ...base,
      table_template: template,
      mapped_table_rows: [
        {
          template,
          page: 1,
          row_index: 0,
          transaction_date: '2026-01-15',
          description: 'Wire transfer',
          amount: '-250.00',
          balance: '1,250.00',
        },
      ],
    };
  }

  return base;
}

function mockHealthPayload(apiVersion = '1.4.0') {
  return {
    status: 'ok',
    api_version: apiVersion,
    layout: { ready: true },
    table: { ready: true, strategy: 'layout_first' },
    kie: { model_loaded: false },
  };
}

/**
 * @param {import('@playwright/test').Page} page
 * @param {object} [options]
 * @param {number} [options.pageCount]
 * @param {boolean} [options.useMappedResult]
 * @param {string} [options.tableTemplate]
 * @param {string} [options.documentProfileType] pdf_digital | pdf_scan | image
 * @param {string} [options.suggestedDocumentType] classifier hint shown as non-binding UI suggestion (default 'auto' = hidden)
 * @param {number} [options.classificationConfidence] 0-1 confidence for the suggestion (default 0 = hidden)
 * @param {string} [options.apiVersion]
 */
async function installProApiMocks(page, options = {}) {
  const pageCount = options.pageCount ?? 1;
  const tasks = new Map();
  const apiVersion = options.apiVersion ?? '1.4.0';
  const documentProfileType = options.documentProfileType ?? 'pdf_digital';
  const suggestedDocumentType = options.suggestedDocumentType ?? 'auto';
  const classificationConfidence = options.classificationConfidence ?? 0;

  await page.route(/\/api\/v1\/health$/i, async (route) => {
    await route.fulfill(jsonResponse(mockHealthPayload(apiVersion)));
  });
  await page.route(/\/health$/i, async (route) => {
    await route.fulfill(jsonResponse(mockHealthPayload(apiVersion)));
  });

  await page.route(`${API_PREFIX}/engines`, async (route) => {
    await route.fulfill(
      jsonResponse({
        layout: ['ppstructure'],
        ocr: ['paddleocr'],
        table: ['layout_first'],
      }),
    );
  });

  await page.route(/http:\/\/(127\.0\.0\.1|localhost):8000\/?(\?.*)?$/, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }
    await route.fulfill(jsonResponse({ name: 'DocuVision', version: apiVersion }));
  });

  await page.route(`${API_PREFIX}/document/profile`, async (route) => {
    await route.fulfill(
      jsonResponse({
        detected_file_type: documentProfileType,
        suggested_routing: documentProfileType === 'pdf_digital' ? 'docuvision_core' : 'ppstructure',
        suggested_document_type: suggestedDocumentType,
        classification_confidence: classificationConfidence,
        file_name: 'sample.pdf',
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

    setTimeout(finish, 0);
  });

  await page.route(/\/api\/v1\/tasks\//, async (route) => {
    const url = route.request().url();
    if (url.includes('/result')) {
      await route.fulfill(jsonResponse(mockResult(pageCount, options)));
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

  await page.route(`${API_PREFIX}/pdf-tools/merge`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: TINY_PDF_BYTES,
    });
  });

  await page.route(`${API_PREFIX}/pdf-tools/metadata`, async (route) => {
    await route.fulfill(
      jsonResponse({
        title: 'Mock bank statement',
        page_count: 2,
        pages: 2,
        author: 'DocuVision E2E',
      }),
    );
  });

  await page.route(`${API_PREFIX}/pdf-tools/split`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: TINY_PDF_BYTES,
    });
  });
}

module.exports = { installProApiMocks, jsonResponse, API_PREFIX, mockResult, mockHealthPayload };
