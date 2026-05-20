# 按文档类型的验收矩阵（人工 + 自动化）

分类存放的样例根目录为 **`test_data/testfiles/`**（按子目录区分类型）；卡证 KIE 固定样例在 **`test_data/testfiles/images/kie/`**。云端截图与临时导出放在 **`test_data/TestResult/`**（已加入 `.gitignore`，不纳入 Git）。

固定样例放在 `test_data/` 下，避免散测。自动化命令见各行的「自动化」列。云测顺序与 **KIE-ACCEPT-001/002** 见 [docs/architecture/CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)。

| 场景 | document_type | enable_kie | 固定样例（1～2 张） | 自动化 | 人工检查 |
|------|----------------|------------|-------------------|--------|----------|
| 通用 PDF / 扫描 | `auto` 或 `layout` | false | `test_data/testfiles/pdf/text_based/sample_report.pdf`；`test_data/testfiles/images/scanned/scanned_page_02.jpg` | `POST /api/v1/analyze` 后轮询 `GET /api/v1/tasks/{id}/result`：`layout` 或 `view.pages`、`tables` 为列表；可选 `GET .../export/json` | 导出 JSON 结构可读；版面与表格与目测一致 |
| 发票 | `invoice` | true | `test_data/testfiles/invoices/invoice_sample_01.pdf`；`test_data/testfiles/invoices/sample-invoice.png` | `DOCUVISION_RUN_KIE_ACCEPTANCE=1 pytest backend/tests/test_kie_acceptance_baseline.py -q`（重）；或 Cloud 按 CLOUD_VALIDATION 阶段 C | `view.fields` 关键键；`quality.kie_production_hit` |
| 收据 | `receipt` | true | `test_data/testfiles/receipts/receipt-with-tips.png` | 同上 opt-in / 阶段 E | 小费字段；production hit |
| 身份证 / 护照 / 银行卡 | `id_card` / `passport` / `bank_card` | true | `test_data/testfiles/images/kie/id_card_sample_01.jpg`；`passport_sample_01.png`；`bank_card_sample_01.png` | Cloud 阶段 D；`document_type` 与 `kie_configs/_registry.yaml` 一致 | 卡证字段与 `kie_production_keys` |
| Phase1 Job | `auto`（`documents:analyze` 默认） | 可选 | 与通用列相同 | `POST /api/v1/documents:analyze` → `GET /api/v1/jobs/{id}/result`：`JobEnvelope.view` / `fused` / `quality` | 与 Legacy task 结果对照 |

**说明**

- 旧版模板 REST（`/api/v1/templates*`）已从服务移除，**OpenAPI 不再列出**；旧客户端请求该路径将得到 **404**。验收不依赖模板匹配。
- 独立 NLP API（`/api/v1/nlp*`）已移除，不再验收。
