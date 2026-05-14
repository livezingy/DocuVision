# 按文档类型的验收矩阵（人工 + 自动化）

分类存放的样例根目录为 **`test_data/testfiles/`**（按子目录区分类型）；下表路径可为历史约定或与 `testfiles` 下实际文件对应。云端截图与临时导出放在 **`test_data/TestResult/`**（已加入 `.gitignore`，不纳入 Git）。

固定样例放在 `test_data/` 下，避免散测。自动化命令见各行的「自动化」列。

| 场景 | document_type | enable_kie | 固定样例（1～2 张） | 自动化 | 人工检查 |
|------|----------------|------------|-------------------|--------|----------|
| 通用 PDF / 扫描 | `auto` 或 `layout` | false | `test_data/testfiles/pdf/text_based/sample_report.pdf`；`test_data/testfiles/images/scanned/scanned_page_02.jpg` | `POST /api/v1/analyze` 后轮询 `GET /api/v1/tasks/{id}/result`：`layout` 或 `view.pages`、`tables` 为列表；可选 `GET .../export/json` | 导出 JSON 结构可读；版面与表格与目测一致 |
| 发票 | `invoice` | true | `test_data/testfiles/templates/invoice/invoice_sample_01.pdf`；`test_data/testfiles/templates/invoice/sample-invoice.png` | `DOCUVISION_RUN_KIE_ACCEPTANCE=1 pytest backend/tests/test_kie_acceptance_baseline.py -q`（重）；或本机对同一文件 `analyze` + KIE | `view.fields` / `kie_fields` 关键键；导出 JSON |
| 收据 | `receipt` | true | `test_data/testfiles/templates/invoice/receipt-invoice-like.png`（收据类占位） | 同上 opt-in smoke | 字段稳定性 |
| 身份证 / 护照 / 银行卡 | `id_card` / `passport` / `bank_card` | true | **占位**：各类型 1 张放入 `test_data/testfiles/images/kie/` 后更新本表路径 | `document_type` 与 `kie_configs/_registry.yaml` 一致；PDF 无预处理图时走 `kie_qwen_service` 栅格 | 卡证字段与遮挡 |
| Phase1 Job | `auto`（`documents:analyze` 默认） | 可选 | 与通用列相同 | `POST /api/v1/documents:analyze` → `GET /api/v1/jobs/{id}/result`：`JobEnvelope.view` / `fused` / `quality` | 与 Legacy task 结果对照 |

**说明**

- 旧版模板 REST（`/api/v1/templates*`）已从服务移除，**OpenAPI 不再列出**；旧客户端请求该路径将得到 **404**。验收不依赖模板匹配。
- 独立 NLP API（`/api/v1/nlp*`）已移除，不再验收。
- 卡证样例若仓库中暂无文件，请先补图再填「固定样例」列路径。
