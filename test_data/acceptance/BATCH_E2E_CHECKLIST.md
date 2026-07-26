# Batch Processing 端到端测试清单（Pro）

Last updated: 2026-06-05  
关联：[batch_kie.md](batch_kie.md)、[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)、[batch-ui-roadmap.md](../../docs/architecture/batch-ui-roadmap.md)、[MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md)（合 `main` 最小集）

> **Shell**：Tencent Cloud Studio 默认 **zsh/bash**（`➜` 提示符）。本文命令均为 bash/zsh；勿粘贴 PowerShell（`$VAR = ...`）。Windows 本地请对照 [006-cloud-testing.mdc](../../.cursor/rules/006-cloud-testing.mdc) 自行转换。

---

## 0. 前置条件

| 项 | 要求 |
|----|------|
| 环境 | Tencent Cloud Studio GPU（或同等 GPU + Pro venv） |
| Shell | **zsh/bash**（Cloud Studio 默认） |
| 后端 | 单独终端运行 `python run.py`，端口 `8000` |
| 前端 | 静态页或 `frontend/index.html` 经 HTTP 打开（UI 用例） |
| 输出目录 | `test_data/TestResult/PhaseBatch/`（gitignored） |

### 0.1 激活环境与启动服务（终端 1）

```bash
export REPO_ROOT="/workspace/DocuVision"
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate
python run.py
```

### 0.2 健康检查（终端 2，所有用例第一步）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"

curl -s -o /dev/null -w "HTTP %{http_code}\n" "$API_ROOT/health"
curl -s "$API_ROOT/health" | python3 -m json.tool | head -20
```

### 0.3 公共变量（后续节复用）

```bash
export REPO_ROOT="/workspace/DocuVision"
export API_ROOT="http://127.0.0.1:8000"
export BATCH_API="$API_ROOT/api/v1/batch"
export OUT_DIR="$REPO_ROOT/test_data/TestResult/PhaseBatch"
mkdir -p "$OUT_DIR"
```

### 0.4 发版前快速单测

```bash
# Backend (works in zsh as-is)
cd "$REPO_ROOT/backend"
source ~/docuvision_env/bin/activate
python -m pytest tests/test_kie_pages_parse.py -q

# Frontend — npm install once if vitest: not found
cd "$REPO_ROOT/frontend"
npm install
npm run test:unit -- tests/unit/queue.test.js
```

---

## 1. API — Layout 小批次（2 张图，无 KIE）

**目的**：验证 batch 全管道、`layout` 选项、导出与轮询；不依赖 Qwen。

| ID | 步骤 | 通过标准 |
|----|------|----------|
| BATCH-L-01 | 创建含 2 个 JPG 的 batch | `total_tasks=2`，`status=pending` |
| BATCH-L-02 | `POST .../start` | `status` 变为 `processing` |
| BATCH-L-03 | 轮询 `GET .../summary` | 终态 `completed`，`status_counts.completed=2` |
| BATCH-L-04 | `export.csv?mode=summary` | 表头含 `file_name`、`status`；两行均为 `completed` |
| BATCH-L-05 | `export.json` | JSON 合法，含 `tasks` 数组 |

### 1.1 创建 Layout batch

```bash
export FILE1="$REPO_ROOT/test_data/testfiles/GeneralFiles/filetable.jpg"
export FILE2="$REPO_ROOT/test_data/testfiles/GeneralFiles/table.jpg"
test -f "$FILE1" && test -f "$FILE2" && echo "files ok"

export BATCH_OPTS='{"document_type":"auto","enable_layout":true,"enable_table":true,"enable_kie":false,"kie_pages":"1","layout_engine":"ppstructure"}'

CREATE_RESP=$(curl -s -X POST "$BATCH_API" \
  -F "name=E2E layout 2jpg" \
  -F "options=$BATCH_OPTS" \
  -F "files=@$FILE1" \
  -F "files=@$FILE2")

echo "$CREATE_RESP" | python3 -m json.tool
export BATCH_ID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['batch_id'])")
echo "batch_id=$BATCH_ID"
```

### 1.2 启动与轮询

```bash
curl -s -X POST "$BATCH_API/$BATCH_ID/start" | python3 -m json.tool

for i in $(seq 1 120); do
  SUMMARY=$(curl -s "$BATCH_API/$BATCH_ID/summary")
  echo "[$i] $SUMMARY" | python3 -c "import sys,json; d=json.loads(sys.stdin.read().split(' ',1)[1]); print(d['status'], d.get('status_counts'))"
  STATUS=$(echo "$SUMMARY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  case "$STATUS" in completed|failed|cancelled) break ;; esac
  sleep 5
done
```

> **轮询陷阱**：长任务请用 **`GET /batch/{id}/summary`**，勿用 `GET /batch/{id}`（内嵌 `tasks[].result` 可能导致 JSON 解析失败）。

### 1.3 导出与断言

```bash
curl -s -o "$OUT_DIR/batch_${BATCH_ID}_summary.csv" \
  "$BATCH_API/$BATCH_ID/export.csv?mode=summary"
head -5 "$OUT_DIR/batch_${BATCH_ID}_summary.csv"

curl -s -o "$OUT_DIR/batch_${BATCH_ID}.json" \
  "$BATCH_API/$BATCH_ID/export.json"
wc -c "$OUT_DIR/batch_${BATCH_ID}.json"
```

---

## 2. API — KIE 批次（`kie_invoice_6`）

**目的**：验收 BATCH-001～004；需 GPU + KIE 模型已加载。

| ID | 步骤 | 通过标准 |
|----|------|----------|
| BATCH-K-01 | 创建并启动 batch | 脚本或手动 curl 成功 |
| BATCH-K-02 | 6/6 `completed` | 见 [batch_kie.md](batch_kie.md) BATCH-001 |
| BATCH-K-03 | CSV `kie_production_hit=true` | BATCH-002 |
| BATCH-K-04 | CSV 表头字段齐全 | BATCH-003 |

### 2.1 一键验收（PowerShell 脚本，需 `pwsh`）

```bash
cd "$REPO_ROOT"
pwsh ./test_data/scripts/run_batch_kie_acceptance.ps1 \
  -RepoRoot "$REPO_ROOT" -ApiRoot "$API_ROOT" -SetName "kie_invoice_6"
# Script prints: options: {...}  batch_id: ...  export BATCH_ID=...
# Exit 0 only when kie_production_hit count equals row count (BATCH-002).
```

脚本输出 `export BATCH_ID=...` 后，可在同一会话执行 §3 控制流（需**另建** processing 中批次；已 completed 批次不能 pause）。

若无 `pwsh`，用 §1 的 `curl -F` 模式上传 `kie_invoice_6` 文件，**options 必须含** `"document_type":"invoice"`（仅 `enable_kie=true` 不够）。

### 2.2 手动核对 CSV

```bash
ls -lt "$OUT_DIR"/batch_*_kie.csv | head -1
head -3 "$(ls -t "$OUT_DIR"/batch_*_kie.csv | head -1)"
# Expect: kie_production_hit=True (not skipped_doc_type) for invoice batch
```

### 2.2.1 已知踩坑（2026-06-06，已修）

| 现象 | 原因 |
|------|------|
| 6/6 completed 但 `kie_production_hit=False` | `options` 缺 `document_type` → 管道用 `auto` → `skipped_doc_type` |
| §3 curl 全 404 | 未 `export BATCH_ID` 或批次已结束 |

### 2.3 失败任务导出（可选）

```bash
curl -s -o "$OUT_DIR/batch_${BATCH_ID}_failures.csv" \
  "$BATCH_API/$BATCH_ID/export.csv?mode=failures"
```

---

## 3. API — 控制流（暂停 / 恢复 / 重试 / 取消）

| ID | 操作 | 通过标准 |
|----|------|----------|
| BATCH-C-01 | `POST .../pause` | `status=paused` |
| BATCH-C-02 | `resume` + `start` | 继续处理剩余 `pending` |
| BATCH-C-03 | `retry` + `start` | 失败任务可重跑 |
| BATCH-C-04 | `cancel` | `status=cancelled` |

```bash
curl -s -X POST "$BATCH_API/$BATCH_ID/pause" | python3 -m json.tool
curl -s "$BATCH_API/$BATCH_ID/summary" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])"

curl -s -X POST "$BATCH_API/$BATCH_ID/resume" | python3 -m json.tool
curl -s -X POST "$BATCH_API/$BATCH_ID/start" | python3 -m json.tool

curl -s -X POST "$BATCH_API/$BATCH_ID/retry" | python3 -m json.tool
curl -s -X POST "$BATCH_API/$BATCH_ID/start" | python3 -m json.tool

curl -s -X POST "$BATCH_API/$BATCH_ID/cancel" | python3 -m json.tool
```

---

## 4. UI — Batch Processing 标签（手工）

**前提**：后端已启动；浏览器打开 Pro UI。Windows 本地路径示例：`REPO_ROOT=D:/3_PROJECTS/DocuVision`。

| ID | 步骤 | 通过标准 |
|----|------|----------|
| BATCH-U-01 | 切到 **Batch Processing** 标签 | 面板可见 |
| BATCH-U-02 | 在 **Process** 标签打开 Analysis Options，选模式（如 **ID Cards**） | 选项对话框可关闭 |
| BATCH-U-03 | Batch：**Select files** → **Create batch** | 任务表出现行 |
| BATCH-U-04 | **Start** | 状态 `processing` |
| BATCH-U-05 | 等待完成 | `completed \| N/N done` |
| BATCH-U-06 | **Download CSV** / **Download JSON** | 浏览器**下载**文件（非新标签页预览 JSON） |
| BATCH-U-07 | 含失败时 **Retry failed** | 失败行重新处理 |

### 4.1 Options 何时生效？

| 问题 | 答案 |
|------|------|
| Batch 标签有没有独立 Options？ | **没有**。读取 Process 标签 **Analysis Options** 对话框中的当前值。 |
| 何时快照？ | 点击 **Create batch** 时，`getProcessingOptions()` 序列化进 `options` 字段。 |
| 是否所有文件同一设定？ | **是**。批次内每个文件共用创建时那份 `options`。 |
| 创建后改 Options？ | **不影响**已建批次；需 **新建 batch**。 |
| ID Cards 模式 | `document_type=id_card`，`enable_kie=true`（自动开启） |

**推荐顺序**：Process 标签设好 Options → 切 Batch 标签 → 选文件 → Create batch → Start。

---

## 5. 回归 — Process 队列 + Layout 图片

### 5.1 队列：处理选中项后不自动跑其他 pending

| ID | 步骤 | 通过标准 |
|----|------|----------|
| FIX-Q-01 | 上传多页 PDF ×2 | 两项 `Waiting` |
| FIX-Q-02 | 选中文件 2，Run | 仅文件 2 `Processing` |
| FIX-Q-03 | 文件 2 完成 | 文件 1 仍 `Waiting` |
| FIX-Q-04 | 文件 1 处理中对文件 2 Run | 文件 2 `Queued`；文件 1 完成后自动跑文件 2 |

### 5.2 Layout + 图片：kie_pages 不导致 400

```bash
curl -s -o /tmp/analyze_layout_jpg.json -w "HTTP %{http_code}\n" \
  -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$REPO_ROOT/test_data/testfiles/GeneralFiles/filetable.jpg" \
  -F "enable_layout=1" -F "enable_table=1" \
  -F "enable_kie=0" -F "document_type=auto" -F "kie_pages=all"
# Expect HTTP 200
```

---

## 6. 结果落盘与追踪

| 产物 | 路径 |
|------|------|
| API 导出 | `$OUT_DIR/batch_<id>_*.csv/json` |
| UI 下载 | 浏览器默认下载目录，`batch_<id>_kie.csv` / `batch_<id>.json` |
| 批次记录 | [KIE_TEST_RUN_TRACKER.md](../../docs/architecture/KIE_TEST_RUN_TRACKER.md) |

---

## 7. 发版最小集（推荐顺序）

1. **0.4** 单测（kie_pages + queue，`npm install` 后跑 Vitest）
2. **1** Layout API 小批次
3. **2** KIE 批次
4. **5** 队列与 Layout 回归
5. **4** UI 冒烟（含 CSV/JSON 下载）
