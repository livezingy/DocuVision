# main @ v1.4.0 — Cloud Studio acceptance checklist

Last updated: 2026-06-30  
Target tag: **`v1.4.0`**  
Shell: **zsh/bash** (batch mapped script: PowerShell on Windows — see §6)

Related: [CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md), [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md), [RELEASE_1.4_NOTES.md](../../docs/release/RELEASE_1.4_NOTES.md)

**Scope delta vs v1.3.1**: Phase A **v1.4 extension** (+12 Pro contract tests); **MAP-TEMPLATE-001** (single-file table mapping); **MAPPED-BATCH-001** (batch MappedRows XLSX). Manual: **PDF-TOOL-001**, **HITL-EDIT-001**.

---

## Pass criteria (merge main / tag v1.4.0 minimum)

| # | Phase | Pass |
|---|-------|------|
| 0 | Env | Pro `:8000` + Lite `:8001` health **200**; `/api/v1/health` JSON on Pro |
| 1 | Phase A v1.4 | Pro pytest **≥57 passed** + core **≥6 passed** (§1; incl. `test_phase1_analyze_form.py`, `test_webhook_service.py`) |
| 2 | v1.3.1 regression | [MERGE_MAIN_v1.3.1](./MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md) §3–§6 (CORE-PDF, LITE-PREVIEW, KIE-VAL, STITCH) |
| 3 | **MAP-TEMPLATE-001** | Single PDF `table_template=bank_statement` → `mapped_table_rows` (§3) |
| 4 | **MAPPED-BATCH-001** | Batch `mapped_bank_statement_3` → XLSX **MappedRows** (§6) |
| 5 | Pro UI (no GPU) | `npm run test:unit` + `npm run test:e2e` (§7) |
| 6 | Lite | `pytest tests/ -q` + `npm run test:e2e:lite` (§8) |
| 7 | Backend hardening | Webhook 404/401/400/200 chain + Phase1 form parity + searchable 501 + debug traversal (§9) |
| — | Manual | **PDF-TOOL-001**, **HITL-EDIT-001** ([UI_VERIFICATION_MATRIX.md](./UI_VERIFICATION_MATRIX.md) §2.3) |

---

## §0 Common variables

**路径（双云）**：仅需在非标准 clone 位置时设置 **`DOCUVISION_ROOT`**；否则脚本自动从 `test_data/scripts/` 推断仓库根目录。

```bash
# Optional — only when repo is not ~/DocuVision (Baidu) or /workspace/DocuVision (Tencent):
# export DOCUVISION_ROOT=~/DocuVision

source test_data/scripts/lib/cloud_env.sh
init_cloud_env
# Sets: REPO_ROOT, CLOUD_PROVIDER (tencent|baidu|generic), API_ROOT=http://127.0.0.1:8000

export LITE_ROOT="http://127.0.0.1:8001"
export BANK_SAMPLE="$REPO_ROOT/test_data/testfiles/GeneralFiles/bank_statement_sample.pdf"
export OUT_DIR="$REPO_ROOT/test_data/TestResult/PhaseV14"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"
git fetch origin && git pull origin main

cd backend && source ~/docuvision_env/bin/activate
# Baidu AI Studio: export PIP_CONFIG_FILE=/tmp/pip-docuvision.conf first (CLOUD_VALIDATION §1.1)
pip install -e ../packages/docuvision-core[lite] pdfplumber pymupdf -q
```

**T1 Pro**: `DEBUG=false python run.py` (`:8000`)  
**T3 Lite**: `cd apps/lite/backend && source ~/docuvision_lite_env/bin/activate && python run_lite.py` (`:8001`)

Health:

```bash
curl -s -o /dev/null -w "Pro HTTP %{http_code}\n" "$API_ROOT/api/v1/health"
curl -s -o /dev/null -w "Lite HTTP %{http_code}\n" "$LITE_ROOT/api/v1/lite/health"
```

---

## §1 Phase A v1.4 (Pro + core)

**v1.3 file list** (same as [v1.3.0 §1](./MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md#1-phase-a-扩展v13)) **plus v1.4**:

```bash
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py \
  tests/test_kie_field_validation.py tests/test_kie_schema_templates.py \
  tests/test_document_type_classifier.py tests/test_file_type_detector.py \
  tests/test_table_template_analyze.py tests/test_hitl_policy.py \
  tests/test_task_kie_fields_patch.py tests/test_pdf_tools_service.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py \
  tests/test_phase1_analyze_form.py tests/test_webhook_service.py -q

cd "$REPO_ROOT/packages/docuvision-core"
pytest tests/processing/test_table_stitch.py \
  tests/processing/test_table_column_mapping.py \
  tests/processing/test_table_result_mapper.py -q
```

**Pass**: all `passed` (Pro **≥63** + core **≥6**; +4 Phase1 form + +9 webhook vs v1.4 baseline).

---

## §3 MAP-TEMPLATE-001 — Pro table mapping (single file)

Requires `bank_statement_sample.pdf` and Pro server running (`DEBUG=false`).

```bash
test -f "$BANK_SAMPLE" || { echo "missing $BANK_SAMPLE"; exit 1; }

curl -s -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$BANK_SAMPLE" \
  -F "document_type=general" \
  -F "enable_layout=0" \
  -F "enable_table=1" \
  -F "enable_kie=0" \
  -F "enable_ocr=0" \
  -F "table_template=bank_statement" | tee "$OUT_DIR/map_analyze.json"

TASK_ID=$(python3 -c "import json; print(json.load(open('$OUT_DIR/map_analyze.json'))['task_id'])")

for i in $(seq 1 60); do
  ST=$(curl -s "$API_ROOT/api/v1/tasks/$TASK_ID" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
  echo "status=$ST"
  [ "$ST" = "completed" ] && break
  sleep 2
done

curl -s "$API_ROOT/api/v1/tasks/$TASK_ID/result" | python3 - <<'PY'
import json, sys
r = json.load(sys.stdin)
assert r.get("table_template") == "bank_statement", r.get("table_template")
rows = r.get("mapped_table_rows") or []
assert len(rows) >= 1, "expected mapped_table_rows"
required = {"transaction_date", "description", "amount", "balance"}
first = rows[0]
assert required.issubset(first.keys()), f"missing keys in {first.keys()}"
print("MAP-TEMPLATE-001 pass", "rows=", len(rows))
PY
```

**Pass**: `table_template=bank_statement`; `mapped_table_rows` ≥1 row with schema column keys.

**One-liner** (requires Pro `:8000` running; auto-detects Tencent / Baidu):

```bash
cd ~/DocuVision          # Baidu AI Studio — or cd /workspace/DocuVision on Tencent
bash test_data/scripts/run_m1_table_mapping_acceptance.sh
```

Non-standard clone path:

```bash
export DOCUVISION_ROOT=/path/to/DocuVision
bash "$DOCUVISION_ROOT/test_data/scripts/run_m1_table_mapping_acceptance.sh"
```

Optional UI spot-check: Analysis Options → **Table mapping** → Template **Bank statement** → Run → Content **Mapped rows**.

---

## §6 MAPPED-BATCH-001

**Windows (PowerShell)**:

```powershell
pwsh -File "$REPO_ROOT/test_data/scripts/run_batch_mapped_acceptance.ps1"
```

**Cloud zsh** (equivalent curl flow): create batch from manifest set `mapped_bank_statement_3`, start, poll to `completed`, download `export.xlsx?mode=all`, verify **MappedRows** sheet has ≥1 data row (see script validation).

**Pass**: batch `status=completed`; Excel contains **MappedRows** with data.

---

## §7 Pro frontend (CPU)

```bash
cd "$REPO_ROOT/frontend"
npm run test:unit
npm run test:e2e
```

**Pass**: unit + Pro E2E green.

---

## §8 Lite regression

```bash
cd "$REPO_ROOT/apps/lite/backend"
source ~/docuvision_lite_env/bin/activate
pytest tests/ -q

cd "$REPO_ROOT/frontend"
npm run test:e2e:lite
```

**Pass**: Lite pytest all green; **LITE-PREVIEW-01** passed.

---

## §9 Backend hardening (v1.4.0-prep additions)

Covers PR #3/#4/#5 merged into `release/v1.4.0-prep`: webhook auth/SSRF, Phase1 form parity, debug traversal, searchable 501.

### 9.1 Webhook service contract (CPU, no server)

```bash
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate
pytest tests/test_webhook_service.py -q
```

**Pass**: 9 passed (SSRF 6 cases + dispatch-disabled + dispatch-enabled + public host).

### 9.2 Phase1 form parity contract (CPU, no server)

```bash
pytest tests/test_phase1_analyze_form.py -q
```

**Pass**: 4 passed (defaults, engine/formula params, table_template/HITL, auto-KIE).

### 9.3 Webhook endpoint auth chain (needs Pro `:8000`)

```bash
# Default (WEBHOOK_ENABLED=false) → 404
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/webhooks" -F "url=https://example.com/hook"
# Expect 404

# Set .env: WEBHOOK_ENABLED=true (no token) → fail-closed 401
# Restart run.py
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/webhooks" -F "url=https://example.com/hook"
# Expect 401

# Set .env: WEBHOOK_ENABLED=true, WEBHOOK_ADMIN_TOKEN=secret123 → restart
# No header → 401
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/webhooks" -F "url=https://example.com/hook"
# Expect 401
# Wrong token → 401
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/webhooks" -H "X-DocuVision-Admin-Token: wrong" \
  -F "url=https://example.com/hook"
# Expect 401
# Correct token + private URL → 400
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/webhooks" -H "X-DocuVision-Admin-Token: secret123" \
  -F "url=http://127.0.0.1:9999/hook"
# Expect 400
# Correct token + public URL → 200
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/webhooks" -H "X-DocuVision-Admin-Token: secret123" \
  -F "url=https://example.com/hook"
# Expect 200
```

### 9.4 Searchable PDF 501 + debug traversal (needs Pro `:8000`)

```bash
# searchable → 501
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/pdf-tools/searchable" \
  -F "file=@$REPO_ROOT/test_data/testfiles/invoices/sample-invoice.png" -F "text=test"
# Expect 501

# Debug traversal (needs DEBUG_MODE=true, restart)
JOB_ID=$(curl -s -X POST "$API_ROOT/api/v1/documents:analyze" \
  -F "file=@$REPO_ROOT/test_data/testfiles/invoices/sample-invoice.png" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
sleep 30
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  "$API_ROOT/api/v1/jobs/$JOB_ID/debug/..%2F..%2F..%2Fetc%2Fpasswd"
# Expect 403 (or 404 if route rejects %2F; both mean no leak)
```

**Pass**: all status codes match expectations.

---

## §3.1–§5 v1.3.1 sections (copy)

Run from [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md):

- **CORE-PDF-001** — use v1.3.0 §3 commands
- **LITE-PREVIEW-001** — v1.3.1 §4
- **KIE-VAL-001** — v1.3.0 §5
- **STITCH-001** — v1.3.0 §6 / `test_table_stitch.py` (also in §1 above)

---

## Artifacts

| Item | Path |
|------|------|
| Map analyze JSON | `$OUT_DIR/map_analyze.json` |
| Batch XLSX | `$REPO_ROOT/test_data/TestResult/PhaseBatch/batch_*_mapped.xlsx` |
| Tracker | `KIE_TEST_RUN_TRACKER.md` → Release 1.4.0 row |
