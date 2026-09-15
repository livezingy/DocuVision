# DEVELOPMENT.md — 六条硬规范

> 每条都有对应的机检脚本，本地与 CI 同一实现，违反即红。
> 后端三条由 `lint_file_size.py` / `lint_routes.py` 把关；前端三条由
> `lint_frontend.py`（F1-F6）与 `check_frontend_baseline.py`（C1-C8）把关。

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
   留成空桩，用户一交互就炸，而语法与 F1-F5 全绿（机检：lint F6）。跨域调用与
   跨批的同域拆分调用一律经 app.js 的 `initXxx({ deps })` 注入，**禁建 `window.*`
   桥**（装配期一次性完成，见 `docs/R&D/PLAN/v1.8.3-frontend-split/cross-domain-edges.md`）。
   新增跨域边要么追加注入、要么提前被调者出仓，并在边表登记。（机检：baseline C8）

> 已知 gap（记录在案，v1.9 候选）：F6 是名字级弱断言，抓不到"在 deps 里被引用但
> 忘了 import"（v1.8.3 B5a 实际踩中一次，靠 e2e + pageerror 探针定位）。彻底解法
> 需作用域分析。
