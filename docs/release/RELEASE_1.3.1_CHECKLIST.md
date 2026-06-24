# Release 1.3.1 checklist

> Target tag: **`v1.3.1`** · Date: **2026-06-23**  
> Scope: deletions (Auto-detect, Lite batch/ROI) + Lite server preview + E2E fixes

## Code and docs

| Item | Status |
|------|--------|
| `APP_VERSION` | `1.3.1` in `backend/app/core/config.py` |
| Lite preview | `routes_preview.py`, `preview_store.py`, `preview_renderer.py` |
| Dead UI cleanup | `previewCanvas`, batch CSS removed from Lite frontend |
| Cloud gate | [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md) |
| Release notes | [RELEASE_1.3.1_NOTES.md](./RELEASE_1.3.1_NOTES.md) |
| Living limits | [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) @ v1.3.1 |

## Pre-tag verification (Cloud)

- [ ] Lite `pytest tests/ -q` all green
- [ ] `npm run test:e2e:lite` — LITE-PREVIEW-01
- [ ] `npm run test:unit` + `npm run test:e2e` (Pro)
- [ ] Phase A ≥45 (GPU)
- [ ] CORE-PDF-001, KIE-VAL-001, STITCH-001 per v1.3.1 merge doc
- [ ] Skip LITE-BATCH-001 (removed)

## Git

```bash
git tag -a v1.3.1 -m "Release 1.3.1: Lite server preview, remove Lite batch/ROI and Pro auto-detect"
git push origin v1.3.1
gh release create v1.3.1 --title "v1.3.1 — Lite preview + scope trim" --notes-file docs/release/RELEASE_1.3.1_NOTES.md
```

## Post-release

- [ ] Append Release 1.3.1 row to [KIE_TEST_RUN_TRACKER.md](../architecture/KIE_TEST_RUN_TRACKER.md)
- [ ] Manual spot-check: Lite queue + PDF preview in browser (LITE-UI-004 subset)
