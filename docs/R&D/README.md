# R&D notes (local / gitignored)

> **Status**: local only — contents under `docs/R&D/**` are not committed (except this README and PENDING).
> **门禁**：`PENDING.md` 的条目状态与滞留由 **DOC-3** 校验（每条首行 `> status: … · since: …`，见该文件抬头）；
> 写 PENDING / CHANGELOG 时须留一行 `Promotion-check:`（规则见 kernel `doc-sync.md`）。

Use this folder for exploratory write-ups that are **not** authoritative for the codebase:

| File | Purpose |
|------|---------|
| [PENDING.md](PENDING.md) | 待决决策清单（每次会话可见"有 N 条结论待确认"） |
| [DocuVision-项目全景图.md](DocuVision-项目全景图.md) | 跨项目切换回来的第一入口（结构/版本/在途事项速览；结构变化时刷新本图） |
| [azure-contract-and-paddle-discovery.md](azure-contract-and-paddle-discovery.md) | Azure sample observations + contract direction notes |
| [P020-ocr-harness-M1M2-执行包.md](P020-ocr-harness-M1M2-执行包.md) | OCR harness 执行包：设计细化 / 护栏 / **§10 云端 runbook 与回填模板** / §10.11-§10.12 空间门禁 |
| [P021-云端对照-执行清单与记录模板.md](P021-云端对照-执行清单与记录模板.md) | P-021 云端对照的执行清单、OCR JSON SHA 清单与 round3 记录 |
| [DocuVision-v1.10-收口审计报告.md](DocuVision-v1.10-收口审计报告.md) | v1.10.0 收口审计（`closure-audit-v2.1`）：门禁/数字核实表 · 切版执行回填（#48/#49/tag） · 遗留 §5 · capability-card 指针 |
| [capability-card-v1.10-v1.0.md](capability-card-v1.10-v1.0.md) | 面向 Agent U 的投标能力卡（v1.0.2）：11 能力域 + 诚实边界 + 营销词黑名单 + 数字来源索引；tag `v1.10.0` 已回填 |
| [DocuVision-P002-表格逐格对齐设计稿_v2.md](DocuVision-P002-表格逐格对齐设计稿_v2.md) | P-002 三层对齐设计稿（draft-v3）：T1/T3 伪代码、契约、C0-C5 切分、执行期裁决 X1-X5 |

**Authoritative docs** live in [../architecture/](../architecture/) and [../README.md](../README.md).

When a conclusion from R&D is ready for the team, promote it into `docuvision-system-design.md` or a living architecture doc — do not grow this folder indefinitely.
Promoted so far: `ocr-quality-measurement-{harness,design}.md` → [../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md)
(2026-09-26); the two local-only drafts were deleted in the same batch. `data-flow-diagram-legacy.md` and `upwork/` were removed earlier.
