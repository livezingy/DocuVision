# Cloud Studio GPU 验证顺序与验收标准

> 本地无 Paddle 完整环境时，以 **腾讯 Cloud Studio GPU** 为端到端真环境。勿提交密钥；使用 `backend/.env.cloud` 复制为 `.env`。

## 1. 环境准备（一次性）

```bash
cd backend
pip install -r requirements.txt
# GPU：按 requirements.txt 头注释安装与 CUDA 匹配的 torch / Paddle
cp .env.cloud .env   # 按需改模型路径，勿提交 .env
```

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

**通过标准**：全部 `passed`。

### 阶段 B — 服务就绪

```bash
cd backend
python run.py
# 另开终端
curl -s http://127.0.0.1:8000/health | head
```

**通过标准**：HTTP 200；health 中 KIE 相关状态符合预期（如 `kie_ready` / 模型路径配置无报错）。首次 analyze 前等待 warmup 日志完成（若已开启）。

### 阶段 C — 发票 KIE 三样例（生产指标）

对下列文件各提交 1 次 Job（`enable_kie=true`，`document_type=invoice`）：

1. `test_data/testfiles/invoices/invoice_sample_01.pdf`
2. `test_data/testfiles/invoices/receipt-invoice-like.png`
3. `test_data/testfiles/invoices/sample-invoice.png`

**记录**到 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)：`kie_stage`、`kie_fields_count`、`kie_production_hit`、`kie_production_reason`、`note`。

| 规则 ID | 用途 | 通过标准 |
|---------|------|----------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed`；`kie_fields_count >= 0` |
| **KIE-ACCEPT-002** | 生产质量 | `quality.kie_production_hit == true`；`kie_production_reason == production_hit` |

**阶段 C 目标**：三样例至少 **2/3** 满足 KIE-ACCEPT-002（可持续调高）。

可选自动化（重、需 GPU + 模型）：

```bash
cd backend
DOCUVISION_RUN_KIE_ACCEPTANCE=1 pytest tests/test_kie_acceptance_baseline.py -q
```

### 阶段 D — 卡证 KIE 三样例

| 样例 | document_type |
|------|----------------|
| `test_data/testfiles/images/kie/id_card_sample_01.jpg` | `id_card` |
| `test_data/testfiles/images/kie/passport_sample_01.png` | `passport` |
| `test_data/testfiles/images/kie/bank_card_sample_01.png` | `bank_card` |

**通过标准**：KIE-ACCEPT-001 必过；KIE-ACCEPT-002 按类型关键字段（见 [KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)）记录 hit/miss。

### 阶段 E — 收据（可选）

`test_data/testfiles/receipts/receipt-with-tips.png`，`document_type=receipt`，同上记录 production 指标。

### 阶段 F — 全量回归（时间允许）

```bash
cd backend
pip install "httpx>=0.24,<0.28"
pytest tests/ -q --tb=short
```

**说明**：`tests/test_user_workflows.py::TestInvoiceProcessingWorkflow` 依赖 **已启动** 的 `http://localhost:8000` 且会真实加载 Qwen。全量 `pytest` 与在线服务 **争用 GPU** 时，该用例可能 `kie_stage=runtime_error` 并被标记为 **skip**（非契约回退）。建议：

- 全量回归：`pytest tests/ -q --ignore=tests/test_user_workflows.py`
- 单独验发票 KIE：`pytest tests/test_user_workflows.py::TestInvoiceProcessingWorkflow -s`（服务重启后）

Phase C/D/E 导出 JSON 可放入 `test_data/TestResult/PhaseCDE/`，运行：

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

## 4. 相关文档

- [kie.md](./kie.md) — KIE 契约与依赖
- [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) — 云测批次记录
- [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md) — 样例矩阵
