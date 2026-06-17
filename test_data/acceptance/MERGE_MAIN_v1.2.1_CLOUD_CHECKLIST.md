# main @ v1.2.1 — Cloud Studio 验收清单（维护补丁）

Last updated: 2026-06-17  
Target tag: **`v1.2.1`**（含 PyMuPDF 修复请 **`git pull origin main`**，勿仅 checkout tag）  
Shell: **zsh/bash**（Cloud Studio）

关联：[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)、[MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md)、[RELEASE_1.2.1_NOTES.md](../../docs/release/RELEASE_1.2.1_NOTES.md)

---

## 通过标准（v1.2.1 最小集）

| 序号 | 阶段 | 通过判据 |
|------|------|----------|
| 0 | 环境与分支 | `git pull origin main`（或含 tag 的 main）；Pro health **HTTP 200** |
| 1 | Phase A 回归 | pytest **≥37/37**（v1.2 基线）+ `test_batch_export_service.py`（含 xlsx）**全绿** |
| 2 | Vitest | `npm run test:unit -- tests/unit/queue.test.js` **全绿** |
| 3 | H-Batch 回归 | `kie_invoice_6`：**6/6** `kie_production_hit`（与 v1.2.0 同标准） |
| 4 | **BATCH-XLSX-001** | 完成 batch 后 `export.xlsx` 下载成功，文件头 `PK`，含 **Summary** sheet |
| 5 | UI（可选） | Batch 页 **Download Excel** 触发浏览器下载；或 curl 等价 |
| 6 | Playwright E2E P0（可选） | §6 全绿；Pro UI 在 **`/frontend/`**，非根路径 `/` |

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
# 或: git checkout v1.2.1  （建议仍 pull main 以含 requirements 修复）

curl -s -o /dev/null -w "health HTTP %{http_code}\n" "$API_ROOT/health"
curl -s -o /dev/null -w "frontend HTTP %{http_code}\n" "$API_ROOT/frontend/index.html"
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

## §2 Vitest（队列逻辑）

```bash
cd "$REPO_ROOT/frontend"
npm install
npm run test:unit -- tests/unit/queue.test.js
```

**通过**：全绿。

---

## §3 H-Batch — `kie_invoice_6`

完整步骤见 [MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md §3](./MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md#3-h-batch--kie_invoice_6合-main-阻塞项)。

**推荐（方式 A）**：

```bash
cd "$REPO_ROOT"
pwsh ./test_data/scripts/run_batch_kie_acceptance.ps1 \
  -RepoRoot "$REPO_ROOT" -ApiRoot "$API_ROOT" -SetName "kie_invoice_6"
```

脚本 exit **0** 且 `kie_production_hit: 6/6` 后，**复制执行**脚本输出的 `export BATCH_ID=...`（仅 `echo` 不会写入 shell）。

**§4 前置**：同一会话须已 `export BATCH_ID=<uuid>`，**勿**使用字面量 `<BATCH_ID>`。脚本在 BATCH-002 失败时仍会写出 CSV/results；可复制 `export BATCH_ID=...` 继续 §4 xlsx 验收。

**H-Batch 失败排查**（`kie_production_hit 0/6` 且 batch 已 `completed`）：

```bash
# 1) KIE 模型是否就绪（GPU 环境）
curl -s "$API_ROOT/health" | python3 -c "import sys,json; k=json.load(sys.stdin).get('kie',{}); print(k)"

# 2) 查看 CSV 每行 kie_stage / kie_fields_count（脚本失败时也会打印）
head -3 "$OUT_DIR"/batch_*_kie.csv

# 3) 常见根因
# - kie_stage=skipped_doc_type → options 缺 document_type（本脚本已合并，不应再出现）
# - kie_stage=completed 但 hit=False → KIE 未抽出 invoice 关键字段；查 T1 日志、显存、首次冷启动
# - kie_stage=runtime_error / failed → 查 quality.kie_error_message
```

---

## §4 BATCH-XLSX-001

在 §3 H-Batch **completed** 且已 `export BATCH_ID` 后：

```bash
test -n "$BATCH_ID" && echo "BATCH_ID=$BATCH_ID" || { echo "export BATCH_ID first (see §3)"; exit 1; }

curl -s -o "$OUT_DIR/batch_test.xlsx" \
  -w "HTTP %{http_code}\n" \
  "$BATCH_API/$BATCH_ID/export.xlsx?mode=all"

file "$OUT_DIR/batch_test.xlsx"
python3 - "$OUT_DIR/batch_test.xlsx" <<'PY'
import zipfile, sys
p = sys.argv[1]
with zipfile.ZipFile(p) as z:
    names = z.namelist()
    assert any("Summary" in n or "xl/" in n for n in names), names
print("xlsx ok")
PY
```

**通过**：HTTP **200**（非 404/000）；`file` 显示 ZIP；python 打印 `xlsx ok`。

> **踩坑**：404 时 curl 仍会把 JSON 错误体写入 `.xlsx`；先确认 `$BATCH_ID` 与 T1 为同一 `run.py` 进程。

---

## §6 Playwright E2E P0（可选，CPU 即可）

Pro 静态 UI 挂载在 **`http://127.0.0.1:8000/frontend/`**；根路径 `/` 仅返回 API JSON。

```bash
cd "$REPO_ROOT/frontend"
npm install
# T1 Pro 已启动；可选显式覆盖：
export PW_BASE_URL="http://127.0.0.1:8000/frontend"
export PW_INDEX_URL="$PW_BASE_URL/index.html"
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
