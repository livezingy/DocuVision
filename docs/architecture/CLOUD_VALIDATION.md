# Cloud Studio GPU 验证顺序与验收标准

> 本地无 Paddle 完整环境时，以 **腾讯 Cloud Studio GPU** 或 **百度 AI Studio V100** 为端到端真环境。勿提交密钥；使用 `backend/.env.cloud` 复制为 `.env`。
>
> **文档定位**：发版前、修改 KIE/编排/模型配置后的**回归手册**；与 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)（批次记录）配套，**测试完成后仍保留**。

## 1. 环境准备（一次性）

Pro GPU 与 Lite CPU **必须使用独立虚拟环境**（`docuvision_env` / `docuvision_lite_env`）。

```bash
cd backend
git pull origin main   # 或当前 feature 分支

# 推荐：一键安装（见 backend/requirements.txt 头注释）
python3 -m venv ~/docuvision_env
source ~/docuvision_env/bin/activate
./install_pro_gpu.sh

# 或手动：requirements.txt → requirements-gpu-torch.txt → Paddle cu129 → requirements-gpu-nvidia.txt
cp -n .env.cloud .env   # 按需改模型路径，勿提交 .env
```

**勿**在 Pro 环境中安装 Lite 依赖。`install_pro_gpu.sh` 会在 venv 激活时自动设置 `LD_LIBRARY_PATH`；`python run.py` 与 pytest 也会自动设置，**通常无需**每次手动 `source env_pro_gpu.sh`。

建议环境变量：

| 变量 | 建议 |
|------|------|
| `DOCUVISION_KIE_WARMUP=1` | 启动后后台预加载 Qwen，减少首单冷启动 |
| `DEBUG_MODE` | 排障时可 `true`，自动写 `backend/debug/{job_id}/` |

显存：**先跑完 PP-StructureV3（layout/table），再跑 KIE**；同一 Job 内编排器已串行。避免并行多 Job 同时加载双模型。

### 1.1 百度 AI Studio（BML CodeLab + V100，已验证）

与腾讯 Cloud Studio 不同：Notebook 通过 **`api_serving/{port}`** 暴露服务，**根路径 `GET /health` 往往无法从浏览器访问**（空白页），但 **`/api/v1/*` 可正常转发**。Pro SPA 与后端 health 检查已对齐为 **`GET /api/v1/health`**（`GET /health` 仍保留，供本机 `:8000` 与 Cloud Studio 直连）。

**环境要求**

| 项 | 说明 |
|----|------|
| GPU | 启动环境时选 **NVIDIA V100**（勿用 Iluvatar/DCU）；与 Pro `install_pro_gpu.sh` 栈一致 |
| Python | 独立 venv `~/docuvision_env`，**勿**把依赖 pip 进 AI Studio `external-libraries` |
| pip | 平台默认 `install.user=true`；安装前设 `PIP_CONFIG_FILE`（见下） |
| `.env` | `cp -n .env.cloud .env`；`DEBUG=false`；`DOCUVISION_KIE_WARMUP=1` 可选（已纳入 Settings） |

**一次性安装（终端）**

```bash
python3 -m venv ~/docuvision_env
source ~/docuvision_env/bin/activate

cat > /tmp/pip-docuvision.conf << 'EOF'
[global]
index-url = http://mirrors.baidubce.com/pypi/simple/

[install]
trusted-host = mirrors.baidubce.com
user = false
EOF
export PIP_CONFIG_FILE=/tmp/pip-docuvision.conf

cd ~/DocuVision/backend
unset LD_LIBRARY_PATH
./install_pro_gpu.sh
cp -n .env.cloud .env
# 建议 .env: DEBUG=false
```

首次启动若 PP-Structure 模型下载超过 worker 120s，日志会出现 `Available layout engines: []`；**预下载或重启** `python run.py` 后再试（见 `layout_service` worker 初始化）。

**启动后端**

```bash
source ~/docuvision_env/bin/activate
cd ~/DocuVision/backend
DEBUG_MODE=false python run.py
```

本机自检（必须通过再开 UI）：

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool | grep -A3 '"layout"'
curl -s http://127.0.0.1:8000/api/v1/health | python3 -m json.tool | head -3
# 期望 layout.ready=true, engines 含 ppstructure
```

**浏览器访问 Pro UI（已验证）**

1. 在 CodeLab 启动 `run.py`（监听 `0.0.0.0:8000`）。
2. 打开（将 `{project_base}` 换为当前项目 URL 中 `/home` 前的部分，端口与 `run.py` 一致）：

   ```text
   {project_base}/api_serving/8000/frontend/index.html
   ```

   示例形态：`https://aistudio.baidu.com/.../user/{uid}/{pid}/api_serving/8000/frontend/index.html`

3. 确认 health 走 API 前缀（应返回 JSON，而非空白页）：

   ```text
   {project_base}/api_serving/8000/api/v1/health
   ```

4. 前端会自动把 API 指到同前缀下的 `/api/v1`（见 `frontend/app.js` 中 `/frontend` 路径推断）。

**已知限制（AI Studio）**

| 限制 | 影响 |
|------|------|
| `api_serving` 不转发 `GET /health` | 已用 `/api/v1/health` 规避 |
| WebSocket `.../tasks/{id}/ws` 常 404 | 进度依赖 HTTP 轮询 `GET /api/v1/tasks/{id}`，功能仍可用 |
| 无定时开关机 | 关页约 10 分钟 idle 自动中止；算力需手动启动环境 |
| UI 演示首选 | 腾讯 Cloud Studio 端口预览仍最省事；AI Studio 适合 **延长 GPU 试用 + 本机 curl/pytest** |

**无 UI 验收（终端，与 UI 等价）**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/v1/analyze" \
  -F "file=@$HOME/DocuVision/test_data/testfiles/invoices/sample-invoice.png" \
  -F "document_type=invoice" -F "enable_layout=1" -F "enable_table=1" \
  -F "enable_kie=1" -F "enable_ocr=0" -F "kie_pages=1"
# 轮询 GET /api/v1/tasks/{task_id}
```

## 2. 验证顺序（按阶段执行）

**v1.3.1 发版最小集**（2026-06-23）：先跑 [MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md)（回归 + BATCH-XLSX-001），再跑 [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md)（CORE-PDF-001、**LITE-PREVIEW-001**、KIE-VAL-001；**不含** LITE-BATCH-001）。

| 版本 | 发版门禁 |
|------|----------|
| v1.2.1 | Phase A ≥37 + BATCH-XLSX-001 + H-Batch 6/6 回归 |
| v1.3.0 | v1.2.1 回归 + Phase A 扩展 ≥45 + CORE-PDF-001 + LITE-BATCH-001 + KIE-VAL-001（历史 tag） |
| v1.3.1 | v1.2.1 回归 + Phase A ≥45 + CORE-PDF-001 + **LITE-PREVIEW-001** + KIE-VAL-001 + Pro/Lite E2E；Lite batch **已移除** |

**v1.2 发版最小集**（2026-06-05 Cloud 已跑通）：**阶段 A（33 项）** → **B** → **MP**（2p `kie_pages=all`）→ **H-Batch**（`kie_invoice_6`）。阶段 C/D/E/F 继承 v1.1 基线，发版前可选复跑。

| 阶段 | v1.2 状态 |
|------|-----------|
| A（契约） | 33/33 pass |
| MP（多页 KIE） | 1/1 pass |
| H-Batch | 6/6 pass |

### 阶段 A — 契约单测（不加载 Qwen 权重）

**v1.1 基线**（4 文件）：

```bash
cd backend
pytest tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q
```

**v1.3 扩展**（含 validation + schema + batch xlsx，Cloud 发 tag 前跑）：

```bash
cd backend
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py \
  tests/test_kie_field_validation.py tests/test_kie_schema_templates.py \
  tests/test_document_type_classifier.py tests/test_file_type_detector.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q

cd ../packages/docuvision-core
pytest tests/processing/test_table_stitch.py -q
```

**通过标准**：全部 `passed`（Pro 预期 **≥45** + core stitch **2**）。

**v1.2 扩展**（含多页 KIE + batch 导出，**33 项**，2026-06-05 Cloud 已绿）：

```bash
cd backend
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q
```

**通过标准**：全部 `passed`（含 `test_pdf_preprocessed_path_same_as_pdf_still_rasterizes`）。

**GitHub Actions**：**PR 至 `main`** 且 `backend/**` 有变更时自动运行 [`.github/workflows/kie-phase-a.yml`](../../.github/workflows/kie-phase-a.yml)（CPU runner，与本节相同命令）。日常 push 默认不触发；需 push 后跑 CI 时在 commit message 加 **`[run ci]`**，或在 Actions 页 **Run workflow**。依赖见 [`backend/requirements-ci-phase-a.txt`](../../backend/requirements-ci-phase-a.txt)（无 Paddle、无 torch/transformers、不下载 Qwen 权重）。

### 阶段 B — 服务就绪

```bash
cd backend
python run.py
# 另开终端
curl -s http://127.0.0.1:8000/health | head
```

**通过标准**：HTTP 200；layout/table `ready: true`。`kie.model_loaded` 在 warmup 或首次 KIE 前可为 `false`。

### 阶段 C — 发票 KIE 三样例（生产指标）

对下列文件各提交 1 次 Job（UI：**Invoice** 模式，或 `enable_kie=true` + `document_type=invoice`）：

1. `test_data/testfiles/invoices/invoice_sample_01.pdf`（**须**走 PDF 第 1 页栅格化，勿再出现 `cannot identify image file ...pdf`）
2. `test_data/testfiles/invoices/receipt-invoice-like.png`
3. `test_data/testfiles/invoices/sample-invoice.png`

| 规则 ID | 用途 | 通过标准 |
|---------|------|----------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed` |
| **KIE-ACCEPT-002** | 生产质量 | `kie_production_hit == true` |

**阶段 C 目标**：**3/3** 满足 001 与 002（当前基线已达成，见 tracker）。

可选自动化：

```bash
cd backend
DOCUVISION_RUN_KIE_ACCEPTANCE=1 pytest tests/test_kie_acceptance_baseline.py -q
```

### 阶段 D — 卡证 KIE

| 样例 | document_type | 001/002 | 003（id_card 专项） |
|------|----------------|---------|---------------------|
| `test_data/testfiles/images/kie/id_card_sample_01.jpg` | `id_card` | 必过 | 推荐 |
| `test_data/testfiles/images/kie/id_card_sample_02.jpg` | `id_card` | 必过 | **必过** |
| `test_data/testfiles/images/kie/id_card_sample_03.jpg` | `id_card` | 必过 | **必过** |
| `test_data/testfiles/images/kie/id_card_sample_04.jpg` | `id_card` | 必过 | **必过** |
| `test_data/testfiles/images/kie/passport_sample_01.png` | `passport` | 必过 | — |
| `test_data/testfiles/images/kie/bank_card_sample_01.png` | `bank_card` | 必过 | — |

**目标**：

- 护照 / 银行卡：各 1/1 满足 001 + 002
- 身份证：**4/4** 满足 001 + 002；**02～04 必过 003**（`kie_id_card_precision_hit`）；01 为历史样例，003 作参考

### 阶段 E — 收据（可选）

`test_data/testfiles/receipts/receipt-with-tips.png`，`document_type=receipt`。

### 阶段 MP — 多页 PDF KIE（v1.2+）

生成样例（一次性）：

```powershell
cd <REPO_ROOT>
py -3 test_data/scripts/build_multipage_kie_fixtures.py
```

| 样例 | 请求 | 通过标准 | 基线（2026-06-05） |
|------|------|----------|-------------------|
| `invoices/invoice_sample_01.pdf` | `kie_pages=1`（默认） | 阶段 C 无回归；001 + 002 | layout 单页回归 pass |
| `invoices/multipage/invoice_multipage_2p_header_detail.pdf` | `kie_pages=all` | 001 + 002；`kie_pages_processed` ≥ 2；`kie_multipage_merge=true` | **pass**（`TASK_ID=d2844524-...`，`[1,2]`，14 字段） |

**推荐请求**（KIE-only，避免合成多页 PDF 与 PP-Structure layout 冲突）：

```powershell
$API_ROOT = "http://127.0.0.1:8000"
$REPO_ROOT = "<REPO_ROOT>"
$SAMPLE = "$REPO_ROOT/test_data/testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf"

$resp = Invoke-RestMethod -Method Post -Uri "$API_ROOT/api/v1/analyze" -Form @{
  file = Get-Item -LiteralPath $SAMPLE
  enable_layout = "0"
  enable_table = "0"
  enable_kie = "1"
  document_type = "invoice"
  kie_pages = "all"
}
$TASK_ID = $resp.task_id
```

**轮询与验收**（与 Phase B **同一** `python run.py` 进程；勿 restart/reload）：

```powershell
# Poll status — use strict=False if full JSON has control chars from KIE raw_output
for ($i = 1; $i -le 120; $i++) {
  $body = (Invoke-WebRequest -Uri "$API_ROOT/api/v1/tasks/$TASK_ID" -UseBasicParsing).Content
  $status = python -c "import sys,json; print(json.loads(sys.argv[1], strict=False).get('status',''))" $body
  Write-Host "[$i] status=$status"
  if ($status -in @("completed","succeeded")) { break }
  if ($status -in @("failed","cancelled")) { throw "task failed" }
  Start-Sleep -Seconds 3
}

# Acceptance — always fetch /result (not embedded in status during processing)
Invoke-WebRequest -Uri "$API_ROOT/api/v1/tasks/$TASK_ID/result" -OutFile "$env:TEMP/mp002_result.json"
python -c "import json; d=json.load(open(r'$env:TEMP/mp002_result.json')); q=d.get('quality',{}); print('kie_stage',q.get('kie_stage')); print('kie_production_hit',q.get('kie_production_hit')); print('kie_pages_processed',q.get('kie_pages_processed')); print('kie_multipage_merge',q.get('kie_multipage_merge'))"
```

**MP-002 通过判据**：`kie_stage=completed`，`kie_production_hit=true`，`kie_pages_processed=[1,2]`（或长度 ≥ 2），`kie_multipage_merge=true`，`kie_fields_by_page` 含 `"1"`、`"2"`。

> **轮询陷阱**：`GET /tasks/{id}` 在任务接近完成时可能内嵌含控制字符的 `result`，`json.load(strict=True)` 会报 `Invalid control character`；**不代表任务失败**。处理：轮询用 `strict=False`，或只读 `status`；验收只看 `GET .../result`。

契约单测（无 GPU，已并入阶段 A v1.2 命令）：

```bash
cd backend
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py -q
```

记录写入 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) 阶段 MP。

### 阶段 H-Batch — Batch KIE + 汇总导出（v1.2+）

`python run.py` 已启动；`DEBUG=false` 推荐（避免 reload 丢 batch）。

**基线（2026-06-05 Cloud）**：`BATCH_ID=52ce6aed-...`，**6/6 completed**，`kie_production_hit` **6/6**，耗时 ~108s。详见 tracker。

**方式一 — 脚本（推荐）**：

```powershell
cd <REPO_ROOT>
pwsh -File test_data/scripts/run_batch_kie_acceptance.ps1
```

**方式二 — 手动**（多文件上传须 multipart 重复 `files` 字段；可复制 `test_data/scripts/run_batch_kie_acceptance.ps1` 的建批逻辑，或 zsh/curl 等价命令）：

创建 batch 后，**轮询与导出**（与方式一相同判据）：

```powershell
$API_ROOT = "http://127.0.0.1:8000"
$BATCH_ID = "<batch_id_from_create>"

# Poll — use /summary (no embedded task results; avoids JSON control-char parse errors)
for ($i = 1; $i -le 360; $i++) {
  $s = Invoke-RestMethod -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/summary"
  Write-Host "[$i] status=$($s.status) counts=$($s.status_counts | ConvertTo-Json -Compress)"
  if ($s.status -in @("completed","failed","cancelled")) { break }
  Start-Sleep -Seconds 5
}

Invoke-WebRequest -Uri "$API_ROOT/api/v1/batch/$BATCH_ID/export.csv?mode=kie" -OutFile "$env:TEMP/batch_$BATCH_ID.csv"
Get-Content "$env:TEMP/batch_$BATCH_ID.csv" -TotalCount 3
```

`kie_invoice_6` 文件列表见 `test_data/testfiles/batch/manifest.json`；options **必须**含 `document_type=invoice`（缺则 KIE 为 `skipped_doc_type`）。建议：`enable_kie=true`，`kie_pages=1`；layout 可与 manifest 一致（`enable_layout=true`）。验收脚本 `run_batch_kie_acceptance.ps1` 会合并 manifest 顶层 `document_type` 并校验 CSV `kie_production_hit`。

**通过标准**（[batch_kie.md](../../test_data/acceptance/batch_kie.md)）：

| Rule | 判据 |
|------|------|
| BATCH-001 | `summary.status=completed`，`status_counts.completed=6` |
| BATCH-002 | CSV 每行 `kie_production_hit=true`（invoice 类） |
| BATCH-003 | CSV 表头含 `file_name`、`status`、`kie_production_hit` |

> **轮询陷阱**：勿用 `GET /batch/{id}` 轮询（内嵌 `tasks[].result` 易触发 JSON 控制字符错误）；改用 **`GET /batch/{id}/summary`**。验收导出用 **`/export.csv?mode=kie`**（CSV 无此问题）。

### 阶段 F — 全量回归（时间允许）

```bash
cd backend
pip install "httpx>=0.24,<0.28"
pytest tests/ -q --tb=short --ignore=tests/test_live_api.py
```

`test_live_api.py` 依赖**已启动**的 `:8000` 且与全量 pytest **争 GPU**；单独验证：

```bash
pytest tests/test_live_api.py::TestLiveInvoiceKie -s
```

结果批次写入 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)。导出 JSON 汇总：

```bash
cd backend
python tests/tools/summarize_kie_results.py ../test_data/TestResult/PhaseCDE
```

## 3. 结果字段说明

| 字段 | 含义 |
|------|------|
| `kie_fields_count` | 非空 schema 字段数（**不含**仅 `raw_output`） |
| `kie_production_hit` | 是否满足 KIE-ACCEPT-002 |
| `kie_production_reason` | 如 `production_hit`、`raw_output_only`、`no_required_keys_filled` |
| `kie_production_keys` | 命中的关键字段名列表 |
| `kie_confidence_avg` | 关键字段填充率启发值（0～1） |
| `kie_error_message` | 失败时异常摘要（如历史 PDF 路径 bug） |
| `kie_meta.error_message` | 与上同源，在完整 Envelope/任务结果中 |
| `kie_pages_requested` | v1.2+：请求页规格（如 `1`、`all`、`1-3`） |
| `kie_pages_processed` | v1.2+：实际处理页列表（如 `[1, 2]`） |
| `kie_multipage_merge` | v1.2+：多页字段是否文档级合并 |
| `kie_fields_by_page` | v1.2+：按页 KIE 字段（键为页码字符串） |

## 4. DocuVision Lite（CPU，无 Paddle）

> **Since Release 1.0.1**, Lite ships on `main` (not a separate long-lived feature branch).  
> **本地不跑 Python/pytest**；改 Lite 代码时维护 `apps/lite/backend/tests/` 与 `packages/docuvision-core/tests/processing/`，由 CI 或云端验收。

### 阶段 G0 — Lite 模型 bootstrap（新主机 / 空 models/ 时执行一次）

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng ghostscript
cd packages/docuvision-core
bash scripts/bootstrap_lite_models.sh
python scripts/bootstrap_lite_models.py --status-only
```

模型权重保存在 **`packages/docuvision-core/models/`**（与源码同路径，持久盘随仓库目录保留）。换主机流程见 [models/README.md](../../packages/docuvision-core/models/README.md)。

### 阶段 G — Lite 契约（GitHub Actions 或 Cloud Studio CPU）

```bash
cd apps/lite/backend
pip install -r requirements-lite.txt
pip install -e '../../packages/docuvision-core[lite,dev]'
pytest tests/ -q
cd ../../packages/docuvision-core
pytest tests/extractors/test_factory.py tests/processing/test_table_type_classifier.py -q
```

（zsh 下 `pip install -e` 的 extras 路径须加单引号，见 [apps/lite/backend/tests/README.md](../../apps/lite/backend/tests/README.md) §2.2。）

**通过标准**：全部 `passed`（规则 **LITE-PROFILE-001～003**、**LITE-CORE-001～002**、**LITE-EXTRACT-001～002**，见 [apps/lite/backend/tests/README.md](../../apps/lite/backend/tests/README.md)）。

**GitHub Actions**：**PR 至 `main`** 且 Lite 路径有变更时，[`.github/workflows/ci-lite.yml`](../../.github/workflows/ci-lite.yml) 自动执行。日常 push 至 `feature/docuvision-lite` 默认不跑；需 CI 时用 **`[run ci]`** 或 Actions 页 **Run workflow**。

### 阶段 H — Lite UI 冒烟（可选）

```bash
cd apps/lite/backend && python run_lite.py
# http://{host}:8001/lite/lite.html
```

上传 digital PDF → Document Profile；Run Extraction → Content/Tables；PNG → scan_profile。

## 5. 相关文档

- [kie.md](./kie.md) — KIE 契约、PDF 输入策略
- [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) — 云测批次记录
- [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md) — 样例矩阵
- [lite-api.md](./lite-api.md) — Lite API
- [apps/lite/backend/tests/README.md](../../apps/lite/backend/tests/README.md) — Lite 验收规则
- [packages/docuvision-core/models/README.md](../../packages/docuvision-core/models/README.md) — Lite 模型目录与换主机流程
