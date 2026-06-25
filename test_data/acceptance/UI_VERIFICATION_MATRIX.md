# UI 自动化 vs 手工验收矩阵

> **Status**: living — update when adding Playwright specs, Vitest cases, or LITE-UI rules.  
> **Purpose**: When UI E2E / unit / API tests are **green**, manual scope **shrinks** to rows marked **manual always** or **manual if touched**.  
> Assistant delivery: see [`.cursor/rules/004-project.mdc`](../../.cursor/rules/004-project.mdc) §手工测试提醒.

## 1. 原则

| 原则 | 说明 |
|------|------|
| **绿 ≠ 全免** | 自动化通过只代表**已映射用例**可回归；未映射项、真实 GPU、视觉/layout 仍可能需人工 |
| **E2E 用 mock** | Pro Playwright 默认 `mock-pro-api.js`，**不**替代 Cloud 真 API / KIE 质量验收 |
| **按改动缩小** | 未改动的区域：若对应用例已在本次/近期 Cloud 跑绿，发版前可跳过重复点击 |
| **发版前最小集** | 见 §5；大版本或合 `main` 前仍建议跑完整 `LITE_UI_TEST_CHECKLIST` 或 Pro spot-check |

## 2. Pro UI

### 2.1 自动化命令

```bash
# Unit (jsdom) — local or Cloud, no GPU
cd frontend && npm install && npm run test:unit

# E2E (Playwright + mock API) — static server or :8000 frontend only
cd frontend && npm run test:e2e
# Optional: PW_INDEX_URL=http://127.0.0.1:8000/frontend/index.html npm run test:e2e
```

| 套件 | 路径 | 后端 |
|------|------|------|
| Vitest | `frontend/tests/unit/queue.test.js`, `envelope_display.test.js` | 无 |
| Playwright | `frontend/tests/e2e/process-smoke.e2e.js`, `process-queue.e2e.js` | **Mock** |

### 2.2 用例映射（当前已落地）

| ID | 功能 | 自动化 | Spec / 说明 | E2E 绿时可减手工？ |
|----|------|--------|-------------|-------------------|
| UI-S-01 | 页面加载、主按钮可见 | Playwright | `process-smoke` UI-S-01 | 是（未改 shell/health 文案） |
| UI-S-02 | 上传单文件入队 | Playwright | `process-smoke` UI-S-02 | 是（未改 upload/queue DOM） |
| UI-S-04 | Content / Result tab | Playwright | `process-smoke` UI-S-04 | 是（未改 tab 绑定） |
| UI-Q-01 | 选中项优先 Run Analysis | Playwright | `process-queue` UI-Q-01 | 是（未改 `app.js` 队列选中逻辑） |
| UI-Q-03 | 完成态页数文案 | Playwright + Vitest | `process-queue` UI-Q-03；`formatCompletedStatus` | 是（未改 `queue_preview.js`） |
| UI-Q-04 | 多页分页控件 | Playwright | `process-queue` UI-Q-04 | 是（未改分页 DOM/事件） |
| UI-V-01 | 页数解析逻辑 | Vitest | `queue.test.js` `resolveDocumentPageCount` | 是（纯函数未改） |
| UI-V-02 | 队列选中/下一项 | Vitest | `pickProcessingTarget`, `findNextQueueItem` | 是 |

### 2.3 始终或条件性手工（Pro）

| ID / 主题 | 验收标准 | 何时必须手工 |
|-----------|----------|--------------|
| **GPU / KIE 结果** | `quality.kie_*`、`view.fields` 与样例一致 | 改 KIE、编排、`enable_kie`、多页 `kie_pages`；Cloud Phase C–E |
| **真实 Analyze 管道** | `POST /api/v1/analyze` 轮询至 completed，Result JSON 可读 | 改 `backend/app`、orchestrator、非 mock 的 API 契约 |
| **Analysis Options** | layout/table/KIE/`kie_query_fields` 传入 analyze | 改 Options 对话框或 Form 字段（无 UI-A-* E2E  yet） |
| **Export 下载** | JSON/CSV 等与 API 一致 | 改 `export-ui.js` 或 export 路由（无 UI-R-03 E2E yet） |
| **Batch tab** | 建批、暂停、CSV 行数 | 改 Batch UI（无 UI-B-* E2E yet） |
| **PDF-TOOL-001** | PDF Tools tab: merge ≥2 PDF → download valid `merged.pdf`; metadata JSON | 改 PDF Tools UI 或 `/api/v1/pdf-tools/*` |
| **HITL-EDIT-001** | Reviews: edit fields → Save → Approve → task `kie_fields` updated | 改 HITL UI 或 PATCH `/tasks/{id}/kie-fields` |
| **三栏 resize** | 拖拽 handle 有效 | 改 `panel-resize.js` / layout CSS |
| **视觉/文案** | 按钮 SVG、空态、主题 | 改 `components.css` / `styles.css`；E2E 不断言像素 |

Planning detail: [PRO_UI_E2E_PLAN.md](../AutoTest/PRO_UI_E2E_PLAN.md).

## 3. Lite UI

### 3.1 自动化命令

```bash
# API contract (CI Lite on PR)
cd apps/lite/backend && python -m pytest tests/ -q

# Preview API subset
python -m pytest tests/test_lite_preview.py -q

# OCR / table messaging subset (documented in checklist)
python -m pytest tests/test_lite_ocr_messaging.py tests/test_lite_bordered_tables.py -q

# Lite browser E2E (requires Lite server; CI Lite runs this on PR)
cd frontend && npm install && npm run test:e2e:lite
# Or from apps/lite/frontend: npm install && npm run test:e2e
```

**CI Lite**（PR → `main`）跑 `pytest tests/` + **`npm run test:e2e:lite`**（`LITE-PREVIEW-01`）。

### 3.2 LITE-UI 映射

| Rule | 主题 | API pytest 覆盖 | E2E 绿减手工？ | 手工验收标准（要点） |
|------|------|-----------------|----------------|----------------------|
| LITE-PREVIEW-01 | PDF 中栏预览 | `test_lite_preview.py` | **是** — `lite-preview.e2e.js` 断言 `#previewImage` 可见 | 上传 PDF 非空白、多页 Next |
| LITE-UI-001 | Upload + Profile | 部分 `test_lite_analyze_profile.py` | **部分** — E2E 覆盖预览可见；Profile 文案/联动仍建议 spot-check | Profile tab、`table_type`、页码联动 |
| LITE-UI-002 | Content tabs | 部分 extract/profile | **否** | Tables 网格、Figures 空态 |
| LITE-UI-003 | OCR 低置信/失败 | `test_lite_ocr_messaging.py` | **部分** — API 消息对；Quality 面板/UI 仍手工 | `low_confidence` / `ocr_extraction_failed` / `no_text_detected` 可见 |
| LITE-UI-004 | Queue | 无 | **否** | 多文件、Remove、选中项单独分析 |
| LITE-UI-005/008 | Export | `test_lite_export.py` | **部分** — 下载 API；toast/四按钮布局手工 | 四按钮等宽、toast + status bar |
| LITE-UI-006 | Bordered tables | `test_lite_bordered_tables.py` | **部分** — API 有表；Tables tab 展示手工 | Profile `bordered`、Tables 非空 |
| LITE-UI-007 | Analysis Options 动态 | 无完整 E2E | **否** | PDF/扫描/PNG 下 Options 显隐 |

Checklist steps: [`apps/lite/backend/tests/LITE_UI_TEST_CHECKLIST.md`](../../apps/lite/backend/tests/LITE_UI_TEST_CHECKLIST.md).

## 4. 按代码改动推断手工范围（助手交付用）

| 改动路径 | 建议自动化（先跑绿） | 仍需提醒用户手工测 | 验收标准引用 |
|----------|----------------------|-------------------|--------------|
| `frontend/app.js`, `index.html` | `npm run test:unit`；`npm run test:e2e` | Analysis Options、真实 KIE 展示、Export、Batch | §2.3；`doc_types.md` |
| `frontend/shared/*` | Vitest + Pro E2E smoke | **Lite + Pro** 各 spot-check Export/resize/notify | §2.3；LITE-UI-005/008；`shared-ui-shell.md` |
| `apps/lite/frontend/*` | `pytest tests/` | **完整** `LITE_UI_TEST_CHECKLIST` 受影响章节 | §3.2 |
| `backend/app/**`（Analyze/KIE） | Phase A pytest（Cloud） | Pro Result/Fields；Cloud Phase C–E 样例 | `CLOUD_VALIDATION.md`；`KIE_ACCEPTANCE_CRITERIA.md` |
| `apps/lite/backend/**` | `pytest tests/` | LITE-UI 表中「否/部分」行 | §3.2 |
| 仅文档 / rules | — | 无（除非文档描述的行为与代码不一致需 spot-check） | — |

## 5. 发版 / 合 main 前最小手工集

| 产品 | 条件 | 最小手工 |
|------|------|----------|
| **Pro** | `test:e2e` + `test:unit` 绿 | ① 单票样例真实 Analyze+KIE（Cloud）② Options 改过后点一轮 ③ Export 任一下载 |
| **Lite** | `pytest tests/` + `npm run test:e2e:lite` 绿 | `LITE_UI_TEST_CHECKLIST` 中 **LITE-UI-004**（队列）+ **LITE-UI-007**（Options）+ 本次改动涉及章节 |
| **共享 CSS/JS** | 上两项相关子集绿 | Lite + Pro 各打开一页，看 Export 四按钮与 toast |

## 6. 维护

- 新增 Playwright `test('UI-…')` 时：更新 §2.2 表与 [PRO_UI_E2E_PLAN.md](../AutoTest/PRO_UI_E2E_PLAN.md).
- 新增 `LITE-UI-*` 时：更新 §3.2 与 `LITE_UI_TEST_CHECKLIST.md`.
- 新增 Lite Playwright（若未来有）时：更新 §3 自动化命令与「E2E 绿减手工」列。
