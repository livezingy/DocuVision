# 按文档类型的验收矩阵（人工 + 自动化）

分类存放的样例根目录为 **`test_data/testfiles/`**（按子目录区分类型）；卡证 KIE 固定样例在 **`test_data/testfiles/images/kie/`**。云端截图与临时导出放在 **`test_data/TestResult/`**（已加入 `.gitignore`，不纳入 Git）。

固定样例放在 `test_data/` 下，避免散测。自动化命令见各行的「自动化」列。云测顺序与 **KIE-ACCEPT-001/002** 见 [docs/architecture/CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)。

| 场景 | document_type | enable_kie | 固定样例（1～2 张） | 自动化 | 人工检查 |
|------|----------------|------------|-------------------|--------|----------|
| 通用 PDF / 扫描 | `auto` 或 `layout` | false | `test_data/testfiles/pdf/text_based/sample_report.pdf`；`test_data/testfiles/images/scanned/scanned_page_02.jpg` | `POST /api/v1/analyze` 后轮询 `GET /api/v1/tasks/{id}/result`：`layout` 或 `view.pages`、`tables` 为列表；可选 `GET .../export/json` | 导出 JSON 结构可读；版面与表格与目测一致 |
| 发票 | `invoice` | true | `test_data/testfiles/invoices/invoice_sample_01.pdf`；`test_data/testfiles/invoices/sample-invoice.png` | 阶段 C / `pytest tests/test_kie_service.py -k pdf` | `kie_production_hit`；PDF 须 `completed`（非 `cannot identify image file ...pdf`） |
| 发票多页 | `invoice` | true | `test_data/testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf`（需 `build_multipage_kie_fixtures.py`） | 阶段 MP | `kie_pages=1` 回归；`kie_pages=all` → `kie_pages_processed>=2` |
| Batch KIE | `invoice` / `receipt` | true | `test_data/testfiles/batch/manifest.json` → `kie_invoice_6` | `run_batch_kie_acceptance.ps1` / 阶段 H-Batch | BATCH-001～003（见 [batch_kie.md](batch_kie.md)） |
| 收据 | `receipt` | true | `test_data/testfiles/receipts/receipt-with-tips.png` | 同上 opt-in / 阶段 E | 小费字段；production hit |
| 身份证 / 护照 / 银行卡 | `id_card` / `passport` / `bank_card` | true | `id_card_sample_01~04.jpg`；`passport_sample_01.png`；`bank_card_sample_01.png`（路径前缀 `test_data/testfiles/images/kie/`） | Cloud 阶段 D；`document_type` 与 `kie_configs/_registry.yaml` 一致 | 卡证字段、`kie_production_keys`；身份证另查 **KIE-ACCEPT-003**（`kie_id_card_precision_*`） |
| Phase1 Job | `auto`（`documents:analyze` 默认） | 可选 | 与通用列相同 | `POST /api/v1/documents:analyze` → `GET /api/v1/jobs/{id}/result`：`JobEnvelope.view` / `fused` / `quality` | 与 Legacy task 结果对照 |

**说明**

- 旧版模板 REST（`/api/v1/templates*`）已从服务移除，**OpenAPI 不再列出**；旧客户端请求该路径将得到 **404**。验收不依赖模板匹配。
- 独立 NLP API（`/api/v1/nlp*`）已移除，不再验收。
