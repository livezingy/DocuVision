# Lite UI Basic Operations — Cloud Test Checklist

Run after starting Lite: `cd apps/lite/backend && python run_lite.py`  
Open: `http://{host}:8001/lite/lite.html`

Automated API/UI contract tests: `python -m pytest tests/test_lite_ocr_messaging.py tests/test_lite_bordered_tables.py -q`

## LITE-UI-001 Upload and Profile

| Step | Action | Expected |
|------|--------|----------|
| 1 | Upload a born-digital PDF | Right panel switches to **Profile** tab |
| 2 | Check Profile content | `table_type`, routing strategy, typography visible |
| 3 | Change page in center preview | Profile page selector syncs |

## LITE-UI-002 Content Tabs

| Step | Action | Expected |
|------|--------|----------|
| 1 | Run Analysis on PDF with tables | Auto switch to **Content** tab, **Tables** sub-tab |
| 2 | Click **Text** / **Tables** / **Figures** | Each sub-tab activates; Tables show grid data |
| 3 | Figures tab | Pro upsell empty state (not broken layout) |

## LITE-UI-003 OCR — Low confidence vs failure

| Step | Action | Expected |
|------|--------|----------|
| 1 | Upload scan/image with **Tables** enabled | Transformer runs when torch/transformers installed; tables in Content |
| 2 | Low confidence case | Quality panel warns `low_confidence`; text still visible; hint may mention Pro |
| 3 | True failure (no engine / init error) | Quality panel shows `ocr_extraction_failed`; Text explains failure |
| 4 | No text detected | Text tab shows `no_text_detected` message, not blank Pro-only state |

## LITE-UI-004 Processing Queue

| Step | Action | Expected |
|------|--------|----------|
| 1 | Upload multiple files | Queue count increases; no fixed max of 3 |
| 2 | Try upload 4th file | All valid files are accepted (same as Pro; no fixed cap) |
| 3 | Hover queue item | **Remove (×)** button appears |
| 4 | Remove a completed file | Item deleted; can upload another file |
| 5 | Remove active file | Preview + results switch to next item or empty state |
| 6 | Upload 3 files, select file 3, Run Analysis | **Only file 3** is profiled/extracted; other queue items unchanged |

## LITE-UI-005 Export actions (Lite generic)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Run analysis, open Export Results | Buttons: **JSON**, **CSV**, **Markdown**, **Word** (Pro-style icons) |
| 2 | Click each export button | Downloads via `/api/v1/lite/export/{job_id}.{format}` |
| 3 | Validation Dashboard / Save | **Hidden** in generic Lite (enable via `ui-features.js` for custom demos); when hidden, not inside 4-column export grid |

## LITE-UI-008 Export parity (shared shell)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Run analysis, inspect Export Results | **4 equal-width buttons** in one grid row (JSON / CSV / Markdown / Word) |
| 2 | Inspect button icons | SVG icons **20×20px**, visually matched to Pro |
| 3 | Click each export | File downloads; **toast** top-right + **status bar** message (both) |
| 4 | Result tab | **Copy** and **Download** JSON toolbar with icons (Pro-style) |
| 5 | Image + Text + Tables | Tables extracted when Transformer deps installed; no `coroutine was never awaited` in server log |

## LITE-UI-006 Bordered PDF tables

| Step | Action | Expected |
|------|--------|----------|
| 1 | Upload obvious bordered table PDF | Profile: `bordered` (or high line count) |
| 2 | Run Analysis (Smart) | Tables tab: at least one table with rows/columns |
| 3 | Export JSON | `tables[]` non-empty in Result tab |

## LITE-UI-007 Analysis Options

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open Analysis Options | Processing / Engines / Advanced tabs |
| 2 | Advanced + Auto param mode | Hint: parameters computed at runtime |
| 3 | Apply Profile to Advanced | Custom JSON prefilled from profile |

## Lite vs Pro UI sharing (reference)

| Area | Lite | Pro | Shared |
|------|------|-----|--------|
| HTML shell | `apps/lite/frontend/lite.html` | `frontend/index.html` | — |
| App logic | `apps/lite/frontend/lite.js` | `frontend/app.js` | — |
| Styles | `lite-overrides.css` (Lite-only; **no** `.export-*` overrides) | `frontend/styles.css` | `layout.css`, `tokens.css`, **`components.css`** |
| Queue/preview JS | Lite IndexedDB queue + remove | Pro DOM queue + server task delete | Pattern only (not shared code) |
| Panel resize | — | — | `frontend/shared/panel-resize.js` |
| Feature flags | — | — | `frontend/shared/ui-features.js` |
| Notifications / Export JS | via `lite.js` config | via `app.js` config | **`notifications.js`**, **`export-ui.js`** |

See [`docs/architecture/shared-ui-shell.md`](../../../docs/architecture/shared-ui-shell.md) for shared UI maintenance rules.
