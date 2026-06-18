# 测试数据快速开始

## 🚀 快速准备测试文件

### 步骤 1: 创建测试文件（最简单方式）

如果您有现成的文档，直接复制到相应目录：

```bash
# Windows PowerShell
Copy-Item "您的发票.pdf" "test_data\testfiles\templates\invoice\invoice_sample_01.pdf"
Copy-Item "您的收据.jpg" "test_data\testfiles\templates\receipt\receipt_sample_01.jpg"
Copy-Item "您的证件.jpg" "test_data\testfiles\templates\id_document\id_card_sample_01.jpg"
```

### 步骤 2: 使用在线工具生成测试文件

#### 发票生成器
- 搜索 "invoice generator online"
- 生成示例发票
- 保存为 PDF 或图片

#### 收据生成器
- 搜索 "receipt generator online"
- 生成示例收据
- 保存为 PDF 或图片

### 步骤 3: 使用扫描仪或手机拍照

1. 准备真实文档（注意隐私）
2. 使用扫描仪或手机拍照
3. 保存到相应目录

---

## 📋 最小测试文件集

仓库内**已跟踪**的起步样例（可直接用于 Cloud 验收）：

```
test_data/
├── acceptance/          # 验收说明与矩阵（本目录）
├── Azure/               # Azure 参考 JSON
├── TestResult/          # 本地/云端临时输出（不提交 Git）
└── testfiles/
    ├── invoices/
    │   ├── sample-invoice.png
    │   └── invoice_sample_01.pdf
    ├── images/kie/
    │   └── id_card_sample_01.jpg
    └── pdf/
        └── sample_report.pdf
```

可选：自行添加扫描页至 `testfiles/images/scanned/`（如 `scanned_page_01.jpg`），**不纳入 Git 也可**；矩阵默认用 `sample-invoice.png` 代替。

---

## ✅ 验证文件准备

运行以下命令验证：

```powershell
Test-Path test_data\testfiles\invoices\sample-invoice.png
Test-Path test_data\testfiles\invoices\invoice_sample_01.pdf
Test-Path test_data\testfiles\images\kie\id_card_sample_01.jpg
Test-Path test_data\testfiles\pdf\sample_report.pdf
```

---

## 🎯 开始测试

文件准备完成后，参考：
- **云测步骤**：[docs/architecture/CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md)
- **验收索引**：[test_data/acceptance/README.md](README.md)
- **API 文档**：`http://localhost:8000/docs`

