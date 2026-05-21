# KIE Test Run Tracker

Last updated: 2026-05-20  
Scope: Cloud verification for invoice + card + receipt KIE (contract + production)

验证顺序见 [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)。Phase C/D/E 原始 JSON：`test_data/TestResult/PhaseCDE/`（本地路径，`.gitignore` 不提交）。

## Tracking Rules

| Rule ID | 用途 | 判定 |
|---------|------|------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed` 且 `kie_fields_count >= 0` |
| **KIE-ACCEPT-002** | 生产质量 | `kie_production_hit == true` |

## Run 2026-05-20 Cloud Studio (Phase C/D/E)

- base_url: `http://127.0.0.1:8000`（UI 导出 Result JSON）
- branch: `main`
- commit: `61dc578` 及之后（含 `kie_production_*` 指标）
- sample_set: CLOUD_VALIDATION 阶段 C + D + E

| sample_path | document_type | result_json | kie_stage | kie_fields_count | kie_production_hit | contract_ok | prod_hit_miss | note |
|---|---|---|---|---:|---|---|---|---|
| testfiles/invoices/invoice_sample_01.pdf | invoice | docuvision_result_1779268769276.json | runtime_error | 0 | false | **fail** | error | **根因**：`preprocessed_image_path` 误传 PDF 路径 → PIL 无法打开；见 `kie_qwen_service` 修复（2026-05-20） |
| testfiles/invoices/receipt-invoice-like.png | invoice | docuvision_result_1779268818176.json | completed | 11 | true | pass | hit | keys: invoice_number, total, seller_name, invoice_date |
| testfiles/invoices/sample-invoice.png | invoice | docuvision_result_1779268894422.json | completed | 14 | true | pass | hit | 同上 + items×3 |
| testfiles/images/kie/id_card_sample_01.jpg | id_card | docuvision_result_1779269150502.json | completed | 5 | true | pass | hit | keys: name（id_number 未命中关键键） |
| testfiles/images/kie/passport_sample_01.png | passport | docuvision_result_1779269003870.json | completed | 11 | true | pass | hit | keys: passport_number, name |
| testfiles/images/kie/bank_card_sample_01.png | bank_card | docuvision_result_1779268968501.json | completed | 5 | true | pass | hit | keys: bank_card_number, bank_name |
| testfiles/receipts/receipt-with-tips.png | receipt | docuvision_result_1779269546698.json | completed | 10 | true | pass | hit | keys: total, merchant_name, receipt_date, receipt_number |

- summary: total=7, contract_ok=6, production_hit=6, production_miss=0, **error=1**
- **阶段 C（发票 3）**：production **2/3 hit**（达标 ≥2/3）；契约 **2/3**（`invoice_sample_01.pdf` 须重跑）
- **阶段 D（卡证 3）**：6/6 生产 hit（全 pass）
- **阶段 E（收据 1）**：1/1 hit

### 重跑建议（仅失败样例）

1. 确认 `DOCUVISION_KIE_WARMUP=1` 或先跑一张轻量 PNG 完成 Qwen 加载。
2. 单独再跑 `invoice_sample_01.pdf`（Invoice 模式），预期 `kie_stage=completed` 且 `kie_model_load_ms`>0（与后 6 张一致，约 48–63s 量级）。

## Related Artifacts

- Acceptance criteria: [backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)
- Summarize script: `backend/tests/tools/summarize_kie_results.py`
- 验收矩阵: [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
