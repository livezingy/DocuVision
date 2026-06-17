# Shared UI Shell（Pro + Lite）

Lite 与 Pro 共用三栏文档处理界面。本文定义**共享层边界**与维护流程，避免 Export、Result 工具栏等组件再次漂移。

## 1. 四层目录职责

| 层级 | 路径 | 内容 |
|------|------|------|
| **L0 Tokens** | [`frontend/shared/tokens.css`](../../frontend/shared/tokens.css) | 颜色、字体、圆角、阴影 |
| **L1 Shell** | [`frontend/shared/layout.css`](../../frontend/shared/layout.css) | 三栏布局、顶栏、侧栏、状态栏、Content/Result 视图骨架 |
| **L2 Components** | [`frontend/shared/components.css`](../../frontend/shared/components.css) | Export 四按钮、Result JSON 工具栏、toast 动画 |
| **L3 Product-only** | `apps/lite/frontend/lite-overrides.css` / 未来 `frontend/pro-only.css` | Lite Profile、品牌；Pro KIE/公式等 |

### 共享 JS   

| 模块 | 路径 | 用途 |
|------|------|------|
| Feature flags | [`frontend/shared/ui-features.js`](../../frontend/shared/ui-features.js) | Transactions/Mapped、Validation Dashboard 显隐 |
| Notifications | [`frontend/shared/notifications.js`](../../frontend/shared/notifications.js) | Toast（`DocuVisionNotify.show`） |
| Export | [`frontend/shared/export-ui.js`](../../frontend/shared/export-ui.js) | Export 按钮绑定与下载（`DocuVisionExport.init`） |
| Panel resize | [`frontend/shared/panel-resize.js`](../../frontend/shared/panel-resize.js) | 三栏拖拽 |

## 2. 加载顺序

**Lite**（[`apps/lite/frontend/lite.html`](../../apps/lite/frontend/lite.html)）：

```
tokens.css (via layout @import)
→ layout.css
→ components.css
→ lite-overrides.css
→ notifications.js, export-ui.js, lite.js
```

**Pro**（当前 PR1）：

```
styles.css（仍含完整样式，视觉不变）
→ notifications.js, export-ui.js, app.js
```

**Pro**（PR2 已落地）：`index.html` 加载 `shared/components.css` + `pro-only.css`；Export 样式与 Lite 共用 [components.css](../../frontend/shared/components.css)。

## 3. 禁止事项

在 [`lite-overrides.css`](../../apps/lite/frontend/lite-overrides.css) 中 **禁止** 覆盖以下选择器：

- `.export-*`
- `.result-tool-*`
- `.result-view-toolbar`

需改 Export 外观时，只改 [`components.css`](../../frontend/shared/components.css)，并同步 Lite checklist +（PR2 后）Pro 回归。

## 4. 新功能放置决策表

| 场景 | 放置位置 | 对方是否受影响 |
|------|----------|----------------|
| Pro Figures / KIE | `app.js` + Pro API + `styles.css` / `pro-only.css` | Lite 无对应 DOM → 不影响 |
| Lite Document Profile | `lite.js` + Lite API + `lite-overrides.css` | Pro 无 Profile → 不影响 |
| 两边新增 Export 格式 | `components.css` + `export-ui.js` + 各自后端路由 | 各实现 URL，UI 一致 |
| Validation Dashboard | `ui-features.exportActions.validationDashboard` | 默认 false，Pro/Lite 分别配置 |
| Lite 队列 IndexedDB | 仅 `lite.js` | Pro 用服务端队列 → 不影响 |

## 5. PR 流程

1. 若改 `frontend/shared/**`：更新 [`LITE_UI_TEST_CHECKLIST.md`](../../apps/lite/backend/tests/LITE_UI_TEST_CHECKLIST.md) 相关项；PR2 完成后补 Pro 目视回归。
2. 日常 push 默认不跑 GitHub Actions（见 [`.cursor/rules/003-git.mdc`](../../.cursor/rules/003-git.mdc)）。
3. Lite 验收：`cd apps/lite/backend && python run_lite.py`，浏览器打开 `/lite/lite.html`。

## 6. PRO-UI-EXPORT 目视回归（PR2 启用）

PR2 将 Pro 迁到 shared CSS 后，在 Pro 界面确认：

- Export 四按钮等宽 4 列 grid，图标 20×20
- Copy / Download JSON 工具栏与改前一致
- Export 四格式下载成功，toast 正常
- 与 Lite 同 viewport 宽度下布局无意外换行

## 7. 相关文档

- [Lite API / UI](../lite-api.md)
- [Lite 测试与 checklist](../../apps/lite/backend/tests/README.md)
