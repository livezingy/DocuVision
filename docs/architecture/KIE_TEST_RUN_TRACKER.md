# KIE Test Run Tracker

Last updated: 2026-05-20  
Scope: Cloud verification for invoice + card KIE (contract + production)

前端 **Content > Fields** 已接入：数据来源为任务结果中的 `kie_fields` 或 Envelope `view.fields`（与 [kie.md](./kie.md) 契约一致）。

验证顺序见 [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)。

## Tracking Rules

| Rule ID | 用途 | 判定 |
|---------|------|------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed` 且 `kie_fields_count >= 0` |
| **KIE-ACCEPT-002** | 生产质量 | `kie_production_hit == true`（关键字段至少一项非空，且非仅 `raw_output`） |

**Hit/Miss 建议**（生产维度）：

- **production_hit**：KIE-ACCEPT-002 为 true
- **production_miss**：stage completed 但 `kie_production_hit == false`
- **contract_error**：stage 非 completed

`kie_fields_count` 为有意义字段计数，与旧版「含 raw_output 键即 +1」不同。

## Run Template

```md
### Run YYYY-MM-DD HH:MM (UTC)
- base_url:
- branch:
- commit:
- sample_set:

| sample_path | document_type | job_id | kie_stage | kie_fields_count | kie_production_hit | contract_ok | prod_hit_miss | note |
|---|---|---|---|---:|---|---|---|---|
| ... | invoice | ... | completed | ... | true/false | true | hit/miss | ... |

- summary: total=, contract_ok=, production_hit=, production_miss=, error=
```

## Latest Confirmed Batch (2026-04-10, 旧口径)

> 下列为 **KIE-ACCEPT-001** 口径；`kie_fields_count=0` 在生产规则下为 miss。重跑后请用新表头记录 `kie_production_hit`。

- base_url: cloudstudio public endpoint (:8000)
- sample_set: 发票三样例（见 CLOUD_VALIDATION 阶段 C）

| sample_path | kie_stage | kie_fields_count (legacy) | contract | prod (待重测) |
|---|---|---:|---|---|
| invoice_sample_01.pdf | completed | 0 | pass | 待填 |
| sample-invoice.png | completed | 0 | pass | 待填 |
| receipt-invoice-like.png | completed | 0 | pass | 待填 |

## Card samples (fixed paths)

- `test_data/testfiles/images/kie/id_card_sample_01.jpg`
- `test_data/testfiles/images/kie/passport_sample_01.png`
- `test_data/testfiles/images/kie/bank_card_sample_01.png`

## Related Artifacts

- Acceptance criteria: [backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)
- Cloud procedure: [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)
- API check: `backend/tests/test_kie_acceptance_baseline.py`
- 验收矩阵: [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
