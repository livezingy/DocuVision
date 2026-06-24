# main @ v1.3.1 — Cloud Studio acceptance checklist

Last updated: 2026-06-23  
Target tag: **`v1.3.1`**  
Shell: **zsh/bash**

Related: [CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md), [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md) (historical v1.3.0 gate), [RELEASE_1.3.1_NOTES.md](../../docs/release/RELEASE_1.3.1_NOTES.md)

**Scope delta vs v1.3.0**: Lite Batch API/UI removed — **skip LITE-BATCH-001**. Adds **LITE-PREVIEW-001** (server-side PDF preview + CI E2E).

---

## Pass criteria (merge main / tag v1.3.1 minimum)

| # | Phase | Pass |
|---|-------|------|
| 0 | Env | Pro `:8000` + Lite `:8001` health **200** |
| 1 | Phase A | Pro pytest **≥45 passed** (§1); core stitch **2 passed** |
| 2 | v1.2.1 regression | [MERGE_MAIN_v1.2.1](./MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md) §1–§4 |
| 3 | **CORE-PDF-001** | Same as [v1.3.0 §3](./MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md#3-core-pdf-001--pro-数字-pdf-core-路由) |
| 4 | **LITE-PREVIEW-001** | Preview API PNG + Lite pytest + Playwright `LITE-PREVIEW-01` (§4) |
| 5 | **KIE-VAL-001** | Same as [v1.3.0 §5](./MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md#5-kie-val-001) |
| 6 | **STITCH-001** | `test_table_stitch.py` passed |
| 7 | Pro UI (no GPU) | `npm run test:unit` + `npm run test:e2e` green (§7) |
| — | **N/A** | **LITE-BATCH-001** — Lite batch removed in v1.3.1 |

---

## §0 Common variables

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export LITE_ROOT="http://127.0.0.1:8001"
export LITE_PREVIEW="$LITE_ROOT/api/v1/lite/preview"
export SAMPLE_BORDERED="$REPO_ROOT/apps/lite/backend/tests/fixtures/sample_bordered.pdf"
export OUT_DIR="$REPO_ROOT/test_data/TestResult/PhaseV131"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"
git fetch origin && git checkout main && git pull origin main

cd backend && source ~/docuvision_env/bin/activate
pip install -e ../packages/docuvision-core[lite] pdfplumber pymupdf -q
```

**T1 Pro**: `DEBUG=false python run.py` (`:8000`)  
**T3 Lite**: `cd apps/lite/backend && source ~/docuvision_lite_env/bin/activate && python run_lite.py` (`:8001`)

---

## §1 Phase A (Pro + core)

Same file list as [MERGE_MAIN_v1.3.0 §1](./MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md#1-phase-a-扩展v13).

**Pass**: all `passed` (Pro **≥45** + core stitch **2**).

---

## §4 LITE-PREVIEW-001

### 4a API smoke (Lite server running)

```bash
curl -s -X POST "$LITE_PREVIEW" \
  -F "file=@$SAMPLE_BORDERED" | tee "$OUT_DIR/lite_preview.json"

PREVIEW_ID=$(python3 -c "import json; print(json.load(open('$OUT_DIR/lite_preview.json'))['preview_id'])")
curl -s -o "$OUT_DIR/lite_page1.png" -w "HTTP %{http_code}\n" \
  "$LITE_PREVIEW/$PREVIEW_ID/page-image/1"

python3 - <<PY
from pathlib import Path
p = Path("${OUT_DIR}/lite_page1.png")
assert p.stat().st_size > 100, "empty page image"
assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "expected PNG"
print("LITE-PREVIEW-001 API pass")
PY
```

**Pass**: upload JSON has `preview_id` + `page_count`; page-image HTTP **200**; PNG magic bytes.

### 4b Lite contract pytest

```bash
cd "$REPO_ROOT/apps/lite/backend"
source ~/docuvision_lite_env/bin/activate
pytest tests/test_lite_preview.py -q
```

**Pass**: all tests in `test_lite_preview.py` passed.

### 4c Playwright (no Lite server required — mock API)

```bash
cd "$REPO_ROOT/frontend"
npm install
npx playwright install chromium
npm run test:e2e:lite
```

**Pass**: `LITE-PREVIEW-01` passed (1 test).

---

## §7 Pro frontend (CPU)

```bash
cd "$REPO_ROOT/frontend"
npm run test:unit
npm run test:e2e
```

**Pass**: unit + Pro E2E green (mock API; covers queue/options regressions after Auto-detect removal).

---

## §5–§6 KIE-VAL / STITCH

Copy commands from [MERGE_MAIN_v1.3.0 §5–§6](./MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md#5-kie-val-001).

---

## Artifacts

| Item | Path |
|------|------|
| Preview JSON | `$OUT_DIR/lite_preview.json` |
| Page PNG | `$OUT_DIR/lite_page1.png` |
| Tracker | `KIE_TEST_RUN_TRACKER.md` → Release 1.3.1 row |
