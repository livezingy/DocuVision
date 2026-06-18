# Release 1.3.0 发布清单

> 目标 tag：**`v1.3.0`** · 日期：**2026-06-17**  
> 范围：路线图 P0（PDF core + Lite batch + KIE validation + templates）

## 代码与文档

| 项 | 说明 |
|----|------|
| `APP_VERSION` | `1.3.0` |
| Pro core PDF | `core_table_extractor.py`, `table_service.py`, `file_type_detector.py` |
| Lite batch | `apps/lite/backend/app/api/routes_batch.py` |
| KIE validation | `kie/field_validation.py`, orchestrator `kie_validation` |
| Templates | `kie/schema_templates.py`, `kie_configs/templates/` |
| Cloud 清单 | [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md) |
| Release notes | [RELEASE_1.3.0_NOTES.md](./RELEASE_1.3.0_NOTES.md) |

## 依赖

Pro 环境需重装：

```bash
cd backend
pip install -r requirements.txt
```

## GitHub

```bash
git tag -a v1.3.0 -m "Release 1.3.0: PDF core routing, Lite batch, KIE validation"
git push origin v1.3.0
gh release create v1.3.0 --title "v1.3.0 — Roadmap P0" --notes-file docs/release/RELEASE_1.3.0_NOTES.md
```

## 发版后

- [ ] Cloud [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md) 全过
- [ ] Tracker 追加 Release 1.3 行
- [ ] 更新 [docuvision-system-design.md](../architecture/docuvision-system-design.md) §10（可选）
