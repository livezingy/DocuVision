# DocuVision 整仓逻辑处理图（logic-flow）

> 依据 2026-11-05 的三份只读勘察绘制：backend/ 与 packages/ 处理逻辑、frontend、运维与治理管线。
> 分区口径与 `docs/architecture/module-map.md` 一致（13 个路由域 55 端点、services 15 域 + 6 共享叶、前端 D 编号域）。
> 本文件与 `docs/architecture/logic-flow.html`（Mermaid CDN 渲染版）内容一致；节点内 `文件:行号` 为源码锚点。

## 图① 端到端业务数据流（前端入口 → 后端路由 → services 域 → 证据/导出）

```mermaid
flowchart TB
  subgraph FE["① 前端 frontend/（原生 ESM 单页 · 无构建）"]
    direction TB
    IDX["frontend/index.html：唯一入口<br/>head defer 加载 KaTeX 与 shared/trial-key.js<br/>body 经典脚本 ui-features → demo-postprocess → export-ui<br/>最后以 type=module 加载 app.js"]
    TKEY["shared/trial-key.js：包装 window.fetch 与 WebSocket<br/>注入 X-API-Key 或 ?key= · 401 弹贴 key 横幅"]
    APPJS["frontend/app.js：DOMContentLoaded 引导 12 个 init（模块作用域另有 11 个 init 调用）<br/>模块作用域依赖注入 · updateResultsDisplay 中介"]
    OPTS["modules/options-dialog.js（D6）<br/>getProcessingOptions 组装 /analyze 表单字段"]
    RUNQ["modules/pipeline/run.js（D8）<br/>挑选队列项 → 表格映射门禁 → POST /api/v1/analyze"]
    SOCK["modules/pipeline/task-socket.js（D8）<br/>WS 事件流 · 30s ping · 最多 5 次重连<br/>重连耗尽回退 HTTP 轮询（每秒 · 上限 600 次）"]
    RES["modules/pipeline/result.js（D8）<br/>GET /result · GET /blocks · completeProcessing 防重入"]
    QUEUE["modules/upload-queue.js（D3）<br/>上传队列状态机<br/>仅两 fetch：运行中 POST /tasks/{id}/cancel（:187） · 删除时 DELETE /tasks/{id}（:249）"]
    NAV5["modules/preview-paging/（D5）<br/>nav.js:160 POST /upload 预览上传<br/>core.js:73 GET /page-image/:n 分页取图"]
    KIE7["modules/kie-mapping.js（D7）<br/>kie-mapping.js:63 POST /document/profile 画像预扫"]
    OVR10["modules/overlay-render.js（D10）<br/>overlay-render.js:114 GET /page-image/:n 标注底图"]
    BATCH["modules/batch.js（D14）<br/>POST /batch 与 start · 2s 轮询 · export 下载"]
    HITLF["modules/hitl-review.js（D15）<br/>reviews 列表与详情 · Save · Approve/Reject"]
    TOOLS["modules/shell/tools.js（D4）<br/>引擎下拉 · 导出按钮 · PDF Tools 三接口"]
    PANELS["modules/result-panels/*（D9 七面板 · enhance 内含公式/Seal 两子 tab）<br/>文本 · 表格 · 图片 · enhance（公式/Seal） · JSON · 质量 · 交易"]
  end

  IDX --> TKEY --> APPJS
  APPJS --> OPTS --> RUNQ
  APPJS --> QUEUE
  APPJS --> NAV5
  APPJS --> KIE7
  APPJS --> OVR10
  APPJS --> BATCH
  APPJS --> HITLF
  APPJS --> TOOLS
  APPJS --> PANELS
  RUNQ --> SOCK --> RES
  RES --> PANELS

  subgraph MW["② 后端装配与路由 backend/app/（FastAPI · 13 域 55 端点）"]
    MAIN["main.py:75-114 构建 app<br/>中间件添加序 TrialAuth(:92) → CORS(:96) → GZip(:114)<br/>（添加序≠层序：GZip 最外层 · CORS 居中装饰内层 TrialAuth 的 401）<br/>13 个 router 按 pinned 顺序 include_router · 无 prefix"]
    ANA["routers/analyzer.py:139 POST /api/v1/analyze<br/>存文件 · AnalyzeOptions 经 options_to_pipeline_dict 转管线 dict<br/>KIE query_fields 解析 · invoice/receipt/id_card 自动启用 KIE"]
    WSR["routers/tasks.py:46 WS /api/v1/tasks/:id/ws<br/>事件历史可重放"]
    DOC["routers/documents.py:30 POST /api/v1/documents:analyze（Phase 1 Job 版）<br/>GET /api/v1/jobs/{job_id}（jobs.py:22 · JobStatus） → GET /api/v1/jobs/{job_id}/result（JobEnvelope）"]
    LIGHT["轻端点（不经编排）<br/>analyzer.py /ocr · documents.py:175 /document/profile 薄委托 services<br/>analyzer.py /upload（:84-110）仅落盘建任务 · 不调任何 service"]
    TASKSR["routers/tasks.py 任务域 HTTP 端点<br/>POST /tasks/{id}/cancel（:146） · DELETE /tasks/{id}（:192）"]
    BATCHR["routers/batch.py:93 POST /api/v1/batch · :165/:166 start<br/>batch_service.start_batch（process_func + on_complete webhook 注入）"]
    EXPRT["routers/tasks_content.py:373<br/>GET /api/v1/tasks/:id/export/:format（json/csv/markdown/docx/xlsx/azure/zip）"]
    HITLR["routers/hitl.py:19 reviews 查询与解决<br/>routers/tasks.py:171 PATCH /tasks/:id/kie-fields"]
    CONTENT["routers/tasks_content.py<br/>GET /result · /layout · /blocks · /page-image · /figures"]
  end

  RUNQ -->|"multipart：document_type · enable_* · kie_* · engines · table_template"| ANA
  QUEUE -->|"POST /tasks/{id}/cancel · DELETE /tasks/{id}"| TASKSR
  NAV5 -->|"POST /upload（仅落盘建任务供预览）"| LIGHT
  KIE7 -->|"POST /document/profile（只提示不自动切模式）"| LIGHT
  NAV5 -->|"GET /page-image/:n"| CONTENT
  OVR10 -->|"GET /page-image/:n"| CONTENT
  SOCK <-->|"WS 事件 log/status/completed · HTTP 回退轮询"| WSR
  BATCH -->|"multipart name + files + options JSON"| BATCHR
  HITLF -->|"GET/POST reviews · PATCH kie-fields"| HITLR
  TOOLS -->|"GET export/:format · pdf-tools merge/metadata/split"| EXPRT
  RES -->|"GET result 与 blocks"| CONTENT
  PANELS -->|"取 figures 与 crop_url"| CONTENT

  subgraph ORCH["③ 编排层 backend/app/orchestration/"]
    PROC["core/runtime.py process_document（447-472）<br/>构造 DocumentPipelineOrchestrator<br/>DI 注入服务 + send_event + is_cancelled 回调"]
    ORCHD["document_pipeline_orchestrator.py run()（77-144）<br/>置 processing 态 · detect_file_type · 组装 PipelineContext<br/>取消 → cancelled · 异常 → failed 并 persist_task_safe"]
    EB["envelope_builder.py EnvelopeBuilder<br/>preprocessing/raw/fused/view/quality 五层 + 调试产物落盘"]
  end

  ANA -->|"tasks 注册 · background_tasks.add_task(process_document)"| PROC
  DOC -->|"job 注册 · background_tasks.add_task(process_document, job_id)"| PROC
  PROC --> ORCHD
  ORCHD --> ST1
  ST7 --- EB

  subgraph STEPS["10 步管线（orchestration/steps/ 五模块 re-export）"]
    direction TB
    ST1["1 layout_step（perception.py:68）<br/>layout_service.analyze · 回写 preprocessed_image_path 坐标系"]
    ST2["2 figure_step（perception.py:122）<br/>FigureService 裁剪 · best-effort 不使任务失败"]
    ST3["3 table_step（extraction.py:28）<br/>表格抽取与对齐"]
    ST4["4 kie_step（kie.py:35）<br/>query_fields 校验 · 文档类型白名单 · kie_service"]
    ST5["5 formula_step（extraction.py:169）<br/>公式识别"]
    ST6["6 seal_step（extraction.py:332）<br/>印章检测"]
    ST7["7 phase1_envelope_step（envelope.py:58）<br/>EnvelopeBuilder 五层 · 公式 in-place 替换 P-040 · seal 块融合"]
    ST8["8 evidence_step（governance.py:18）<br/>EVIDENCE_ENABLED 默认关"]
    ST9["9 pii_mask_step（governance.py:52）<br/>enable_pii_mask 默认关 · 持久化前出口掩码"]
    ST10["10 finalize_step（governance.py:78）<br/>envelope view/quality/preprocessing 并入 result<br/>persist_task_safe · webhook task.completed"]
    ST1 --> ST2 --> ST3 --> ST4 --> ST5 --> ST6 --> ST7 --> ST8 --> ST9 --> ST10
  end

  subgraph SVC["④ services 域（15 域 · scripts/service_domain_map.json）"]
    SVL["layout · figure · ocr"]
    SVT["table：table_service · table_alignment · table_backfill"]
    SVK["kie：kie_service · kie_default_rules"]
    SVM["formula · seal"]
    SVE["evidence：gate.run_evidence_gate 三闸<br/>grounding.attribute_candidates 引文页归属<br/>verifier.audit_finding V0-V6 梯度判档"]
    SVH["hitl_queue"]
    SVO["export_service 门面 + markdown/docx 渲染 Mixin<br/>pack_export_service 打包 tables+figures zip（超限 HTTP 413）"]
    SVB["batch_service · batch_export_service"]
  end

  ST1 --> SVL
  ST2 --> SVL
  ST3 --> SVT
  ST4 --> SVK
  ST5 --> SVM
  ST6 --> SVM
  ST8 -->|"闸门开启时"| SVE
  SVE --> HP["near_match / slot 结果以 hitl_payloads 数据出口"]
  HP --> HQ["编排点 steps/governance.py:41-48<br/>hitl_queue.enqueue · 回填 hitl_review_ids"]
  HQ -->|"enqueue"| SVH
  HQ -.->|"人工复核入口"| HITLR
  HITLR -->|"PATCH kie-fields"| KF["runtime._apply_kie_fields_to_task<br/>kie_fields_update（policy_resolver 注入）"]

  BATCHR --> SVB
  SVB --> SFP["orchestration/single_file_pipeline.py:13<br/>run_single_file_pipeline：自建 task_id<br/>is_canceled 恒 False · 不进全局 tasks dict"]
  SFP --> ORCHD
  EXPRT --> SVO

  ST10 -->|"completed 事件推送"| WSR
  ST10 -.->|"webhook 回调"| WB["services/webhook_service.webhook_registry<br/>（注册端点 routers/webhooks.py · batch on_complete 注入 routers/batch.py:86-88/:173）"]
```

说明：

1. 前端唯一入口 `frontend/index.html` 以 defer/module 顺序先加载 `frontend/shared/trial-key.js` 的 fetch/WebSocket 鉴权包装，再加载 `frontend/app.js`；Run Analysis 主链自 `frontend/modules/pipeline/run.js`（D6 组表单 → 表格映射门禁）POST `/api/v1/analyze`（`backend/app/routers/analyzer.py:139`），事件经 `backend/app/routers/tasks.py:46` 的 WebSocket 回流，重连耗尽回退每秒 HTTP 轮询（上限 600 次）。预览侧：`/upload`（预览上传）由 D5 `preview-paging/nav.js:160` 调用、`/document/profile`（画像预扫）由 D7 `kie-mapping.js:63` 调用，`/page-image` 由 D5 `preview-paging/core.js:73` 与 D10 `overlay-render.js:114` 调用；`upload-queue.js` 自身仅调 `POST /tasks/{id}/cancel`（:187）与 `DELETE /tasks/{id}`（:249）。
2. 后端把任务注册进 `backend/app/core/runtime.py` 的 tasks dict，经 `background_tasks.add_task(process_document)` 进入 `process_document`（runtime.py:447-472），由 DocumentPipelineOrchestrator.run（`backend/app/orchestration/document_pipeline_orchestrator.py:77-144`）按 112-123 行定义的固定顺序执行 steps/ 的 10 个 step（该顺序本次会话已抽查核对，与图一致）。
3. 10 步管线依次覆盖感知（layout/figure）、抽取（table/kie/formula/seal）、封套（phase1_envelope，五层 Envelope 由 `backend/app/orchestration/envelope_builder.py` 构建）与治理（evidence/pii/finalize）；证据链路受 `EVIDENCE_ENABLED` 闸控制（默认关），near_match/slot 结果以 hitl_payloads 数据出口，在编排点（steps/governance.py:41-48）入队 hitl_queue，人工复核经 `/api/v1/hitl/reviews` 与 `PATCH /tasks/:id/kie-fields` 回写。
4. 导出与批量为两条旁链：`GET /api/v1/tasks/:id/export/:format` 直入 export_service 门面（zip 由 pack_export_service 打包、超限 HTTP 413）；批量经 `batch_service.start_batch` → `run_single_file_pipeline`（`backend/app/orchestration/single_file_pipeline.py:13`）汇入同一编排器。另有 Phase 1 Job 版入口 `POST /api/v1/documents:analyze`（`backend/app/routers/documents.py:30`），经 `background_tasks.add_task(process_document, job_id)`（`documents.py:164`）汇入同一编排，查询端点为 `GET /api/v1/jobs/{job_id}`（`backend/app/routers/jobs.py:22` · JobStatus）与 `GET /api/v1/jobs/{job_id}/result`（JobEnvelope）——无 `/status` 后缀端点。

## 图② 模块/服务依赖关系（含 core / models / packages 边界）

```mermaid
flowchart LR
  subgraph FE2["frontend/（D 编号域互不 import · 仅经 app.js 注入）"]
    direction TB
    IDX2["index.html：唯一入口（无构建）<br/>经典脚本先于 ESM：trial-key → ui-features<br/>→ demo-postprocess → export-ui → app.js"]
    APP2["app.js 装配层<br/>initXxx 依赖注入（D6→D7 解环）<br/>DOMContentLoaded 引导 · updateResultsDisplay 中介"]
    D2["modules/ D 编号业务域（module-map §3 共 14 域）<br/>D1 api-base · D3 upload-queue · D4 shell/ui+tools · D5 preview-paging core/nav/render<br/>D6 options-dialog · D7 kie-mapping · D8 pipeline run/task-socket/result<br/>D9 result-panels · D10 overlay-render · D12 export-csv · D14 batch · D15 hitl-review<br/>（D2 status-bar · D13 notifications 为 F5 叶服务，见 LEAF2）"]
    STATE2["共享可变状态（仅两处 · setter 单写通道）<br/>modules/preview-state.js · modules/api-state.js"]
    LEAF2["F5 注册叶服务共 4：notifications · status-bar · kie-config · api-config<br/>+ modules/utils 纯工具 3：dom · text · csv（任何域可 import）<br/>C0/C6 零 document/window 门禁只约束 modules/utils/（api-config.js:7-12 注释自证）"]
    SH2["shared/ 横切脚本<br/>trial-key（fetch/WS 鉴权包装）· ui-features<br/>demo-postprocess · export-ui · queue_preview（ESM 纯函数）"]
  end

  IDX2 --> APP2
  APP2 -->|"同目录 sibling 可直连；跨域一律经此注入"| D2
  D2 --> STATE2
  D2 --> LEAF2
  IDX2 --> SH2
  SH2 -.->|"X-API-Key / ?key= 横切所有 fetch 与 WS"| D2

  subgraph RT3["backend/app/routers/（13 域 55 端点 · 互相无引用）"]
    direction TB
    RTH["重管线端点（经编排）<br/>POST /analyze · POST /documents:analyze · /batch"]
    WSEV["WS /tasks/:id/ws（tasks.py:46-90）<br/>事件流回放转发 · 不触发编排"]
    RTL["轻端点（不经编排）<br/>薄委托 services：/ocr · /document/profile · /pdf-tools<br/>/tasks/:id/export · /hitl<br/>/upload 仅落盘建任务（analyzer.py:84-110）"]
  end
  subgraph CORE3["backend/app/core/"]
    RUNT["runtime.py：共享状态枢纽（L4）<br/>import 时构建 9 个服务单例（GPU 探测失败自动回 CPU）<br/>tasks dict · 取消标志 · WS 状态 · init_runtime 接 SQLite 队列"]
    CFG2["config.py：Settings（pydantic-settings 读 .env）"]
    AUTH2["trial_auth.py：纯 ASGI 鉴权 · hmac.compare_digest<br/>配 key 不匹配即 401（无旁路）· 未配 key 放行（open local-dev）"]
    SUP2["gpu_lib_path · aistudio_compat（须在 import paddlex 前调用）· debug_utils"]
  end
  subgraph ORCH3["backend/app/orchestration/"]
    OD["document_pipeline_orchestrator.py<br/>+ steps/ 五模块（perception/extraction/kie/envelope/governance）"]
    EB2["envelope_builder.py（Phase 1 Envelope 五层）"]
    SFP3["single_file_pipeline.py（唯一消费方 routers/batch.py）"]
  end
  subgraph SVC3["backend/app/services/（15 域 + 6 共享叶）"]
    SV3["layout · table · figure · formula · ocr · seal · kie<br/>evidence · hitl · batch · report · document · infra · pipeline · trial<br/>共享叶：pdf_raster · text_first_contract · kie_default_rules<br/>page_text_trust · bbox_geometry · table_cell_confidence"]
  end
  subgraph MDL3["backend/app/models/（API 契约层 · L4 叶）"]
    M3["api_models.py：Envelope 五层 + JobEnvelope/JobStatus/TaskStatus<br/>analyze_options.py：AnalyzeOptions → options_to_pipeline_dict<br/>layout_result.py：版面元素结构"]
  end
  subgraph PKG3["packages/docuvision-core（独立可安装包 · backend/requirements.txt:90 以 -e 引入）"]
    P3["docuvision_core/processing/table_column_mapping.py<br/>docuvision_core/utils/logger · path_utils · pdf_text_utils"]
  end

  RTH -->|"经 runtime 枢纽取服务（analyzer.py:19 · tasks_content.py:24 · batch_export.py:13）"| RUNT
  RUNT -->|"9 个服务单例 DI"| SV3
  RUNT -->|"process_document 构造编排器并 DI"| OD
  RTL -.->|"直连"| SV3
  OD -->|"10 步 steps 调用各域服务"| SV3
  OD --- EB2
  SFP3 --> OD
  SV3 -->|"读运行配置"| CFG2
  SV3 -->|"4 处消费：列映射 · normalize_for_compare · engine 名"| P3
  OD -.->|"steps/extraction.py:107 table_template 列映射"| P3
  RTH -->|"请求/响应 Pydantic 契约"| M3
  OD -.->|"Envelope 契约"| M3
  AUTH2 -.->|"/api/v1/* 中间件横切（含 WS ?key=）"| RT3
  SUP2 -.->|"启动期前置（LD_LIBRARY_PATH / snapshot_download shim）"| RUNT

  SV3 -.->|"✗ 禁止：services→orchestration（S1a fail-closed · 勘察 grep 实测零例外）"| OD
  LINTS2["scripts/lint_services.py<br/>S1a 层方向 / S1b 域归属 / S1c 无环 · fail-closed 棘轮"]
  LINTS2 -.->|"机检"| SV3
```

说明：

1. 后端依赖三铁律：13 个 router 互不引用、统一经 `backend/app/core/runtime.py` 枢纽取服务（runtime 在 import 时构建 9 个服务单例，GPU 探测失败自动回 CPU）；编排层经 DI 消费 services；services→orchestration 是 S1a 禁止边（`scripts/lint_services.py` fail-closed 机检，本次勘察 grep 实测 backend/app/services/** 无任何 from/import app.orchestration）。
2. 轻端点不经编排：/ocr、/document/profile、/pdf-tools、/tasks/:id/export、/hitl 直接薄委托 services，/upload（analyzer.py:84-110）仅落盘建任务、不调 service；重管线端点（/analyze、/documents:analyze、/batch）进 orchestration；WS /tasks/:id/ws 只从 runtime 事件历史回放转发（tasks.py:46-90，含 since/last_event_id），不触发编排。
3. 支撑层：core/ 内 config.py（pydantic-settings 读 .env）、trial_auth.py（纯 ASGI 鉴权：配 key 不匹配即 401，未配 key 放行 open local-dev）、gpu_lib_path/aistudio_compat/debug_utils（启动期前置）；`backend/app/models/` 是 API 契约层（Envelope 五层、AnalyzeOptions→管线 dict、版面元素结构）；`packages/docuvision-core` 以可安装包形式（backend/requirements.txt:90 以 -e 引入）被 4 处消费：`backend/app/orchestration/steps/extraction.py:107`（table_template 列映射）、`backend/app/services/table_alignment.py:22` 与 `table_backfill.py:13`（normalize_for_compare）、`backend/app/services/document_profile.py:21`（engine 名）。
4. 前端侧：D 编号域互不 import，跨域只经 `frontend/app.js` 模块作用域注入（同目录 sibling 允许直连，如 pipeline/run→result→task-socket）；共享可变状态仅 `frontend/modules/preview-state.js` 与 `frontend/modules/api-state.js` 两处（setter 单写通道）；`frontend/shared/trial-key.js` 以包装 window.fetch/WebSocket 实现鉴权横切；`window.DOCUVISION_CONFIG` 仓库内无定义处，属部署期外部注入。

## 图③ 运维与治理管线（PR → CI 门禁序列 + kernel → sync → audit 治理环）

```mermaid
flowchart TB
  PR["PR 开出（ruleset main-branch-protection 拒绝直推 main）<br/>要求三个必需 status check 全绿才可合入"]
  PUSH["push 触发条件：提交信息含半角 [run ci]（kie-phase-a.yml:29）<br/>且 diff 触及 backend/** · packages/docuvision-core/** · workflow 自身"]

  subgraph G1["必需检查① lint.yml · lint job"]
    direction TB
    G1P["Python 3.11 stdlib 门禁（Node 之前先红先停）<br/>lint_file_size → lint_routes → lint_frontend<br/>→ check_frontend_baseline → check_e2e_allowlist → fixture --check"]
    G1N["npm ci → ESLint → vitest<br/>unit_suite_pin 防缩水 · skip 即 ERROR"]
    G1P --> G1N
  end
  subgraph G2["必需检查② lint.yml · e2e job（与①并行）"]
    G2P["npm ci → Playwright Chromium → test:e2e<br/>pageerror / console.error 即红<br/>e2e_allowlist_ratchet 棘轮 · e2e_suite_pin 钉死用例数"]
  end
  subgraph G3["必需检查③ agent-ops-audit.yml"]
    direction TB
    G3S["audit_agent_ops.py --selftest<br/>93 例解析器回归"]
    G3F["全量审计（7 个 check 模块 / 10 个 check 函数 · 任一 ERROR 退出 1 阻断合入）"]
    G3S --> G3F
  end
  subgraph G4["kie-phase-a.yml（非必需 · CPU 契约 · 无 Paddle 无权重）"]
    G4P["11 个 kind=phase-a-ci 的 mock 测试<br/>+ packages/docuvision-core/tests/processing/test_table_column_mapping.py"]
  end

  PR --> G1
  PR --> G2
  PR --> G3
  PUSH -->|"commit 含半角 [run ci]"| G4
  PR -.->|"非必需 · PR 触碰 paths 也跑（job 级 if 对非 push 恒真）"| G4
  G1N --> MERGE["三必需全绿 → ruleset 放行合入 main"]
  G2P --> MERGE
  G3F --> MERGE

  subgraph LOOP["治理环：kernel → sync → audit"]
    direction LR
    KERNEL["docs/agent-ops/core/（kernel 7 文件 · 规则唯一真源）<br/>constraints · environment · testing · doc-sync · routing · frontend · agents"]
    SYNC["scripts/sync_agent_rules.py<br/>渲染 15 个副本并盖 kernel-ref sha256 前缀<br/>--check 只报漂移不写"]
    COPY[".cursor/rules/*.mdc · .codebuddy/rules/*.md · .zcode/rules/*.md<br/>生成式薄壳 · 勿手改"]
    FIX["不一致 = ERROR<br/>处置：重跑 sync · kernel 与副本同 commit"]
    KERNEL -->|"改共享约束后跑 sync"| SYNC
    SYNC --> COPY
    COPY -.->|"check_agent_rules 重渲染逐字节比对"| FIX
    FIX -.-> SYNC
  end
  G3F -.->|"审计内容之一"| COPY

  subgraph MML["module-map 对账环（audit check 3）"]
    MM["docs/architecture/module-map.md<br/>§2 路由守恒（冻结 55）· §3 域集合 · §5 门禁表 path+symbol"]
    AST["运行期 AST 实数 + backend/tests/test_route_inventory.py<br/>EXPECTED_COUNT=55 三方守恒<br/>audit_agent_ops.py:158-168 运行期 import 反接"]
    MM ---|"三方守恒 · §5 门禁表逐行验证符号可解析"| AST
  end
  G3F -.-> MM

  subgraph REG["测试登记环（T1/T2）"]
    DISK["backend/tests/**/test_*.py 磁盘 rglob<br/>（跳过 tools/snapshots/fixtures）"]
    REGJ["backend/tests/test_registry.json（登记真源）<br/>kind ∈ phase-a-ci / live-gpu / manual-script / full"]
    YML[".github/workflows/kie-phase-a.yml<br/>Run Phase A pytest 步骤清单"]
    DISK ---|"三向对账"| REGJ
    REGJ ---|"双向机检"| YML
    DISK --- YML
  end
  G3F -.->|"check_test_registry · check_stub_scope（P-023）"| REGJ
  REGJ -.->|"phase-a-ci 必须进 CI 清单<br/>CI 跑未登记文件 = ERROR"| G4P

  KERNEL --- OPS["docs/agent-ops/operations.md 稳态巡检<br/>本地手动（改 core 后或每周）：selftest + 全量审计<br/>PR→main 由 agent-ops-audit workflow 自动承接"]
  G3F -.->|"check_services 接线（routing.md:19）"| LINTS3["scripts/lint_services.py<br/>S1a/S1b/S1c · module-map §2b 三向对账"]
```

说明：

1. 合入闸（书面口径见 `docs/agent-ops/operations.md:143-145` 与 lint.yml 注释）：ruleset main-branch-protection 要求 lint、e2e、agent-ops-audit 三个必需检查全绿，直推 main 被拒；lint job 先跑 Python stdlib 门禁再进 Node（npm ci → ESLint → vitest），e2e job 并行跑 Playwright（pageerror/console.error 即红）。
2. agent-ops-audit 先跑 93 例 `--selftest` 再全量审计（7 个 check 模块 / 10 个 check 函数，任一 ERROR 退出 1）；kie-phase-a 为非必需的 CPU 契约测试（无 Paddle、无权重）：push 需提交信息含半角 `[run ci]`（kie-phase-a.yml:29）且 diff 触及 backend/**、packages/docuvision-core/** 或 workflow 自身；PR 触碰相同 paths 也运行（job 级 `if: github.event_name != 'push' || contains(...)` 对非 push 事件恒真）；跑的正是 test_registry.json 中 kind=phase-a-ci 的 11 个文件加 packages 测试。
3. 治理环闭环：改 `docs/agent-ops/core/` kernel → 跑 `scripts/sync_agent_rules.py` 派生 15 个副本（.cursor/.codebuddy/.zcode，盖 kernel-ref sha256 前缀）→ CI 中 check_agent_rules 重渲染逐字节比对，不一致即 ERROR，处置动作是重跑 sync 且 kernel 与副本同 commit。
4. 两条数据对账环：module-map §2 路由守恒（冻结 55）↔ AST 实数 ↔ `backend/tests/test_route_inventory.py` 的 EXPECTED_COUNT 三方守恒；`backend/tests/test_registry.json` ↔ 磁盘 ↔ kie-phase-a.yml 清单三向对账（phase-a-ci 双向机检）。注意 pytest 运行时不消费 registry——它只服务于审计期防 dangling test。
5. 已知文档矛盾（图按 kernel/operations 口径绘制）：lint.yml:115-116 的 e2e 注释仍称 branch protection 未启用，与 required checks 口径相抵。（原记载的「根 AGENTS.md 称 ZCode 已退役」矛盾已于 2026-11-06 修正对齐 kernel。）

## 未决事项（勘察遗留，图未下结论）

- 版本口径未定论：module-map.md 头部“最近对照 v1.13.0（main 07de132）”、`backend/app/core/config.py:22` APP_VERSION="1.9.0"、CHANGELOG.md 首节 [Unreleased]，三者来源不一致；本图不标注版本号。
- GitHub ruleset（main-branch-protection 的 required checks 配置）本会话无法核验（gh 未认证），图③合入闸依据 lint.yml 注释与 operations.md 书面口径。
- GPU 相关能力（模型服务实际行为）未验证：本机无 GPU（仓库红线），图中 GPU 探测/回退仅按代码静态描述。
