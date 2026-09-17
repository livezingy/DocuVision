# DEVELOPMENT.md — 六条硬规范

> 每条都有对应的机检脚本，本地与 CI 同一实现，违反即红。
> 后端三条由 `lint_file_size.py` / `lint_routes.py` 把关；前端三条由
> `lint_frontend.py`（F1-F7）、`check_frontend_baseline.py`（C1-C8 + C9 注入保真）与
> ESLint（`cd frontend && npm run lint`，已接 CI）把关。

## 后端（三条）

1. **文件行数预算 500**：backend/app 与 scripts 下新文件超 500 行 CI 即红；
   存量超标文件在 scripts/file_size_allowlist.json 里棘轮管理（只减不增，
   缩小后跑 `python scripts/lint_file_size.py --update` 下调记录）。

2. **路由只进域 router**：新路由写进 backend/app/routers/ 对应域文件
   （必要时新建域），main.py 出现路由装饰器 = CI 红。main.py 只是装配层。

3. **叶子模块禁止 import app.main**：可独立测试的模块（渲染器、纯计算、
   后处理器）不得依赖 FastAPI 应用对象；需要共享状态的走 core/runtime.py。
   新服务模块的单测必须能在不启动 app 的情况下 import 通过。

## 前端（三条，v1.8.3 起）

4. **模块 ≤500 行 + import 只许向下**：`frontend/modules/**` 新文件超 500 行 CI 即红
   （存量超标走 `frontend_size_allowlist.json` 棘轮，只减不增）。模块只允许 import
   `./utils/*`、同目录兄弟文件、白名单叶服务（`notifications` / `status-bar` /
   `api-config` / `kie-config`）与共享状态模块（`preview-state` / `api-state`）、
   以及 `../shared/*`。**禁 import `../app.js`；禁跨域 import 兄弟域模块**——
   跨域调用一律走第 6 条的装配注入。（机检：lint F1 / F3 / F5）

5. **入口 app.js 只留装配**：`frontend/app.js` = imports + 依赖注入 + 引导序列 +
   mediator（`updateResultsDisplay`），**不放域逻辑**。行数与顶层函数数走棘轮，
   只减不增；缩小后跑 `python scripts/check_frontend_baseline.py --update` 下调记录。
   （机检：lint F2 / baseline C1 / C2）

6. **模块必须被装配、依赖必须注入**：`frontend/modules/**` 的每个
   `export function initXxx` 必须在 app.js 被调用——漏装配会让该模块的注入依赖
   留成空桩，用户一交互就炸，而语法与 F1-F7 全绿（机检：lint F6 + baseline C9——C9 断言 app.js 注入的
  key 集合**恰好等于**模块体读取的 `deps.*` 集合，缺 key 与多 key 都红）。跨域调用与
   跨批的同域拆分调用一律经 app.js 的 `initXxx({ deps })` 注入，**禁建 `window.*`
   桥**（装配期一次性完成，见 `docs/R&D/PLAN/v1.8.3-frontend-split/cross-domain-edges.md`）。
   新增跨域边要么追加注入、要么提前被调者出仓，并在边表登记。（机检：baseline C8）

> 已知 gap（记录在案，v1.9 候选）：F6 只有名字级断言——deps 侧已由 **C9**（2026-09-17 落地，
> P-008 gap 1）补齐；彻底解法（作用域分析）的中间态 = JSDoc + `tsc --allowJs --checkJs --noEmit`，
> 留 v1.9 前端批次评估。
> F7（模块可达性）只判"有没有被 import"，不判"接得对不对"：D11 `floating-progress.js`
> 已登记 `known_orphans`（P-008），浏览器仍不加载它——接回管线属 v1.9 行为变更。
> **运行时覆盖度报告（2026-09-17，P-008 gap 2 的 MVP）**：`cd frontend && npm run test:e2e` 顺带产出
> `test_data/TestResult/PhaseUI/coverage-<date>.md`（模块加载覆盖 / 各模块监听器"注册 vs 触发" /
> 目录聚合 / 运行时错误），`PW_COVERAGE=0` 可关闭打点。**它是报告不是门禁**（永不红）——用来给
> P-010 的清账提供机器写的死代码候选。首次运行即抓到 `onload="adjustDocumentSize()"` 的
> ReferenceError（内联处理器是 `no-undef` 的盲区，见 PENDING P-016）。
