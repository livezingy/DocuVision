# 后端路由架构规范

> 生成自 kernel `docs/agent-ops/core/`（routing）。勿手改副本；改共享约束请编辑 kernel 后重跑 `scripts/sync_agent_rules.py`。
<!-- kernel-ref: routing.md:6c3bfff63e516733 -->

## 目标
把 2644 行的 `main.py` 收敛为 268 行装配层；路由全部进 `backend/app/routers/`，用机器可判规则锁死风格，使不同 Agent 后续新增路由时产出同构代码。

## 硬规则（`lint_routes.py` 机器判，违反 = CI 红）
1. **路由只进域 router**：`@app.get|post|put|delete|patch|websocket` 装饰器只允许出现在 `backend/app/routers/*.py`；`main.py` 与 `services/` 出现即红。新路由写进对应域文件，必要时新建域。
2. **`router = APIRouter()` 且禁止 `prefix` 参数**：路径写全量，`include_router` 不重复挂前缀——保证 OpenAPI 路径不变。
3. **禁止 import `app.main`**：`routers/`、`core/runtime.py`、`services/` 不得 `from app.main import ...`（防环 + 重依赖）；共享状态走 `core/runtime.py`。

## 新增/删除路由的强制动作（防「门禁阻碍演进」）
4. **登记清单**：`backend/tests/test_route_inventory.py` 维护显式 `ROUTES` 表（域 → 路径列表）；新增必须登记、删除必须注销，route 数守恒断言随之更新。
5. **更新 OpenAPI 快照**：新增/删除路由改变 `app.openapi()` → 全量快照测试 additive 更新 baseline 并重新落盘（云测）；未同步更新快照 = 红。上云前先用规则 6 在本机自查。
6. **本机契约冻结（先于云测）**：`backend/tests/test_route_contract_freeze.py` 以 AST 冻结每条路由的**函数名 / 签名 / 文档串 / 装饰器关键字**（即 OpenAPI 可见面）。改动这四项须显式重生成：`cd backend && DOCUVISION_ROUTE_FREEZE=write pytest tests/test_route_contract_freeze.py`。**纯搬移/重构（不改契约）不得触发重生成**——v1.8.2 C2 的翻车点正是「顺手清理 docstring 乱码」导致 `description` 漂移，当时只有云端全量快照能抓。

## 黄金样例（样例即真源）
- 新增路由先照 `backend/app/routers/system.py`（拆分后最小域）的结构抄：`router = APIRouter()` 置顶 → 服务/依赖 import → 路由函数（`response_model` 显式声明）。
- 样例与本规范冲突时以样例为准；改样例须同步本规范。

## 本机 lint
`python scripts/lint_routes.py`（stdlib AST，不 import、不碰 paddle）：校验规则 1/2/3；拆分前自动跳过 1/2，拆分后全量。
