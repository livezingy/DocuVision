# KIE Test Run Tracker

Last updated: 2026-05-20  
Scope: Cloud verification for invoice + card + receipt KIE (contract + production)

验证步骤见 [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（**长期保留**：发版/改 KIE 后按同流程回归）。  
Phase C/D/E 原始 JSON 可放在 `test_data/TestResult/PhaseCDE/`（`.gitignore`，不提交 Git）。

## Tracking Rules

| Rule ID | 用途 | 判定 |
|---------|------|------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed` 且 `kie_fields_count >= 0` |
| **KIE-ACCEPT-002** | 生产质量 | `kie_production_hit == true` |
| **KIE-ACCEPT-003** | id_card 字段精度 | `kie_id_card_precision_hit == true`（`name` + 18 位 `id_number`） |

`kie_fields_count` 为有意义字段计数（排除仅 `raw_output`、空值不计）。

---

## Latest baseline — 2026-05-20 Cloud Studio（commit `e7dc4ab` 及之后）

- base_url: `http://127.0.0.1:8000`（UI / Legacy analyze）
- branch: `main`
- fix: PDF 发票 KIE 不再将 `.pdf` 当作 `preprocessed_image_path`；无栅格预处理图时用 PyMuPDF 栅格第 1 页（`kie_qwen_service._resolve_kie_image_path`）

| sample_path | document_type | kie_stage | kie_fields_count | kie_production_hit | contract | prod | id_card_003 |
|---|---|---|---:|---|---|---|---|
| testfiles/invoices/invoice_sample_01.pdf | invoice | completed | >0 | true | pass | hit | n/a |
| testfiles/invoices/receipt-invoice-like.png | invoice | completed | 11 | true | pass | hit | n/a |
| testfiles/invoices/sample-invoice.png | invoice | completed | 14 | true | pass | hit | n/a |
| testfiles/images/kie/id_card_sample_01.jpg | id_card | completed | 5 | true | pass | hit | ref |
| testfiles/images/kie/id_card_sample_02.jpg | id_card | — | — | — | — | — | **待 Cloud D** |
| testfiles/images/kie/id_card_sample_03.jpg | id_card | — | — | — | — | — | **待 Cloud D** |
| testfiles/images/kie/id_card_sample_04.jpg | id_card | — | — | — | — | — | **待 Cloud D** |
| testfiles/images/kie/passport_sample_01.png | passport | completed | 11 | true | pass | hit | n/a |
| testfiles/images/kie/bank_card_sample_01.png | bank_card | completed | 5 | true | pass | hit | n/a |
| testfiles/receipts/receipt-with-tips.png | receipt | completed | 10 | true | pass | hit | n/a |

- **summary (legacy 7)**: contract_ok=**7**, production_hit=**7**, error=**0**
- **阶段 C**：3/3 契约 + 3/3 生产
- **阶段 D（增量）**：身份证 **4 样例** + 护照 + 银行卡；02～04 待 Cloud 回归 **003**
- **阶段 E**：1/1

> 修复前 `invoice_sample_01.pdf` 曾 `runtime_error`（PIL 无法打开 PDF），见下方历史批次。

---

## Historical — pre-fix batch（commit `61dc578`，仅供参考）

| sample_path | kie_stage | note |
|---|---|---|
| invoice_sample_01.pdf | runtime_error | `preprocessed_image_path` 误为 PDF 路径；已在 `e7dc4ab` 修复 |
| 其余 6 样例 | completed + production_hit | 见 PhaseCDE 导出 JSON（`docuvision_result_*.json`） |

---

## Related Artifacts

- Acceptance criteria: [backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)
- Summarize script: `backend/tests/tools/summarize_kie_results.py`
- 验收矩阵: [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
