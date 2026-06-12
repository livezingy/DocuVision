# Release 1.2 发布清单

> 目标 tag：**`v1.2.0`** · 日期：**2026-06-12** · 合并：`feature/batch-ui` → `main`  
> 范围：Pro **`kie_pages`** 多页 KIE + Batch 产品化（API + UI）。

## 1. 代码与文档（仓库内）

| 项 | 状态 | 说明 |
|----|:----:|------|
| `kie_pages` + field merge | ☑ | `backend/app/services/kie/` |
| Batch export CSV/JSON | ☑ | `batch_export_service.py` |
| Pro Batch UI tab | ☑ | `frontend/index.html`, `app.js` |
| Phase A 扩展单测 | ☑ | `test_kie_pages_parse`, `test_batch_export_service`, etc. |
| `CHANGELOG.md` `[1.2.0]` | ☑ | 发版 commit |
| `RELEASE_1.2_NOTES.md` | ☑ | GitHub Release notes |
| `KIE_TEST_RUN_TRACKER.md` Release 1.2 | ☑ | 合 main 门禁 2026-06-12 |
| `APP_VERSION` = `1.2.0` | ☑ | `backend/app/core/config.py` |
| Git tag `v1.2.0` on `main` | ☐ | 推送后打 tag |

## 2. Cloud 验收（GPU 环境）

| 阶段 | 目标 | Release 1.2 状态 |
|------|------|------------------|
| Phase A | 37/37 pytest | ☑ 2026-06-12 |
| MP-002 | 2p PDF `kie_pages=all` | ☑ |
| H-Batch | `kie_invoice_6` 6/6 hit | ☑ |
| Layout batch + 控制流 | pause/resume | ☑ |
| UI 冒烟 §7 | BATCH-U + FIX-Q | ☑ |

清单：[MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md)

## 3. GitHub 操作

```bash
# 已合并 feature/batch-ui → main 后：
git checkout main && git pull origin main
git tag -a v1.2.0 -m "Release 1.2.0: multipage KIE and Batch Processing UI"
git push origin main
git push origin v1.2.0
gh release create v1.2.0 --title "v1.2.0 — Multipage KIE + Batch UI" --notes-file docs/release/RELEASE_1.2_NOTES.md
```

PR 至 `main` 且 `backend/**` 变更会触发 **KIE Phase A** CI（当前 workflow 仍为 v1.1 四文件集；v1.2 扩展测项以 Cloud Phase A 37 项为准）。

## 4. 发版后检查

- [ ] Tracker「Release 1.2」`branch` = `main`、`tag` = `v1.2.0`
- [ ] GitHub Release `v1.2.0` 已发布
- [ ] 可选：删除远端已合并的 `feature/batch-ui`
