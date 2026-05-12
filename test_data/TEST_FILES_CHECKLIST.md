# 测试文件准备清单

按文档类型的**固定样例与人工/自动化验收**见 [acceptance/doc_types.md](acceptance/doc_types.md)。分类样例目录：`test_data/testfiles/`。云端截图仅放 `test_data/TestResult/`（不纳入 Git）。

## 📋 文件准备检查清单

请准备以下测试文件，并在完成后勾选：

### PDF 测试文件

#### 文本型 PDF (`test_data/pdf/text_based/`)
- [ ] `sample_report.pdf` - 包含文本和表格的报告文档
- [ ] `sample_article.pdf` - 纯文本文章
- [ ] `sample_form.pdf` - 表单文档

#### 图像型 PDF (`test_data/pdf/image_based/`)
- [ ] `scanned_document.pdf` - 扫描的文档
- [ ] `scanned_invoice.pdf` - 扫描的发票
- [ ] `scanned_receipt.pdf` - 扫描的收据

#### 混合型 PDF (`test_data/pdf/mixed/`)
- [ ] `mixed_document.pdf` - 包含文本和图像的混合文档

### 图片测试文件

#### 扫描图片 (`test_data/images/scanned/`)
- [ ] `scanned_page_01.jpg` - 扫描页面（JPG格式）
- [ ] `scanned_invoice.png` - 扫描发票（PNG格式）
- [ ] `scanned_receipt.tiff` - 扫描收据（TIFF格式）

#### 照片 (`test_data/images/photos/`)
- [ ] `document_photo.jpg` - 文档照片
- [ ] `id_card_photo.png` - 证件照片

#### 截图 (`test_data/images/screenshots/`)
- [ ] `webpage_screenshot.png` - 网页截图
- [ ] `app_screenshot.jpg` - 应用截图

### 模板测试文档

#### 发票 (`test_data/templates/invoice/`)
- [ ] `invoice_sample_01.pdf` - PDF格式发票
- [ ] `invoice_sample_02.jpg` - JPG格式发票
- [ ] `invoice_sample_03.png` - PNG格式发票

**必需字段检查**：
- [ ] 包含发票号码 (Invoice Number)
- [ ] 包含发票日期 (Invoice Date)
- [ ] 包含总金额 (Total Amount)
- [ ] 包含供应商 (Vendor)
- [ ] 包含客户 (Customer)

#### 收据 (`test_data/templates/receipt/`)
- [ ] `receipt_sample_01.pdf` - PDF格式收据
- [ ] `receipt_sample_02.jpg` - JPG格式收据

**必需字段检查**：
- [ ] 包含收据号码 (Receipt Number)
- [ ] 包含日期 (Date)
- [ ] 包含总金额 (Total)
- [ ] 包含商户名称 (Merchant)

#### 证件 (`test_data/templates/id_document/`)
- [ ] `id_card_sample_01.jpg` - 身份证样本
- [ ] `passport_sample_01.jpg` - 护照样本
- [ ] `driver_license_sample_01.jpg` - 驾照样本

**必需字段检查**：
- [ ] 包含姓名 (Name)
- [ ] 包含证件号码 (ID Number)
- [ ] 包含出生日期 (Date of Birth)
- [ ] 包含有效期 (Expiry Date)

#### 名片 (`test_data/templates/business_card/`)
- [ ] `business_card_sample_01.jpg` - 名片样本1
- [ ] `business_card_sample_02.png` - 名片样本2

**必需字段检查**：
- [ ] 包含姓名 (Name)
- [ ] 包含职位 (Title)
- [ ] 包含公司 (Company)
- [ ] 包含电话 (Phone)
- [ ] 包含邮箱 (Email)

#### 合同 (`test_data/templates/contract/`)
- [ ] `contract_sample_01.pdf` - 合同样本

**必需字段检查**：
- [ ] 包含合同编号 (Contract Number)
- [ ] 包含签署日期 (Sign Date)
- [ ] 包含甲方 (Party A)
- [ ] 包含乙方 (Party B)

---

## 📝 文件准备说明

### 文件获取方式

1. **使用真实文档**（推荐，注意隐私）
   - 使用您自己的发票、收据、证件等
   - 扫描或拍照保存为 PDF/图片格式
   - ⚠️ **重要**：请移除敏感信息（如真实身份证号、银行卡号）

2. **生成测试文档**
   - 使用在线工具生成示例发票/收据
   - 使用文档生成工具创建测试 PDF

3. **使用公开样本**
   - 搜索公开的文档样本（注意版权）
   - 使用测试数据生成器

### 文件要求

- **格式**：PDF (`.pdf`), JPG (`.jpg`, `.jpeg`), PNG (`.png`), TIFF (`.tiff`, `.tif`)
- **大小**：建议单个文件 < 10MB
- **命名**：使用有意义的文件名，避免特殊字符
- **质量**：确保文件清晰可读

### 隐私保护

如果使用真实文档：
- ✅ 移除敏感信息（身份证号、银行卡号、真实地址等）
- ✅ 仅用于测试目的
- ✅ 测试后及时删除或妥善保管
- ❌ 不要提交到公共代码仓库

---

## 🎯 快速测试文件准备

### 最小测试集（快速开始）

如果时间有限，至少准备以下文件：

- [ ] 1 个 PDF 文件（任意类型）
- [ ] 1 个图片文件（JPG 或 PNG）
- [ ] 1 个发票样本（PDF 或图片）
- [ ] 1 个收据样本（PDF 或图片）
- [ ] 1 个证件样本（图片）

这些文件足以完成基本功能测试。

---

## ✅ 验证步骤

准备完文件后，请验证：

1. **文件存在性**
   ```bash
   # 检查文件是否存在
   ls test_data/templates/invoice/
   ls test_data/templates/receipt/
   ls test_data/templates/id_document/
   ```

2. **文件格式**
   - 确认文件扩展名正确
   - 确认文件可以正常打开

3. **文件内容**
   - 确认文件内容清晰可读
   - 确认包含必要的字段信息

---

## 📚 相关文档

- 测试数据说明：`test_data/README.md`
- 手动测试步骤：`docs/MANUAL_TESTING_GUIDE.md`
- API 文档：`http://localhost:8000/docs`

