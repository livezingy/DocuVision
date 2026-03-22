#!/bin/bash
# 手动测试脚本示例（Linux/Mac）
# Windows 用户请参考 example_test_script.ps1

API_BASE="http://localhost:8000/api/v1"

echo "=========================================="
echo "DocuVision 手动测试脚本"
echo "=========================================="
echo ""

# 测试 1: 健康检查
echo "[测试 1] 健康检查"
curl -s "$API_BASE/../health" | jq .
echo ""

# 测试 2: OCR 测试
echo "[测试 2] OCR 文本提取"
if [ -f "images/scanned/scanned_page_01.jpg" ]; then
    curl -X POST "$API_BASE/ocr" \
        -F "file=@images/scanned/scanned_page_01.jpg" | jq .
else
    echo "跳过：测试文件不存在"
fi
echo ""

# 测试 3: 模板列表
echo "[测试 3] 模板列表"
curl -s "$API_BASE/templates" | jq .
echo ""

# 测试 4: 发票模板匹配
echo "[测试 4] 发票模板匹配"
curl -X POST "$API_BASE/templates/match" \
    -F "text=发票号码: INV-2024-001
发票日期: 2024-01-15
总金额: \$1,234.56
供应商: ABC公司
客户: XYZ公司" | jq .
echo ""

echo "=========================================="
echo "测试完成"
echo "=========================================="

