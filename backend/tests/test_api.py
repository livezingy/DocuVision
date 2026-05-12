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

        print(f"{PASS} Engines API works")
        print(f"   OCR engines: {data['ocr']['available']}")
        print(f"   Layout engines: {data['layout']['available']}")
        print(f"   Table engines: {data['table']['available']}")


class TestTemplateAPI:
    """模板 API 测试"""

    @staticmethod
    def _assert_service_only_deprecated(response, path: str):
        """Service-only profile should return HTTP 410 for deprecated template routes."""
        assert response.status_code == 410, f"Expected 410 for {path}, got {response.status_code}"
        try:
            detail = str(response.json().get("detail", ""))
            assert "deprecated" in detail.lower() or "no longer available" in detail.lower()
        except Exception:
            pass

    def test_list_templates(self):
        """测试模板列表"""
        response = requests.get(f"{API_BASE_URL}/templates", timeout=5)
        self._assert_service_only_deprecated(response, "/api/v1/templates")
        print(f"{PASS} Templates list route is deprecated as expected (410)")

    def test_get_template(self):
        """测试获取模板详情"""
        response = requests.get(f"{API_BASE_URL}/templates/invoice", timeout=5)
        self._assert_service_only_deprecated(response, "/api/v1/templates/{template_id}")
        print(f"{PASS} Template detail route is deprecated as expected (410)")

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

        self._assert_service_only_deprecated(response, "/api/v1/templates/match")
        print(f"{PASS} Template match route is deprecated as expected (410)")


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

