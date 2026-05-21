# KIE Acceptance Criteria Baseline

Last updated: 2026-05-20  
Scope: Tracker item 1 (KIE field extraction quality)

## Sample Matrix (invoice)

1. test_data/testfiles/invoices/invoice_sample_01.pdf
2. test_data/testfiles/invoices/receipt-invoice-like.png
3. test_data/testfiles/invoices/sample-invoice.png

## Sample Matrix (card — `test_data/testfiles/images/kie/`)

1. id_card_sample_01.jpg → `document_type=id_card`
2. passport_sample_01.png → `document_type=passport`
3. bank_card_sample_01.png → `document_type=bank_card`

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

## Reporting Convention

Per sample, record at least:

- sample_path
- document_type
- kie_stage
- kie_fields_count
- kie_production_hit / kie_production_reason
- contract_accepted (KIE-ACCEPT-001)
- production_hit_miss (KIE-ACCEPT-002)
- note

## Test Entry

```bash
cd backend
pytest -q tests/test_kie_field_metrics.py tests/test_kie_acceptance_baseline.py -k "rule or matrix"
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
