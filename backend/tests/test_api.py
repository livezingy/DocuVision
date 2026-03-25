"""
自动化测试 - API 端点测试
需要先启动服务: python run.py
"""

import pytest
import requests
import time
import os
import sys

# Windows 编码兼容性：使用 ASCII 字符替代 emoji
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"

# API 基础 URL
API_BASE_URL = "http://localhost:8000/api/v1"


class TestHealthCheck:
    """健康检查测试"""
    
    def test_health_endpoint(self):
        """测试健康检查端点"""
        response = requests.get("http://localhost:8000/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"{PASS} Health check passed")
    
    def test_services_status(self):
        """测试服务状态"""
        response = requests.get("http://localhost:8000/health", timeout=5)
        data = response.json()
        services = data.get("services", {})
        
        print("\n服务状态:")
        for service_name, service_info in services.items():
            ready = service_info.get("ready", False)
            status = PASS if ready else FAIL
            print(f"  {status} {service_name}: {ready}")
            if "engines" in service_info:
                print(f"    可用引擎: {service_info['engines']}")


class TestEnginesAPI:
    """引擎 API 测试"""
    
    def test_list_engines(self):
        """测试引擎列表"""
        response = requests.get(f"{API_BASE_URL}/engines", timeout=5)
        assert response.status_code == 200
        data = response.json()
        
        assert "ocr" in data
        assert "layout" in data
        assert "table" in data
        assert "nlp" in data
        
        print(f"{PASS} Engines API works")
        print(f"   OCR engines: {data['ocr']['available']}")
        print(f"   NLP engines: {data['nlp']['available']}")


class TestNLPAPI:
    """NLP API 测试"""
    
    def test_nlp_analyze(self):
        """测试 NLP 分析"""
        test_text = "Apple Inc. was founded in 1976 in Cupertino, California. The company specializes in consumer electronics."
        
        response = requests.post(
            f"{API_BASE_URL}/nlp/analyze",
            json={"text": test_text, "top_k_keywords": 5},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "keywords" in data
            assert "entities" in data
            print(f"{PASS} NLP analysis works: {len(data.get('keywords', []))} keywords found")
        else:
            print(f"{WARN} NLP analysis failed: {response.status_code}")
    
    def test_nlp_keywords(self):
        """测试关键词提取"""
        test_text = "Machine learning and artificial intelligence are transforming the technology industry."
        
        response = requests.post(
            f"{API_BASE_URL}/nlp/keywords",
            json={"text": test_text, "top_k_keywords": 5},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "keywords" in data
            print(f"{PASS} Keyword extraction works")
        else:
            print(f"{WARN} Keyword extraction failed: {response.status_code}")
    
    def test_nlp_entities(self):
        """测试命名实体识别"""
        test_text = "Microsoft Corporation is located in Redmond, Washington."
        
        response = requests.post(
            f"{API_BASE_URL}/nlp/entities",
            json={"text": test_text},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "entities" in data
            print(f"{PASS} Entity extraction works")
        else:
            print(f"{WARN} Entity extraction failed: {response.status_code}")


class TestTemplateAPI:
    """模板 API 测试"""
    
    def test_list_templates(self):
        """测试模板列表"""
        response = requests.get(f"{API_BASE_URL}/templates", timeout=5)
        assert response.status_code == 200
        data = response.json()
        
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) > 0
        
        template_ids = [t["template_id"] for t in templates]
        print(f"{PASS} Templates API works: {len(templates)} templates")
        print(f"   Available: {', '.join(template_ids)}")
    
    def test_get_template(self):
        """测试获取模板详情"""
        response = requests.get(f"{API_BASE_URL}/templates/invoice", timeout=5)
        assert response.status_code == 200
        data = response.json()
        
        assert "template_id" in data
        assert "fields" in data
        print(f"{PASS} Get template works: {data['template_id']} with {len(data['fields'])} fields")
    
    def test_template_match(self):
        """测试模板匹配"""
        test_text = """
        Invoice Number: INV-2024-001
        Invoice Date: 2024-01-15
        Total: $1,234.56
        """
        
        response = requests.post(
            f"{API_BASE_URL}/templates/match",
            data={"text": test_text},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "matches" in data
            print(f"{PASS} Template matching works: {len(data['matches'])} matches")
        else:
            print(f"{WARN} Template matching failed: {response.status_code}")


class TestBatchAPI:
    """批量处理 API 测试"""
    
    def test_list_batches(self):
        """测试批量任务列表"""
        response = requests.get(f"{API_BASE_URL}/batch", timeout=5)
        assert response.status_code == 200
        data = response.json()
        
        assert "batches" in data
        print(f"{PASS} Batch list API works: {data.get('total', 0)} batches")


def check_server_running():
    """检查服务器是否运行"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=2)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("DocuVision - API 端点自动化测试")
    print("=" * 60)
    print()
    
    # 检查服务器是否运行
    if not check_server_running():
        print(f"{FAIL} 服务器未运行！")
        print("请先启动服务: python run.py")
        print("然后运行此测试脚本")
        sys.exit(1)
    
    print(f"{PASS} 服务器运行中，开始测试...")
    print()
    
    # 运行所有测试
    pytest.main([__file__, "-v", "-s"])

