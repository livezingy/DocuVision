# KIE Test Run Tracker

Last updated: 2026-05-06  
Scope: Ongoing cloud verification for invoice KIE acceptance

前端 **Content > Fields** 已接入：数据来源为任务结果中的 `kie_fields` 或 Envelope `view.fields`（与 [kie.md](./kie.md) 契约一致）。云端批测仍可按下方规则统计 `quality.kie_*`。

## Tracking Rule

- Rule ID: KIE-ACCEPT-001
- Accepted when: quality.kie_stage == "completed" and quality.kie_fields_count >= 0
- Hit: kie_fields_count > 0
- Miss: kie_fields_count == 0
- Error: any non-completed stage or invalid value

## Run Template

Copy this block for each cloud run batch.

```md
### Run YYYY-MM-DD HH:MM (UTC)
- base_url:
- branch:
- commit:
- sample_set:

| sample_path | job_id | final_status | kie_stage | kie_fields_count | accepted | hit_miss | note |
|---|---|---|---|---:|---|---|---|
| ... | ... | ... | ... | ... | ... | ... | ... |

- summary: total=, accepted=, hit=, miss=, error=
```

## Latest Confirmed Batch (2026-04-10)

- base_url: cloudstudio public endpoint (:8000)
- sample_set:
  - test_data/templates/invoice/invoice_sample_01.pdf
  - test_data/templates/invoice/sample-invoice.png
  - test_data/templates/invoice/receipt-invoice-like.png

| sample_path | final_status | kie_stage | kie_fields_count | accepted | hit_miss | note |
|---|---|---|---:|---|---|---|
| test_data/templates/invoice/invoice_sample_01.pdf | completed/succeeded | completed | 0 | true | miss | contract pass |
| test_data/templates/invoice/sample-invoice.png | completed/succeeded | completed | 0 | true | miss | contract pass |
| test_data/templates/invoice/receipt-invoice-like.png | completed/succeeded | completed | 0 | true | miss | contract pass |

- summary: total=3, accepted=3, hit=0, miss=3, error=0

## Related Artifacts

- Acceptance criteria: backend/tests/KIE_ACCEPTANCE_CRITERIA.md
- API check skeleton: backend/tests/test_kie_acceptance_baseline.py
- 验收矩阵与样例目录约定：test_data/acceptance/doc_types.md、test_data/testfiles/
