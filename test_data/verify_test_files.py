#!/usr/bin/env python3
"""
测试文件验证脚本
检查测试文件是否准备完整
"""

import os
from pathlib import Path

# 测试文件目录
BASE_DIR = Path(__file__).parent

# 必需的文件列表
REQUIRED_FILES = {
    "pdf/text_based": [
        "sample_report.pdf",
        "sample_article.pdf",
        "sample_form.pdf"
    ],
    "pdf/image_based": [
        "scanned_document.pdf",
        "scanned_invoice.pdf",
        "scanned_receipt.pdf"
    ],
    "pdf/mixed": [
        "mixed_document.pdf"
    ],
    "images/scanned": [
        "scanned_page_01.jpg",
        "scanned_invoice.png",
        "scanned_receipt.tiff"
    ],
    "images/photos": [
        "document_photo.jpg",
        "id_card_photo.png"
    ],
    "images/screenshots": [
        "webpage_screenshot.png",
        "app_screenshot.jpg"
    ],
    "templates/invoice": [
        "invoice_sample_01.pdf",
        "invoice_sample_02.jpg",
        "invoice_sample_03.png"
    ],
    "templates/receipt": [
        "receipt_sample_01.pdf",
        "receipt_sample_02.jpg"
    ],
    "templates/id_document": [
        "id_card_sample_01.jpg",
        "passport_sample_01.jpg",
        "driver_license_sample_01.jpg"
    ],
    "templates/business_card": [
        "business_card_sample_01.jpg",
        "business_card_sample_02.png"
    ],
    "templates/contract": [
        "contract_sample_01.pdf"
    ]
}

# 最小测试文件集（快速开始）
MINIMAL_FILES = {
    "pdf/text_based": ["sample_report.pdf"],
    "images/scanned": ["scanned_page_01.jpg"],
    "templates/invoice": ["invoice_sample_01.pdf"],
    "templates/receipt": ["receipt_sample_01.jpg"],
    "templates/id_document": ["id_card_sample_01.jpg"]
}


def check_files(file_list, minimal=False):
    """检查文件是否存在"""
    found = []
    missing = []
    
    for category, files in file_list.items():
        category_path = BASE_DIR / category
        for filename in files:
            file_path = category_path / filename
            if file_path.exists():
                found.append((category, filename))
            else:
                missing.append((category, filename))
    
    return found, missing


def print_results(found, missing, title="测试文件检查结果"):
    """打印检查结果"""
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()
    
    if found:
        print(f"[PASS] 找到 {len(found)} 个文件:")
        for category, filename in found:
            print(f"  [OK] {category}/{filename}")
        print()
    
    if missing:
        print(f"[MISS] 缺少 {len(missing)} 个文件:")
        for category, filename in missing:
            print(f"  [NO] {category}/{filename}")
        print()
    else:
        print("[PASS] 所有必需文件都已准备！")
        print()


def main():
    """主函数"""
    print("DocuVision - 测试文件验证工具")
    print()
    
    # 检查完整文件集
    print("检查完整测试文件集...")
    found_full, missing_full = check_files(REQUIRED_FILES)
    print_results(found_full, missing_full, "完整测试文件集")
    
    # 检查最小文件集
    print("检查最小测试文件集...")
    found_min, missing_min = check_files(MINIMAL_FILES, minimal=True)
    print_results(found_min, missing_min, "最小测试文件集")
    
    # 统计信息
    print("=" * 60)
    print("统计信息")
    print("=" * 60)
    print(f"完整文件集: {len(found_full)}/{len(found_full) + len(missing_full)} 已准备")
    print(f"最小文件集: {len(found_min)}/{len(found_min) + len(missing_min)} 已准备")
    print()
    
    # 建议
    if len(missing_min) == 0:
        print("[PASS] 最小测试文件集已准备，可以开始测试！")
        print("参考文档: docs/MANUAL_TESTING_GUIDE.md")
    elif len(found_min) > 0:
        print("[WARN] 部分文件已准备，可以开始基本测试")
        print("建议: 准备更多文件以进行完整测试")
    else:
        print("[INFO] 请先准备测试文件")
        print("参考: test_data/README.md")
        print("快速开始: test_data/QUICK_START.md")
    
    print()


if __name__ == "__main__":
    main()

