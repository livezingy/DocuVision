# main @ v1.2.1 — Cloud Studio 验收清单（维护补丁）

Last updated: 2026-06-17  
Target tag: **`v1.2.1`**  
Shell: **zsh/bash**（Cloud Studio）

关联：[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)、[MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md)、[RELEASE_1.2.1_NOTES.md](../../docs/release/RELEASE_1.2.1_NOTES.md)

---

## 通过标准（v1.2.1 最小集）

| 序号 | 阶段 | 通过判据 |
|------|------|----------|
| 0 | 环境与分支 | `git checkout v1.2.1`（或含该 tag 的 `main`）；Pro health **HTTP 200** |
| 1 | Phase A 回归 | pytest **≥37/37**（v1.2 基线）+ `test_batch_export_service.py`（含 xlsx）**全绿** |
| 2 | Vitest | `npm run test:unit -- tests/unit/queue.test.js` **全绿** |
| 3 | H-Batch 回归 | `kie_invoice_6`：**6/6** `kie_production_hit`（与 v1.2.0 同标准） |
| 4 | **BATCH-XLSX-001** | 完成 batch 后 `export.xlsx` 下载成功，文件头 `PK`，含 **Summary** sheet |
| 5 | UI（可选） | Batch 页 **Download Excel** 触发浏览器下载；或 curl 等价 |

全部通过后：更新 Tracker → tag `v1.2.1`（若与 v1.3.0 同 commit，两 tag 共用本清单 §1–§4）。

---

## §0 公共变量

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export BATCH_API="$API_ROOT/api/v1/batch"
export OUT_DIR="$REPO_ROOT/test_data/TestResult/PhaseBatch"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"
git fetch origin
git checkout main && git pull origin main
# 或: git checkout v1.2.1

curl -s -o /dev/null -w "health HTTP %{http_code}\n" "$API_ROOT/health"
```

**T1**：`cd backend && source ~/docuvision_env/bin/activate && DEBUG=false python run.py`

---

## §1 Phase A + Batch export 单测

```bash
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q
```

**通过**：无 failed；`test_build_batch_xlsx_bytes` passed。

---

## §4 BATCH-XLSX-001

在 H-Batch 或任意已完成 KIE batch 上：

```bash
curl -s -o "$OUT_DIR/batch_test.xlsx" \
  -w "HTTP %{http_code}\n" \
  "$BATCH_API/<BATCH_ID>/export.xlsx?mode=all"

file "$OUT_DIR/batch_test.xlsx"
python3 - <<'PY'
import zipfile, sys
p = sys.argv[1]
with zipfile.ZipFile(p) as z:
    names = z.namelist()
    assert any("Summary" in n or "xl/" in n for n in names), names
print("xlsx ok")
PY "$OUT_DIR/batch_test.xlsx"
```

**通过**：HTTP 200；xlsx 为合法 ZIP；含 Summary 或 KIE sheet。

---

## §5 Playwright E2E P0（可选，CPU 即可）

```bash
cd "$REPO_ROOT/frontend"
npm install
# T1 Pro 已启动并挂载 frontend
npm run test:e2e
```

**通过**：`process-smoke.e2e.js` + `process-queue.e2e.js` 全绿；报告在 `test_data/TestResult/PhaseUI/`。

---

## 结果落盘

| 产物 | 路径 |
|------|------|
| xlsx 样例 | `$OUT_DIR/batch_*.xlsx` |
| Playwright | `$REPO_ROOT/test_data/TestResult/PhaseUI/` |
| Tracker | `docs/architecture/KIE_TEST_RUN_TRACKER.md` 追加 v1.2.1 行 |
