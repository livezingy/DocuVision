# 文档归属表（kernel `doc-sync.md` 机制 2 附表）

> 本表是 kernel `docs/agent-ops/core/doc-sync.md` 机制 2 的附表：拆出 kernel 是为了让归属表能随
> 模块增删自由扩展，不挤占 kernel 的 ~60 行软上限（机制 1/3/4/5 与文档生命周期仍在 kernel）。
> 改代码模块时按表同步 owning doc（`updated <doc> §<节>`）；**表未覆盖的新模块，新增契约时一并补表**。
> 最近对照：v1.9.0 / commit 3fd4d11（2026-09-26，E2 单测 pin + OCR harness 晋升批次）

| 代码模块 | owning living doc |
|---------|-------------------|
| `backend/app/main.py` | `routing.md`（R1 装配层唯一 / R2 无 prefix）、`module-map.md` §1 |
| `backend/app/routers/**` | `routing.md`（域归属 / 无 prefix / 禁 `import app.main`）、`module-map.md` §2（域清单 / 端点数 / 对照行；逐域 owning doc 见该表「owning doc」列） |
| `backend/app/routers/batch.py`、`batch_export.py` | `batch-ui-roadmap.md` |
| `backend/app/routers/pdftools.py` | `shared-ui-shell.md` |
| `backend/app/routers/kie.py` | `kie.md`、`kie-custom-fields.md` |
| `backend/app/orchestration/**` | `docuvision-system-design.md` §4 |
| `backend/app/core/runtime.py` | `docuvision-system-design.md`（共享单例 / 装配 `init_runtime()`） |
| `backend/app/core/config.py` | `docuvision-system-design.md`（配置方式段） |
| `backend/app/models/api_models.py` | `docuvision-system-design.md` §6（三层数据结构模型） |
| `backend/app/services/kie/**`、`kie_qwen_service.py` | `kie.md`、`kie-custom-fields.md` |
| `backend/app/services/table_backfill.py`、`page_text_trust.py`、`proof_pack.py`、`proof_render.py`、`proof_report.py` | `provenance-review.md`（该文头部即声明「代码归属」） |
| `backend/app/services/layout_service.py`、`table_service.py`、`figure_service.py` | `pp-structurev3-official-findings.md`；契约向 `docuvision-system-design.md` §9.1（figure 另见 §11） |
| `backend/app/services/ocr_service.py` | `docuvision-system-design.md` §3.2–§3.4（`use_doc_unwarping` 固定 False 的引擎 init 不变量：该文 §3.4「当前固定为 False，引擎 init 硬编码」是 `POST /api/v1/ocr` 不声明却必须成立的回传坐标帧契约）；端点侧由 `backend/tests/test_ocr_service_engine_params.py` 承载（P-021） |
| `backend/app/services/export_service.py` | `docuvision-system-design.md` §9.1 |
| `backend/app/services/pack_export_service.py` | `docuvision-system-design.md` §9.1；`v1.6-roadmap.md`（发版后以 §9.1 为准） |
| `backend/app/services/persistence/queue_store.py` | `v1.5-roadmap.md`（Epic Queue persistence）；`v1.7-roadmap.md`（`analyze_jobs`） |
| `backend/app/services/persistence/analyze_job_store.py` | `v1.7-roadmap.md`；`docuvision-system-design.md` §9.1（单任务 result 持久化） |
| `backend/app/services/batch_service.py`、`hitl_queue.py` | `v1.5-roadmap.md`（Epic Queue persistence：`batches` / `_items` 结构、`load_from_db()` 语义、模块级单例签名不变）；批处理消费方另见 `batch-ui-roadmap.md` |
| `packages/docuvision-core/**` | `docs/README.md` §core + 相关 living doc |
| `frontend/**` | `frontend/README_FRONTEND.md`、`module-map.md` §3（域清单 / 文件数 / 白名单 / 对照行） |
| `scripts/lint_file_size.py`、`lint_routes.py`、`lint_frontend.py`、`check_frontend_baseline.py`、`audit_agent_ops.py`、`test_registry_audit.py`、`check_e2e_allowlist.py`、`unit_suite_pin.py` | **`DEVELOPMENT.md`（规范型 owning doc，非派生视图）**：规则文本在第 1-6 条；`module-map.md` §5 只登记「门禁与其实现」（E1 = e2e 白名单+套件 pin / **E2** = 单测 pin）；kernel `routing.md` / `frontend.md` 是同源规则（面向 Agent 的可执行措辞） |
| `scripts/docs_refs_audit.py` | `docs/architecture/doc-governance.md`（该文即规则文本；白名单/豁免/ALLOWLIST 的机器可读真源留脚本内常量；晋升自 PENDING P-022，2026-09-25） |

## 脚注

1. **owning doc 的判定**：只认「改这个模块就必须同步的 living 文档」。`docs/release/*` 为 frozen
   （发版快照），`docs/R&D/*` 为 local-only，两者都不作 owning doc——frozen 文档里的引用只算历史证据。
2. **服务层模块的归属已二分（2026-09-17，`PENDING.md` P-013 选项 C 执行完毕）**。判定规则：
   **「载体」= 该 living 文档在描述本模块自身的契约**（结构 / 签名 / 行为约束），改其契约就必须同步它；
   **仅在别处被引用名字**（表格单元格、示例、他人文档里的调用点）**不计**载体。
   - **有载体（已补入主表）**：`batch_service.py`、`hitl_queue.py` → `v1.5-roadmap.md`。
   - **无常驻 living 契约（23 个；改其内部实现无须同步任何 living 文档）**：`batch_export_service.py`、
     `hitl_policy.py`、`webhook_service.py`、`document_info_utils.py`、`document_profile.py`、
     `document_type_classifier.py`、`file_type_detector.py`、`kie_fields_update.py`、`formula_service.py`、
     `seal_service.py`、`page_type_probe.py`、`pdf_raster.py`、`pdf_tools_service.py`、`pymupdf_table_engine.py`、
     `single_file_pipeline.py`、`unified_layout_service.py`、`_layout_order.py`；
     `backend/app/core/{aistudio_compat,debug_utils,gpu_lib_path,trial_auth}.py`；
     `backend/app/models/{analyze_options,layout_result}.py`。
     **触发条件**：任一模块发生契约变更时**先定归属再改**——届时有契约就补入主表。
   - **仅被提及、按规则不计载体（线索留档，供将来复核）**：`hitl_policy` @ `kie.md`；`seal_service` @
     `pp-structurev3-official-findings.md`；`pdf_raster` @ `kie.md`；`layout_result` @
     `pp-structurev3-fix-plan.md`；另 `batch_export_service.py` 的实现伙伴 `routers/batch_export.py` 已归属
     `batch-ui-roadmap.md`，但该文档未描述本服务契约。
   - 证据（2026-09-17）：对上述 25 个模块做**双重**扫描——模块/文件名 与 派生类名（`BatchService` /
     `HitlReviewQueue` / `FormulaService` / …）——在 living 文档集（`docs/architecture/*.md` +
     `docs/agent-ops/**` + `DEVELOPMENT.md` + `frontend/README_FRONTEND.md`；`docs/release/**` frozen、
     `docs/R&D/**` local-only，均不计）内命中。两条口径结论一致（仅 `batch_service` / `hitl_queue` 命中），
     故「无载体」不是命名口径造成的假阴性。
3. 本表由人工维护（无机检对账，因「模块→文档」是判断而非可推导事实）；**能机检的是**该表所属的
   kernel 文件仍被 `docs/README.md` 索引、且表内仍含 `module-map.md` 归属行（audit check 3 A4）。
