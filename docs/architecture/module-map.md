# DocuVision Module Map（当前态模块地图）

> Status: living — 结构变化时同步（owning 行见 `docs/agent-ops/core/doc-sync.md`）
> 最近对照：v1.8.3.0 / commit 695414a（2026-09-16）
> 事实源：`scripts/frontend_domain_map.json`（前端域/白名单/init 序列）· `backend/app/routers/`（后端域）·
> `backend/tests/test_route_inventory.py`（路由守恒 55）· 各 lint 脚本（门禁规则号）
> 规则真源：`docs/agent-ops/core/frontend.md`（前端 F1-F6 语义 / 落点义务）与 `DEVELOPMENT.md` 第 1-6 条——
> 本图 §5 只登记「门禁与其实现」，不复述规则文本。
> 本图回答「模块怎么摆、依赖往哪走、跨模块怎么对接、哪些门禁在守」。语义/契约向设计见
> `docuvision-system-design.md`，两者互补不重叠。§2/§3/§5 由 `scripts/audit_agent_ops.py` 对账（§6）。

## §1 分层与依赖律（手写·慢变，audit 不对账本节）

```
后端栈                                前端栈
main.py（装配：include_router）        app.js（装配：imports + initXxx({deps})）
  ↓ import 只许向下                      ↓ import 只许向下（F3）
routers/ 13 域                          modules/ 15 域（D1-D15）
  ↓                                      ↓（域内兄弟 | utils/* | F5 白名单叶服务）
services/（业务）                        shared/* · preview-state · api-state（共享状态）
  ↓                                      （D4 shell / D5 preview-paging / D8 pipeline / D9 result-panels 为目录域）
orchestration/（编排）
  ↓
core/runtime.py（共享状态枢纽）
```

依赖律（两栈同构，五条）：
- **L1 装配层唯一**：后端 `main.py` / 前端 `app.js` 只装配不放域逻辑（R1 背景 / F2 棘轮）。
- **L2 import 只许向下**：后端 routers→services→orchestration→core，禁环（R3：禁 import app.main）；
  前端 域→（域内兄弟|utils|shared|白名单叶服务），**禁 import `../app.js`、禁跨域 import 兄弟域**（F3）。
- **L3 跨域调用经装配注入**：后端 include_router 挂载；前端 `initXxx({deps})` 装配期一次性注入（F6），
  **禁 `window.*` 桥**。
- **L4 共享状态走指定枢纽**：后端 `core/runtime.py`；前端 `preview-state` / `api-state`
  （唯一允许双向 live binding 的例外）。
- **L5 例外必须注册制**：前端 import 白名单 = `frontend_domain_map.json`（F5）；新增例外 = 数据编辑
  （criterion L1+L2+L3 + evidence），不开代码口子。

## §2 后端段：routers/ 13 域（逐行守恒：每行端点数 == 该文件 AST 实测；合计 55 == 冻结清单）

<!-- audit:backend-domains -->
| 域 | 文件 | 端点数 | 职责 | owning doc |
| system | backend/app/routers/system.py | 4 | 运行状态/引擎清单（GET /、/health、/engines） | — |
| analyzer | backend/app/routers/analyzer.py | 3 | OCR/上传/分析入口（/ocr、/upload、/analyze；提交后经编排层后台处理） | — |
| documents | backend/app/routers/documents.py | 2 | 上传分析入口 + 文档画像（/analyze、/document/profile） | docuvision-system-design.md |
| jobs | backend/app/routers/jobs.py | 4 | Phase 1 作业查询与调试产物（status/result/debug/debug 文件下载） | — |
| tasks | backend/app/routers/tasks.py | 6 | 任务生命周期（状态/取消/删除/页图/HITL 提交） | docuvision-system-design.md |
| tasks_content | backend/app/routers/tasks_content.py | 7 | 任务结果内容（result/blocks/分页内容） | docuvision-system-design.md |
| trial | backend/app/routers/trial.py | 2 | GLM trial 真值比对与 HTML 报告（POST gt-diff/{task_id} + GET report） | — |
| batch | backend/app/routers/batch.py | 9 | 批量任务管理（start/pause/resume/cancel/retry/results） | batch-ui-roadmap.md |
| batch_export | backend/app/routers/batch_export.py | 5 | 批量导出打包 | batch-ui-roadmap.md |
| kie | backend/app/routers/kie.py | 3 | KIE 分析选项/模板 | kie.md、kie-custom-fields.md |
| hitl | backend/app/routers/hitl.py | 3 | 人工复核队列 | docuvision-system-design.md |
| webhooks | backend/app/routers/webhooks.py | 2 | 订阅清单/注册（WEBHOOK_ENABLED 开关 + admin-token 双守卫，fail-closed） | — |
| pdftools | backend/app/routers/pdftools.py | 5 | PDF 工具（split/merge/metadata） | shared-ui-shell.md |

分层对接方式（后端）：
- **router → service**：域内 import，路由函数显式 `response_model` 声明后编排调用（黄金样例 `routers/system.py`）。
- **service → orchestration / core**：业务模块经编排层进管线；共享状态唯一枢纽 `core/runtime.py`（禁 import app.main）。
- **装配**：`main.py` 逐域 `include_router`（无 prefix，路径全量——R2）。

## §3 前端段：modules/ 15 域（集合守恒：本表第一列 == domain_map.json domains 键集）

<!-- audit:frontend-domains -->
| 域 | 文件 | 性质 | 对接方式 |
| D1 api-base | frontend/modules/api-base.js | 普通域 | init 装配；API 可达性探针（/health、/engines） |
| D2 status-bar | frontend/modules/status-bar.js | 叶服务（F5 白名单） | 任何域可直 import |
| D3 upload-queue | frontend/modules/upload-queue.js | 普通域 | init 装配；任务取消/删除调 tasks 域端点 |
| D4 shell-init | frontend/modules/shell/{ui,tools}.js（2 文件） | 目录域 | init 装配；tools 子模块调 pdftools 端点 |
| D5 preview-paging | frontend/modules/preview-paging/{core,nav,render}.js（3 文件） | 目录域 | init 装配；预览上传 /upload + 页图调 tasks 端点 |
| D6 options-dialog | frontend/modules/options-dialog.js | 普通域 | init 装配；引擎/模式选择经表单提交 |
| D7 kie-mapping | frontend/modules/kie-mapping.js | 普通域 | init 装配；文档画像调 /document/profile |
| D8 pipeline | frontend/modules/pipeline/{run,result}.js（2 文件） | 目录域 | init 装配；提交 /analyze、轮询/取结果；known_edge_pairs → D5/D7/D9 经注入 |
| D9 result-panels | frontend/modules/result-panels/{demo-transaction,enhance,figures,json,quality,tables,text}.js（7 文件） | 目录域 | init 装配（黄金样例 json.js）；渲染注入数据 |
| D10 overlay | frontend/modules/overlay-render.js | 普通域 | init 装配；overlay 图层渲染（直接 fetch 图片 src） |
| D11 floating-progress | frontend/modules/floating-progress.js | unwired（P-008） | 无 import 者；浏览器从不加载（接线待 P-008 决策） |
| D12 export-csv | frontend/modules/export-csv.js | 普通域 | init 装配；导出经注入 URL 下载 |
| D13 notifications | frontend/modules/notifications.js | 叶服务（F5 白名单） | 任何域可直 import |
| D14 batch | frontend/modules/batch.js | 普通域 | init 装配；批量生命周期全套端点 |
| D15 hitl-review | frontend/modules/hitl-review.js | 普通域 | init 装配；复核队列/提交端点 |

基建（非域；A3 对账本节全部登记数字与名单，格式勿改）：
- `frontend/modules/utils/`（4 文件）：纯工具，任何域可 import。
- `frontend/shared/`（9 条目）：跨批共享 DOM/样式/试件（含 trial-key.js）。
- F5 白名单叶服务（4）：`notifications`、`status-bar`、`api-config`、`kie-config`。
- 共享状态模块（2）：`preview-state`、`api-state`（L4 例外）。
- init 接线清单：`boot_sequence` 17 项（audit 只对账数量；顺序与接线完备性由 F6 管）。

## §4 跨端对接表（谁消费谁；本表行数不机检，A1 只查路径存在）

<!-- audit:cross-end -->
| 后端域 | 消费它的前端域 | 关键端点 |
| system | D1 api-base | /health、/engines |
| analyzer | D5 preview-paging（/upload 预览上传）、D8 pipeline（/analyze 提交） | /upload、/analyze |
| documents | D7 kie-mapping、D8 pipeline | /document/profile、/analyze |
| tasks | D3 upload-queue、D5 preview-paging、D8 pipeline、D15 hitl-review | /tasks/{id}、/cancel、/page-image/{n} |
| tasks_content | D8 pipeline | /result、/blocks |
| batch | D14 batch | /batch 生命周期全套 |
| batch_export | D14 batch（动态路径）、D12 export-csv（注入 URL） | /batch/{id}/export… |
| hitl | D15 hitl-review | /hitl/reviews… |
| pdftools | D4 shell(tools.js) | /pdf-tools/split、/merge、/metadata |
| kie | 无独立消费端点：KIE 选项经 /analyze 表单参数携带；/kie/templates 无模块调用 | — |
| jobs / webhooks | 无前端消费（Phase 1 遗留查询 / 管理面 API，供客户端脚本或运维调用） | — |
| trial | 无前端消费（shared/trial-key.js 是 fetch/WebSocket 鉴权桥，不调 trial 端点；gt-diff 由操作方调用） | — |

注：前端 URL 多以 `API_BASE_URL`（已含 `/api/v1`）拼接，全文检索时勿只搜 `/api/v1/` 字面量。
/ocr 无 JS 消费（index.html 仅遗留标签文案）。D11 floating-progress 未接线，不列为任何域的消费者。

## §5 不变量门禁表（单元格语法见 §6 A0；状态列管退役）

<!-- audit:gates -->
| 规则 | 断言 | 机检实现 | DEVELOPMENT.md 条目 | 状态 |
| R1 | 路由装饰器只进 routers/ | scripts/lint_routes.py（`_check_file`） | 第 2 条 | active |
| R2 | APIRouter 无 prefix、路径全量 | scripts/lint_routes.py（`_apirouter_has_prefix`） | 第 2 条 | active |
| R3 | 禁 import app.main | scripts/lint_routes.py（`_check_file`） | 第 3 条 | active |
| INV-1 | (method,path) 集合 == 冻结清单 55 | backend/tests/test_route_inventory.py（`test_route_inventory_matches_frozen_set`） | 第 2 条 | active |
| INV-2 | 路由四要素 AST 冻结（name/signature/docstring/decorator kwargs） | backend/tests/test_route_contract_freeze.py（`test_route_contract_matches_frozen_baseline`） | 第 2 条 | active |
| S-a/b/c | 行数预算 500 + 棘轮只减不增；main.py 禁 @app. 路由（脚本内编号 R-a/R-b/R-c） | scripts/lint_file_size.py（`DEFAULT_BUDGET`） | 第 1 条 | active |
| F1 | 前端行数预算+单文件棘轮 | scripts/lint_frontend.py（`check_f1`） | 第 4 条 | active |
| F2 | app.js 顶层函数棘轮 | scripts/lint_frontend.py（`check_f2`） | 第 5 条 | active |
| F3 | import 方向（禁 ../app.js、禁跨域） | scripts/lint_frontend.py（`check_f3`） | 第 4 条 | active |
| F4 | 装配形态 | scripts/lint_frontend.py（`check_f4`） | 第 5 条 | active |
| F5 | 叶服务注册制 | scripts/lint_frontend.py（`check_f5`） | 第 4 条 | active |
| F6 | init 必被装配（名字级弱断言；P-008 gap 在案） | scripts/lint_frontend.py（`check_f6`） | 第 6 条 | active |
| C1-C8 | B0 基线校准（设计 rev2 断言；--report-out 存档） | scripts/check_frontend_baseline.py | — | 时点工具 |
| C4 | shared 反向依赖（B5 后由 F3 取代） | scripts/check_frontend_baseline.py | — | retired |
| C5 | preview-state 例外存在性（模块常驻后失效） | scripts/check_frontend_baseline.py | — | retired |

注：INV-1/INV-2/S-a/b/c 为本图命名（脚本内无同名规则号，实现函数/常量以反引号标出）；
R1-R3 沿用 kernel `routing.md` 硬规则编号；lint_file_size 内部编号 R-a/R-b/R-c 记于断言列。

OpenAPI 全量快照：云端 pytest（上云前本机自查用 INV-2 契约冻结测试）——发版路径，非 PR 门禁。

## §6 对账协议（audit_agent_ops.py check 3，A0-A5）

| 断言 | 内容 | 级别 |
| A0 解析守卫 | 3 个锚各**恰好出现一次**（缺失/重复 = ERROR）；锚块数据行非空；数据行列数 == 表头列数；列按表头名定位（缺列 = ERROR）；§5 状态列 ∈ {active, retired, 时点工具}；「机检实现」单元格符合语法 `<path>` 或 `<path>（\`symbol\`）`：全大写 symbol → 该文件须有 `<symbol> =` 赋值；**其余一律按 `def <symbol>` 查找，查不到 = ERROR（fail-closed；未知 symbol 形态同样落到此错）**；无 symbol → 只断言 path 存在；状态列必须是裸枚举值，备注一律写进断言列 | ERROR |
| A1 路径存在 | 全文抽 `backend/ frontend/ scripts/ docs/ packages/` 前缀路径（含行号剥离、glob 字符拒绝）+ §2/§3 单元格 `{a,b}.js` 花括号展开，逐个须存在于 worktree；无豁免前缀（出现运行时产物路径 = ERROR，届时带证据再加豁免） | ERROR |
| A2 计数守恒 | §2 行数 == routers/*.py（除 __init__）数；**逐行**：端点数列 == 该文件 AST 实测（复用 `test_route_inventory._route_from_decorator`，import 失败 = ERROR）；**三条腿**：§2 端点数合计 == AST 合计 == `EXPECTED_COUNT`（55）；§3 第一列**集合** == `domains.keys()`；§3 `（N 文件）`单元格 == 展开后实际存在的文件数 | ERROR |
| A3 基建对账 | §3 基建 5 个登记数字与名单：utils 文件数（4）/ shared 条目数（9）/ `leaf_services`（4，且名单与 json 键 basename 一致）/ `shared_state_modules`（2，同前）/ `boot_sequence`（17） | ERROR |
| A4 登记完备 | 本文件出现在 docs/README.md Architecture 节；doc-sync.md owning 表含 module-map.md | ERROR |
| A5 新鲜度 | 头部「最近对照」版本 vs CHANGELOG 第一个 `## [x.y.z]` 头：两侧各取前 3 段数字成元组比较，**doc < latest → WARN（含双方版本号）**；CHANGELOG 无匹配 → WARN skip；禁止字符串 rstrip 归一化 | WARN |

刷新触发（owning 行）：新增/删除 routers 域文件或 modules 域 → 同步 §2/§3 行 + 端点数/文件数 +
§5 门禁行 + 头部对照行。本机命令：`python scripts/audit_agent_ops.py`（与 CI 同一实现）；
解析器回归：`python scripts/audit_agent_ops.py --selftest`。
