# Release documentation index

> **Status**: **历史快照（v1.6 及以前）**——过去的 checklist / notes 发布后不再修改。
> **v1.7 起**：发布说明以 [`CHANGELOG.md`](../../CHANGELOG.md) 为**唯一入口**，不再新增 `RELEASE_*_NOTES.md` / `RELEASE_*_CHECKLIST.md`（流程已简化，见下方注）。
> 云端合并门禁清单：v1.6 及以前仍按版本落在 [`test_data/acceptance/`](../../test_data/acceptance/)；
> v1.7 的那份已随门禁关闭归档到本目录（见下）。

| Version | Notes | Checklist | Cloud merge gate |
|---------|-------|-----------|------------------|
| v1.0.0 | [RELEASE_1.0.1_NOTES.md](RELEASE_1.0.1_NOTES.md) | [RELEASE_1.0_CHECKLIST.md](RELEASE_1.0_CHECKLIST.md) | — |
| v1.1.0 | [RELEASE_1.1_NOTES.md](RELEASE_1.1_NOTES.md) | [RELEASE_1.1_CHECKLIST.md](RELEASE_1.1_CHECKLIST.md) | — |
| v1.2.0 | [RELEASE_1.2_NOTES.md](RELEASE_1.2_NOTES.md) | [RELEASE_1.2_CHECKLIST.md](RELEASE_1.2_CHECKLIST.md) | [MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md) |
| v1.2.1 | [RELEASE_1.2.1_NOTES.md](RELEASE_1.2.1_NOTES.md) | [RELEASE_1.2.1_CHECKLIST.md](RELEASE_1.2.1_CHECKLIST.md) | [MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md) |
| v1.3.0 | [RELEASE_1.3.0_NOTES.md](RELEASE_1.3.0_NOTES.md) | [RELEASE_1.3.0_CHECKLIST.md](RELEASE_1.3.0_CHECKLIST.md) | [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md) |
| v1.3.1 | [RELEASE_1.3.1_NOTES.md](RELEASE_1.3.1_NOTES.md) | [RELEASE_1.3.1_CHECKLIST.md](RELEASE_1.3.1_CHECKLIST.md) | [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md) |
| v1.4.0 | [RELEASE_1.4_NOTES.md](RELEASE_1.4_NOTES.md) | [RELEASE_1.4_CHECKLIST.md](RELEASE_1.4_CHECKLIST.md) | [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md) |
| v1.4.1 | [RELEASE_1.4.1_NOTES.md](RELEASE_1.4.1_NOTES.md) | — | [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md) |
| v1.5.0 | [RELEASE_1.5_NOTES.md](RELEASE_1.5_NOTES.md) | — | [MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md) |
| v1.6.0 | [RELEASE_1.6_NOTES.md](RELEASE_1.6_NOTES.md) | — | [MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md) |

> **v1.7 及之后不在此表**（有意为之，不是遗漏）：`v1.7.0` / `v1.8.0` / `v1.8.1.0` / `v1.8.2.0` / `v1.8.3.0` 五个 tag
> 都没有 `RELEASE_*` 文件——发布说明见 [`CHANGELOG.md`](../../CHANGELOG.md) 对应版本段。
> 云端合并门禁清单：最新一份是 v1.7 的
> [`MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md`](MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md)（v1.8.x 未单独建），
> 该门禁 `TASK-PERSIST-001` 已于 2026-09-17 验证通过，清单随之归档冻结。

Cross-cutting: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) · [CHANGELOG.md](../../CHANGELOG.md)

## 归档的验证材料（不再更新，只备查）

发版**前**的逐版本验证手册，以及门禁已关闭的云端合并清单：一旦归档于此即冻结；通用回归手册仍在
[`../architecture/CLOUD_VALIDATION.md`](../architecture/CLOUD_VALIDATION.md)。

| 文件 | 范围 |
|------|------|
| [v1.8-cloud-validation.md](v1.8-cloud-validation.md) | v1.8 发版前 **Cloud Studio GPU** 验证手册（文本层选择性回填 / 页信任守门器 / Lite 收编）；v1.8.0–v1.8.3 均已发出，归档备查 |
| [MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md](MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md) | v1.7 合 main 的云端验收清单；门禁 `TASK-PERSIST-001` 于 2026-09-17 在 `main` 基线验证通过后归档冻结（§0 的部分命令已过期） |

Design reference: [docuvision-system-design.md](../architecture/docuvision-system-design.md)
