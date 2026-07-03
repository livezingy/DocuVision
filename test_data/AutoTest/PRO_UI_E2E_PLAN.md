# Pro UI Playwright E2E 规划（讨论稿）

Last updated: 2026-06-30  
Status: **P0 + v1.4 UI-TM / UI-PT**（`process-smoke.e2e.js`、`process-queue.e2e.js`、`process-table-mapping.e2e.js`、`process-pdf-tools.e2e.js` + mock API）；Batch/Reviews/HITL 仍待扩展  
关联：`frontend/tests/e2e/`、`frontend/playwright.config.js`、[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)

---

## 1. 背景与目标

### 1.1 为何需要 UI E2E

近期手动测试暴露的 Pro UI 问题（多页翻页无效、侧边栏 `Completed · 0 pages`、队列未按选中项处理等）已通过 **Vitest 纯函数** + **后端单测** + **手工 Cloud 验收** 修复。此类问题说明：

- **API / pytest** 无法覆盖 DOM 事件绑定、队列交互、分页控件等 **浏览器侧行为**；
- **Vitest（jsdom）** 可测逻辑，但无法替代真实点击、文件上传、下载与长耗时推理 UI。

UI E2E 的目标是：在 **固定后端 + 固定样例** 环境下，对 **关键用户路径** 做可重复、可落盘的自动化回归，减轻发版前手工点 UI 的负担。

### 1.2 不追求的目标（边界）

| 不追求 | 原因 |
|--------|------|
| 仅凭 UI 设计稿「全自动」穷举所有控件 | Playwright 无产品语义，无法自动判断 KIE 字段是否正确 |
| 替代 Cloud Phase A / MP / H-Batch | GPU 推理质量仍以 pytest + 手动 API 验收为准 |
| 像素级标注 / Canvas 对齐 | 成本高，宜抽样人工或专项视觉测试 |
| 本地 Windows 无 GPU 环境跑完整 KIE | E2E 应绑定 Cloud Studio 或 CI GPU runner（若未来有） |

---

## 2. 能否「根据 UI 功能设计自动测全部」？

**结论：不能全自动；可以按功能清单系统化编写用例，逐步逼近高覆盖。**

| 方式 | 可行性 | 说明 |
|------|--------|------|
| 设计文档 → 自动生成全量用例 | 低 | 需人工将「功能 ID」映射为 selector + 断言 |
| DOM 扫描所有可点击元素做冒烟 | 中 | 可发现「点得动」，无法断言业务正确性 |
| 按验收矩阵手写 Playwright spec | **高（推荐）** | 与 `test_data/acceptance/*.md`、CLOUD_VALIDATION 对齐 |
| 截图 / 视觉回归 | 中 | `toHaveScreenshot`，需维护基线，对主题/字体敏感 |

---

## 3. 测试结果能否写入文件？

**可以。** Playwright 内置 reporter，无需改业务代码即可落盘：

| Reporter | 输出 | 用途 |
|----------|------|------|
| `html` | `playwright-report/` | 人工查看失败步骤、trace、截图 |
| `json` | 单文件 JSON | CI 解析、自定义汇总 |
| `junit` | XML | GitHub Actions / 门禁 |
| `blob` | 二进制 | 多 shard 合并 |

**建议输出目录（与 Cloud 验收一致，可 gitignore）：**

```
test_data/TestResult/PhaseUI/
  playwright-report/          # HTML（可选提交摘要）
  results.json                # 机器可读
  junit.xml                   # CI
  artifacts/                  # 截图、下载的 CSV 等
```

当前 [playwright.config.js](../../frontend/playwright.config.js) 仅 `reporter: [['list']]`（终端）。落地时增加 `html` + `json` + `junit` 即可。

可选：脚本将 `results.json` 摘要追加到 `docs/architecture/KIE_TEST_RUN_TRACKER.md` 的「阶段 UI-E2E」表（与 MP / H-Batch 同级）。

---

## 4. Pro UI 功能面与 E2E 可测性矩阵

基于 `frontend/index.html` + `app.js`（Analysis + Batch tab）。

### 4.1 Smoke（建议优先，~5–10 min）

| ID | 功能 | E2E 可测性 | 断言示例 |
|----|------|------------|----------|
| UI-S-01 | 页面加载、`/health` 成功 | 高 | 状态栏/API 版本文案出现 |
| UI-S-02 | 上传单文件入队 | 高 | `.queue-item` 数量 + 文件名 |
| UI-S-03 | Run Analysis 单页图 | 中–高 | 队列 `processing` → `completed`（需 mock 或短样例 + 长 timeout） |
| UI-S-04 | 右侧 Content / Result tab 切换 | 高 | 对应 panel `visible` |

### 4.2 队列与预览（本次手工问题回归）

| ID | 功能 | E2E 可测性 | 断言示例 |
|----|------|------------|----------|
| UI-Q-01 | 选中项优先 Run Analysis | 高 | 先完成 file2 再 file1（DOM 顺序与选中态） |
| UI-Q-02 | 完成后自动处理下一 pending | 高 | 两文件均 `completed` |
| UI-Q-03 | 侧边栏页数文案 | 高 | `Completed · N pages`，N>0 |
| UI-Q-04 | 多页 PDF 分页控件 | 高 | `1 / 3` → 点 next → 页码变 2，`#documentImage` src 变化 |
| UI-Q-05 | 切换队列项刷新预览 | 中 | 中栏文件名 / 页码与选中项一致 |

**说明：** UI-Q-03/04 依赖后端 `document_info.pages` 与 `/upload` 的 `page_count`（已在 `fix` 分支修复）。

### 4.3 Analysis Options

| ID | 功能 | E2E 可测性 | 说明 |
|----|------|------------|------|
| UI-A-01 | 打开 Options 对话框 | 高 | modal visible |
| UI-A-02 | 切换 layout / table / KIE | 高 | checkbox 状态 |
| UI-A-03 | `kie_pages` 输入 | 高 | 值传入 analyze（可 intercept API 断言 Form） |
| UI-A-04 | `kie_query_fields` | 中 | JSON 校验错误提示（Phase B 偏 API） |

### 4.4 结果展示与导出

| ID | 功能 | E2E 可测性 | 说明 |
|----|------|------------|------|
| UI-R-01 | Content > Text / Tables / Figures | 高 | 非空态 DOM |
| UI-R-02 | KIE Fields 子 tab | 中 | `enable_kie` 且完成后出现 |
| UI-R-03 | 单任务 export JSON/CSV | 中 | `download` 事件或 API 直连对比 |

### 4.5 Batch tab（v1.2）

| ID | 功能 | E2E 可测性 | 说明 |
|----|------|------------|------|
| UI-B-01 | 多文件建批 | 高 | `batch_id` 显示 |
| UI-B-02 | Start / Pause / Resume | 中 | 状态文案变化 |
| UI-B-03 | 表格行数与状态 | 高 | 6 行 completed |
| UI-B-04 | 下载 CSV / JSON | 高 | 文件落盘 + 表头断言 |

与 [batch_kie.md](../acceptance/batch_kie.md) / 阶段 H-Batch 对齐；E2E 偏 UI 操作，质量仍以 `kie_production_hit` 为准。

### 4.6 不宜纯 E2E 或成本过高

- Layout SVG 框与图像像素对齐  
- 多页合成 PDF + layout（PP-Structure 兼容性）  
- 首次 KIE 冷启动 60s+（单独用例 + `test.setTimeout`）  
- Help 外链、Templates/History（未实现或外链）

### 4.7 E2E 绿则缩小手工范围（已落地用例）

**权威对照表**：[UI_VERIFICATION_MATRIX.md](../acceptance/UI_VERIFICATION_MATRIX.md) §2.

| 条件 | 可减手工（本次未改动相关代码） | 仍须手工 |
|------|-------------------------------|----------|
| `npm run test:unit` + `npm run test:e2e` 全绿 | UI-S-01/02/04，UI-Q-01/03/04，Vitest 队列逻辑 | 真实 GPU KIE、Analysis Options、Export、Batch、三栏 resize、视觉 |
| 仅改 `shared/queue_preview.js` | UI-Q-03/04 + Vitest 相关用例 | 真 API 轮询、KIE Fields 展示 |
| 发版 / 合 `main` | 重复点击已映射 smoke/queue 用例 | §5 最小手工集（矩阵 §5） |

助手每次改 Pro/Lite/共享 UI 后，须在交付中附 **Manual test scope**（`004-project.mdc`）。

---

## 5. 推荐环境与前置条件

与 [CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md) 一致：

1. **终端 1**：`cd backend && python run.py`（`DEBUG=false` 避免 reload 丢任务）  
2. **终端 2**：Playwright `baseURL` / `PW_INDEX_URL` 指向 **`http://127.0.0.1:8000/frontend`**（`run.py` 挂载；根 `/` 为 API JSON）  
3. **样例**：`test_data/testfiles/invoices/`、`multipage/`、`batch/manifest.json`  
4. **GPU**：完整 KIE E2E 需在 Cloud Studio；本地可 **mock `/api/v1/analyze`** 返回固定 `task_id` + 轮询 stub（Smoke 层）

**Playwright 配置建议（落地时）：**

```javascript
// 示例：仅规划，未启用
reporter: [
  ['list'],
  ['html', { outputFolder: '../../test_data/TestResult/PhaseUI/playwright-report' }],
  ['json', { outputFile: '../../test_data/TestResult/PhaseUI/results.json' }],
  ['junit', { outputFile: '../../test_data/TestResult/PhaseUI/junit.xml' }],
],
timeout: 120_000,  // KIE 路径
```

---

## 6. 分层实施路线（讨论用）

| 阶段 | 范围 | 预估用例数 | 依赖 |
|------|------|------------|------|
| **P0** | UI-S-01~04 + UI-Q-01~05 | 8–12 | 后端 + 小图/PDF；可 mock analyze |
| **P1** | UI-A-01~03、UI-R-01~02 | 6–8 | 真实 analyze 或录制 HAR |
| **P2** | UI-B-01~04 | 4–6 | Batch + 6 文件，长超时 |
| **P3** | 视觉回归 / 多浏览器 | 可选 | baseline 维护成本 |

**与现有测试分工：**

| 层级 | 工具 | 职责 |
|------|------|------|
| 契约 / 编排 | backend pytest（Phase A） | `kie_pages`、batch export、orchestrator |
| 浏览器逻辑 | Vitest + `queue_preview.js` | 页数 fallback、队列选取、纯函数 |
| 用户路径 | Playwright E2E | 点击、上传、翻页、队列顺序、下载 |
| 推理质量 | Cloud 手动 API + Tracker | MP、H-Batch、KIE-ACCEPT |

---

## 7. 落地前待决问题（后续讨论）

1. **运行位置**：仅 Cloud Studio 手动？还是 GitHub Actions（无 GPU 时是否 mock）？  
2. **静态资源**：已通过 `run.py` 挂载；`PW_BASE_URL=http://127.0.0.1:8000/frontend`（见 v1.2.1 Cloud 清单 §6）  
3. **超时与并行**：KIE 用例是否串行、`workers: 1`？  
4. **结果入库**：`TestResult/PhaseUI/` 是否 gitignore（建议 yes）？Tracker 是否增加「阶段 UI-E2E」表？  
5. **与 Lite 关系**：Pro 与 Lite 分离 spec 目录，避免混跑。

---

## 8. 相关文件

| 路径 | 说明 |
|------|------|
| [frontend/playwright.config.js](../../frontend/playwright.config.js) | `baseURL` → `/frontend`；html/json/junit reporter |
| `frontend/tests/e2e/process-smoke.e2e.js` | UI-S P0 smoke |
| `frontend/tests/e2e/process-queue.e2e.js` | UI-Q P0 queue/preview |
| [frontend/tests/unit/queue.test.js](../../frontend/tests/unit/queue.test.js) | 队列/页数纯函数单测 |
| [frontend/shared/queue_preview.js](../../frontend/shared/queue_preview.js) | 可复用逻辑（Vitest 已覆盖） |
| [test_data/acceptance/batch_kie.md](../acceptance/batch_kie.md) | Batch 验收规则 |
| [test_data/acceptance/multipage_kie.md](../acceptance/multipage_kie.md) | 多页 KIE 验收规则 |

---

## 9. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-05 | 初稿：基于手工测试问题与 Playwright 能力分析，供后续落地讨论 |
