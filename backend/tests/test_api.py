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

