# testfiles — 测试样例库（放置规则）

本目录存放 DocuVision 的**分类固定样例**，供 Cloud / 本地验收与回归测试使用。
新增样例前请先读本节规则再动手。

## 目录语义（每类唯一权威目录）

| 文档类型 | 权威目录 | 备注 |
|---------|---------|------|
| 卡证（身份证/护照/银行卡/驾照/名片） | `images/kie/` | 已退役 `BankCard/`、`IDCard/`、`passports/` |
| 发票 | `invoices/`（多页入 `invoices/multipage/`） | |
| 收据 | `receipts/` | 多页夹具已移除（体积超限） |
| 通用表格/版面 | `GeneralFiles/` | |
| 纯文本/报告 PDF | `pdf/` | |
| PDF 解析基准 | `PDF_Parsing/`（GT 入 `PDF_Parsing/gt/`） | |
| 试用演示 | `trial/` | |
| 批处理清单 | `batch/manifest.json` | |

## 放置规则

- **R1 目录唯一**：每类文档只放一个权威目录，勿新建平行目录（如曾经的 `templates/`、`BankCard/`）。
- **R2 命名规范**：`类型_描述_编号.扩展名`，小写、无空格、无 `[ ] ( )`、无非 ASCII 隐形字符（如 `U+202F`）。禁用 `foo.pdf`、`P903454_1.jpg` 这类无意义名。
- **R3 可再生成**：凡能用脚本再生成的样例，必须提供生成脚本并写入对应 README 的「Regenerate」行；只提交「样例 + 脚本」，不提交一次性手工产物。**改生成脚本后必须同批重跑并提交**：`node test_data/scripts/generate_general_testfiles_pure.mjs --check` 必须报 `OK - no drift`（有漂移即非零退出）；只想重生成单个样例用 `--only <文件名>`，不加参数为全量写入。历史的「脚本改了但夹具未重跑」漂移见 2026-10-08 收敛批次（PR 记录）。
- **R4 隐私与临时产物不入库**：真实个人/客户/敏感文档、相机照片、截图、调试输出一律放 `test_data/local/` 或本地目录，**不进 `testfiles/`**。客户/来源资产归属 `test_data/assets/<namespace>/`（原 `others/` 已迁至 `assets/upwork-legacy-202610/`，永不进 git）。
- **R5 体积门槛**：单个样例 ≤ 10MB；超限须在对应 README 说明必要性。`receipts/multipage/receipt_multipage_2p.pdf`（17.7MB）已因此移除。
- **R6 新目录先登记**：新增子目录须同时放 `README.md`（用途、来源、生成脚本、字段/GT），否则视为不完整。

## 相关文档

- 验收矩阵：`test_data/acceptance/`（`doc_types.md`、`TEST_FILES_CHECKLIST.md`）
- 卡证验收样例：`images/kie/README.md`
- PDF 解析基准：`PDF_Parsing/gt/README.md`
