# main @ v1.3.0 — Cloud Studio 验收清单（路线图 P0）

Last updated: 2026-06-17  
Target tag: **`v1.3.0`**  
Shell: **zsh/bash**

关联：[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)、[MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md)、[RELEASE_1.3.0_NOTES.md](../../docs/release/RELEASE_1.3.0_NOTES.md)

---

## 通过标准（v1.3.0 合 main / 发 tag 最小集）

| 序号 | 阶段 | 通过判据 |
|------|------|----------|
| 0 | 环境 | Pro `:8000` + Lite `:8001` health **200**；`pip install -r requirements.txt` 含 **docuvision-core** |
| 1 | Phase A 扩展 | pytest **≥45 passed**（见 §1 文件列表） |
| 2 | v1.2.1 回归 | [MERGE_MAIN_v1.2.1](./MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md) §1–§4 **全过** |
| 3 | **CORE-PDF-001** | 数字 PDF 表格走 core 路径，`table_extraction_meta.service.path=docuvision_core` |
| 4 | **LITE-BATCH-001** | Lite batch 2 PDF → completed → `export.xlsx` HTTP 200 |
| 5 | **KIE-VAL-001** | 发票 KIE 结果含 `kie_validation`；失败字段可进 HITL 队列（可选） |
| 6 | **STITCH-001** | 两页同表头 PDF 抽表后 `stitched_from=2`（见 §6） |

---

## §0 公共变量

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export LITE_ROOT="http://127.0.0.1:8001"
export BATCH_API="$API_ROOT/api/v1/batch"
export LITE_BATCH="$LITE_ROOT/api/v1/lite/batch"
export SAMPLE_BORDERED="$REPO_ROOT/apps/lite/backend/tests/fixtures/sample_bordered.pdf"
export OUT_DIR="$REPO_ROOT/test_data/TestResult/PhaseV13"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"
git fetch origin && git checkout main && git pull origin main

# Pro deps (core table path)
cd backend && source ~/docuvision_env/bin/activate
pip install -e ../packages/docuvision-core[lite] pdfplumber pymupdf -q
```

**T1 Pro**：`DEBUG=false python run.py`（`:8000`）  
**T3 Lite**：`cd apps/lite/backend && source ~/docuvision_lite_env/bin/activate && python run_lite.py`（`:8001`）

---

## §1 Phase A 扩展（v1.3）

```bash
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py \
  tests/test_kie_field_validation.py tests/test_kie_schema_templates.py \
  tests/test_document_type_classifier.py tests/test_file_type_detector.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q

cd "$REPO_ROOT/packages/docuvision-core"
pytest tests/processing/test_table_stitch.py -q
```

**通过**：全部 `passed`（预期 **≥45** 项 Pro + 2 项 core）。

---

## §3 CORE-PDF-001 — Pro 数字 PDF core 路由

```bash
curl -s -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$SAMPLE_BORDERED" \
  -F "enable_layout=0" \
  -F "enable_table=1" \
  -F "enable_kie=0" | tee "$OUT_DIR/core_analyze.json"

TASK_ID=$(python3 -c "import json; print(json.load(open('$OUT_DIR/core_analyze.json'))['task_id'])")

# poll until completed
for i in $(seq 1 60); do
  ST=$(curl -s "$API_ROOT/api/v1/tasks/$TASK_ID" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))")
  echo "status=$ST"
  [ "$ST" = "completed" ] && break
  sleep 2
done

curl -s "$API_ROOT/api/v1/tasks/$TASK_ID/result" | python3 - <<'PY'
import json, sys
r = json.load(sys.stdin)
meta = r.get("table_extraction_meta") or {}
svc = (meta.get("service") or meta)
path = svc.get("path") or meta.get("path")
assert path == "docuvision_core", f"expected docuvision_core, got {path!r}"
tables = r.get("tables") or []
assert len(tables) >= 1, "expected at least one table"
print("CORE-PDF-001 pass", "tables=", len(tables))
PY
```

**通过**：`path=docuvision_core`；`tables` 非空。

---

## §4 LITE-BATCH-001

```bash
curl -s -X POST "$LITE_BATCH" \
  -F "name=v13 lite batch" \
  -F 'options={"table_only":true}' \
  -F "files=@$SAMPLE_BORDERED" \
  -F "files=@$SAMPLE_BORDERED" | tee "$OUT_DIR/lite_batch.json"

BID=$(python3 -c "import json; print(json.load(open('$OUT_DIR/lite_batch.json'))['batch_id'])")
curl -s -X POST "$LITE_BATCH/$BID/start" | python3 -m json.tool

curl -s -o "$OUT_DIR/lite_batch.xlsx" -w "HTTP %{http_code}\n" \
  "$LITE_BATCH/$BID/export.xlsx"
```

**通过**：batch `completed`（或 failed_tasks=0）；xlsx HTTP **200**。

---

## §5 KIE-VAL-001

```bash
export SAMPLE="$REPO_ROOT/test_data/testfiles/invoices/sample-invoice.png"
curl -s -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$SAMPLE" \
  -F "enable_kie=1" \
  -F "document_type=invoice" | tee "$OUT_DIR/kie_val.json"

TASK_ID=$(python3 -c "import json; print(json.load(open('$OUT_DIR/kie_val.json'))['task_id'])")
# poll + result
curl -s "$API_ROOT/api/v1/tasks/$TASK_ID/result" | python3 - <<'PY'
import json, sys
r = json.load(sys.stdin)
v = r.get("kie_validation")
assert isinstance(v, dict), "missing kie_validation"
assert "validation_passed" in v
print("KIE-VAL-001 pass", v.get("validation_passed"), v.get("validation_fields_failed"))
PY
```

**通过**：`kie_validation` 对象存在。

---

## §6 STITCH-001（单元 / 集成）

优先跑 core 单测：

```bash
cd "$REPO_ROOT/packages/docuvision-core"
pytest tests/processing/test_table_stitch.py -q
```

**通过**：`test_stitch_same_header_tables` passed。

---

## §7 模板 API（可选）

```bash
curl -s "$API_ROOT/api/v1/kie/templates" | python3 -m json.tool
curl -s "$API_ROOT/api/v1/kie/templates/bank_statement" | python3 -m json.tool | head -20
```

**通过**：列表含 `bank_statement`、`invoice_line_items`。

---

## 结果落盘

| 产物 | 路径 |
|------|------|
| CORE-PDF | `$OUT_DIR/core_analyze.json` |
| Lite batch | `$OUT_DIR/lite_batch.xlsx` |
| Tracker | `KIE_TEST_RUN_TRACKER.md` → Release 1.3 行 |
