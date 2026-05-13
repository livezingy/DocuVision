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

为了快速开始测试，至少需要：

```
test_data/
├── acceptance/          # 验收说明与矩阵（本目录）
├── Azure/               # Azure 参考 JSON
├── TestResult/          # 本地/云端临时输出（不提交 Git）
└── testfiles/
    ├── templates/
    │   ├── invoice/
    │   │   └── invoice_sample_01.pdf  (或 .jpg)
    │   ├── receipt/
    │   │   └── receipt_sample_01.jpg
    │   └── id_document/
    │       └── id_card_sample_01.jpg
    └── images/
        └── scanned/
            └── scanned_page_01.jpg
```

---

## ✅ 验证文件准备

运行以下命令验证：

```powershell
Test-Path test_data\testfiles\templates\invoice\invoice_sample_01.pdf
Test-Path test_data\testfiles\templates\receipt\receipt_sample_01.jpg
Test-Path test_data\testfiles\templates\id_document\id_card_sample_01.jpg
```

---

## 🎯 开始测试

文件准备完成后，参考：
- **详细测试步骤**：`docs/MANUAL_TESTING_GUIDE.md`
- **API 文档**：`http://localhost:8000/docs`

