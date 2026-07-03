#!/usr/bin/env bash
# M1 / MAP-TEMPLATE-001 — Pro table mapping acceptance (Tencent Cloud Studio / Baidu AI Studio).
# Validates API path for M1_pro_map_bank_statement.gif storyboard before UI recording.
#
# Prerequisite: Pro server on :8000 (DEBUG=false python run.py).
# Usage (zero config when cwd is repo root):
#   cd ~/DocuVision && bash test_data/scripts/run_m1_table_mapping_acceptance.sh
# Optional (non-standard clone path only):
#   export DOCUVISION_ROOT=~/DocuVision
#   bash test_data/scripts/run_m1_table_mapping_acceptance.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/cloud_env.sh
source "$SCRIPT_DIR/lib/cloud_env.sh"
init_cloud_env

BANK_SAMPLE="${BANK_SAMPLE:-$REPO_ROOT/test_data/testfiles/GeneralFiles/bank_statement_sample.pdf}"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/test_data/TestResult/PhaseV14/M1}"
EXPECTED_API_VERSION="${EXPECTED_API_VERSION:-1.4.0}"

mkdir -p "$OUT_DIR"

echo "=== M1 Table mapping acceptance (MAP-TEMPLATE-001) ==="
echo "CLOUD_PROVIDER=$CLOUD_PROVIDER"
echo "REPO_ROOT=$REPO_ROOT"
echo "API_ROOT=$API_ROOT"
echo "OUT_DIR=$OUT_DIR"
cloud_pip_hint "$CLOUD_PROVIDER" || true
echo ""

if [[ ! -f "$BANK_SAMPLE" ]]; then
  echo "FAIL: missing sample PDF: $BANK_SAMPLE" >&2
  exit 1
fi

# --- Step 0: health (status bar / api_version for GIF end card) ---
HEALTH_JSON="$OUT_DIR/health.json"
HTTP_CODE=$(curl -s -o "$HEALTH_JSON" -w "%{http_code}" "$API_ROOT/api/v1/health")
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "FAIL: GET /api/v1/health returned HTTP $HTTP_CODE" >&2
  echo "Start Pro: cd $REPO_ROOT/backend && source $VENV_ACTIVATE && DEBUG=false python run.py" >&2
  exit 1
fi

python3 - <<PY
import json, sys
from pathlib import Path
h = json.loads(Path("$HEALTH_JSON").read_text())
ver = str(h.get("api_version") or "")
expected = "$EXPECTED_API_VERSION"
if ver != expected:
    print(f"WARN: api_version={ver!r} (expected {expected!r}) — update EXPECTED_API_VERSION if tagging another train")
else:
    print(f"OK: api_version={ver}")
print(f"OK: health status={h.get('status')!r}")
PY

# --- Step 1: document profile (M1 upload pre-scan -> eligibility) ---
PROFILE_JSON="$OUT_DIR/document_profile.json"
curl -s -X POST "$API_ROOT/api/v1/document/profile" \
  -F "file=@$BANK_SAMPLE" | tee "$PROFILE_JSON" | python3 - <<'PY'
import json, sys
p = json.load(sys.stdin)
detected = p.get("detected_file_type")
assert detected == "pdf_digital", f"expected pdf_digital for M1 sample, got {detected!r}"
print("OK: document/profile detected_file_type=pdf_digital (UI: Ready for table mapping)")
PY

# --- Step 2: analyze table_mapping path (M1 Run Analysis) ---
ANALYZE_JSON="$OUT_DIR/map_analyze.json"
curl -s -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$BANK_SAMPLE" \
  -F "document_type=general" \
  -F "enable_layout=0" \
  -F "enable_table=1" \
  -F "enable_kie=0" \
  -F "enable_ocr=0" \
  -F "table_template=bank_statement" | tee "$ANALYZE_JSON"

TASK_ID=$(python3 -c "import json; print(json.load(open('$ANALYZE_JSON'))['task_id'])")
echo "task_id=$TASK_ID"
echo "export TASK_ID=$TASK_ID"

STATUS=""
for i in $(seq 1 90); do
  STATUS=$(curl -s "$API_ROOT/api/v1/tasks/$TASK_ID" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
  echo "poll[$i] status=$STATUS"
  if [[ "$STATUS" == "completed" ]]; then
    break
  fi
  if [[ "$STATUS" == "failed" || "$STATUS" == "cancelled" ]]; then
    echo "FAIL: task ended with status=$STATUS" >&2
    exit 1
  fi
  sleep 2
done

if [[ "$STATUS" != "completed" ]]; then
  echo "FAIL: task did not complete within timeout" >&2
  exit 1
fi

# --- Step 3: result (M1 Mapped rows + Result JSON tab) ---
RESULT_JSON="$OUT_DIR/map_result.json"
curl -s "$API_ROOT/api/v1/tasks/$TASK_ID/result" | tee "$RESULT_JSON" | python3 - <<'PY'
import json, sys
r = json.load(sys.stdin)
assert r.get("table_template") == "bank_statement", r.get("table_template")
rows = r.get("mapped_table_rows") or []
assert len(rows) >= 1, "expected mapped_table_rows"
required = {"transaction_date", "description", "amount", "balance"}
first = rows[0]
missing = required - set(first.keys())
assert not missing, f"missing schema keys: {missing}"
print("MAP-TEMPLATE-001 pass")
print(f"  table_template=bank_statement")
print(f"  mapped_table_rows={len(rows)}")
print(f"  sample row keys: {sorted(first.keys())}")
PY

echo ""
echo "=== M1 GIF recording checklist (manual, after API green) ==="
cloud_ui_hint "$API_ROOT" "$CLOUD_PROVIDER"
echo "2. Upload: $BANK_SAMPLE"
echo "3. Analysis Options -> Processing -> Table mapping -> Template Bank statement"
echo "4. Run Analysis -> Content -> Mapped rows (expect schema columns)"
echo "5. Result tab -> confirm mapped_table_rows in JSON"
echo "6. End card: status bar api_version + processing_ms"
echo "7. ffmpeg: fps=12,scale=960:-1 -> docs/architecture/media/M1_pro_map_bank_statement.gif"
echo ""
echo "Artifacts:"
echo "  $HEALTH_JSON"
echo "  $PROFILE_JSON"
echo "  $ANALYZE_JSON"
echo "  $RESULT_JSON"
echo "M1 acceptance PASSED"
