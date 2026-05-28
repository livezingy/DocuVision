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
| 1 | Upload scan/image; Run with EasyOCR | **Content/Text** shows extracted text if any blocks exist |
| 2 | Low confidence case | Quality panel warns `low_confidence`; text still visible; hint may mention Pro |
| 3 | True failure (no engine / init error) | Quality panel shows `ocr_extraction_failed`; Text explains failure |
| 4 | No text detected | Text tab shows `no_text_detected` message, not blank Pro-only state |

## LITE-UI-004 Processing Queue

| Step | Action | Expected |
|------|--------|----------|
| 1 | Upload 3 files | Queue count = 3; status message confirms |
| 2 | Try upload 4th file | Status: queue full; suggests removing a file |
| 3 | Hover queue item | **Remove (×)** button appears |
| 4 | Remove a completed file | Item deleted; can upload another file |
| 5 | Remove active file | Preview + results switch to next item or empty state |
| 6 | Upload 3 files, select file 3, Run Analysis | **Only file 3** is profiled/extracted; other queue items unchanged |

## LITE-UI-005 Export actions (Lite generic)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open Result export section | JSON / CSV / Excel visible |
| 2 | Validation Dashboard / Save | **Hidden** in generic Lite (enable via `ui-features.js` for custom demos) |

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
| Styles | `lite-overrides.css` | `frontend/styles.css` | `frontend/shared/layout.css`, `tokens.css` |
| Queue/preview JS | Lite IndexedDB + max 3 + remove | Pro DOM queue + server task delete | Pattern only (not shared code) |
| Panel resize | — | — | `frontend/shared/panel-resize.js` |
| Feature flags | — | — | `frontend/shared/ui-features.js` |
