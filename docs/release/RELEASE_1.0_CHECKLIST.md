# Release 1.0 发布清单

> 目标 tag：**`v1.0.0`** · 日期：**2026-05-21** · 分支：`main`  
> 范围定义见 [docuvision-system-design.md](../architecture/docuvision-system-design.md) §10「Release 1.0 范围」。

## 1. 代码与文档（仓库内）

| 项 | 状态 | 说明 |
|----|:----:|------|
| `LICENSE`（MIT） | ☑ | 根目录 |
| `CHANGELOG.md` | ☑ | 含 1.0.0 条目 |
| `docs/release/KNOWN_LIMITATIONS.md` | ☑ | 含 id_card_sample_01 / 003 |
| `KIE_TEST_RUN_TRACKER.md` | ☑ | Release 1.0 批次 |
| Phase A CI green | ☑ | GitHub Actions **KIE Phase A** on `main` |
| 总纲 1.0 checklist | ☑ | 见 §10 更新 |

## 2. Cloud 验收（GPU 环境）

| 阶段 | 目标 | Release 1.0 状态 |
|------|------|------------------|
| **A** | 契约 pytest / Actions | CI 自动 |
| **B** | `/health` 200 | 发 tag 前再 curl 一次 |
| **C** | 发票 3 样例 001+002 | ☑ 2026-05-20 基线（`e7dc4ab+`） |
| **D** | kie/ 6 样例 001+002；id_card 02~04 **003** | ☑ 2026-05-21 UI 批次 |
| **E** | 收据 1 样例 001+002 | ☑ 2026-05-20 基线 |
| Layout 冒烟（可选） | 1 PDF/扫描件，无 KIE | 建议 tag 前 UI 点一次 |

**建议 tag 前**：在同一 Cloud 会话、`git pull` 到发版 commit 后，**重跑 C + E**（约 30 分钟）以防最后一次提交引入回归。

## 3. GitHub Release 操作（维护者）

```bash
# 1. 确认 main 已包含发版 commit
git checkout main
git pull origin main

# 2. 打 tag（annotated）
git tag -a v1.0.0 -m "Release 1.0.0: Layout + Qwen KIE baseline"

# 3. 推送 tag
git push origin v1.0.0

# 4. 创建 GitHub Release（需 gh CLI）
gh release create v1.0.0 \
  --title "v1.0.0 — Layout + Qwen KIE baseline" \
  --notes-file CHANGELOG.md
```

或在 GitHub 网页：**Releases → Draft a new release** → 选择 tag `v1.0.0` → 粘贴 `CHANGELOG.md` 中 `[1.0.0]` 一节。

## 4. 版本号对齐

| 位置 | 当前值 |
|------|--------|
| Git tag | `v1.0.0`（待打） |
| `APP_VERSION`（`backend/app/core/config.py`） | `1.0.0` |
| Job Envelope `version`（API） | `"1.0"` |

对外说明：Git **tag** 为 `v1.0.0`；API envelope 字段仍为 `"1.0"`（Phase 1 契约）。

## 5. 明确不在 v1.0.0

- 用户自定义 KIE fields（v1.1）
- Batch Processing 产品化 UI
- 多页 PDF KIE、字段 bbox
- 全量 pytest 全绿作为发版门槛

## 6. 发版后

- [ ] 更新 [KIE_TEST_RUN_TRACKER.md](../architecture/KIE_TEST_RUN_TRACKER.md) 若 tag 后又有 hotfix
- [ ] 对外公告 / README 置顶 Release 链接（可选）
- [ ] 规划 v1.0.x（id_card 真实样例）或 v1.1 设计稿
