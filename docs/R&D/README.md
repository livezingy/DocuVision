# R&D notes (local / gitignored)

> **Status**: local only — contents under `docs/R&D/**` are not committed (except this README and PENDING).
> **门禁**：`PENDING.md` 的条目状态与滞留由 **DOC-3** 校验（每条首行 `> status: … · since: …`，见该文件抬头）；
> 写 PENDING / CHANGELOG 时须留一行 `Promotion-check:`（规则见 kernel `doc-sync.md`）。

Use this folder for exploratory write-ups that are **not** authoritative for the codebase:

Files are organised into `reference/` (long-lived, updated irregularly) and `runs/` (per-project
execution packs & records — temporary, deletable once the project lands).

### Root (always tracked)
| File | Purpose |
|------|---------|
| [PENDING.md](PENDING.md) | 待决决策清单（每次会话可见"有 N 条结论待确认"） |

### reference/ (long-lived, local-only)
| File | Purpose |
|------|---------|
| [DocuVision-项目全景图.md](reference/DocuVision-项目全景图.md) | 跨项目切换回来的第一入口（结构/版本/在途事项速览；结构变化时刷新本图） |
| [capability-card-v1.12.md](reference/capability-card-v1.12.md) | 面向 Agent U 的投标能力卡（v1.0.3）：13 能力域（+行 12 RCT 验证资产 / 行 13 evidence 校验层）+ 诚实边界 + 营销词黑名单 + 数字来源索引；tag `v1.12.0` 已回填 |
| [capability-card-v1.10-v1.0.md](reference/capability-card-v1.10-v1.0.md) | 前版能力卡（v1.0.2）：11 能力域；tag `v1.10.0` 已回填（历史留档） |
| [azure-contract-and-paddle-discovery.md](reference/azure-contract-and-paddle-discovery.md) | Azure sample observations + contract direction notes |

### runs/ (per-project execution packs/records — temporary, local-only)

Deletion rule: a pack/record is deletable once its project lands (PENDING status `landed`/`retained`); while it is still `open`/`decided` the record stays, because it is cited as the evidence source.

| File | Purpose |
|------|---------|
| [P027/R2-执行记录.md](runs/P027/R2-执行记录.md) | P-027 R2 弱 GT 合成与文本层对账执行记录 |
| [P027/R3-执行包.md](runs/P027/R3-执行包.md) | P-027 R3 验收三闸 harness 化执行包 |
| [P027/R3-执行记录.md](runs/P027/R3-执行记录.md) | P-027 R3 验收三闸 harness 化执行记录 |
| [P027/R4-执行包.md](runs/P027/R4-执行包.md) | P-027 R4 IE 语义层专项执行包 |
| [P027/R4-执行记录.md](runs/P027/R4-执行记录.md) | P-027 R4 IE 语义层专项执行记录 |

**保留依据**：`runs/P027/` 是唯一在册子目录，保留理由写在 PENDING **P-027** 条目（该条 status = `decided`，未到删除条件）。

**已清理（2026-10-07 索引校正；本目录为 local-only，git 无历史可回溯，故清理批次未逐件留痕）**：
`runs/P020-ocr-harness-M1M2-执行包.md`（实质结论已由 living doc [../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md) + CHANGELOG 承载）·
`runs/P021-云端对照-执行清单与记录模板.md`（结论已由 PENDING P-021 round3 段 + CHANGELOG 承载）·
P-029 / P-030 / P-031 / P-032 的 local-only 执行包与记录（各自 landed 后按「提炼后删除」清理）。

**Authoritative docs** live in [../architecture/](../architecture/) and [../README.md](../README.md).

When a conclusion from R&D is ready for the team, promote it into `docuvision-system-design.md` or a living architecture doc — do not grow this folder indefinitely.
Promoted so far: `ocr-quality-measurement-{harness,design}.md` → [../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md)
(2026-09-26); the two local-only drafts were deleted in the same batch. `data-flow-diagram-legacy.md` and `upwork/` were removed earlier.
