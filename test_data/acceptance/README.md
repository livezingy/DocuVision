# 测试数据说明（`test_data/` 总览）

本目录（`acceptance/`）存放验收矩阵/清单/规划；本文件兼作 **`test_data/` 根目录总览**。

## `test_data/` 根下目录

| 目录 | 用途 | Git |
|------|------|-----|
| `acceptance/` | 验收矩阵、清单、快速开始、UI E2E 规划（本目录） | tracked |
| `scripts/` | 验收与 fixture 脚本 | tracked |
| `testfiles/` | 分类固定样例（pdf、images、invoices 等，公开合成） | tracked |
| `fonts/` | P-018-P3 钉版字体（Paddle 渲染基线） | **gitignored** |
| `assets/<client-id>/` | **不可再生源资产**：客户机密件（`raw/`）+ 公开标准（`public/`）+ `manifest.json` + `notes/` | **gitignored** |
| `derived/` | **可再生派生产物**：`gt/` `cache/` `eval/` `packs/` | **gitignored** |
| `local/` | 本地产物（原 `TestResult/`）：截图、导出、评测运行 | **gitignored** |

> **分层原则（2026-10-04）**：**不可再生（`assets/`）与可再生（`derived/`）物理隔离**；`assets/<client-id>/manifest.json` 为指纹唯一机器真源，由 `test_data/scripts/verify_assets.py`（内容指纹）+ `scripts/assets_manifest_audit.py`（结构/在场）校验。
> Azure 风格参考 JSON 已于 2026-10-04 迁至 [`docs/R&D/reference/azure/`](../../docs/R&D/reference/azure/)；`AutoTest/` 已撤销，其 `PRO_UI_E2E_PLAN.md` 归入本目录。

## 📁 `test_data` 根目录结构

```
test_data/
├── acceptance/       # 验收矩阵、清单、快速开始、UI E2E 规划 + 本总览
├── scripts/          # 验收与 fixture 脚本
├── testfiles/        # 分类固定样例（进 git）
├── fonts/            # 钉版字体（gitignored）
├── assets/           # 客户源资产（gitignored，永不进 git）
│   ├── upwork-022102306242203617428/   # P-027 RF：raw/ · public/ · manifest.json · README · notes/
│   └── upwork-legacy-202610/           # 历史多单附件：raw/ · manifest.json · README
├── derived/          # 可再生派生产物（gitignored）：gt/ cache/ eval/ packs/
├── local/            # 本地产物（gitignored，原 TestResult/）
└── .gitignore        # 仅一条规则：local/；其余见根 .gitignore
```

> **Git 规则分布**：`local/` 由本目录 `.gitignore` 管理；`assets/`、`derived/`、`fonts/`、`testfiles/GeneralFiles_staging/` 由**仓库根 `.gitignore`** 统一管理（顺序敏感，详见根文件注释）。改任一侧前请先看另一侧。

样例文件的**物理路径**形如：`test_data/testfiles/pdf/sample_report.pdf`。

**UI 自动化 vs 手工验收**（E2E 绿缩小手工范围、助手交付提醒）：[UI_VERIFICATION_MATRIX.md](UI_VERIFICATION_MATRIX.md)

## 云端与旧目录（Git 之外）

- **代码已更新后**：在云端工作区执行一次 `git pull`，已从 Git 删除的路径会随提交消失；若磁盘上仍有**未跟踪**的旧目录（例如历史 `test_data/rf-quarantine`、`test_data/TestResult`），可手动删除：`rm -rf test_data/rf-quarantine test_data/TestResult`（仅删除你确认不再需要的目录）。
- **不要让 CI/脚本再写入**已废弃路径：流水线里若有硬编码旧路径，请改为 `test_data/local/`（临时产物）或 `test_data/assets`/`test_data/derived`；生成物统一写入 `test_data/local/` 或 `backend/outputs/`。
- **持久化云盘**：若平台在仓库外同步了旧副本，与本次仓库布局无关，需在平台侧改挂载目录或清理镜像/快照策略。

## 📄 测试文件准备指南

### 1. PDF 测试文件

#### 文本型 PDF (`testfiles/pdf/`)
- **用途**：测试文本提取和表格识别
- **仓库内样例**：`sample_report.pdf`、`financial_report.pdf` 等（见 `testfiles/pdf/`）
- **可本地补充**（非 Git 必需）：
  - `sample_article.pdf` - 纯文本文章
  - `sample_form.pdf` - 表单文档

#### 图像型 PDF (`testfiles/pdf/` 或本地 `image_based/`)
- **用途**：测试 OCR 功能
- **可本地补充**（非 Git 必需）：
  - `scanned_document.pdf` - 扫描的文档
  - `scanned_invoice.pdf` - 扫描的发票
  - `scanned_receipt.pdf` - 扫描的收据

#### 混合型 PDF
- **可本地补充**（非 Git 必需）：
  - `mixed_document.pdf` - 包含文本和图像的混合文档

### 2. 图片测试文件

#### 扫描图片（可选本地目录 `testfiles/images/scanned/`）

> **Git 内默认样例**：矩阵与手动脚本使用 `testfiles/invoices/sample-invoice.png` 或 `testfiles/images/kie/id_card_sample_01.jpg`。下列文件名供自行扫描补充，**不要求进仓库**。

- **格式**：JPG, PNG, TIFF
- **可本地补充**：
  - `scanned_page_01.jpg` - 扫描页面
  - `scanned_invoice.png` - 扫描发票
  - `scanned_receipt.tiff` - 扫描收据

#### 照片 (`testfiles/images/photos/`) — 可本地补充
- **格式**：JPG, PNG
- **建议文件**：
  - `document_photo.jpg` - 文档照片
  - `id_card_photo.png` - 证件照片

#### 截图 (`testfiles/images/screenshots/`)
- **格式**：PNG, JPG
- **建议文件**：
  - `webpage_screenshot.png` - 网页截图
  - `app_screenshot.jpg` - 应用截图

### 3. 模板测试文档

#### 发票 (`testfiles/invoices/`)
- **必需字段**：
  - 发票号码 (Invoice Number)
  - 发票日期 (Invoice Date)
  - 总金额 (Total Amount)
  - 供应商 (Vendor)
  - 客户 (Customer)
- **建议文件**：
  - `invoice_sample_01.pdf`
  - `invoice_sample_02.jpg`
  - `invoice_sample_03.png`

#### 收据 (`testfiles/receipts/`)
- **必需字段**：
  - 收据号码 (Receipt Number)
  - 日期 (Date)
  - 总金额 (Total)
  - 商户名称 (Merchant)
- **建议文件**：
  - `receipt_sample_01.pdf`
  - `receipt_sample_02.jpg`

#### 证件 (`testfiles/images/kie/`)
- **必需字段**：
  - 姓名 (Name)
  - 证件号码 (ID Number)
  - 出生日期 (Date of Birth)
  - 有效期 (Expiry Date)
- **建议文件**：
  - `id_card_sample_01.jpg` - 身份证
  - `passport_sample_01.jpg` - 护照
  - `driver_license_sample_01.jpg` - 驾照

#### 名片 (`testfiles/images/kie/`)
- **必需字段**：
  - 姓名 (Name)
  - 职位 (Title)
  - 公司 (Company)
  - 电话 (Phone)
  - 邮箱 (Email)
- **建议文件**：
  - `business_card_sample_01.jpg`
  - `business_card_sample_02.png`

#### 合同 (`testfiles/GeneralFiles/`)
- **必需字段**：
  - 合同编号 (Contract Number)
  - 签署日期 (Sign Date)
  - 甲方 (Party A)
  - 乙方 (Party B)
- **建议文件**：
  - `contract_sample_01.pdf`

## 🎯 测试文件获取方式

### 方式 1: 使用真实文档（推荐）
- 使用您自己的发票、收据、证件等（注意隐私保护）
- 扫描或拍照保存为 PDF/图片格式

### 方式 2: 生成测试文档
- 使用在线工具生成示例发票/收据
- 使用文档生成工具创建测试 PDF

### 方式 3: 使用公开样本
- 搜索公开的文档样本（注意版权）
- 使用测试数据生成器

## ⚠️ 注意事项

1. **隐私保护**：如果使用真实文档，请确保：
   - 移除敏感信息（如真实身份证号、银行卡号）
   - 仅用于测试目的
   - 测试后及时删除

2. **文件大小**：
   - 单个文件建议 < 10MB
   - 大文件可能处理较慢

3. **文件格式**：
   - PDF: `.pdf`
   - 图片: `.jpg`, `.jpeg`, `.png`, `.tiff`, `.tif`

4. **文件命名**：
   - 使用有意义的文件名
   - 避免特殊字符
   - 建议格式：`类型_描述_编号.扩展名`

## 📝 测试文件清单

创建测试文件后，请在此记录：

- [ ] PDF 测试文件（至少 3 个）
- [ ] 图片测试文件（至少 3 个）
- [ ] 发票样本（至少 2 个）
- [ ] 收据样本（至少 2 个）
- [ ] 证件样本（至少 2 个）
- [ ] 名片样本（至少 1 个）
- [ ] 合同样本（至少 1 个）

## 🔗 相关文档

- 云测步骤：[docs/architecture/CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)
- 快速开始：[QUICK_START.md](QUICK_START.md)
- UI 自动化 vs 手工：[UI_VERIFICATION_MATRIX.md](UI_VERIFICATION_MATRIX.md)
- 文档索引：[docs/README.md](../../docs/README.md)
- API 文档：`http://localhost:8000/docs`

