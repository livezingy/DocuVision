# Architecture media

## Pro (in repo)

- `docuvision-ui.png` — hero screenshot for the root README.
- `DocVision_table.gif`, `DocVision_receipt.gif`, `DocVision_Invoice.gif` — recorded UI walkthroughs for the README **Examples** section.

## Lite (record locally; add to repo when ready)

Target files for Release 1.0.1+ marketing (not yet committed):

| File | Scenario | Duration | Key frames |
|------|----------|----------|------------|
| `DocVision_Lite_table.gif` | Born-digital PDF with bordered table | 20–30s | Upload → Profile (`bordered`) → Run Analysis → Content/Tables → Export JSON |
| `DocVision_Lite_ocr.gif` | Scan/image OCR | 15–25s | Upload PNG → Analysis Options (no Tables) → Run Analysis → Content/Text → Quality hint |

### Recording checklist

- Resolution: 1280×720 (or 1440w); browser zoom 100%; hide bookmarks bar.
- Environment: Cloud Studio CPU; `cd apps/lite/backend && python run_lite.py`; open `http://{host}:8001/lite/lite.html`.
- Samples: `apps/lite/backend/tests/fixtures/sample_bordered.pdf`; OCR from `test_data/testfiles/images/scanned/` (no PII).
- Tooling: OBS → MP4 → ffmpeg or ScreenToGif; target **under 5 MB** (10–15 fps, width 960 if needed).
- On-screen title (optional): **Self-hosted · CPU · No cloud API keys**.
- Do **not** show: raster Transformer tables, Fields tab (Lite has no KIE).
- End card: status bar with `processing_ms` and engine (`easyocr` / `pdfplumber`).

### ffmpeg example (after OBS export)

```bash
ffmpeg -i lite_table.mp4 -vf "fps=12,scale=960:-1:flags=lanczos" -loop 0 DocVision_Lite_table.gif
```

After adding GIFs, link them from the root [README.md](../../README.md) **Lite** subsection.
