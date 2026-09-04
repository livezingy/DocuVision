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
├── index.html          # 主 HTML 页面（484 行）
├── app.js              # 主应用逻辑（4287+ 行）
├── styles.css          # 样式表和主题
└── tests/              # 前端测试
    ├── e2e/            # 端到端测试
    │   └── example.spec.js
    └── unit/           # 单元测试
        └── example.spec.js
```

## 🔧 配置和初始化

### API 连接配置

```javascript
// app.js - 第 7 行
const API_BASE_URL = 'http://localhost:8000/api/v1';
```

修改此值来改变 API 连接地址。

### 初始化流程

当页面加载时，按以下顺序执行：

1. **`DOMContentLoaded` 事件触发**
   ```javascript
   document.addEventListener('DOMContentLoaded', () => { ... });
   ```

2. **API 连接检查** (新增)
   ```javascript
   initializeAPIConnection();  // 检查服务器是否运行
   ```

3. **UI 初始化**
   ```javascript
   initUploadZone();           // 初始化上传区域
   initTabs();                 // 初始化选项卡
   initActionButtons();        // 初始化按钮
   // ... 其他初始化
   ```

4. **显示骨架屏**
   ```javascript
   insertInitialSkeleton();    // 显示加载骨架
   ```

## 📊 主要模块

### 1. 文件上传管理 (`initUploadZone()`)

**功能**:
- 支持拖拽上传
- 点击选择文件
- 实时验证文件类型
- 队列管理

**相关代码**:
- 上传区域处理: `handleFiles()`
- 文件队列: `updateQueue()`
- 队列项渲染: `createQueueItem()`

### 2. 文档处理 (`runAnalysis()`)

**功能**:
- 与后端 API 通信
- 处理多个选项（OCR、Layout、Table 等）
- 监控处理进度
- 错误处理和重试

**相关代码**:
- 分析调用: `fetch('/api/v1/analyze')`
- 进度监控: `checkProcessingStatus()`
- 结果回调: `updateResultsDisplay()`

### 3. 结果显示 (`updateResultsDisplay()`)

**功能**:
- 显示 OCR 文本
- 文档预览上的 SVG 布局叠加（hover 高亮）
- 显示表格、图表、公式、印章等子 Tab
- 显示导出选项

**相关代码**:
- 结果渲染: `renderAnalysisResults()`
- 预览与叠加: `updateDocumentPreview()`、`renderBlocks()`（SVG overlay）
- 表格显示: `displayTableResults()`

### 4. 导出功能

**支持的格式**:
- JSON: `/api/v1/tasks/{id}/export/json`
- CSV: `/api/v1/tasks/{id}/export/csv`
- Markdown: `/api/v1/tasks/{id}/export/markdown`
- Word: `/api/v1/tasks/{id}/export/docx`
- Excel: `/api/v1/tasks/{id}/export/xlsx`

**相关代码**:
- 导出按钮: `initExportButtons()`
- 导出处理: `exportResults()`（侧栏 JSON/CSV/Markdown/DOCX/XLSX 走 `/tasks/{id}/export/{format}`）
- 侧栏 CSV：`ExportService.to_csv`，每表分隔行 `=== Table {n} (Page {p}) confidence={pct}% ===`
- Tables 卡片 Export CSV：`downloadCurrentTableCsv()`，仅当前表，文件名 `table_{nn}_p{page}.csv`

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
- 叠加渲染: `renderBlocks()` in `app.js`
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
// app.js — after result loads, updateDocumentPreview + renderBlocks
async function updateDocumentPreview(result) {
    // 1. Load page image from /api/v1/tasks/{id}/page-image/{page}
    // 2. Fetch layout blocks when needed
    // 3. renderBlocks() draws SVG overlay aligned to image natural size
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

- **JavaScript**: 查看 `app.js` 中的注释和函数文档
- **HTML/CSS**: 查看 `index.html` 和 `styles.css`
- **Layout overlay**: `renderBlocks()` in `app.js`
- **API**: 查看 `http://localhost:8000/docs` 的 Swagger 文档

## 🔄 常见修改

### 修改 API 地址

```javascript
// app.js 第 7 行
const API_BASE_URL = 'http://your-server.com/api/v1';
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

**版本**: 1.1.0  
**最后更新**: 2026-02-03  
**维护者**: DocuVision Team
