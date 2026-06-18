# Release 1.1 发布清单

> 目标 tag：**`v1.1.0`** · 日期：**2026-06-04** · 合并分支：`feature/pro-v1.1-custom-fields` → `main`  
> 范围：Pro **`kie_query_fields`**（extend-only，对标 Azure Query Fields）。设计见 [kie-custom-fields.md](../architecture/kie-custom-fields.md)。

## 1. 代码与文档（仓库内）

| 项 | 状态 | 说明 |
|----|:----:|------|
| `kie_query_fields` API + 校验 | ☑ | `backend/app/services/kie/query_fields.py` |
| Pro UI Advanced 字段输入 | ☑ | `frontend/app.js` |
| Phase A `test_kie_query_fields.py` | ☑ | 契约单测 |
| `CHANGELOG.md` `[1.1.0]` | ☑ | 发版 commit |
| `KIE_TEST_RUN_TRACKER.md` Release 1.1 baseline | ☑ | 阶段 F |
| `KNOWN_LIMITATIONS.md` | ☑ | 适用范围至 v1.1.0 |
| `APP_VERSION` = `1.1.0` | ☑ | `backend/app/core/config.py` |
| Git tag `v1.1.0` on `main` | ☑ | `e79db9a` |

## 2. Cloud 验收（GPU 环境）

| 阶段 | 目标 | Release 1.1 状态 |
|------|------|------------------|
| **A** | 契约 pytest（含 query fields） | ☑ feature 分支 / PR → main 后 CI |
| **B** | `kie_query_fields` 400 用例 | ☑ 2026-06-04 |
| **F** | 阶段 C 样例 + query；001/002 仍通过 | ☑ `sample-invoice.png` 1/1 |
| **C + E 回归** | 固定矩阵未因 v1.1 退步 | ☑ 发版后 Cloud 已复跑（2026-06-04） |

**阶段 F 可选**：`invoice_sample_01.pdf` + `OurReference`/`BookingDate`（见 Tracker「待补」）。

端到端注意：analyze 与 poll 须在**同一** `python run.py` 进程；`DEBUG=true` reload 会导致 `Task not found`。见 [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md)。

## 3. GitHub 分支与 Release 操作

### 3.1 推荐分支流（本 release）

```text
feature/pro-v1.1-custom-fields
  → merge origin/main（含 1.0.1 后 Lite CI 修复）
  → PR → main（自动 KIE Phase A + CI Lite）
  → merge
  → tag v1.1.0 on main
  → 后续新功能：feature/batch-ui、feature/kie-field-validation 等（勿堆在已合并的 v1.1 feature 分支）
```

`develop` 分支非必需；以 **`main` + `feature/*`** 为主干。

### 3.2 维护者命令（PowerShell 示例）

```powershell
cd <REPO_ROOT>
git checkout feature/pro-v1.1-custom-fields
git pull origin feature/pro-v1.1-custom-fields
git merge origin/main
# 解决冲突后
git push origin feature/pro-v1.1-custom-fields
gh pr create --base main --head feature/pro-v1.1-custom-fields --title "release: v1.1.0 Pro KIE query fields" --body "See RELEASE_1.1_CHECKLIST.md and CHANGELOG [1.1.0]."
# PR 合并后：
git checkout main
git pull origin main
git tag -a v1.1.0 -m "Release 1.1.0: Pro KIE query fields (extend-only)"
git push origin v1.1.0
gh release create v1.1.0 --title "v1.1.0 — Pro KIE query fields" --notes-file docs/release/RELEASE_1.1_NOTES.md
```

日常 push **不要**加 `[run ci]`；PR 至 `main` 会按路径自动跑门禁。

## 4. 版本号对齐

| 位置 | v1.1.0 值 |
|------|-----------|
| Git tag | `v1.1.0` |
| `APP_VERSION` | `1.1.0` |
| Job Envelope `version`（API） | 仍为 `"1.0"`（Phase 1 契约，未改） |

## 5. 明确不在 v1.1.0

- `document_type=custom` 全量 schema、模板持久化
- Batch Processing **产品化 UI**（placeholder 仍在）
- 多页 PDF KIE、字段 bbox 画布联动
- 通用字段校验引擎（date/currency/regex）— 规划 v1.2+

## 6. 发版后路线图（优先级）

| 优先级 | 能力 | 状态 / 分支 |
|--------|------|-------------|
| **P0** | Batch UI + 汇总 CSV/失败报告 | ☑ **v1.2.0**（`feature/batch-ui` 已合并） |
| **P0** | 多页 PDF KIE 策略 | ☑ **v1.2.0** |
| **P0** | 字段校验与 `quality` 扩展 | ☐ `feature/kie-field-validation` |
| **P1** | 文档类型自动分类、HITL、可搜索 PDF | 独立 feature |
| **维护** | id_card 精度 / 样例 | `bugfix/*` 或 patch |

产品对照（**local only, gitignored** — do not commit）：`test_data/TestResult/PLAN/Upwork文档处理需求与DocuVision能力分析.md` 及同目录其他 `*Upwork*` 规划稿。

## 7. 发版后检查

- [x] Tracker「Release 1.1 baseline」`branch` = `main`、`tag` = `v1.1.0`
- [x] Cloud 阶段 C+E 发版后复跑
- [x] GitHub Release `v1.1.0`（网页已发布）
- [ ] 删除远端已合并的 `feature/pro-v1.1-custom-fields`（见下文 §8）

## 8. GitHub Actions 与 `v1.1.0` tag（为何显示 Skipped）

本仓库 **不会** 因打 tag / 发布 Release 自动跑 CI：

| 原因 | 说明 |
|------|------|
| **无 tag 触发器** | `kie-phase-a.yml` / `ci-lite.yml` 的 `on.push` 仅 `branches: [main]`（及 Lite 的 `feature/docuvision-lite`），**不含** `tags: v*` 或 `release:` 事件。 |
| **push 默认不跑 job** | 即使 push 到 `main`，job 带 `if: … \|\| contains(github.event.head_commit.message, '[run ci]')`；合并提交 `docs: …` / `merge: …` **无** `[run ci]` → workflow 可能 **出现一次 run**，但 job 状态为 **Skipped**。 |
| **未走 PR** | v1.1 为本地 fast-forward 合并到 `main`，无 `pull_request` 事件 → 未触发 PR 门禁。 |

**若要验证 v1.1.0 契约**：GitHub → **Actions** → 选 **KIE Phase A** → **Run workflow** → Branch `main`；或新开 PR（改 `backend/**`）到 `main` 会自动跑 Phase A。  
发版 push 若需 CI，须在 commit message 加 **`[run ci]`**（见 `.cursor/rules/003-git.mdc`）。

**注意**：当前 `kie-phase-a.yml` 的 pytest 列表**未包含** `test_kie_query_fields.py`；v1.1 query 字段契约以 Cloud Phase B + 本地/Cloud pytest 为准，后续可在 workflow 中补测项（改 workflow 需维护者同意）。
