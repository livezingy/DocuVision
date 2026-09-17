# 📖 前端代码说明

> **DocuVision 前端应用的详细文档和架构说明**

## 🎯 前端概览

前端是一个纯 JavaScript 单页应用（SPA），使用现代化的 UI 设计，与后端 REST API 通信。

### 主要特性

- ✅ **零依赖**: 不需要 Node.js、npm 或任何构建工具
- ✅ **即用**: 直接在浏览器中打开 HTML 文件即可运行
- ✅ **自适应**: 完全响应式设计，支持各种屏幕尺寸
- ✅ **现代 UI**: 黑暗主题、流畅动画、清晰布局
- ✅ **实时反馈**: 动态状态更新、进度条、日志显示
- ✅ **完整功能**: 支持所有后端功能

### 状态栏与主导航

- 底部 **PaddleOCR / PaddleX 版本** 与 **API 版本** 来自 `GET /api/v1/health`（`dependencies`、`api_version`）；直连 `:8000` 时 `GET /health` 等价。**KIE ready/cold** 来自 `health.kie.model_loaded`（后台 `DOCUVISION_KIE_WARMUP` 完成后约 12s 内会自动再拉一次 health 刷新）。
- 已移除虚假 **Memory** 读数；**Templates / History** 从未实现已从顶栏移除。顶栏：**Document Processing**、**Batch Processing**、**Reviews**（HITL）、**PDF Tools** 可用；**Settings** 仍为禁用占位；**Help** 打开 `HELP_DOC_URL` 或默认 `/docs`。
- **v1.4**：Analysis Options → Processing 可选 **Table mapping**（`table_template`）；Content 子 Tab **Mapped rows** 展示 `mapped_table_rows`。

## 📁 文件结构

```
frontend/
├── index.html          # 唯一入口 HTML；app.js 以 type="module" 加载
├── app.js              # 装配层：imports + 依赖注入 + 17 步引导序列 + mediator
│                       #   （B5a 终态 211 行 / 1 个顶层函数，棘轮管理）
├── modules/            # 原生 ESM 模块（v1.8.3 起，无构建工具、无打包）
│   ├── utils/          # 纯函数工具：geometry / csv / text / dom
│   ├── shell/          # D4 页面骨架：ui.js（页签/标注/面板/JSON 视图）+ tools.js（引擎/导出/PDF 工具）
│   ├── preview-paging/ # D5 预览分页：core（共享基座）+ nav + render
│   ├── pipeline/       # D8 处理链：run（发起/轮询）+ result（结果落地）
│   ├── result-panels/  # D9 结果面板：quality / text / tables / figures / enhance / json / demo-transaction
│   ├── overlay-render.js      # D10 SVG 叠加渲染 + 标注命中
│   ├── options-dialog.js      # D6 分析选项对话框（含处理模式钩子）
│   ├── kie-mapping.js         # D7 KIE 字段与表格映射
│   ├── upload-queue.js        # D3 上传队列
│   ├── batch.js               # D14 批处理
│   ├── hitl-review.js         # D15 人工复核
│   ├── export-csv.js          # D12 CSV 导出
│   ├── floating-progress.js   # D11 浮动进度卡
│   └── 叶服务 / 共享状态：notifications、status-bar、api-base、api-config、
│       api-state、preview-state、kie-config
├── shared/             # 经典脚本 + CSS（过渡期保留；新模块一律不进 index.html）
├── styles.css          # 样式表和主题
└── tests/
    ├── e2e/            # Playwright（4 套 *.e2e.js，走 mock API；需 npx playwright install chromium）
    └── unit/           # vitest + jsdom
```

> **结构规则（v1.8.3 起，机器可判——详见仓库根 `DEVELOPMENT.md` 第 4-6 条）**：
> `frontend/modules/**` 新文件 ≤500 行；模块只允许 import `./utils/*`、同目录兄弟、
> 白名单叶服务/共享状态与 `../shared/*`；**禁 import `../app.js`、禁跨域 import 兄弟域模块**
> （跨域一律经 app.js 装配注入）；新模块文件不得出现在 `index.html`（由 app.js import 链加载）。
>
> 门禁：`python scripts/lint_frontend.py`（F1-F7；F7 = 孤儿模块可达性，例外登记
> `scripts/frontend_domain_map.json` 的 `known_orphans`）+ `python scripts/check_frontend_baseline.py`
> （C0-C8）+ `python scripts/check_frontend_baseline.py --edges`（跨域边表，须与设计稿一致）。
> 风格 linter（P-010 阶段 1，2026-09-17 起）：`cd frontend && npm run lint`（ESLint flat config，
> 仅 `no-unused-vars` + `no-undef`，作用域 `app.js` + `modules/**` + `shared/**`；`tests/**` 属第二批）。
> **尚未接 CI**——清零并观察后再定（P-010 阶段 3）。

## 🔧 配置和初始化

### API 连接配置

```javascript
// modules/api-config.js
export const API_BASE_URL = resolveApiBaseUrl();  // 走 window.DOCUVISION_CONFIG 或 location 推导
```

改地址不再改 `app.js`：`api-config.js` 是唯一的静态配置叶服务（4 个常量 + 2 个 URL helper），
`preview-state.js` 承载可变共享状态。**不要**再把配置写回入口。

### 初始化流程（三段式，v1.8.3 起）

页面加载分三步，顺序不可换：

1. **模块图求值**——`app.js` 顶部的 `import` 链把 33 个模块全部加载（原生 ESM，浏览器直接执行）。
2. **依赖装配（模块顶层，早于任何运行时调用）**——跨域调用没有 import 通道（第 4-6 条硬规范），
   一律在这里注入。每个被注入的 `initXxx({ deps })` 用同名模块级绑定承接，因此模块内的调用点
   与拆分前**字节级一致**：

   ```javascript
   // app.js - 装配段（节选）
   initKieMapping({ getSelectedProcessingMode });              // D6 ↔ D7 环
   initOverlayRender({ previewHelpers, fetchTaskBlocks, updateContentText, initAnnotationInteractions, … });
   initPreviewNav({ renderDocumentWithAnnotations, renderResults: (r) => updateResultsDisplay(r) });
   initPipelineRun({ checkApiReachable, startProcessing 相关 deps, … });
   initUploadQueue({ switchToQueueItem, fetchDocumentProfileForQueueItem, … });
   initShellUi({ startProcessing, openAnalysisOptionsDialog, updateEnhancementTabs, … });
   ```

   `updateResultsDisplay` 是唯一留在 `app.js` 的**域函数**（mediator）：D5/D8 两半都回调它，
   由它按固定顺序驱动 D9/D10 各面板。

3. **`DOMContentLoaded` 引导序列（17 步，顺序被机检断言）**：

   ```javascript
   document.addEventListener('DOMContentLoaded', () => {
       clearResultsDisplay();          // 清残留结果
       updateStatusBar();              // 状态栏
       initializeAPIConnection();      // 健康检查 + 页脚
       initUploadZone();               // 上传区
       initTabs(); initHelpButton(); initResultTabs(); initActionButtons();
       initAnalysisOptionsDialog({ … });   // D6，deps 单行注入
       initEngineSelectors(); initAnalysisView(); initExportButtons();
       initBatchProcessing({ getProcessingOptions });
       initHitlReviews(); initPdfTools(); initPreviewPagination();
       insertInitialSkeleton();        // 骨架屏（e2e 的就绪信号）
   });
   ```

   > `scripts/frontend_domain_map.json` 的 `boot_sequence` 是这 17 步的权威副本；
   > `check_frontend_baseline.py` C3 校验步数与顺序。改动引导序列 = 同步改该文件。

## 📊 主要模块

### 按域模块总表（v1.8.3 拆分后）

| 域 | 文件 | 职责 |
|---|---|---|
| D3 上传队列 | `modules/upload-queue.js` | 拖拽/选择上传、队列渲染、处理调度（`initUploadZone` / `handleFiles` / `createQueueItem` / `processNextInQueue`） |
| D5 预览分页 | `modules/preview-paging/{core,nav,render}.js` | 页图加载与分页控件（core 为共享基座）、页导航、预览渲染与叠加触发 |
| D6 选项对话框 | `modules/options-dialog.js` | Analysis Options 模态、处理模式读取、`syncProcessingModeUI` 钩子 |
| D7 KIE 映射 | `modules/kie-mapping.js` | 文档画像预扫、表格映射资格、KIE 字段解析与 Fields 渲染 |
| D8 处理链 | `modules/pipeline/{run,result}.js` | 发起分析/轮询进度（run）、结果落地（result，经 mediator） |
| D9 结果面板 | `modules/result-panels/*.js` | 七子面板：quality / text / tables / figures / enhance / json / demo-transaction |
| D10 叠加渲染 | `modules/overlay-render.js` | 页图坐标绑定、SVG 叠加、标注命中高亮 |
| D4 页面骨架 | `modules/shell/{ui,tools}.js` | 导航页签、结果页签、标注 tooltip、面板拖拽、JSON 视图；引擎选择、导出按钮、PDF 工具 |
| 批处理 / HITL / 导出 / 进度 | `batch.js`、`hitl-review.js`、`export-csv.js`、`floating-progress.js` | D14 / D15 / D12 / D11 |
| 叶服务与共享状态 | `notifications.js`、`status-bar.js`、`api-base.js`、`api-config.js`、`api-state.js`、`preview-state.js`、`kie-config.js` | 通知 / 状态栏 / 健康检查 / 静态配置 / 可变缓存（白名单，见 `DEVELOPMENT.md` 第 4 条） |
| 纯函数工具 | `modules/utils/{geometry,csv,text,dom}.js` | 坐标换算、CSV/Markdown、文本归一、HTML 转义 |

> 权威边界：`scripts/frontend_domain_map.json`（域 → 函数清单 + 状态归属 + 导入白名单）
> 与设计稿 `docs/R&D/PLAN/v1.8.3-frontend-split/cross-domain-edges.md`（跨域调用与注入矩阵）。
> 本文不再逐函数列举——直接读模块文件是更可靠的入口。

### 4. 导出功能

**支持的格式**:
- JSON: `/api/v1/tasks/{id}/export/json`
- CSV: `/api/v1/tasks/{id}/export/csv`
- Markdown: `/api/v1/tasks/{id}/export/markdown`
- Word: `/api/v1/tasks/{id}/export/docx`
- Excel: `/api/v1/tasks/{id}/export/xlsx`
- ZIP: `/api/v1/tasks/{id}/export/zip` (tables + figure crops; optional `?include=tables,figures,json`)

**相关代码**:
- 导出按钮: `initExportButtons()`
- 导出处理: `exportResults()`（侧栏 JSON/CSV/Markdown/DOCX/XLSX/ZIP 走 `/tasks/{id}/export/{format}`）
- 侧栏 ZIP：右栏 Export Results 第 5 个按钮，下载 `{task_id}_pack.zip`（`manifest.json` + `tables/` + `figures/`）
- 侧栏 CSV：`ExportService.to_csv`，每表分隔行 `=== Table {n} (Page {p}) confidence={pct}% ===`，下一行可选 `Caption: …`；`+`/`=` 等公式前缀会加 `'` 以免 Excel `#NAME?`
- Tables 卡片 Export CSV：`downloadCurrentTableCsv()`，仅当前表，文件名 `table_{nn}_p{page}.csv`；卡片 header 显示 `table.caption`
- Figures 轮播不含 `is_merged` 项；告警条提供 View merged crop；卡片 header 可显示短 caption

### 5. 批处理 (`initBatchProcessing()`)

**功能**:
- 创建批处理任务
- 监控批处理进度
- 暂停/恢复/取消
- 导出批处理结果

**相关代码**:
- 批处理界面: Batch Processing 标签
- 批处理 API: `/api/v1/batch`

### 6. SVG 布局叠加

**功能**:
- 在文档预览图像上绘制布局块（SVG `viewBox` 与图像坐标对齐）
- 支持 hover 高亮与块类型标签
- 与 Content 面板联动

**相关代码**:
- 叠加渲染: `renderDocumentWithAnnotations()` in `modules/overlay-render.js`
- 标注命中与 tooltip: `highlightResultItem()`（overlay-render）+ `initAnnotationInteractions()`（`modules/shell/ui.js`）
- 预览容器: `#documentPage` / `#documentImage` in `index.html`
- 样式: `styles.css`（`.layout-overlay` 等）

## 🎨 UI 布局

### 三列布局

```
┌─────────────────────────────────────┐
│         顶部导航栏                   │
├─────────┬─────────────┬─────────────┤
│  左列   │   中列      │   右列      │
│ 文件    │ 文档预览    │ 结果显示    │
│ 管理    │             │             │
│         │             │             │
│         │             │             │
├─────────┴─────────────┴─────────────┤
│         底部状态栏                   │
└─────────────────────────────────────┘
```

### 左列 - 文件管理
- 上传区域（拖拽/点击）
- 处理队列列表
- 队列控制按钮（取消等）

### 中列 - 文档预览
- 当前文档显示
- SVG 布局叠加层
- 分页导航

### 右列 - 结果显示
- 选项卡导航（OCR、Layout、Table、导出等）
- 结果内容显示
- 控制面板（元素列表等）

## 🔌 API 交互

### 主要 API 调用

```javascript
// 1. 上传文件并分析
fetch('/api/v1/analyze', {
    method: 'POST',
    body: formData  // 包含文件和选项
})

// 2. 检查处理状态
fetch('/api/v1/tasks/{taskId}')

// 3. 获取结果
fetch('/api/v1/tasks/{taskId}/result')

// 4. 获取页面图像
fetch('/api/v1/tasks/{taskId}/page-image/{pageNum}')

// 5. 获取布局分析
fetch('/api/v1/tasks/{taskId}/layout')

// 6. 导出结果
fetch('/api/v1/tasks/{taskId}/export/{format}')
```

## 🎯 新增功能说明

### API 连接初始化 (新增)

```javascript
// app.js - 新增函数
async function initializeAPIConnection() {
    // 1. 检查 /health 端点
    // 2. 获取服务器信息
    // 3. 显示连接状态
    // 4. 处理连接失败的情况
}
```

**功能**:
- 页面加载时自动检查后端连接
- 显示服务器版本和功能信息
- 如果无连接，显示警告信息
- 提供清晰的用户反馈

### SVG 布局叠加

```javascript
// modules/preview-paging/render.js — after the preview image lands
async function updateDocumentPreview(result) {
    // 1. Load page image from /api/v1/tasks/{id}/page-image/{page}
    // 2. Fetch layout blocks when needed
    // 3. renderDocumentWithAnnotations() (modules/overlay-render.js) draws the
    //    SVG overlay aligned to the image natural size
}
```

**功能**:
- 在预览图上绘制识别的布局块
- 多种元素类型，颜色区分角色
- 鼠标 hover 高亮
- 与右侧 Content 子 Tab 同步

## 🔐 安全性考虑

- ✅ 所有 API 调用使用 HTTPS（在生产环境）
- ✅ 没有敏感信息存储在客户端
- ✅ 文件大小限制（后端实施）
- ✅ CORS 正确配置（后端实施）

## 📱 响应式设计

前端完全响应式设计，支持：
- 📱 手机 (320px+)
- 📱 平板 (768px+)
- 💻 桌面 (1024px+)
- 🖥️ 宽屏 (1920px+)

## 🚀 性能优化

- ✅ 懒加载图像
- ✅ 事件委托（减少事件监听器）
- ✅ 节流状态更新（状态栏）
- ✅ 缓存 DOM 查询结果
- ✅ 异步操作（不阻塞 UI）

## 🐛 调试技巧

### 打开开发者工具

```
Windows/Linux: F12 或 Ctrl+Shift+I
Mac: Cmd+Option+I
```

### 查看日志

前端会输出详细的日志信息：

```javascript
// 查看初始化信息
console.log('App initialized');

// 查看 API 调用
console.log('[API] Fetching...');

// 查看错误
console.error('[Error]...');

// 查看布局叠加
console.log('[Layout] ...');
```

### 检查网络请求

在 Network 标签中查看：
- `/api/v1/analyze` - 上传和分析
- `/api/v1/tasks/{id}` - 查询状态
- `/api/v1/tasks/{id}/result` - 获取结果
- `/api/v1/tasks/{id}/layout` - 获取布局

## 📚 进一步学习

- **JavaScript**: 先看 `app.js`（装配层）的装配段与引导序列，再按需进入 `modules/` 对应域
- **HTML/CSS**: 查看 `index.html` 和 `styles.css`
- **Layout overlay**: `renderDocumentWithAnnotations()` in `modules/overlay-render.js`
- **API**: 查看 `http://localhost:8000/docs` 的 Swagger 文档

## 🔄 常见修改

### 修改 API 地址

```javascript
// modules/api-config.js
export const API_BASE_URL = resolveApiBaseUrl();  // 由 window.DOCUVISION_CONFIG 或 location 推导
```

### 修改主题颜色

```css
/* styles.css */
:root {
    --primary-color: #00d084;      /* 修改此值 */
    --dark-bg: #0a0e27;
    --light-text: #ffffff;
}
```

### 添加新功能

1. 在 `DOMContentLoaded` 中调用初始化函数
2. 创建对应的初始化函数（`init*()` 命名）
3. 在相应的模块中添加功能代码
4. 调用后端 API 获取数据
5. 使用 DOM 操作渲染结果

## 💡 最佳实践

- ✅ 使用 `fetch()` API 而非 XMLHttpRequest
- ✅ 使用 `async/await` 处理异步操作
- ✅ 捕获所有 Promise 的错误
- ✅ 使用 `console.log()` 进行调试
- ✅ 给所有 DOM 元素添加 ID 或 class
- ✅ 使用事件委托处理动态元素

## 🎓 总结

前端是一个功能完整、用户友好的 Web 应用，通过 REST API 与后端通信。它提供了：

- 直观的文件上传界面
- 实时的处理状态反馈
- 完整的结果展示和交互
- 多格式导出功能
- 高度可定制和可扩展

无需任何构建工具或依赖管理，完全可以直接在浏览器中运行！

---

**版本**: 1.8.3  
**最后更新**: 2026-09-15（v1.8.3 B5b：文件结构 / 初始化流程 / 主要模块三节按拆分后实际重写）  
**维护者**: DocuVision Team

> 拆分后的权威入口是**模块文件本身** + `scripts/frontend_domain_map.json`（域边界）+
> 设计稿 `docs/R&D/PLAN/v1.8.3-frontend-split/`（边表与注入矩阵）。本文的「🔌 API 交互」
> 「🎨 UI 布局」「📱 响应式设计」「🚀 性能优化」等节保留为功能性描述（端点与布局未变），
> 但其函数名示例以模块文件为准——`app.js` 现在只有装配与 mediator。
