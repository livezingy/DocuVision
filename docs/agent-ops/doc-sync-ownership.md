# 文档归属表（kernel `doc-sync.md` 机制 2 附表）

> 本表是 kernel `docs/agent-ops/core/doc-sync.md` 机制 2 的附表：拆出 kernel 是为了让归属表能随
> 模块增删自由扩展，不挤占 kernel 的 ~60 行软上限（机制 1/3/4/5 与文档生命周期仍在 kernel）。
> 改代码模块时按表同步 owning doc（`updated <doc> §<节>`）；**表未覆盖的新模块，新增契约时一并补表**。
> 最近对照：v1.8.3.0 / commit 17142b0（2026-09-17，P-008 文档与测试治理批次）

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
| `backend/app/services/export_service.py` | `docuvision-system-design.md` §9.1 |
| `backend/app/services/pack_export_service.py` | `docuvision-system-design.md` §9.1；`v1.6-roadmap.md`（发版后以 §9.1 为准） |
| `backend/app/services/persistence/queue_store.py` | `v1.5-roadmap.md`（Epic Queue persistence）；`v1.7-roadmap.md`（`analyze_jobs`） |
| `backend/app/services/persistence/analyze_job_store.py` | `v1.7-roadmap.md`；`docuvision-system-design.md` §9.1（单任务 result 持久化） |
| `packages/docuvision-core/**` | `docs/README.md` §core + 相关 living doc |
| `frontend/**` | `frontend/README_FRONTEND.md`、`module-map.md` §3（域清单 / 文件数 / 白名单 / 对照行） |
| `scripts/lint_file_size.py`、`lint_routes.py`、`lint_frontend.py`、`check_frontend_baseline.py`、`audit_agent_ops.py`、`test_registry_audit.py` | **`DEVELOPMENT.md`（规范型 owning doc，非派生视图）**：规则文本在第 1-6 条；`module-map.md` §5 只登记「门禁与其实现」；kernel `routing.md` / `frontend.md` 是同源规则（面向 Agent 的可执行措辞） |

## 脚注

1. **owning doc 的判定**：只认「改这个模块就必须同步的 living 文档」。`docs/release/*` 为 frozen
   （发版快照），`docs/R&D/*` 为 local-only，两者都不作 owning doc——frozen 文档里的引用只算历史证据。
2. **尚未单列的服务层模块（TODO，登记于 `docs/R&D/PENDING.md` P-013）**：这些模块目前只在 frozen
   release 文档或测试清单里被引用，没有稳定的 living owning doc，**未经核实不填**（P-012 教训）：
   `batch_service.py`、`batch_export_service.py`、`hitl_policy.py`、`hitl_queue.py`、`webhook_service.py`、
   `document_info_utils.py`、`document_profile.py`、`document_type_classifier.py`、`file_type_detector.py`、
   `kie_fields_update.py`、`formula_service.py`、`seal_service.py`、`page_type_probe.py`、`pdf_raster.py`、
   `pdf_tools_service.py`、`pymupdf_table_engine.py`、`single_file_pipeline.py`、`unified_layout_service.py`、
   `_layout_order.py`；`backend/app/core/{aistudio_compat,debug_utils,gpu_lib_path,trial_auth}.py`；
   `backend/app/models/{analyze_options,layout_result}.py`。
3. 本表由人工维护（无机检对账，因「模块→文档」是判断而非可推导事实）；**能机检的是**该表所属的
   kernel 文件仍被 `docs/README.md` 索引、且表内仍含 `module-map.md` 归属行（audit check 3 A4）。
