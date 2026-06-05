# Batch Processing 端到端测试清单（Pro）

Last updated: 2026-06-05  
关联：[batch_kie.md](batch_kie.md)、[CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)、[batch-ui-roadmap.md](../../docs/architecture/batch-ui-roadmap.md)

---

## 0. 前置条件

| 项 | 要求 |
|----|------|
| 环境 | Tencent Cloud Studio GPU（或同等 GPU + Pro venv） |
| Shell | **PowerShell**（`pwsh`）；勿在 zsh 中粘贴下列命令 |
| 后端 | 单独终端运行 `python run.py`，端口 `8000` |
| 前端 | 静态页或 `frontend/index.html` 经 HTTP 打开（UI 用例） |
| 输出目录 | `test_data/TestResult/PhaseBatch/`（gitignored，脚本自动创建） |

### 0.1 激活环境与启动服务

```powershell
$REPO_ROOT = "D:\3_PROJECTS\DocuVision"   # Cloud: /workspace/DocuVision
cd $REPO_ROOT\backend

# Activate venv per CLOUD_VALIDATION.md (example name)
# .\docuvision_env\Scripts\Activate.ps1

python run.py
```

### 0.2 健康检查（所有用例第一步）

```powershell
$REPO_ROOT = "D:\3_PROJECTS\DocuVision"
$API_ROOT = "http://127.0.0.1:8000"

$health = Invoke-RestMethod -Uri "$API_ROOT/health"
$health | ConvertTo-Json -Depth 4
# Expect: HTTP 200, kie section present on GPU host
```

### 0.3 公共变量（后续节复用）

```powershell
$REPO_ROOT = "D:\3_PROJECTS\DocuVision"
$API_ROOT = "http://127.0.0.1:8000"
$BATCH_API = "$API_ROOT/api/v1/batch"
$OUT_DIR = Join-Path $REPO_ROOT "test_data\TestResult\PhaseBatch"
New-Item -ItemType Directory -Force -Path $OUT_DIR | Out-Null
```

### 0.4 发版前快速单测（本修复相关）

```powershell
cd $REPO_ROOT\backend
python -m pytest tests/test_kie_pages_parse.py -q

cd $REPO_ROOT\frontend
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

### 1.1 创建 Layout batch（PowerShell）

```powershell
$REPO_ROOT = "D:\3_PROJECTS\DocuVision"
$API_ROOT = "http://127.0.0.1:8000"
$file1 = Join-Path $REPO_ROOT "test_data\testfiles\GeneralFiles\filetable.jpg"
$file2 = Join-Path $REPO_ROOT "test_data\testfiles\GeneralFiles\table.jpg"
Test-Path $file1, $file2

$options = @{
    document_type   = "auto"
    enable_layout   = $true
    enable_ocr      = $false
    enable_table    = $true
    enable_kie      = $false
    kie_pages       = "1"
    layout_engine   = "ppstructure"
} | ConvertTo-Json -Compress

$boundary = [guid]::NewGuid().ToString()
$lines = New-Object System.Collections.Generic.List[string]

function Add-Field([string]$name, [string]$value) {
    $script:lines.Add("--$boundary")
    $script:lines.Add("Content-Disposition: form-data; name=`"$name`"")
    $script:lines.Add("")
    $script:lines.Add($value)
}

Add-Field "name" "E2E layout 2jpg"
Add-Field "options" $options

foreach ($path in @($file1, $file2)) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $fn = [System.IO.Path]::GetFileName($path)
    $script:lines.Add("--$boundary")
    $script:lines.Add("Content-Disposition: form-data; name=`"files`"; filename=`"$fn`"")
    $script:lines.Add("Content-Type: application/octet-stream")
    $script:lines.Add("")
    $lines.Add([System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($bytes))
}

$lines.Add("--$boundary--")
$lines.Add("")
$bodyRaw = ($lines -join "`r`n") + "`r`n"
$bodyBytes = [System.Text.Encoding]::GetEncoding("iso-8859-1").GetBytes($bodyRaw)

$create = Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch" -Method POST `
    -ContentType "multipart/form-data; boundary=$boundary" -Body $bodyBytes -UseBasicParsing
$batch = $create.Content | ConvertFrom-Json
$BATCH_ID = $batch.batch_id
Write-Host "batch_id:" $BATCH_ID "total_tasks:" $batch.total_tasks
```

### 1.2 启动与轮询

```powershell
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/start" -Method POST -UseBasicParsing | Out-Null

for ($i = 1; $i -le 120; $i++) {
    $summary = Invoke-RestMethod -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/summary"
    Write-Host "[$i] status=$($summary.status) counts=$($summary.status_counts | ConvertTo-Json -Compress)"
    if ($summary.status -in @("completed", "failed", "cancelled")) { break }
    Start-Sleep -Seconds 5
}
# BATCH-L-03: expect status=completed, completed=2
```

> **轮询陷阱**：长任务请用 **`GET /batch/{id}/summary`**，勿用 `GET /batch/{id}`（内嵌 `tasks[].result` 可能导致 JSON 解析失败）。

### 1.3 导出与断言

```powershell
$OUT_DIR = Join-Path $REPO_ROOT "test_data\TestResult\PhaseBatch"
$csvPath = Join-Path $OUT_DIR "batch_${BATCH_ID}_summary.csv"
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/export.csv?mode=summary" `
    -OutFile $csvPath -UseBasicParsing
Get-Content $csvPath -TotalCount 5

$jsonPath = Join-Path $OUT_DIR "batch_${BATCH_ID}.json"
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/export.json" `
    -OutFile $jsonPath -UseBasicParsing
(Get-Item $jsonPath).Length
```

---

## 2. API — KIE 批次（`kie_invoice_6`）

**目的**：验收 BATCH-001～004；需 GPU + KIE 模型已加载。

| ID | 步骤 | 通过标准 |
|----|------|----------|
| BATCH-K-01 | 一键脚本创建并启动 | 脚本退出码 0 |
| BATCH-K-02 | 6/6 `completed` | 见 [batch_kie.md](batch_kie.md) BATCH-001 |
| BATCH-K-03 | CSV `kie_production_hit=true` | BATCH-002 |
| BATCH-K-04 | CSV 表头字段齐全 | BATCH-003 |

### 2.1 一键验收脚本

```powershell
$REPO_ROOT = "D:\3_PROJECTS\DocuVision"
cd $REPO_ROOT
.\test_data\scripts\run_batch_kie_acceptance.ps1 -RepoRoot $REPO_ROOT -ApiRoot "http://127.0.0.1:8000" -SetName "kie_invoice_6"
```

清单文件：`test_data/testfiles/batch/manifest.json`（`sets[].name = kie_invoice_6`）。

### 2.2 手动核对 CSV

```powershell
$OUT_DIR = Join-Path $REPO_ROOT "test_data\TestResult\PhaseBatch"
$latest = Get-ChildItem $OUT_DIR -Filter "batch_*_kie.csv" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Import-Csv $latest.FullName | Select-Object file_name, status, kie_production_hit | Format-Table
```

### 2.3 失败任务导出（可选）

```powershell
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/export.csv?mode=failures" `
    -OutFile (Join-Path $OUT_DIR "batch_${BATCH_ID}_failures.csv") -UseBasicParsing
```

---

## 3. API — 控制流（暂停 / 恢复 / 重试 / 取消）

**目的**：验证 `batch_service` 状态机；建议用 3+ 文件、较慢的 layout 批次。

| ID | 操作 | 命令 | 通过标准 |
|----|------|------|----------|
| BATCH-C-01 | 暂停 | `POST .../pause` | `status=paused`，无新任务进入 `processing` |
| BATCH-C-02 | 恢复 | `POST .../resume` + `POST .../start` | 继续处理剩余 `pending` |
| BATCH-C-03 | 重试失败 | `POST .../retry` + `POST .../start` | 失败任务重置为 `pending` 后可完成 |
| BATCH-C-04 | 取消 | `POST .../cancel` | `status=cancelled` |

```powershell
# After batch is processing:
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/pause" -Method POST -UseBasicParsing
(Invoke-RestMethod -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/summary").status   # paused

Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/resume" -Method POST -UseBasicParsing
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/start" -Method POST -UseBasicParsing

# After terminal state with failures:
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/retry" -Method POST -UseBasicParsing
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/start" -Method POST -UseBasicParsing

# Cancel in-flight batch:
Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/cancel" -Method POST -UseBasicParsing
```

---

## 4. UI — Batch Processing 标签（手工）

**前提**：后端已启动；浏览器打开 Pro UI。

| ID | 步骤 | 通过标准 |
|----|------|----------|
| BATCH-U-01 | 切到 **Batch Processing** 标签 | 面板可见，按钮初始 disabled 合理 |
| BATCH-U-02 | 在 **Process** 标签打开 Analysis Options，选 **Layout** | 选项对话框可关闭 |
| BATCH-U-03 | Batch 标签：**Select files** → 选 2+ 文件 → **Create batch** | 通知成功；任务表出现行；`batch_id` 已绑定 |
| BATCH-U-04 | **Start** | 状态变为 `processing`；表格行状态更新 |
| BATCH-U-05 | 轮询至完成 | `Status: completed \| N/N done` |
| BATCH-U-06 | **Download CSV** / **Download JSON** | 浏览器下载成功，内容与 API 导出一致 |
| BATCH-U-07 | 含失败时 **Retry failed** | 失败行重新处理 |

**注意**：

- Batch 选项在 **Create batch** 时从 `getProcessingOptions()` 快照；创建后改 Analysis Options **不会**更新已建批次。
- KIE 批次创建前确认 `/health` 中 `kie.model_loaded=true`（或接受首次加载延迟）。

---

## 5. 回归 — 本次修复（Process 队列 + Layout 图片）

与 Batch 无关，但建议同一次云测会话执行。

### 5.1 队列：处理选中项后不自动跑其他 pending

| ID | 步骤 | 通过标准 |
|----|------|----------|
| FIX-Q-01 | Process 标签上传多页 PDF ×2 | 两项均为 `Waiting` |
| FIX-Q-02 | 选中文件 2，**Run Analysis** | 仅文件 2 进入 `Processing` |
| FIX-Q-03 | 等待文件 2 完成 | 文件 1 **仍为 Waiting**，不自动开始 |
| FIX-Q-04 | 文件 1 处理中时对文件 2 点 Run | 文件 2 变为 `Queued`；文件 1 完成后 **自动** 开始文件 2 |

### 5.2 Layout + 图片：kie_pages 残留不导致 400

| ID | 步骤 | 通过标准 |
|----|------|----------|
| FIX-K-01 | Analysis Options 中 KIE pages 填 `all` | — |
| FIX-K-02 | 模式选 **Layout**，上传 `filetable.jpg`，Run | **无** `kie_pages is only supported for PDF inputs` |
| FIX-K-03 | API 对照（可选） | 见下 |

```powershell
$file = Join-Path $REPO_ROOT "test_data\testfiles\GeneralFiles\filetable.jpg"
$form = @{
    file            = Get-Item $file
    enable_layout   = "1"
    enable_ocr      = "0"
    enable_table    = "1"
    enable_kie      = "0"
    document_type   = "auto"
    kie_pages       = "all"
}
# Expect HTTP 200 (not 400) when enable_kie=0
Invoke-WebRequest -Uri "$API_ROOT/api/v1/analyze" -Method POST -Form $form -UseBasicParsing |
    Select-Object StatusCode, @{n='task_id';e={ ($_.Content | ConvertFrom-Json).task_id }}
```

---

## 6. 结果落盘与追踪

| 产物 | 路径 |
|------|------|
| 脚本 CSV/JSON | `test_data/TestResult/PhaseBatch/batch_<id>_*.csv/json` |
| 手工 API 导出 | 同上 `$OUT_DIR` |
| 批次记录 | 摘要写入 [KIE_TEST_RUN_TRACKER.md](../../docs/architecture/KIE_TEST_RUN_TRACKER.md) 「阶段 Batch」表 |

### 6.1 记录模板（复制到 TRACKER）

```text
| 日期 | 用例集 | batch_id | completed/total | CSV kie hit | 备注 |
|------|--------|----------|-----------------|-------------|------|
| 2026-06-05 | layout 2jpg | <id> | 2/2 | N/A | BATCH-L pass |
| 2026-06-05 | kie_invoice_6 | <id> | 6/6 | 6/6 true | BATCH-K pass |
```

---

## 7. 发版最小集（推荐顺序）

1. **0.4** 单测（kie_pages + queue）
2. **1** Layout API 小批次（BATCH-L-01～05）
3. **2** KIE 脚本验收（BATCH-K-01～04）
4. **5** 队列与 Layout 图片回归（FIX-Q / FIX-K）
5. **4** UI 冒烟（时间允许）

全部通过即可认为 Batch v1.2 可交付；详细 GPU/KIE 契约仍以 [CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md) 阶段 A～H 为准。
