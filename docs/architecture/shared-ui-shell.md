# Shared UI Shell（Pro）

Pro 共用三栏文档处理界面。本文定义**共享层边界**与维护流程，避免 Export、Result 工具栏等组件再次漂移。

> **Lite 已于 v1.8 退役**（commit `1c9807c`，必要时可从 git 历史 v1.7 锚点复活）。本文只描述 Pro 共享层；原 Lite 侧的 `lite-overrides.css` / `lite.js` 规范随其退役一并取消。

## 1. 四层目录职责

| 层级 | 路径 | 内容 |
|------|------|------|
| **L0 Tokens** | [`frontend/shared/tokens.css`](../../frontend/shared/tokens.css) | 颜色、字体、圆角、阴影 |
| **L1 Shell** | [`frontend/shared/layout.css`](../../frontend/shared/layout.css) | 三栏布局、顶栏、侧栏、状态栏、Content/Result 视图骨架 |
| **L2 Components** | [`frontend/shared/components.css`](../../frontend/shared/components.css) | Export 四按钮、Result JSON 工具栏、toast 动画 |
| **L3 Product-only** | [`frontend/pro-only.css`](../../frontend/pro-only.css) | Pro KIE / 公式等专属样式 |

### 共享 JS

| 模块 | 路径 | 用途 |
|------|------|------|
| Feature flags | [`frontend/shared/ui-features.js`](../../frontend/shared/ui-features.js) | Transactions/Mapped、Validation Dashboard 显隐 |
| Notifications | [`frontend/modules/notifications.js`](../../frontend/modules/notifications.js) | Toast（v1.8.3 B1 起迁入 modules/，F5 白名单叶服务，经装配注入） |
| Export | [`frontend/shared/export-ui.js`](../../frontend/shared/export-ui.js) | Export 按钮绑定与下载（`DocuVisionExport.init`） |
| Panel resize | —（v1.8.3 B0b 已移除，`panel_resize_removed` flag） | 三栏拖拽（历史功能，必要时从 git 历史复活） |

## 2. 加载顺序

**Pro**（当前 PR1）：

```
styles.css（仍含完整样式，视觉不变）
→ notifications.js, export-ui.js, app.js
```

**Pro**（PR2 已落地）：`index.html` 加载 `shared/components.css` + `pro-only.css`；Export 样式统一走 [components.css](../../frontend/shared/components.css)。

## 3. 禁止事项

在 [`pro-only.css`](../../frontend/pro-only.css) 中 **禁止** 覆盖以下选择器：

- `.export-*`
- `.result-tool-*`
- `.result-view-toolbar`

需改 Export 外观时，只改 [`components.css`](../../frontend/shared/components.css)，并做 §6 Pro 目视回归。

## 4. 新功能放置决策表

| 场景 | 放置位置 | 共享层是否受影响 |
|------|----------|------------------|
| Pro Figures / KIE | `app.js` + Pro API + `styles.css` / `pro-only.css` | 否（Pro 专属） |
| 新增 Export 格式 | `components.css` + `export-ui.js` + 后端路由 | 是（改动共享层，需 §6 回归） |
| Validation Dashboard | `ui-features.exportActions.validationDashboard` | 否（默认 false） |
| 队列 | 服务端队列（v1.5 SQLite `queue_store`） | 否 |

## 5. PR 流程

1. 若改 `frontend/shared/**`：按 §6 做 Pro 目视回归。
2. 日常 push 默认不跑 GitHub Actions（见 [`.cursor/rules/003-git.mdc`](../../.cursor/rules/003-git.mdc)）。

## 6. PRO-UI-EXPORT 目视回归（PR2 启用）

PR2 将 Pro 迁到 shared CSS 后，在 Pro 界面确认：

- Export 四按钮等宽 4 列 grid，图标 20×20
- Copy / Download JSON 工具栏与改前一致
- Export 四格式下载成功，toast 正常
- viewport 宽度变化时布局无意外换行
