# feature/batch-ui → main 合入前 Cloud Studio 验收清单

Last updated: 2026-06-12  
Branch: `feature/batch-ui` · Target: `v1.2.0`  
Shell: **zsh/bash only**（Cloud Studio 默认 `➜` 提示符）

关联：[BATCH_E2E_CHECKLIST.md](BATCH_E2E_CHECKLIST.md)、[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)、[KIE_TEST_RUN_TRACKER.md](../../docs/architecture/KIE_TEST_RUN_TRACKER.md)

---

## 通过标准（合 main 最小集）

| 序号 | 阶段 | 通过判据 |
|------|------|----------|
| 0 | 环境与分支 | health HTTP 200；`git` 在 `feature/batch-ui` 且已 `pull` |
| 1 | Phase A + Vitest | pytest **37/37**；`queue.test.js` 全绿 |
| 2 | MP-002 | `kie_production_hit=true`，`kie_pages_processed` 长度 ≥ 2 |
| 3 | H-Batch | `kie_invoice_6`：**6/6 completed**，CSV `kie_production_hit` **6/6** |
| 4 | Layout batch | 2 JPG：**2/2 completed**，`export.csv?mode=summary` 合法 |
| 5 | 控制流 | pause → resume+start；可选 retry/cancel |
| 6 | Layout 回归 | JPG + `kie_pages=all` + `enable_kie=0` → **HTTP 200** |
| 7 | UI 冒烟 | 手工 BATCH-U-01～07（见 §7） |

全部通过后：更新 Tracker「Release 1.2」→ 开 PR → 合并 → tag `v1.2.0`。

### 验收记录（2026-06-12 Cloud Studio）

| 阶段 | 状态 | 证据 |
|------|:----:|------|
| §0 | pass | health HTTP 200 |
| §1 pytest | **待复测** | 36/37（`test_document_page_count`）；见 `fix: pdf_page_count` commit |
| §1 Vitest | pass | 11/11 |
| §2 MP-002 | pass | `TASK_ID=3826fbf2-4edd-4353-98e5-1c586aaf6d59` |
| §3 H-Batch | pass | `BATCH_ID=2a74ad5c-e263-4b03-b4d5-989fc0b6968f`，6/6 hit |
| §4 Layout | pass | `LAYOUT_BATCH_ID=1f70fb58-7d26-45df-a47a-35548060e1d4` |
| §5 控制流 | **待复测** | 勿复用 §4 已完成批次；见 §5 独立脚本 |
| §6 | pass | HTTP 200 |
| §7 UI | pass | BATCH-U + FIX-Q，与预期相符 |

### 合 PR 前复测（本 commit 之后）

1. **Phase A**：`git pull` 后 `pytest` 全绿 **37/37**（`pdf_page_count` 打开失败返回 `0`，`view.pages` 回退可测）。
2. **§5 控制流**：新建 layout 批次 → `start` 后**立刻** `pause` → `resume`+`start` → `completed`。

---

## 终端分工

| 终端 | 用途 |
|------|------|
| **T1** | `python run.py`（全程保持，勿 restart） |
| **T2** | 本清单所有 curl / pytest 命令 |

**T1 启动前**（推荐，避免 reload 丢 task/batch）：

```bash
export REPO_ROOT="/workspace/DocuVision"
cd "$REPO_ROOT/backend"
grep -q '^DEBUG=' .env 2>/dev/null && sed -i 's/^DEBUG=.*/DEBUG=false/' .env || echo 'DEBUG=false' >> .env
source ~/docuvision_env/bin/activate
python run.py
```

---

## §0 公共变量（T2，每节可重复 source）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export BATCH_API="$API_ROOT/api/v1/batch"
export OUT_DIR="$REPO_ROOT/test_data/TestResult/PhaseBatch"
mkdir -p "$OUT_DIR"

cd "$REPO_ROOT"
git fetch origin
git checkout feature/batch-ui
git pull origin feature/batch-ui
git log -1 --oneline

curl -s -o /dev/null -w "health HTTP %{http_code}\n" "$API_ROOT/health"
curl -s "$API_ROOT/health" | python3 -m json.tool | head -15
```

期望：`health HTTP 200`；`/health` 中 `api_version` 为 **`1.2.0`**（若仍为 `1.1.0`：先 `git pull`，再**重启 T1** `python run.py`）。

---

## §1 Phase A 契约单测 + 前端 Vitest

```bash
export REPO_ROOT="/workspace/DocuVision"
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate

pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py tests/test_document_page_count.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q --tb=short
```

期望：**33 passed**（或当前仓库 Phase A 总数全绿）。

```bash
cd "$REPO_ROOT/frontend"
npm install
npm run test:unit -- tests/unit/queue.test.js
```

期望：Vitest 全绿。

---

## §2 MP-002 — 多页 PDF KIE（`kie_pages=all`）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export SAMPLE="$REPO_ROOT/test_data/testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf"
test -f "$SAMPLE" && echo "sample ok"

CREATE=$(curl -s -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$SAMPLE" \
  -F "enable_layout=0" -F "enable_table=0" -F "enable_ocr=0" \
  -F "enable_kie=1" -F "document_type=invoice" -F "kie_pages=all")

echo "$CREATE" | python3 -m json.tool
export TASK_ID=$(echo "$CREATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
echo "TASK_ID=$TASK_ID"
```

轮询（**同一 T1 进程**；`strict=False` 防 KIE raw_output 控制字符）：

```bash
for i in $(seq 1 120); do
  BODY=$(curl -s "$API_ROOT/api/v1/tasks/$TASK_ID")
  STATUS=$(echo "$BODY" | python3 -c "import sys,json; print(json.loads(sys.stdin.read(), strict=False).get('status',''))")
  echo "[$i] status=$STATUS"
  case "$STATUS" in completed|succeeded) break ;; failed|cancelled) echo "FAIL"; break ;; esac
  sleep 3
done
```

验收：

```bash
curl -s "$API_ROOT/api/v1/tasks/$TASK_ID/result" -o "$OUT_DIR/mp002_result.json"
python3 - <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
q = d.get("quality", {})
checks = [
    ("kie_stage", q.get("kie_stage") == "completed"),
    ("kie_production_hit", q.get("kie_production_hit") is True),
    ("kie_pages_processed>=2", len(q.get("kie_pages_processed") or []) >= 2),
    ("kie_multipage_merge", q.get("kie_multipage_merge") is True),
    ("kie_fields_by_page", set((d.get("kie_fields_by_page") or {}).keys()) >= {"1", "2"}),
]
for name, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'}: {name}")
sys.exit(0 if all(x[1] for x in checks) else 1)
PY "$OUT_DIR/mp002_result.json"
```

---

## §3 H-Batch — `kie_invoice_6`（**合 main 阻塞项**）

### 方式 A — `pwsh` 脚本（推荐）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
cd "$REPO_ROOT"

pwsh ./test_data/scripts/run_batch_kie_acceptance.ps1 \
  -RepoRoot "$REPO_ROOT" -ApiRoot "$API_ROOT" -SetName "kie_invoice_6"
```

期望：脚本 exit **0**；输出 `kie_production_hit: 6/6`。

> **方式 A 通过后无需再轮询**。脚本已建批、轮询、导出 CSV 并断言 BATCH-002。  
> 若仍想手动查 summary，须**复制执行**脚本输出的那一行（仅 `echo` 不会写入 shell 变量）：
> `export BATCH_ID=2a74ad5c-...`  
> 未 export 时 `$BATCH_API/$BATCH_ID/summary` 请求无效 → `KeyError: 'status'`。

### 方式 B — 纯 curl（无 `pwsh` 时）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export BATCH_API="$API_ROOT/api/v1/batch"
export TF="$REPO_ROOT/test_data/testfiles"

export BATCH_OPTS='{"document_type":"invoice","enable_layout":true,"enable_table":false,"enable_kie":true,"kie_pages":"1"}'

CREATE_RESP=$(curl -s -X POST "$BATCH_API" \
  -F "name=Cloud kie_invoice_6" \
  -F "options=$BATCH_OPTS" \
  -F "files=@$TF/invoices/sample-invoice.png" \
  -F "files=@$TF/invoices/receipt-invoice-like.png" \
  -F "files=@$TF/invoices/invoice_sample_01.pdf" \
  -F "files=@$TF/invoices/multipage/invoice_multipage_2p_header_detail.pdf" \
  -F "files=@$TF/invoices/multipage/invoice_multipage_3p_items.pdf" \
  -F "files=@$TF/invoices/sample-invoice.png")

echo "$CREATE_RESP" | python3 -m json.tool
export BATCH_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['batch_id'])")
echo "export BATCH_ID=$BATCH_ID"

curl -s -X POST "$BATCH_API/$BATCH_ID/start" | python3 -m json.tool
```

轮询（用 **`/summary`**，勿用 `GET /batch/{id}` 全量 JSON）：

```bash
for i in $(seq 1 360); do
  SUMMARY=$(curl -s "$BATCH_API/$BATCH_ID/summary")
  echo "[$i] $(echo "$SUMMARY" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], d.get('status_counts'))")"
  STATUS=$(echo "$SUMMARY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  case "$STATUS" in completed|failed|cancelled) break ;; esac
  sleep 5
done
```

导出与 BATCH-002 断言：

```bash
curl -s -o "$OUT_DIR/batch_${BATCH_ID}_kie.csv" \
  "$BATCH_API/$BATCH_ID/export.csv?mode=kie"
head -3 "$OUT_DIR/batch_${BATCH_ID}_kie.csv"

python3 - <<'PY'
import csv, sys
path = sys.argv[1]
with open(path, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
hits = sum(1 for r in rows if str(r.get("kie_production_hit", "")).lower() == "true")
print(f"kie_production_hit: {hits}/{len(rows)}")
if hits != len(rows) or len(rows) != 6:
    sys.exit(1)
PY "$OUT_DIR/batch_${BATCH_ID}_kie.csv" && echo "H-Batch PASS"
```

> **踩坑**：`options` 必须含 `"document_type":"invoice"`，否则 6/6 `skipped_doc_type`。

---

## §4 Layout 小批次（2 JPG，无 KIE）

```bash
export REPO_ROOT="/workspace/DocuVision"
export BATCH_API="$API_ROOT/api/v1/batch"
export FILE1="$REPO_ROOT/test_data/testfiles/GeneralFiles/filetable.jpg"
export FILE2="$REPO_ROOT/test_data/testfiles/GeneralFiles/table.jpg"
test -f "$FILE1" && test -f "$FILE2" && echo "files ok"

export BATCH_OPTS='{"document_type":"auto","enable_layout":true,"enable_ocr":false,"enable_table":true,"enable_kie":false,"kie_pages":"1","layout_engine":"ppstructure"}'

CREATE_RESP=$(curl -s -X POST "$BATCH_API" \
  -F "name=E2E layout 2jpg" \
  -F "options=$BATCH_OPTS" \
  -F "files=@$FILE1" \
  -F "files=@$FILE2")

export LAYOUT_BATCH_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['batch_id'])")
echo "LAYOUT_BATCH_ID=$LAYOUT_BATCH_ID"

curl -s -X POST "$BATCH_API/$LAYOUT_BATCH_ID/start" | python3 -m json.tool

for i in $(seq 1 120); do
  SUMMARY=$(curl -s "$BATCH_API/$LAYOUT_BATCH_ID/summary")
  STATUS=$(echo "$SUMMARY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "[$i] $STATUS"
  case "$STATUS" in completed|failed|cancelled) break ;; esac
  sleep 5
done

curl -s -o "$OUT_DIR/batch_${LAYOUT_BATCH_ID}_summary.csv" \
  "$BATCH_API/$LAYOUT_BATCH_ID/export.csv?mode=summary"
head -5 "$OUT_DIR/batch_${LAYOUT_BATCH_ID}_summary.csv"

curl -s -o "$OUT_DIR/batch_${LAYOUT_BATCH_ID}.json" \
  "$BATCH_API/$LAYOUT_BATCH_ID/export.json"
python3 -m json.tool "$OUT_DIR/batch_${LAYOUT_BATCH_ID}.json" | head -20
```

期望：`completed`；`export.json` 中 `tasks` 长度 2；`summary.csv` 含 `status,completed`。

> 若 `head` 显示 `metric,value` 表头：说明 `mode=summary` 被误写成无 mode 或路径错误；应使用 `export.csv?mode=summary`。

---

## §5 Batch 控制流（pause / resume / cancel）

**勿复用 §4 已 completed 的批次**（2 JPG 常在 5–15s 内跑完）。须**新建**批次，且 **start 后立刻 pause**（同一脚本块，中间不要 `sleep` 轮询）。

```bash
export REPO_ROOT="/workspace/DocuVision"
export BATCH_API="$API_ROOT/api/v1/batch"
export FILE1="$REPO_ROOT/test_data/testfiles/GeneralFiles/filetable.jpg"
export FILE2="$REPO_ROOT/test_data/testfiles/GeneralFiles/table.jpg"
export BATCH_OPTS='{"document_type":"auto","enable_layout":true,"enable_ocr":false,"enable_table":true,"enable_kie":false,"kie_pages":"1","layout_engine":"ppstructure"}'

CREATE_RESP=$(curl -s -X POST "$BATCH_API" \
  -F "name=E2E ctrl pause" \
  -F "options=$BATCH_OPTS" \
  -F "files=@$FILE1" \
  -F "files=@$FILE2")
export CTRL_BATCH_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['batch_id'])")
echo "CTRL_BATCH_ID=$CTRL_BATCH_ID"

curl -s -X POST "$BATCH_API/$CTRL_BATCH_ID/start" | python3 -m json.tool
curl -s -X POST "$BATCH_API/$CTRL_BATCH_ID/pause" | python3 -m json.tool
curl -s "$BATCH_API/$CTRL_BATCH_ID/summary" | python3 -c "import sys,json; print('status', json.load(sys.stdin)['status'])"

curl -s -X POST "$BATCH_API/$CTRL_BATCH_ID/resume" | python3 -m json.tool
curl -s -X POST "$BATCH_API/$CTRL_BATCH_ID/start" | python3 -m json.tool

for i in $(seq 1 60); do
  STATUS=$(curl -s "$BATCH_API/$CTRL_BATCH_ID/summary" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "[$i] $STATUS"
  case "$STATUS" in completed|failed|cancelled) break ;; esac
  sleep 3
done
```

期望：`pause` 返回非 `Cannot pause`，summary 为 **`paused`**；`resume`+`start` 后终态 **`completed`**。

**cancel（可选，另建第三批）**：

```bash
# 新建 batch → start → 立刻 cancel
curl -s -X POST "$BATCH_API/$NEW_BATCH_ID/cancel" | python3 -m json.tool
```

若仍 `Cannot pause`：改用更多/更大文件（如 4× JPG），或 `kie_invoice_6` 在 **processing ~16%** 时手动 `pause`。

---

## §6 Layout 单文件回归（`kie_pages=all` 不 400）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"

curl -s -o /tmp/analyze_layout_jpg.json -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$REPO_ROOT/test_data/testfiles/GeneralFiles/filetable.jpg" \
  -F "enable_layout=1" -F "enable_ocr=0" -F "enable_table=1" \
  -F "enable_kie=0" -F "document_type=auto" -F "kie_pages=all"
```

期望：**HTTP 200**。

---

## §7 UI 冒烟（手工，浏览器）

**前提**：T1 后端已启动；浏览器打开 Pro UI（Cloud 上经 HTTP 提供 `frontend/`，或本地等价路径）。

| ID | 操作 | 通过标准 |
|----|------|----------|
| BATCH-U-01 | 切到 **Batch Processing** | 面板可见 |
| BATCH-U-02 | **Process** 标签 → Analysis Options → 选 **ID Cards**（或 Invoice） | 对话框可关 |
| BATCH-U-03 | Batch：**Select files**（2～3 个小图）→ **Create batch** | 任务表有行 |
| BATCH-U-04 | **Start** | 状态 `processing` |
| BATCH-U-05 | 等待完成 | `completed \| N/N done` |
| BATCH-U-06 | **Download CSV** / **Download JSON** | 浏览器**下载**文件（非新标签 JSON 预览） |
| BATCH-U-07 | 若有失败 → **Retry failed** | 失败行重跑 |

**2026-06-12**：上述项 + FIX-Q 队列回归均已手工验收通过。

**Options 快照**：仅在 **Create batch** 时读取 Process 标签的 Analysis Options；创建后改 Options **不影响**当前批次。

**队列回归 FIX-Q**（Process 标签）：

1. 上传 2 个多页 PDF → 两项 `Waiting`
2. 选中文件 2 → **Run Analysis** → 仅文件 2 `Processing`
3. 文件 2 完成后 → 文件 1 仍 `Waiting`（不自动跑）
4. 文件 1 处理中对文件 2 再 Run → 文件 2 `Queued`；文件 1 完成后自动跑文件 2

---

## §8 结果落盘与 Tracker 更新

| 产物 | 路径 |
|------|------|
| API 导出 | `$OUT_DIR/batch_*.{csv,json}`、`mp002_result.json` |
| Tracker | `docs/architecture/KIE_TEST_RUN_TRACKER.md` → 「Release 1.2」补一行复测日期与 batch_id / task_id |
| PR | `feature/batch-ui` → `main`（`backend/**` 变更会触发 KIE Phase A CI） |

**合 main 后**：`CHANGELOG [Unreleased]` → `[1.2.0]`，打 tag，GitHub Release。

---

## 快速顺序（复制执行）

```text
T1: DEBUG=false → python run.py
T2: §0 → §1 → §2 → §3 → §4 → §5 → §6 → §7（手工）
```

预计 GPU 时间：§2 ~1–3 min，§3 ~2 min，§4 ~1 min；其余 <5 min。
