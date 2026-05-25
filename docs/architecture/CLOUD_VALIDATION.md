# Cloud Studio GPU 验证顺序与验收标准

> 本地无 Paddle 完整环境时，以 **腾讯 Cloud Studio GPU** 为端到端真环境。勿提交密钥；使用 `backend/.env.cloud` 复制为 `.env`。
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

**勿**在 Pro 环境中安装 Lite 依赖。启动前 **`source backend/env_pro_gpu.sh`**（设置 `LD_LIBRARY_PATH`，含 `libcusparseLt` 等 pip 自带库路径）。

建议环境变量：

| 变量 | 建议 |
|------|------|
| `DOCUVISION_KIE_WARMUP=1` | 启动后后台预加载 Qwen，减少首单冷启动 |
| `DEBUG_MODE` | 排障时可 `true`，自动写 `backend/debug/{job_id}/` |

显存：**先跑完 PP-StructureV3（layout/table），再跑 KIE**；同一 Job 内编排器已串行。避免并行多 Job 同时加载双模型。

## 2. 验证顺序（按阶段执行）

### 阶段 A — 契约单测（不加载 Qwen 权重）

```bash
cd backend
pytest tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q
```

**通过标准**：全部 `passed`（含 `test_pdf_preprocessed_path_same_as_pdf_still_rasterizes`）。

**GitHub Actions（自动）**：push/PR 至 `main` 且 `backend/**` 有变更时，workflow [`.github/workflows/kie-phase-a.yml`](../../.github/workflows/kie-phase-a.yml) 在 CPU runner 上执行与本节相同命令；依赖见 [`backend/requirements-ci-phase-a.txt`](../../backend/requirements-ci-phase-a.txt)（无 Paddle、无 torch/transformers、不下载 Qwen 权重）。

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

### 阶段 F — 全量回归（时间允许）

```bash
cd backend
pip install "httpx>=0.24,<0.28"
pytest tests/ -q --tb=short --ignore=tests/test_user_workflows.py
```

`test_user_workflows.py` 依赖**已启动**的 `:8000` 且与全量 pytest **争 GPU**；单独验证：

```bash
pytest tests/test_user_workflows.py::TestInvoiceProcessingWorkflow -s
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

## 4. 相关文档

- [kie.md](./kie.md) — KIE 契约、PDF 输入策略
- [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) — 云测批次记录
- [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md) — 样例矩阵
