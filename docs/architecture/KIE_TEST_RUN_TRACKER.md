# KIE Test Run Tracker

Last updated: 2026-05-21  
Scope: Cloud verification for invoice + card + receipt KIE (contract + production + id_card precision)

验证步骤见 [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（**长期保留**：发版/改 KIE 后按同流程回归）。  
Phase C/D/E 原始 JSON 可放在 `test_data/TestResult/PhaseCDE/`（`.gitignore`，不提交 Git）。

Release 1.0 发版清单：[docs/release/RELEASE_1.0_CHECKLIST.md](../release/RELEASE_1.0_CHECKLIST.md) · Known limitations：[docs/release/KNOWN_LIMITATIONS.md](../release/KNOWN_LIMITATIONS.md)

## Tracking Rules

| Rule ID | 用途 | 判定 |
|---------|------|------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed` 且 `kie_fields_count >= 0` |
| **KIE-ACCEPT-002** | 生产质量 | `kie_production_hit == true` |
| **KIE-ACCEPT-003** | id_card 字段精度 | `kie_id_card_precision_hit == true`（`name` + 18 位 `id_number`） |

`kie_fields_count` 为有意义字段计数（排除仅 `raw_output`、空值不计）。

---

## Release 1.0 baseline — 2026-05-21

- **tag target**: `v1.0.0`
- **branch**: `main`
- **commits**: `e7dc4ab`（PDF KIE）→ `2c9c58b`（id_card 02–04、ACCEPT-003、Phase A CI）
- **base_url**: `http://127.0.0.1:8000`（UI）
- **Phase A CI**: green on `main`

### 阶段 C — 发票（2026-05-20 批次，commit `e7dc4ab+`）

| sample_path | document_type | kie_stage | kie_fields_count | 001 | 002 |
|---|---|---|---:|---|---|
| testfiles/invoices/invoice_sample_01.pdf | invoice | completed | >0 | pass | hit |
| testfiles/invoices/receipt-invoice-like.png | invoice | completed | 11 | pass | hit |
| testfiles/invoices/sample-invoice.png | invoice | completed | 14 | pass | hit |

**C 汇总**：3/3

### 阶段 D — 卡证 `images/kie/`（2026-05-21 UI 批次，commit `2c9c58b+`）

| sample_path | document_type | kie_stage | fields | 001 | 002 | 003 | note |
|---|---|---|---:|---|---|---|---|
| testfiles/images/kie/bank_card_sample_01.png | bank_card | completed | 5 | pass | hit | n/a | JSON `…5023578` |
| testfiles/images/kie/passport_sample_01.png | passport | completed | 11 | pass | hit | n/a | JSON `…5009993` |
| testfiles/images/kie/id_card_sample_01.jpg | id_card | completed | 5 | pass | hit | **ref miss** | 美国驾照风格；003 预期失败 |
| testfiles/images/kie/id_card_sample_02.jpg | id_card | completed | 6 | pass | hit | **hit** | JSON `…5018388` |
| testfiles/images/kie/id_card_sample_03.jpg | id_card | completed | 6 | pass | hit | **hit** | JSON `…5015901` |
| testfiles/images/kie/id_card_sample_04.jpg | id_card | completed | 6 | pass | hit | **hit** | JSON `…5013366` |

**D 汇总**：

- 001 + 002：**6/6**
- 003（id_card 02~04）：**3/3**；01 为 **ref**（见 Known limitations）

### 阶段 E — 收据（2026-05-20 批次）

| sample_path | document_type | kie_stage | kie_fields_count | 001 | 002 |
|---|---|---|---:|---|---|
| testfiles/receipts/receipt-with-tips.png | receipt | completed | 10 | pass | hit |

**E 汇总**：1/1

### 阶段 F — Query fields（v1.1，可选 Cloud 抽检）

在 **阶段 C 任一样例** 上追加 `kie_query_fields`，确认 001/002 仍通过且 query 字段可观测。

| sample_path | document_type | kie_query_fields | 001 | 002 | query filled |
|---|---|---|---|---|---|
| testfiles/invoices/invoice_sample_01.pdf | invoice | `OurReference`, `BookingDate` | pass | hit | manual check `quality.kie_query_fields_filled` |

**请求示例**（`POST /api/v1/analyze`）：

```text
enable_kie=1
document_type=invoice
kie_query_fields=[{"name":"OurReference","description":"Customer or PO reference"},{"name":"BookingDate"}]
```

**F 汇总**：契约 001/002 不因 query 字段失败；query 填充率 **不** 纳入 002。

### Release 1.0 KIE 总览

| 维度 | 结果 |
|------|------|
| 固定矩阵（C+D 卡证+E） | **10** 样例路径；001 **10/10**；002 **10/10** |
| id_card 003（02~04） | **3/3** |
| 阻塞项 | 无 |

> **发 tag 前建议**：在同一 Cloud 环境对 **阶段 C + E** 再跑一轮（同一 commit），确认发票 PDF 与收据未回归。

---

## Historical — 2026-05-20 Cloud Studio（commit `e7dc4ab`）

首批 **7 样例** 001/002 全过；`id_card_sample_02~04` 尚未入库。PDF 发票修复见 `e7dc4ab`。

| sample_path | note |
|---|---|
| invoice_sample_01.pdf | 修复前曾 `runtime_error`（PIL 无法打开 PDF） |
| 其余 6 样例 | completed + production_hit |

---

## Historical — pre-fix batch（commit `61dc578`）

| sample_path | kie_stage | note |
|---|---|---|
| invoice_sample_01.pdf | runtime_error | `preprocessed_image_path` 误为 PDF 路径 |

---

## Related Artifacts

- Acceptance criteria: [backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)
- Summarize script: `backend/tests/tools/summarize_kie_results.py`
- 验收矩阵: [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
- Changelog: [CHANGELOG.md](../../CHANGELOG.md)
