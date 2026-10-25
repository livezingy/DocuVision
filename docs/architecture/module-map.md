# DocuVision Module Map（当前态模块地图）

> Status: living — 结构变化时同步（owning 行见 `docs/agent-ops/core/doc-sync.md`）
> 最近对照：v1.12.0 / main 06d6e7c（2026-10-24，S1 落地批 0：新增 §2b services 15 域表 + §5 S1a/S1b/S1c/A2b 门禁行 +
> §1 后端依赖律改写——orchestration 定位为 services 的同级消费方；同日批 1：共享叶首登 pdf_raster（消解 2 边）+
> single_file_pipeline 上移 orchestration/（#13 消解，services→编排零例外），棘轮 15→12 条目；§2/§3 路由/前端域结构不变，55 守恒）
> 事实源：`scripts/frontend_domain_map.json`（前端域/白名单/init 序列）· `backend/app/routers/`（后端域）·
> `scripts/service_domain_map.json`（services 15 域，§2b）· `scripts/service_dependency_allowlist.json`（冻结跨域边，只减不增）·
> `backend/tests/test_route_inventory.py`（路由守恒 55）· 各 lint 脚本（门禁规则号）
> 规则真源：`docs/agent-ops/core/frontend.md`（前端 F1-F7 语义 / 落点义务）与 `DEVELOPMENT.md` 第 1-7 条——
> 本图 §5 只登记「门禁与其实现」，不复述规则文本。
> 本图回答「模块怎么摆、依赖往哪走、跨模块怎么对接、哪些门禁在守」。语义/契约向设计见
> `docuvision-system-design.md`，两者互补不重叠。§2/§3/§5 由 `scripts/audit_agent_ops.py` 对账（§6）。

## §1 分层与依赖律（手写·慢变，audit 不对账本节）

```
后端栈                                    前端栈
main.py（装配：include_router）            app.js（装配：imports + initXxx({deps}))
  ↓ import 只许向下（S1a）                  ↓ import 只许向下（F3）
routers/ 13 域（→runtime 枢纽通道 ✓）       modules/ 14 域（D1-D15，D11 已退役）
  ↓ 薄委托                                   ↓（域内兄弟 | utils/* | F5 白名单叶服务）
services/ 15 域（业务，§2b；域内互引 ✓，    shared/* · preview-state · api-state（共享状态）
  跨域须登记 S1b，禁→编排/路由/runtime）     （D4 shell / D5 preview-paging / D8 pipeline
orchestration/（编排 = services 的同级        / D9 result-panels 为目录域）
  消费方：DI 注入不建服务；含批 1 上移的
  single_file_pipeline——services→编排
  零例外，S1a 全量生效）
core/runtime.py（共享状态枢纽，双身份）
core/ · models/ · packages/（L4 叶子；packages 独立可安装）
```

依赖律（两栈同构，六条）：
- **L1 装配层唯一**：后端 `main.py` / 前端 `app.js` 只装配不放域逻辑（R1 背景 / F2 棘轮）。
- **L2 import 只许向下**：后端 `main → routers → services → core/models/packages`（S1a 机检）；
  **orchestration 是 services 的同级消费方**（构造期 DI 组装，不位于 services 之下）——services 禁→
  orchestration/routers/core.runtime（原唯一例外 #13 已于 2026-10-24 批 1 以「pipeline 上移」倒置消解，
  services→编排现为零例外）；禁环（R3：禁 import app.main）；
  前端 域→（域内兄弟|utils|shared|白名单叶服务），**禁 import `../app.js`、禁跨域 import 兄弟域**（F3）。
- **L3 跨域调用经装配注入**：后端 include_router 挂载；前端 `initXxx({deps})` 装配期一次性注入（F6），
  **禁 `window.*` 桥**。
- **L4 共享状态走指定枢纽**：后端 `core/runtime.py`；前端 `preview-state` / `api-state`
  （唯一允许双向 live binding 的例外）。
- **L5 例外必须注册制**：前端 import 白名单 = `frontend_domain_map.json`（F5）；后端跨域边豁免 =
  `service_dependency_allowlist.json`（S1b，只减不增，新增条目 = 红线先问）；新增例外 = 数据编辑
  （前端 criterion L1+L2+L3 + evidence），不开代码口子。

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

## §2b 后端段：services/ 15 域（三向守恒：本表文件列展开 ↔ `service_domain_map.json` ↔ 磁盘；fail-closed——新文件未映射 = ERROR）

<!-- audit:backend-service-domains -->
| 域 | 文件 | 职责 | owning doc | 出向跨域边 |
| layout | backend/app/services/{layout_service,_layout_geometry,_layout_order,unified_layout_service}.py（4 文件） | 版面结构与阅读顺序（主入口 + 几何/顺序私有叶 + unified 融合） | pp-structurev3-official-findings.md | layout->table |
| table | backend/app/services/{table_service,table_alignment,table_backfill,table_band_range,table_cell_confidence,table_cell_geo,table_html,table_layout,table_ocr_blocks,table_pseudo_filter}.py（10 文件） | 表格识别全家族：检测/伪表过滤/对齐/回填/HTML/逐格置信 | pp-structurev3-official-findings.md（table_service）· provenance-review.md（backfill/alignment） | table->figure、table->document |
| figure | backend/app/services/figure_service.py | 图像区域提取 | pp-structurev3-official-findings.md | — |
| formula | backend/app/services/formula_service.py | 公式区域提取 | — | — |
| ocr | backend/app/services/ocr_service.py | OCR 引擎封装 | docuvision-system-design.md §3.2–3.4 | — |
| seal | backend/app/services/seal_service.py | 印章区域提取 | — | — |
| kie | backend/app/services/kie/{KieManager,__init__,azure_schema,field_merge,field_validation,kie_field_metrics,kie_pages,query_fields,schema_templates,text_first,value_typer}.py（11 文件） + backend/app/services/{kie_fields_update,kie_qwen_service}.py（2 文件） | KIE 字段抽取/合并/校验/模板/指标 | kie.md、kie-custom-fields.md | kie->evidence、kie->hitl |
| evidence | backend/app/services/evidence/{__init__,findings_schema,gate,grounding,normalize,verifier}.py（6 文件） | 证据门禁与 grounding（三闸 / V0-V6 梯 / text-first） | evidence-layer.md | evidence->kie、evidence->hitl、evidence->document |
| hitl | backend/app/services/{hitl_policy,hitl_queue}.py（2 文件） | 人工复核策略与队列 | v1.5-roadmap.md（hitl_queue） | hitl->kie |
| batch | backend/app/services/{batch_service,batch_export_service}.py（2 文件） | 批量任务管理与导出打包 | v1.5-roadmap.md | batch->infra |
| report | backend/app/services/{export_service,pack_export_service,proof_pack,proof_render,proof_report}.py（5 文件） | 导出与证明包（export/pack + proof_* 三件） | docuvision-system-design.md §9.1 · provenance-review.md（proof_*） | report->table |
| document | backend/app/services/{document_info_utils,document_profile,document_type_classifier,file_type_detector,page_text_trust,page_type_probe}.py（6 文件） | 文档画像/类型分类/文件探测 + 页面文本信任与页型探测（裁决：page 并入） | provenance-review.md（page_text_trust） | — |
| infra | backend/app/services/{pdf_raster,pdf_tools_service,webhook_service}.py（3 文件） + backend/app/services/persistence/{__init__,analyze_job_store,queue_store}.py（3 文件） | 基础设施：PDF 光栅与工具、webhook、持久化 | v1.5-roadmap.md、v1.7-roadmap.md（persistence） | — |
| pipeline | backend/app/services/pii_mask.py | PII 掩码（分析前敏感信息遮蔽；原管线入口 `single_file_pipeline` 已于 2026-10-24 批 1 上移 `orchestration/`，#13 反向边就此消解） | — | — |
| trial | backend/app/services/trial/{__init__,gt_diff}.py（2 文件） | GLM trial 真值比对 | — | — |

共享壳（非域）：`backend/app/services/__init__.py` 为空壳（无 eager import），域归属 = shared，A2b 三向对账含它。
共享叶（1）：`pdf_raster`（I-1/P-038 首登：L1 零出向机检 + L2/L3 人审证据见 `service_domain_map.json` 的
`shared_leaf_modules`；任何域可 import，前端 F5 `leaf_services` 的后端对应物；名单与本行 A2b 双向对账）。
边列登记的是 allowlist **域对键**（双向对账：表内键 ⊆ allowlist 且 allowlist 键 ⊆ 表内）；条目粒度 = 具体边
（src_file + dst_module），见 `scripts/service_dependency_allowlist.json`。

## §3 前端段：modules/ 14 域（集合守恒：本表第一列 == domain_map.json domains 键集）

<!-- audit:frontend-domains -->
| 域 | 文件 | 性质 | 对接方式 |
| D1 api-base | frontend/modules/api-base.js | 普通域 | init 装配；API 可达性探针（/health、/engines） |
| D2 status-bar | frontend/modules/status-bar.js | 叶服务（F5 白名单） | 任何域可直 import |
| D3 upload-queue | frontend/modules/upload-queue.js | 普通域 | init 装配；任务取消/删除调 tasks 域端点 |
| D4 shell-init | frontend/modules/shell/{ui,tools}.js（2 文件） | 目录域 | init 装配；tools 子模块调 pdftools 端点 |
| D5 preview-paging | frontend/modules/preview-paging/{core,nav,render}.js（3 文件） | 目录域 | init 装配；预览上传 /upload + 页图调 tasks 端点 |
| D6 options-dialog | frontend/modules/options-dialog.js | 普通域 | init 装配；引擎/模式选择经表单提交 |
| D7 kie-mapping | frontend/modules/kie-mapping.js | 普通域 | init 装配；文档画像调 /document/profile |
| D8 pipeline | frontend/modules/pipeline/{run,result,task-socket}.js（3 文件） | 目录域 | init 装配；提交 /analyze、轮询/取结果；known_edge_pairs → D5/D7/D9 经注入 |
| D9 result-panels | frontend/modules/result-panels/{demo-transaction,enhance,figures,json,quality,tables,text}.js（7 文件） | 目录域 | init 装配（黄金样例 json.js）；渲染注入数据 |
| D10 overlay | frontend/modules/overlay-render.js | 普通域 | init 装配；overlay 图层渲染（直接 fetch 图片 src） |
| D12 export-csv | frontend/modules/export-csv.js | 普通域 | init 装配；导出经注入 URL 下载 |
| D13 notifications | frontend/modules/notifications.js | 叶服务（F5 白名单） | 任何域可直 import |
| D14 batch | frontend/modules/batch.js | 普通域 | init 装配；批量生命周期全套端点 |
| D15 hitl-review | frontend/modules/hitl-review.js | 普通域 | init 装配；复核队列/提交端点 |

基建（非域；A3 对账本节全部登记数字与名单，格式勿改）：
- `frontend/modules/utils/`（3 文件）：纯工具，任何域可 import（geometry 已于 v1.9 S4 退役）。
- `frontend/shared/`（9 条目）：跨批共享 DOM/样式/试件（含 trial-key.js）。
- F5 白名单叶服务（4）：`notifications`、`status-bar`、`api-config`、`kie-config`。
- 共享状态模块（2）：`preview-state`、`api-state`（L4 例外）。
- init 接线清单：`boot_sequence` 16 项（audit 只对账数量；顺序与接线完备性由 F6 管）。

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
/ocr 无 JS 消费（index.html 仅遗留标签文案）。D11 floating-progress 已于 v1.9 S4 退役（2026-09-20，
用户裁决：接线属新增行为且无需求方），不再列为任何域的消费者。

服务内部依赖（P-002，2026-09-29）：`backend/app/services/table_backfill.py` → `table_alignment.py`
单向 import（布局模型 / T1 值匹配 / T3 文本聚类 / sanity 闸的新代码宿主，D1 零迁移）；服务内部
依赖无前端消费，故不入上表。

## §5 不变量门禁表（单元格语法见 §6 A0；状态列管退役）

<!-- audit:gates -->
| 规则 | 断言 | 机检实现 | DEVELOPMENT.md 条目 | 状态 |
| R1 | 路由装饰器只进 routers/ | scripts/lint_routes.py（`_check_file`） | 第 2 条 | active |
| R2 | APIRouter 无 prefix、路径全量 | scripts/lint_routes.py（`_apirouter_has_prefix`） | 第 2 条 | active |
| R3 | 禁 import app.main | scripts/lint_routes.py（`_check_file`） | 第 3 条 | active |
| S1a | 层方向（02 表 1 ✗ 格 + A-2）：services 禁→orchestration/routers/runtime；orchestration 禁→routers/runtime；routers 禁互引；core(除 runtime)/models 禁→上三层；packages 禁→app.*（app.main 归 R3，A-5） | scripts/lint_services.py（`check_services`） | 第 7 条 | active |
| S1b | services 域归属 fail-closed（新文件必须落域，未映射/幽灵 = ERROR）+ 跨域 import 须在 allowlist 登记（冻结棘轮只减不增，新增条目 = 红线先问）**或目标为已登记共享叶**（`shared_leaf_modules`，L1 零出向机检 + L2/L3 人审证据，任何域可 import） | scripts/lint_services.py（`check_services`） | 第 7 条 | active |
| S1c | 域间依赖图无环：非豁免边成环 = ERROR；环上边全在册 = 90 天时钟到期后 WARN（A-9/A6 范式） | scripts/lint_services.py（`check_services`） | 第 7 条 | active |
| INV-1 | (method,path) 集合 == 冻结清单 55 | backend/tests/test_route_inventory.py（`test_route_inventory_matches_frozen_set`） | 第 2 条 | active |
| INV-2 | 路由四要素 AST 冻结（name/signature/docstring/decorator kwargs） | backend/tests/test_route_contract_freeze.py（`test_route_contract_matches_frozen_baseline`） | 第 2 条 | active |
| S-a/b/c | 行数预算 500 + 棘轮只减不增；main.py 禁 @app. 路由（脚本内编号 R-a/R-b/R-c） | scripts/lint_file_size.py（`DEFAULT_BUDGET`） | 第 1 条 | active |
| F1 | 前端行数预算+单文件棘轮 | scripts/lint_frontend.py（`check_f1`） | 第 4 条 | active |
| F2 | app.js 顶层函数棘轮 | scripts/lint_frontend.py（`check_f2`） | 第 5 条 | active |
| F3 | import 方向（禁 ../app.js、禁跨域） | scripts/lint_frontend.py（`check_f3`） | 第 4 条 | active |
| F4 | 装配形态 | scripts/lint_frontend.py（`check_f4`） | 第 5 条 | active |
| F5 | 叶服务注册制 | scripts/lint_frontend.py（`check_f5`） | 第 4 条 | active |
| F6 | init 必被装配（名字级；deps 侧由 C9 承接） | scripts/lint_frontend.py（`check_f6`） | 第 6 条 | active |
| F7 | 孤儿模块可达性：modules/** 每个文件须被 app.js/index.html/其它脚本 import，例外登记 `known_orphans`（P-008；当前在册 0 条——两个孤儿已于 v1.9 S4 退役） | scripts/lint_frontend.py（`check_f7`） | — | active |
| T1 | 测试登记与 Phase A CI 列表对账（登记表 ↔ 磁盘 ↔ workflow；P-008） | scripts/test_registry_audit.py（`check_test_registry`） | — | active |
| T2 | 测试 stub 作用域：`backend/tests` 内不得在**模块级**写 `sys.modules[...]`（收集期即生效 → 泄漏给邻居、破坏其 `importorskip` 环境闸门；P-023） | scripts/test_registry_audit.py（`check_stub_scope`） | — | active |
| DOC-1 | 文档墓碑前缀：对外物料不得出现已退役的路径/端口/命令/模块名（同行带退役标记视为公告；归档物料豁免；ALLOWLIST 只减不增） | scripts/docs_refs_audit.py（`check_retired_refs`） | — | active |
| DOC-2 | living-doc 路径漂移：`docs/architecture` 与本索引引用的代码路径必须存在（glob / 省略号跳过；WARN 级） | scripts/docs_refs_audit.py（`check_doc_drift`） | — | active |
| DOC-3 | PENDING 条目元数据与滞留：每条须带 `> status: <open/decided/landed/retained> · since: YYYY-MM-DD`，抬头 ID 索引须与 `### P-xxx` 标题集合一致（缺元数据/状态未知/日期非 ISO/未来日期/索引不符 = ERROR，fail-closed）；`landed` 超 90 天未晋升 = WARN（P-025） | scripts/docs_refs_audit.py（`check_pending_staleness`） | — | active |
| E1 | e2e 运行时错误允许清单的格式/时效/棘轮（数据文件，非许可）+ 套件用例数钉死防缩水（P-008 gap 2，2026-09-20 落 CI） | scripts/check_e2e_allowlist.py（`check_allowlist`） | — | active |
| E2 | 单测防缩水：`frontend/tests/unit/**/*.test.js` 的文件数与用例声明数必须等于 pin，`it.skip`/`it.todo`/`describe.skip` 出现即 ERROR、空套件 fail-closed（vitest 已在必需 job `lint` 内运行，但删文件/跳过不会让 CI 变红——P-008 最后一项残留，2026-09-26） | scripts/unit_suite_pin.py（`check_unit_pin`） | — | active |
| E3 | 测试夹具可复现：零依赖生成器 `--check` 必须与已提交样例零漂移（`OK - no drift`；非零退出即红。CI `lint` job 内执行；只覆盖该生成器的三个输出，图片类/其他生成器见 P-033 边界；P-033） | test_data/scripts/generate_general_testfiles_pure.mjs | — | active |
| C1-C8 | B0 基线校准（设计 rev2 断言；--report-out 存档） | scripts/check_frontend_baseline.py | — | 时点工具 |
| C9 | 注入保真：app.js 传入每个 initXxx 的 key 集合 == 模块体读取的 deps.* 集合（缺/多均红，不可判定签名 fail-closed；P-008 gap 1，2026-09-17 起常驻） | scripts/frontend_coupling.py（`check_injection_keys`） | 第 6 条 | active |
| C4 | shared 反向依赖（B5 后由 F3 取代） | scripts/check_frontend_baseline.py | — | retired |
| C5 | preview-state 例外存在性（模块常驻后失效） | scripts/check_frontend_baseline.py | — | retired |

注：INV-1/INV-2/S-a/b/c 为本图命名（脚本内无同名规则号，实现函数/常量以反引号标出）；
R1-R3 沿用 kernel `routing.md` 硬规则编号；lint_file_size 内部编号 R-a/R-b/R-c 记于断言列。

OpenAPI 全量快照：云端 pytest（上云前本机自查用 INV-2 契约冻结测试）——发版路径，非 PR 门禁。

## §6 对账协议（audit_agent_ops.py check 3，A0-A6）

| 断言 | 内容 | 级别 |
| A0 解析守卫 | 4 个锚各**恰好出现一次**（缺失/重复 = ERROR）；锚块数据行非空；数据行列数 == 表头列数；列按表头名定位（缺列 = ERROR）；§5 状态列 ∈ {active, retired, 时点工具}；「机检实现」单元格符合语法 `<path>` 或 `<path>（\`symbol\`）`：全大写 symbol → 该文件须有 `<symbol> =` 赋值；**其余一律按 `def <symbol>` 查找，查不到 = ERROR（fail-closed；未知 symbol 形态同样落到此错）**；无 symbol → 只断言 path 存在；状态列必须是裸枚举值，备注一律写进断言列 | ERROR |
| A1 路径存在 | 全文抽 `backend/ frontend/ scripts/ docs/ packages/` 前缀路径（含行号剥离、glob 字符拒绝）+ §2/§3 单元格 `{a,b}.js` 花括号展开，逐个须存在于 worktree；无豁免前缀（出现运行时产物路径 = ERROR，届时带证据再加豁免） | ERROR |
| A2 计数守恒 | §2 行数 == routers/*.py（除 __init__）数；**逐行**：端点数列 == 该文件 AST 实测（复用 `test_route_inventory._route_from_decorator`，import 失败 = ERROR）；**三条腿**：§2 端点数合计 == AST 合计 == `EXPECTED_COUNT`（55）；§3 第一列**集合** == `domains.keys()`；§3 `（N 文件）`单元格 == 展开后实际存在的文件数 | ERROR |
| A2b services 域对账 | §2b（锚 `backend-service-domains`）三向守恒：文件列花括号展开 ↔ `service_domain_map.json` 键（shared 壳走散文行登记）↔ 磁盘 `services/**/*.py`；未映射新文件 / 幽灵条目 / 行集不符 / 域集漂移 = ERROR（fail-closed，B-2）；边列域对键 ↔ allowlist `domain_pair` **双向**对账（I-3）；共享叶散文行计数与名单 ↔ `shared_leaf_modules` 对账；S1a/S1b/S1c 判据、冻结边棘轮与 90 天时钟由 `lint_services.py` 承载（§5 S 行，经 audit 接线） | ERROR / WARN |
| A3 基建对账 | §3 基建 5 个登记数字与名单（utils · shared · `leaf_services`（名单与 json 键 basename 一致）· `shared_state_modules`（同前）· `boot_sequence`（数量））；**登记文本以 §3 为单一源，本格不留数字副本** | ERROR |
| A4 登记完备 | 本文件出现在 docs/README.md Architecture 节；doc-sync owning 表（`docs/agent-ops/doc-sync-ownership.md`）含 module-map.md 行；该附表本身被 docs/README.md 索引 | ERROR |
| A5 新鲜度 | 头部「最近对照」版本 vs CHANGELOG 第一个 `## [x.y.z]` 头：两侧各取前 3 段数字成元组比较，**doc < latest → WARN（含双方版本号）**；CHANGELOG 无匹配 → WARN skip；禁止字符串 rstrip 归一化 | WARN |
| A6 孤儿登记时效 | `known_orphans` 每条须带 ISO `added`（缺失/格式错 = ERROR，fail-closed）；超过 `ORPHAN_STALE_DAYS`（90 天）仍在册 = **WARN**，要求重新裁决「接线或退役」并记入 PENDING（把"定期巡表"降为"看告警"；P-008 gap 2）——见 `frontend_coupling.py::check_orphan_staleness` | ERROR / WARN |
| A6 测试登记 | check 4（`scripts/test_registry_audit.py`）：`backend/tests/test_registry.json` ↔ 磁盘 `test_*.py` ↔ Phase A 列表三向对账；未登记 / 幽灵条目 / CI 跑未登记测试 = ERROR，CI 侧漂移 = WARN。**check 5**（同模块 `check_stub_scope`，P-023）：`backend/tests` 内**模块级** `sys.modules[...]` 写入 = ERROR（不可解析 = fail-closed ERROR） | ERROR/WARN |

刷新触发（owning 行）：新增/删除 routers 域文件或 modules 域 → 同步 §2/§3 行 + 端点数/文件数 +
§5 门禁行 + 头部对照行。**对照行的 commit 写本 PR 的 base commit**（不是合入后的 merge commit；口径见
kernel `docs/agent-ops/core/doc-sync.md` 机制 4）。本机命令：`python scripts/audit_agent_ops.py`（与 CI 同一实现）；
解析器回归：`python scripts/audit_agent_ops.py --selftest`。
