# KIE Acceptance Criteria Baseline

Last updated: 2026-05-20  
Scope: Tracker item 1 (KIE field extraction quality)

## Sample Matrix (invoice)

1. test_data/testfiles/invoices/invoice_sample_01.pdf
2. test_data/testfiles/invoices/receipt-invoice-like.png
3. test_data/testfiles/invoices/sample-invoice.png

## Sample Matrix (card — `test_data/testfiles/images/kie/`)

1. id_card_sample_01.jpg → `document_type=id_card`（历史样例）
2. id_card_sample_02.jpg → `document_type=id_card`（合成中文 · 清晰）
3. id_card_sample_03.jpg → `document_type=id_card`（合成中文 · 倾斜+压缩）
4. id_card_sample_04.jpg → `document_type=id_card`（合成中文 · 轻微模糊）
5. passport_sample_01.png → `document_type=passport`
6. bank_card_sample_01.png → `document_type=bank_card`

合成身份证 ground-truth（虚构，供 Cloud 人工核对）见 [`test_data/testfiles/images/kie/README.md`](../../test_data/testfiles/images/kie/README.md)。

## Rule KIE-ACCEPT-001（流水线契约）

When `quality.kie_stage == "completed"`:

- Accept `kie_fields_count >= 0`（含 0，表示契约闭环）。
- Reject non-`completed` stage or negative counts.

Implementation: `app.services.kie.kie_field_metrics.evaluate_kie_contract`

`kie_fields_count` 使用 **有意义字段计数**（排除仅 `raw_output`、空字符串不计）。

## Rule KIE-ACCEPT-002（生产质量）

When stage is `completed` **and** KIE was attempted for a supported `document_type`:

- **Hit**：`quality.kie_production_hit == true`
- **Miss**：`completed` 但 `kie_production_hit == false`（如 `raw_output_only`、`no_required_keys_filled`）

### Required key hints (any one non-empty)

| document_type | Keys (any one) |
|---------------|----------------|
| invoice | `invoice_number`, `total`, `seller_name`, `invoice_date` |
| receipt | `total`, `merchant_name`, `receipt_date`, `receipt_number` |
| id_card | `name`, `id_number` |
| passport | `passport_number`, `name` |
| bank_card | `bank_card_number`, `bank_name` |

Implementation: `app.services.kie.kie_field_metrics.evaluate_kie_production_hit`

## Rule KIE-ACCEPT-003（id_card 字段精度，专项）

在 **002 通过** 的前提下，对 `document_type=id_card` 额外要求：

- **Hit**：`quality.kie_id_card_precision_hit == true`
- 条件：`name` 非空 **且** `id_number` 为 **18 位**格式（`^[0-9]{17}[0-9Xx]$`，不验证校验位算法）
- **Miss 原因示例**：`id_number_missing_or_invalid`、`name_missing`

**Cloud 阶段 D（身份证）目标**：4 张 `id_card_sample_*.jpg` 均满足 **001 + 002 + 003**。

Implementation: `app.services.kie.kie_field_metrics.evaluate_kie_id_card_precision`

## Reporting Convention

Per sample, record at least:

- sample_path
- document_type
- kie_stage
- kie_fields_count
- kie_production_hit / kie_production_reason
- kie_id_card_precision_hit / kie_id_card_precision_reason（id_card 时）
- contract_accepted (KIE-ACCEPT-001)
- production_hit_miss (KIE-ACCEPT-002)
- id_card_precision (KIE-ACCEPT-003, id_card only)
- note

## Test Entry

```bash
cd backend
pytest -q tests/test_kie_field_metrics.py tests/test_kie_acceptance_baseline.py -k "rule or matrix or id_card"
```

Cloud smoke:

```bash
cd backend
DOCUVISION_RUN_KIE_ACCEPTANCE=1 pytest -q tests/test_kie_acceptance_baseline.py -k smoke
```

Full cloud procedure: [docs/architecture/CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)

## Baseline status (2026-05-20)

Cloud Studio 固定 **7 样例**（C+D+E）在 commit **`e7dc4ab`** 及之后应满足：

- **KIE-ACCEPT-001**：7/7 `kie_stage == completed`
- **KIE-ACCEPT-002**：7/7 `kie_production_hit == true`

含 **`invoice_sample_01.pdf`**（PDF 须栅格化，见 `test_kie_service.test_pdf_preprocessed_path_same_as_pdf_still_rasterizes`）。记录见 [KIE_TEST_RUN_TRACKER.md](../../docs/architecture/KIE_TEST_RUN_TRACKER.md)。

**增量（id_card 加强）**：新增 `id_card_sample_02~04.jpg` 后，Cloud 阶段 D 身份证子集目标为 **4/4** 满足 **003**；全矩阵见上文 Sample Matrix。
