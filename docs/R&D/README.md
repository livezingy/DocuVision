# R&D notes (local / gitignored)

> **Status**: local only — contents under `docs/R&D/**` are not committed (except this README and PENDING).
> **门禁**：`PENDING.md` 的条目状态与滞留由 **DOC-3** 校验（每条首行 `> status: … · since: …`，见该文件抬头）；
> 写 PENDING / CHANGELOG 时须留一行 `Promotion-check:`（规则见 kernel `doc-sync.md`）。

Use this folder for exploratory write-ups that are **not** authoritative for the codebase:

Files are organised into `reference/` (long-lived, updated irregularly) and `runs/` (per-project
execution packs & records — temporary, deletable once no tracked document still references them).

### Root (always tracked)
| File | Purpose |
|------|---------|
| [PENDING.md](PENDING.md) | 待决决策清单（每次会话可见"有 N 条结论待确认"） |

### reference/ (long-lived, local-only)
| File | Purpose |
|------|---------|
| [DocuVision-项目全景图.md](reference/DocuVision-项目全景图.md) | 跨项目切换回来的第一入口（结构/版本/在途事项速览；结构变化时刷新本图） |
| [capability-card-v1.12.md](reference/capability-card-v1.12.md) | 面向 Agent U 的投标能力卡（v1.0.3）：13 能力域（+行 12 RCT 验证资产 / 行 13 evidence 校验层）+ 诚实边界 + 营销词黑名单 + 数字来源索引；tag `v1.12.0` 已回填 |
| [azure/azure-contract-and-paddle-discovery.md](reference/azure/azure-contract-and-paddle-discovery.md) | Azure sample observations + contract direction notes（2026-10-08 索引校正：实际在 `reference/azure/` 子目录下） |

> **已清理（2026-10-08 索引校正）**：`capability-card-v1.10-v1.0.md`（前版能力卡，磁盘已不在；其历史内容由 git 历史承载）。

### runs/ (per-project execution packs/records — temporary, local-only)

Deletion rule: a pack/record is deletable once **no tracked document still references any file in it** — check PENDING entries and this index first. CHANGELOG / release-note history citations do **not** block deletion (they are archives by design). Any add/delete under `runs/` must update the index below **in the same batch**: runs files are gitignored, so a dead index link is invisible to CI — verify locally with `python scripts/docs_refs_audit.py --check-rnd-index`.

| File | Purpose |
|------|---------|
| [P027/R2-执行记录.md](runs/P027/R2-执行记录.md) | P-027 R2 弱 GT 合成与文本层对账执行记录 |
| [P027/R3-执行包.md](runs/P027/R3-执行包.md) | P-027 R3 验收三闸 harness 化执行包 |
| [P027/R3-执行记录.md](runs/P027/R3-执行记录.md) | P-027 R3 验收三闸 harness 化执行记录 |
| [P027/R4-执行包.md](runs/P027/R4-执行包.md) | P-027 R4 IE 语义层专项执行包 |
| [P027/R4-执行记录.md](runs/P027/R4-执行记录.md) | P-027 R4 IE 语义层专项执行记录 |
| [split/README.md](runs/split/README.md) | L0-L4 分层与 S1 门禁三案对抗审核目录索引（00-05 规划稿；批 0 已于 2026-10-24 落地，基线勘误见 PENDING P-037） |
| [split/06-批次执行计划.md](runs/split/06-批次执行计划.md) | P-037 批 1+ 操作规范：批次序列 / 批前基线四样 / 执行纪律 / 等价性证据档位 A/B/C |
| [split/07-批1-执行记录.md](runs/split/07-批1-执行记录.md) | P-037 批 1 执行记录：共享叶首登 pdf_raster + #13 上移倒置，棘轮 15→12（基线四样与证据表） |
| [split/08-批2-执行记录.md](runs/split/08-批2-执行记录.md) | P-037 批 2 执行记录：双共享叶破两组域环（图无环），棘轮 12→9；orchestrator 顶格判例与 Cloud 验证步骤 |

**保留依据**：`runs/P027/` 的保留理由写在 PENDING **P-027** 条目——**2026-10-16 更新**：P-027 已由 `decided` 转 **`retained`**，保留依据不再是「在途义务未清」，而是**被 tracked 文档反引**（PENDING 的 P-002 条目把 IE-p079 判据指向「P-027 R4 执行记录 §4.1」；[../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md) 的 R2/R3/R4 行；R4 记录 §6 是隔离区 `test_data/derived/**` 证据链的唯一盘存表）⇒ 仍**未到删除条件**。`runs/split/` 的保留依据 = PENDING **P-037**（还债批次在途）/ **P-038**（I-1 待决）以**目录级**引用本目录，06 是批 1+ 的操作规范载体；全部批次收口、P-037/P-038 结案后按删除规则处置（00-05 规划稿的结论已晋升 kernel/module-map）。

**已清理（2026-10-07 索引校正；本目录为 local-only，git 无历史可回溯，故清理批次未逐件留痕）**：
`runs/P020-ocr-harness-M1M2-执行包.md`（实质结论已由 living doc [../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md) + CHANGELOG 承载）·
`runs/P021-云端对照-执行清单与记录模板.md`（结论已由 PENDING P-021 round3 段 + CHANGELOG 承载）·
P-029 / P-030 / P-031 / P-032 的 local-only 执行包与记录（各自 landed 后按「提炼后删除」清理）。

**已清理（2026-10-16，同批纪律首批适用）**：`runs/PENDING-维护建议-审核纪要-2026-10-16.md`（一次性议题纪要，
结论已落进 kernel `doc-sync.md` + `operations.md` §清账批次 + `scripts/docs_refs_audit.py` 的 `--check-rnd-index`，
按「落地即删、同批更新本索引」删除，上文死链行已随本批移除）。

**Authoritative docs** live in [../architecture/](../architecture/) and [../README.md](../README.md).

When a conclusion from R&D is ready for the team, promote it into `docuvision-system-design.md` or a living architecture doc — do not grow this folder indefinitely.
Promoted so far: `ocr-quality-measurement-{harness,design}.md` → [../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md)
(2026-09-26); the two local-only drafts were deleted in the same batch. `data-flow-diagram-legacy.md` and `upwork/` were removed earlier.
