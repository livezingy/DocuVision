# Release 1.4.0 checklist

> Target tag: **`v1.4.0`** · Date: **2026-06-30**  
> Scope: table mapping UI, HITL editable review, PDF Tools tab, batch MappedRows, Phase A CI extension

## Code and docs

| Item | Status |
|------|--------|
| `APP_VERSION` | `1.4.0` in `backend/app/core/config.py` |
| Table mapping | Processing mode UI, `mapped_table_rows` tab, orchestrator `table_step` |
| HITL | `hitl_policy.py`, editable Reviews UI, `kie-fields` PATCH |
| PDF Tools | Top nav + merge/split/metadata UI |
| Cloud gate | [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md) |
| Release notes | [RELEASE_1.4_NOTES.md](./RELEASE_1.4_NOTES.md) |
| Living limits | [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) @ v1.4.0 |
| README | Batch/Reviews/PDF Tools nav; v1.4 release link |

## Pre-tag verification (Cloud)

- [ ] Phase A v1.4 — Pro **≥57** + core mapping/stitch **≥6** (see merge doc §1)
- [ ] v1.3.1 regression subset — CORE-PDF-001, LITE-PREVIEW-001, KIE-VAL-001
- [ ] **MAP-TEMPLATE-001** — single-file `bank_statement` → `mapped_table_rows`
- [ ] **MAPPED-BATCH-001** — batch Excel MappedRows sheet
- [ ] `npm run test:unit` + `npm run test:e2e` (Pro)
- [ ] Lite `pytest tests/ -q` + `npm run test:e2e:lite`
- [ ] Manual: **PDF-TOOL-001**, **HITL-EDIT-001** ([UI_VERIFICATION_MATRIX.md](../../test_data/acceptance/UI_VERIFICATION_MATRIX.md) §2.3)

## Git

```bash
git tag -a v1.4.0 -m "Release 1.4.0: table mapping, HITL review UI, PDF Tools, batch MappedRows"
git push origin v1.4.0
gh release create v1.4.0 --title "v1.4.0 — Table mapping + HITL + PDF Tools" --notes-file docs/release/RELEASE_1.4_NOTES.md
```

## Post-release

- [ ] Append Release 1.4.0 row to [KIE_TEST_RUN_TRACKER.md](../architecture/KIE_TEST_RUN_TRACKER.md)
- [ ] Record demo GIFs per [media/README.md](../architecture/media/README.md) (M1 table mapping minimum)
- [ ] Optional: `[run ci]` push to verify extended `kie-phase-a.yml` on GitHub
