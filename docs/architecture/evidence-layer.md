# Evidence Layer（证据接地抽取校验层）— P-029

> Status: living — **权威：`backend/tests/evidence/`**（契约由 pytest 承载，本文为人类可读派生视图）
> 最近对照：feat/p032-text-first @ 8c09afc（2026-10-07，P-032 M1-M5 + C4 落地；C1b/C5 Cloud 复验待执行）
> 来源：sciextract RCT 报告 v2 实证的三闸方法（闸 A 逐字 quote 接地 / 闸 B hedge 保真 / 闸 C 槽完整性），
> 自交接件移植（设计稿/执行包/执行记录 local-only：`docs/R&D/runs/P029/`）。

## §1 定位与边界

- `backend/app/services/evidence/` 是**进程内 evidence 服务**：对 KIE（本地 Qwen2.5-VL）产出的 PICO findings
  做独立校验并挂 verdict + provenance。不重建任何推理服务链，抽取仍走 KIE。
- **独立性纪律**：verifier 禁 import 任何 KIE 抽取模块、禁共享其匹配/归一代码——闸 A 证的是
  「quote 在文本层逐字存在」，不等于「文本层正确」（共享 OCR 错字可同时骗过两边）。
- **never silently corrected**：quote 文本永不改写、分类不修正；**fail-closed 禁降级**。

## §2 模块构成

| 模块 | 职责 |
|---|---|
| `backend/app/services/evidence/findings_schema.py` | FindingRecord 契约（`SCHEMA_VERSION = evidence-findings/1.0`）；`PROMPT_VERSION = v4`（P-032 C4）与 `kie_configs/pico.yaml` 模板头版本绑定（机器校验读真实模板头），不一致 = 门禁 ERROR（防抽取模板与校验契约两处漂移）；`PicoSlots` 为首张域槽模板，新域经 `register_slot_template` 注册、核心形状不动 |
| `backend/app/services/evidence/closed_lists.json` | 闭表单一真源（`closed_lists/1.0`）：hedge EN 14 词（prompt 白名单种子，金样校准）；ZH 12 词与因果动词三档待首个中文域数据 PR 补种，不自行造词 |
| `backend/app/services/evidence/normalize.py` | 接地归一器（交接件 `ingest_pdf.py` 的 `normalize()` + `LIGATURES` 原样移植；只入 evidence 层，不进表格域） |
| `backend/app/services/evidence/verifier.py` | V0-V6 归一梯 + 判类写死 + 闸 B 集差语义 + 闸 C 槽行；`--selftest` 自检入口；全链 UTF-8、诊断 ASCII（Windows GBK 守卫） |
| `backend/app/services/evidence/gate.py` | fail-closed 门禁：failure ledger、HITL 路由、findings JSONL 产物、页接地文本构建与页信任闸（旗标分叉见 §4） |
| `backend/app/services/evidence/grounding.py` | P-032 新增：同源原生文本层构建（`grounding_source`，PyMuPDF 按页分块）+ evidence 专用信任谓词（`trusted_grounding_page_set`，M5：`total_chars>0` 且 `invisible_ratio<0.5`）+ 确定性页归属（`attribute_candidates`：marker 提示 → V0-V6 梯扫最低页 → 最高前缀比页兜底承载 `N/Mw prefix` detail）；`page_text_trust.py` 本体只读不动 |
| `backend/app/services/kie/text_first.py` | P-032 新增（M1/M2，纯逻辑）：`[p{页}_b{块}]` marker 注入（绝对页号、0 起块序）、块边界滑窗（重叠 1 块）、正文页判定（≥8 body 型元素且 ≥500 字符，裁决常量）与页解析包装；与 `grounding_source` 同源是契约 |
| `backend/app/services/kie/kie_configs/pico.yaml` | PICO 域模板（prompt v4 + `prompt_version: v4` 头 + schema，`quote_block` 引 marker），`_registry.yaml` 注册；KieManager 可加载 |

## §3 三闸语义（写死）

- **闸 A（quote 接地）**：归一变体梯 `V0 raw → V1 NFC → V2 连字展开 → V3 空白折叠 → V4 软连字符/破折号归一
  → V5 断词连字符接回 → V6 = V5 + 连字符剥离`；任一档命中 = `verbatim_exact`（记 `matched_variant`）；
  全梯未命中但词前缀匹配（V4 quote 对 V6 haystack，`pref ≥ total-3` 且 `pref/total ≥ 0.90`，双边界含）
  = `near_match`；否则 `unsupported`。
- **闸 B（hedge 保真）**：quote/claim 的闭表内 hedge 词集对照（词边界、忽略大小写）：quote 有而 claim 丢
  = `overclaim`（硬拒）；claim 新增 = `add_hedge`（只计不拒）；其余 `faithful`。
- **闸 C（槽完整性）**：5 槽（population/intervention/comparator/outcome/follow_up）须非空字符串或字面量
  `NOT_REPORTED`；`None`/`""`/缺键 = 校验 ERROR（silent null 禁）；`not reported` 等拼写变体一律拒收
  （规范化只能显式完成，不能静默带过）。

## §4 门禁与接线（默认关）

- 旗标 `EVIDENCE_ENABLED`（默认 **False**，env `DOCUVISION_EVIDENCE_ENABLED`/`EVIDENCE_ENABLED`）；
  开启后 orchestrator 的 `evidence_step`（`phase1_envelope_step` 之后、`finalize_step` 之前）运行，旗标关 = 零行为。
- fail-closed 判定：缺页或页不可信（`page_text_trust.judge_page_trust`，quote 接地只对文本层可信页跑）
  ⇒ 无接地 ⇒ `unsupported` 拒收（axis A）；`overclaim` ⇒ 拒收（axis B）。
- 拒收记录落 `failure_ledger.json`（任务 DEBUG 产物目录）；批次内任一拒收未解决 ⇒ findings 导出阻断
  （`export_allowed = false`，与隔离区纪律同款）。
- `near_match` / 槽不完整 / schema 不合法候选 ⇒ `HitlReviewQueue`（reason = `near_match_review` /
  `evidence_slot_incomplete` / `evidence_schema_invalid`；payload 带 closed_lists 版本、两词表快照与
  matched_variant/detail），处置经既有 HITL resolve 流程回写。
- 全通过 ⇒ findings JSONL（`schema_version + prompt_version + verdict + provenance`）随任务结果与 DEBUG 产物落盘。

### §4.1 text-first 分支（P-032，默认关）

- 旗标 `EVIDENCE_TEXT_FIRST`（默认 **False**，env `DOCUVISION_EVIDENCE_TEXT_FIRST`/`EVIDENCE_TEXT_FIRST`，须与
  `EVIDENCE_ENABLED` 同开）：`run_evidence_gate` 与 pico KIE 输入同时切到 text-first 通道；**旗标关 = #68 图片
  通道行为逐分支原样**（enrich 三级启发式 / fused 接地 / E1 信任集）。
- **抽取输入**（M1/M2）：pico 在 PDF 上不再喂图——每页喂「原生文本层按块拼接 + `[p{页}_b{块}]` marker」（每页
  一次调用；超窗按块边界滑窗、重叠 1 块）；默认页集 = layout 正文页（≥8 body 型元素且 ≥500 字符）再交
  `KIE_MAX_PAGES` 截断；`debug_input` 记录每页输入来源 `text_layer`/`fused_ocr`（M5 谓词失败页显式降级 fused_ocr
  并在证据闸 fail-closed，不静默混用；两通道皆无文本的页回落图片通道，以 payload 缺席显式呈现）。
- **确定性接地**（M4）：页归属不再用 `kie_pages_processed`/`quote_block` 启发式——marker 提示页优先，其次对
  同源原生文本做 V0-V6 梯扫（页序升序、最低页胜），全落空归属最高前缀比页使 ledger detail 保持 `N/Mw prefix`
  （E2 禁 `grounding unavailable`）；命中后 `SourceRef.page_num` + `quote_span` 落记录。
- **信任判据**（M5）：evidence 专用谓词 = `total_chars>0 且 invisible_ratio<0.5`（原生文本层存在且非 OCR 覆盖
  层），**弃用** `image_coverage`（E1 表格回填判据保留其另外 3 个消费者）；BMC 首页（image_coverage≈0.61）在此
  判据下受信。
- `evidence.stats`：text-first 路径的 `page_injected` = 确定性逐字命中数（marker 提示 + 梯扫），并附
  `marker_hint_hits`/`scan_hits`/`prefix_only`/`unresolved` 计数；legacy 路径语义不变。

## §5 金样哨兵（棘轮）

- `backend/tests/evidence/golden/`：45 条 FindingRecord（`F-001`…`F-045`）+ 18 页接地文本
  （BMC/Springer **Open Access** 论文的页级 norm 文本；页 `sha256[:12]` 即 `source.sha12`；原文 PDF 不入仓）。
- `test_golden_baseline.py` 钉死读数：**35 verbatim_exact / 3 near_match / 7 unsupported**
  （7 拒收 = 4 original_finding + 3 background_citation）；**38/38 faithful、0 overclaim**；
  空槽 **0/45**；statement_type **28/13/4/0**。
- **棘轮口径**：任何 verifier/闭表改动后重跑，须「跑赢 baseline 且 unsupported 不增」才可 ship，
  否则停手回报（handoff D8 原文）；不得改金样数据迁就新代码。
- 转换器 `scripts/qa/convert_golden.py`（`--check` 漂移门；双跑产物逐字节一致）；离线 QA 工具
  `scripts/qa/make_spotcheck.py`（双人盲审协议）与 `scripts/qa/make_test_report.py`（无漂移报告，
  每个数字从数据文件现算）入 `scripts/qa/`，不进任何服务路径；`scripts/qa/archive/RUNBOOK.md`
  为形态 B（vLLM 端点）留档，**不执行**。

## §6 连带审计结论（P-029 C3）

- `kie_field_metrics.compute_fill_confidence` = `_PRODUCTION_KEY_HINTS` 关键字段填充率启发式，
  **非模型自报信号**，无「自报置信偏差」问题（只审不改）。
- 对外口径红线：禁把模型自报置信写成质量证据；Qwen2.5-VL 为 Apache-2.0 第三方权重，
  对外材料禁写「DocuVision 的模型」。
