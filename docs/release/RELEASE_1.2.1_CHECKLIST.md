# Release 1.2.1 发布清单

> 目标 tag：**`v1.2.1`** · 日期：**2026-06-17**  
> 范围：Batch Excel + Playwright E2E P0 + Shared UI PR2

## 代码与文档

| 项 | 说明 |
|----|------|
| Batch `export.xlsx` | `batch_export_service.py`, `main.py`, Batch UI |
| Playwright P0 | `frontend/tests/e2e/`, `playwright.config.js` |
| Shared UI PR2 | `shared/components.css`, `pro-only.css` |
| Cloud 清单 | [MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md) |
| Release notes | [RELEASE_1.2.1_NOTES.md](./RELEASE_1.2.1_NOTES.md) |

## GitHub

```bash
git tag -a v1.2.1 -m "Release 1.2.1: Batch Excel, Playwright E2E P0, Shared UI PR2"
git push origin v1.2.1
gh release create v1.2.1 --title "v1.2.1 — Batch Excel + E2E P0" --notes-file docs/release/RELEASE_1.2.1_NOTES.md
```

## 发版后

- [ ] Cloud [MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md) 全过
- [ ] Tracker 追加 v1.2.1 行
