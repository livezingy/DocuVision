# 测试数据说明

仓库中 **`test_data/` 根下仅四个目录**：`acceptance/`（本说明与验收矩阵）、`testfiles/`（分类样例）、`Azure/`（参考 JSON）、`TestResult/`（本地临时输出，**不提交 Git**）。

## 📁 `test_data` 根目录结构

```
test_data/
├── acceptance/     # 验收矩阵、清单、快速开始
├── testfiles/      # 所有待测/固定样例：pdf、images、templates 等（路径均相对本目录）
├── Azure/          # Azure Layout / DI 风格参考 JSON（纳入版本库）
├── TestResult/     # 云端截图、导出缓存等（已在 test_data/.gitignore 中忽略）
└── .gitignore      # 仅忽略 TestResult/
```

样例文件的**物理路径**形如：`test_data/testfiles/pdf/text_based/sample_report.pdf`（即原 `test_data/pdf/...` 已迁入 `testfiles/`）。

## 云端与旧目录（Git 之外）

- **代码已更新后**：在云端工作区执行一次 `git pull`，已从 Git 删除的路径会随提交消失；若磁盘上仍有**未跟踪**的旧目录（例如历史 `test_data/pdf`），可手动删除：`rm -rf test_data/pdf test_data/images ...`（仅删除你确认不再需要的目录）。
- **不要让 CI/脚本再写入**已废弃路径：流水线里若有硬编码 `test_data/pdf` 等，请改为 `test_data/testfiles/...`；生成物统一写入 `test_data/TestResult/` 或 `backend/outputs/`，二者均不应作为「需归档的源码树」依赖。
- **持久化云盘**：若平台在仓库外同步了旧副本，与本次仓库布局无关，需在平台侧改挂载目录或清理镜像/快照策略。

## 📄 测试文件准备指南

### 1. PDF 测试文件

#### 文本型 PDF (`testfiles/pdf/text_based/`)
- **用途**：测试文本提取和表格识别
- **建议文件**：
  - `sample_report.pdf` - 包含文本和表格的报告
  - `sample_article.pdf` - 纯文本文章
  - `sample_form.pdf` - 表单文档

#### 图像型 PDF (`testfiles/pdf/image_based/`)
- **用途**：测试 OCR 功能
- **建议文件**：
  - `scanned_document.pdf` - 扫描的文档
  - `scanned_invoice.pdf` - 扫描的发票
  - `scanned_receipt.pdf` - 扫描的收据

#### 混合型 PDF (`testfiles/pdf/mixed/`)
- **用途**：测试综合处理能力
- **建议文件**：
  - `mixed_document.pdf` - 包含文本和图像的混合文档

### 2. 图片测试文件

#### 扫描图片 (`testfiles/images/scanned/`)
- **格式**：JPG, PNG, TIFF
- **建议文件**：
  - `scanned_page_01.jpg` - 扫描页面
  - `scanned_invoice.png` - 扫描发票
  - `scanned_receipt.tiff` - 扫描收据

#### 照片 (`testfiles/images/photos/`)
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

#### 收据 (`testfiles/templates/receipt/`)
- **必需字段**：
  - 收据号码 (Receipt Number)
  - 日期 (Date)
  - 总金额 (Total)
  - 商户名称 (Merchant)
- **建议文件**：
  - `receipt_sample_01.pdf`
  - `receipt_sample_02.jpg`

#### 证件 (`testfiles/templates/id_document/`)
- **必需字段**：
  - 姓名 (Name)
  - 证件号码 (ID Number)
  - 出生日期 (Date of Birth)
  - 有效期 (Expiry Date)
- **建议文件**：
  - `id_card_sample_01.jpg` - 身份证
  - `passport_sample_01.jpg` - 护照
  - `driver_license_sample_01.jpg` - 驾照

#### 名片 (`testfiles/templates/business_card/`)
- **必需字段**：
  - 姓名 (Name)
  - 职位 (Title)
  - 公司 (Company)
  - 电话 (Phone)
  - 邮箱 (Email)
- **建议文件**：
  - `business_card_sample_01.jpg`
  - `business_card_sample_02.png`

#### 合同 (`testfiles/templates/contract/`)
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

- 手动测试步骤：`docs/MANUAL_TESTING_GUIDE.md`
- API 文档：`http://localhost:8000/docs`
- 测试指南：`docs/TESTING_GUIDE.md`

