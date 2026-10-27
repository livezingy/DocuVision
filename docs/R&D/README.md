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
| [P034/P-034-执行包-v1.md](runs/P034/P-034-执行包-v1.md) | P-034 text-first 泛化到 coi 执行包 v1（Agent D 出包） |
| [P034/P-034-执行包-v1-审核记录.md](runs/P034/P-034-执行包-v1-审核记录.md) | P-034 执行包 v1 审核记录（有条件通过，P1×3） |
| [P034/P-034-云测-第1轮-读数.md](runs/P034/P-034-云测-第1轮-读数.md) | P-034 云测第 1 轮读数（X2 FAIL 病灶解剖 + v3.1 迭代依据） |
| [P034/P-034-云测-第2-3轮-读数.md](runs/P034/P-034-云测-第2-3轮-读数.md) | P-034 云测第 2-3 轮读数（通道自证 ✅ + X2 PASS，limits 退化定性 → 设计复核选项） |
| [P034/P-034-云测第2-3轮-复核记录.md](runs/P034/P-034-云测第2-3轮-复核记录.md) | P-034 云测第 2-3 轮复核记录（X2 键省略稀释 + limits 退化再定性 → P0-P3 对策待裁决） |
| （已删）P034/p034_round4_cloud_test.sh → [scripts/cloud/cloud_round_test.sh](../../scripts/cloud/cloud_round_test.sh) | P-034 第 4 轮一键云测脚本**已提炼入库**（2026-10-27，`dcf99a2`/`4eb3939`，用户改版的 venv/基线包含核验/打包改进一并吸收）；目录原件同批删除，git 历史可回溯；后续云测一律用 `scripts/cloud/` 金样例 |
| [P034/p034_round4_artifacts_dcf99a2_20261027_065004.tar.gz](runs/P034/p034_round4_artifacts_dcf99a2_20261027_065004.tar.gz) | P-034 第 4 轮产物包（七件齐：双侧日志/result JSON×4/summary；已解包留档同目录） |

**保留依据**：`runs/P027/` 的保留理由写在 PENDING **P-027** 条目——**2026-10-16 更新**：P-027 已由 `decided` 转 **`retained`**，保留依据不再是「在途义务未清」，而是**被 tracked 文档反引**（PENDING 的 P-002 条目把 IE-p079 判据指向「P-027 R4 执行记录 §4.1」；[../architecture/ocr-quality-harness.md](../architecture/ocr-quality-harness.md) 的 R2/R3/R4 行；R4 记录 §6 是隔离区 `test_data/derived/**` 证据链的唯一盘存表）⇒ 仍**未到删除条件**。

**已清理（2026-10-25 收尾批，PR #108）**：`runs/split/` 全目录（24 文件，00-22 号 + README）——删除前提达成：P-037 已收口（`retained`，机制由 S1 门禁承载）、P-038 已定稿（6 叶封册，候选池真源在其条目内）、P-039/P-040/P-041 已结并自 PENDING 移除；21 号清单 §八 webhook 命令模板与 §四 formula 判据已先行内联迁移进 P-041/P-040 条目正文（随结案记录进 git 历史），06 批次操作规范的结论已由 kernel `routing.md`/`testing.md` + module-map §2b 承载。目录内容明细见 git 历史（本批删除 commit）与 CHANGELOG `[Unreleased]`。

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
