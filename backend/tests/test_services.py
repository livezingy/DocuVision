"""
自动化测试 - 服务层测试
测试各个服务的初始化和基本功能
"""

import pytest
import sys
import os

# Windows 编码兼容性：使用 ASCII 字符替代 emoji
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ocr_service import OCRService
from app.services.layout_service import LayoutService
from app.services.table_service import TableService
from app.services.nlp_service import NLPService
from app.services.template_service import TemplateService
from app.services.batch_service import BatchService
from app.services.export_service import ExportService


class TestOCRService:
    """OCR 服务测试"""
    
    def test_ocr_service_init(self):
        """测试 OCR 服务初始化"""
        service = OCRService(use_gpu=False)
        assert service is not None
        print(f"{PASS} OCR Service initialized")
    
    def test_ocr_engines_available(self):
        """测试 OCR 引擎可用性"""
        service = OCRService(use_gpu=False)
        engines = service.get_available_engines()
        assert len(engines) > 0, "至少应该有一个 OCR 引擎可用"
        print(f"{PASS} Available OCR engines: {engines}")
    
    def test_ocr_service_ready(self):
        """测试 OCR 服务是否就绪"""
        service = OCRService(use_gpu=False)
        if service.is_ready():
            print(f"{PASS} OCR Service is ready (Primary: {service.get_available_engines()[0]})")
        else:
            print(f"{WARN} OCR Service not ready (may need model download)")


class TestLayoutService:
    """版面分析服务测试"""
    
    def test_layout_service_init(self):
        """测试版面分析服务初始化"""
        service = LayoutService(use_gpu=False)
        assert service is not None
        print(f"{PASS} Layout Service initialized")
    
    def test_layout_engines_available(self):
        """测试版面分析引擎可用性"""
        service = LayoutService(use_gpu=False)
        engines = service.get_available_engines()
        assert len(engines) > 0, "至少应该有一个版面分析引擎可用"
        print(f"{PASS} Available Layout engines: {engines}")


class TestTableService:
    """表格识别服务测试"""
    
    def test_table_service_init(self):
        """测试表格识别服务初始化"""
        service = TableService(use_gpu=False)
        assert service is not None
        print(f"{PASS} Table Service initialized")
    
    def test_table_engines_available(self):
        """测试表格识别引擎可用性"""
        service = TableService(use_gpu=False)
        engines = service.get_available_engines()
        assert len(engines) > 0, "至少应该有一个表格识别引擎可用"
        print(f"{PASS} Available Table engines: {engines}")


class TestNLPService:
    """NLP 服务测试"""
    
    def test_nlp_service_init(self):
        """测试 NLP 服务初始化"""
        service = NLPService(language="en")
        assert service is not None
        print(f"{PASS} NLP Service initialized")
    
    def test_nlp_engines_available(self):
        """测试 NLP 引擎可用性"""
        service = NLPService(language="en")
        engines = service.get_available_engines()
        assert len(engines) > 0, "至少应该有一个 NLP 引擎可用（SimpleNLP 总是可用）"
        print(f"{PASS} Available NLP engines: {engines}")
    
    def test_nlp_keyword_extraction(self):
        """测试关键词提取"""
        service = NLPService(language="en")
        if service.is_ready():
            import asyncio
            result = asyncio.run(service.extract_keywords(
                "This is a test document about artificial intelligence and machine learning.",
                top_k=5
            ))
            assert "keywords" in result
            assert len(result["keywords"]) > 0
            print(f"{PASS} Keyword extraction works: {len(result['keywords'])} keywords found")
        else:
            print(f"{WARN} NLP Service not ready, skipping keyword extraction test")
    
    def test_nlp_entity_extraction(self):
        """测试命名实体识别"""
        service = NLPService(language="en")
        if service.is_ready():
            import asyncio
            result = asyncio.run(service.extract_entities(
                "Apple Inc. was founded in 1976 in Cupertino, California."
            ))
            assert "entities" in result
            print(f"{PASS} Entity extraction works: {len(result.get('entities', []))} entities found")
        else:
            print(f"{WARN} NLP Service not ready, skipping entity extraction test")


class TestTemplateService:
    """模板服务测试"""
    
    def test_template_service_init(self):
        """测试模板服务初始化"""
        service = TemplateService()
        assert service is not None
        print(f"{PASS} Template Service initialized")
    
    def test_preset_templates_loaded(self):
        """测试预置模板是否加载"""
        service = TemplateService()
        templates = service.list_templates()
        assert len(templates) > 0, "应该有预置模板"
        
        template_ids = [t["template_id"] for t in templates]
        assert "invoice" in template_ids, "应该有发票模板"
        assert "receipt" in template_ids, "应该有收据模板"
        assert "id_document" in template_ids, "应该有证件模板"
        
        print(f"{PASS} Preset templates loaded: {len(templates)} templates")
        print(f"   Templates: {', '.join(template_ids)}")
    
    def test_template_field_extraction(self):
        """测试模板字段提取"""
        service = TemplateService()
        import asyncio
        
        # 测试发票模板
        test_text = """
        Invoice Number: INV-2024-001
        Invoice Date: 2024-01-15
        Total Amount: $1,234.56
        Vendor: ABC Company
        Customer: XYZ Corp
        """
        
        result = asyncio.run(service.extract_fields("invoice", test_text))
        assert "fields" in result
        assert "template_id" in result
        print(f"{PASS} Template extraction works: {len(result['fields'])} fields extracted")


class TestBatchService:
    """批量处理服务测试"""
    
    def test_batch_service_init(self):
        """测试批量处理服务初始化"""
        service = BatchService(max_concurrent=3)
        assert service is not None
        print(f"{PASS} Batch Service initialized")
    
    def test_batch_creation(self):
        """测试批量任务创建"""
        service = BatchService(max_concurrent=3)
        
        files = [
            {"file_path": "test1.pdf", "file_name": "test1.pdf"},
            {"file_path": "test2.pdf", "file_name": "test2.pdf"}
        ]
        
        batch = service.create_batch("Test Batch", files, {})
        assert batch is not None
        assert batch.batch_id is not None
        assert batch.total_tasks == 2
        print(f"{PASS} Batch creation works: {batch.batch_id}")


class TestExportService:
    """导出服务测试"""
    
    def test_export_service_init(self):
        """测试导出服务初始化"""
        service = ExportService()
        assert service is not None
        print(f"{PASS} Export Service initialized")
    
    def test_export_to_json(self):
        """测试 JSON 导出"""
        service = ExportService()
        import asyncio
        
        test_data = {
            "text_blocks": [{"text": "Test", "confidence": 0.95}],
            "tables": []
        }
        
        result = asyncio.run(service.to_json(test_data, "test_task"))
        assert result is not None
        assert os.path.exists(result)
        print(f"{PASS} JSON export works: {result}")


if __name__ == "__main__":
    print("=" * 60)
    print("DocuVision - 服务层自动化测试")
    print("=" * 60)
    print()
    
    # 运行所有测试
    pytest.main([__file__, "-v", "-s"])

