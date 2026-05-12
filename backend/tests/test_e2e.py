"""
端到端自动化测试 - 模拟用户完整工作流
从用户使用角度测试系统功能

需要先启动服务: python run.py
需要准备测试文件: test_data/ 目录
"""

import pytest
import requests
import time
import os
import sys
from pathlib import Path

# Windows 编码兼容性
PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"
SKIP = "[SKIP]"

# API 基础 URL
API_BASE_URL = "http://localhost:8000/api/v1"
BASE_URL = "http://localhost:8000"

# 测试文件路径（相对于项目根目录）
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data"


def _poll_task_status(
    task_id: str,
    *,
    max_wait: int = 300,
    interval: int = 3,
    max_consecutive_errors: int = 20,
):
    """轮询任务直到 completed/failed/超时。连续失败达到阈值则 pytest.fail。"""
    elapsed = 0
    last_status = None
    consecutive_errors = 0
    last_diag = ""

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval
        try:
            response = requests.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=30)
        except requests.exceptions.RequestException as exc:
            consecutive_errors += 1
            last_diag = f"request_error:{exc}"
            if consecutive_errors >= max_consecutive_errors:
                pytest.fail(f"任务轮询连续失败 {consecutive_errors} 次: {last_diag}")
            print(f"{WARN} 查询任务状态网络异常: {exc}")
            continue

        if response.status_code != 200:
            consecutive_errors += 1
            last_diag = f"http_{response.status_code}"
            if consecutive_errors >= max_consecutive_errors:
                pytest.fail(f"任务轮询连续 HTTP 失败 {consecutive_errors} 次: {last_diag}")
            print(f"{WARN} 查询任务状态失败: {response.status_code}")
            continue

        consecutive_errors = 0
        task_status = response.json()
        status = task_status["status"]
        progress = task_status.get("progress", 0)
        message = task_status.get("message", "")

        if status != last_status:
            print(f"   状态: {status}, 进度: {progress}%, 消息: {message}")
            last_status = status

        if status == "completed":
            return "completed", task_status
        if status == "failed":
            pytest.fail(f"Task failed: {task_status.get('message', 'Unknown error')}")

    pytest.fail(
        f"Task not completed within {max_wait} seconds "
        f"(last_status={last_status!r}, last_diag={last_diag!r})"
    )


class TestUserScenarios:
    """用户场景测试 - 模拟真实用户使用流程"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """测试前检查"""
        # 检查服务器是否运行
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code != 200:
                pytest.skip("Server not running")
        except:
            pytest.skip("Server not running")

    def test_scenario_1_quick_ocr(self):
        """
        用户场景 1: 快速 OCR 文本提取
        用户需求: 上传一张图片，快速提取文本
        """
        print(f"\n{INFO} 场景 1: 快速 OCR 文本提取")

        # 查找测试图片
        test_file = TEST_DATA_DIR / "images" / "scanned" / "scanned_page_01.jpg"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # 用户操作: 上传文件进行 OCR
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "image/jpeg")}
            response = requests.post(
                f"{API_BASE_URL}/ocr",
                files=files,
                timeout=30
            )

        # 验证结果
        assert response.status_code == 200, f"OCR failed: {response.status_code}"
        data = response.json()

        assert "text" in data, "Missing text field"
        assert "engine" in data, "Missing engine field"
        assert len(data.get("text", "")) > 0, "No text extracted"

        print(f"{PASS} OCR 成功: 提取了 {len(data['text'])} 个字符")
        print(f"   使用引擎: {data.get('engine', 'unknown')}")
        print(f"   置信度: {data.get('confidence', 0):.2f}")

    def test_scenario_2_complete_document_analysis(self):
        """
        用户场景 2: 完整文档分析
        用户需求: 上传 PDF，进行 OCR + Layout + Table 分析（版面管线）
        """
        print(f"\n{INFO} 场景 2: 完整文档分析")

        # 查找测试 PDF
        test_file = TEST_DATA_DIR / "pdf" / "text_based" / "sample_report.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # 步骤 1: 用户提交文档分析任务
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            data = {
                "enable_ocr": "true",
                "enable_layout": "true",
                "enable_table": "true",
            }
            response = requests.post(
                f"{API_BASE_URL}/analyze",
                files=files,
                data=data,
                timeout=30
            )

        assert response.status_code == 200, f"Analysis failed: {response.status_code}"
        task_data = response.json()
        task_id = task_data["task_id"]

        print(f"{INFO} 任务已创建: {task_id}")
        print(f"   初始状态: {task_data['status']}")

        _state, _task_status = _poll_task_status(task_id)

        result_response = requests.get(
            f"{API_BASE_URL}/tasks/{task_id}/result",
            timeout=30,
        )
        assert result_response.status_code == 200, "Failed to get result"
        result = result_response.json()

        assert "document_info" in result, "Missing document_info"
        assert isinstance(result.get("tables", []), list)
        has_layout = isinstance(result.get("layout"), dict) and bool(result.get("layout"))
        view = result.get("view") if isinstance(result.get("view"), dict) else {}
        has_view = bool(view.get("pages"))
        assert has_layout or has_view, "Expected layout or view.pages"

        print(f"{PASS} 文档分析完成")
        print(f"   页面数: {result.get('document_info', {}).get('pages', 0)}")
        print(f"   表格数: {len(result.get('tables', []))}")

    @pytest.mark.skip(reason="Template API 已冻结为 HTTP 410；发票字段见 KIE 与 test_data/acceptance")
    def test_scenario_3_invoice_extraction(self):
        """用户场景 3: 发票信息提取（已由 KIE 路径替代，本用例冻结跳过）"""
        pass

    def test_scenario_4_batch_processing(self):
        """
        用户场景 4: 批量处理多个文档
        用户需求: 上传多个文件，批量处理
        """
        print(f"\n{INFO} 场景 4: 批量处理多个文档")

        # 查找多个测试文件
        test_files = [
            TEST_DATA_DIR / "pdf" / "text_based" / "sample_report.pdf",
            TEST_DATA_DIR / "images" / "scanned" / "scanned_page_01.jpg",
        ]

        existing_files = [f for f in test_files if f.exists()]
        if len(existing_files) < 2:
            pytest.skip(f"Need at least 2 test files, found {len(existing_files)}")

        # 步骤 1: 用户创建批量任务
        files = []
        for test_file in existing_files[:2]:  # 只使用前 2 个文件
            files.append(("files", (test_file.name, open(test_file, "rb"), "application/octet-stream")))

        data = {
            "name": "E2E Test Batch",
            "options": '{"enable_ocr": true, "enable_layout": true}'
        }

        try:
            response = requests.post(
                f"{API_BASE_URL}/batch",
                files=files,
                data=data,
                timeout=30
            )

            assert response.status_code == 200, f"Batch creation failed: {response.status_code}"
            batch_data = response.json()
            batch_id = batch_data["batch_id"]

            print(f"{INFO} 批量任务已创建: {batch_id}")
            print(f"   文件数: {batch_data.get('total_tasks', 0)}")

            # 步骤 2: 启动批量处理
            start_response = requests.post(f"{API_BASE_URL}/batch/{batch_id}/start", timeout=30)
            if start_response.status_code == 200:
                print(f"{INFO} 批量任务已启动")
            else:
                print(f"{WARN} 启动批量任务失败: {start_response.status_code}")

            # 步骤 3: 用户查询批量任务状态
            max_wait = 300  # 最多等待 5 分钟
            wait_interval = 3
            elapsed = 0
            last_status = None

            while elapsed < max_wait:
                time.sleep(wait_interval)
                elapsed += wait_interval

                try:
                    response = requests.get(f"{API_BASE_URL}/batch/{batch_id}", timeout=30)
                    if response.status_code != 200:
                        print(f"{WARN} 查询批量状态失败: {response.status_code}")
                        continue

                    batch_status = response.json()
                    status = batch_status["status"]
                    completed = batch_status.get("completed_tasks", 0)
                    total = batch_status.get("total_tasks", 0)
                    progress = batch_status.get("progress", 0)

                    # 只在状态变化时打印
                    if status != last_status:
                        print(f"   状态: {status}, 完成: {completed}/{total} ({progress}%)")
                        last_status = status

                    if status == "completed":
                        # 步骤 4: 用户获取批量结果
                        results_response = requests.get(
                            f"{API_BASE_URL}/batch/{batch_id}/results",
                            timeout=30
                        )
                        assert results_response.status_code == 200, "Failed to get batch results"
                        results = results_response.json()

                        print(f"{PASS} 批量处理完成")
                        print(f"   结果数: {len(results.get('results', []))}")
                        return
                    elif status == "failed":
                        error_msg = batch_status.get("message", "Unknown error")
                        pytest.fail(f"Batch failed: {error_msg}")
                except requests.exceptions.ReadTimeout:
                    print(f"{WARN} 查询批量状态超时，继续等待...")
                    continue
                except Exception as e:
                    print(f"{WARN} 查询批量状态异常: {e}")
                    continue

            pytest.fail(f"Batch not completed within {max_wait} seconds")

        finally:
            # 关闭文件
            for _, (_, file_obj, _) in files:
                if hasattr(file_obj, 'close'):
                    file_obj.close()

    def test_scenario_5_export_results(self):
        """
        用户场景 5: 导出处理结果
        用户需求: 处理文档后，导出为不同格式（JSON、Excel、Word）
        """
        print(f"\n{INFO} 场景 5: 导出处理结果")

        # 查找测试文件
        test_file = TEST_DATA_DIR / "pdf" / "text_based" / "sample_report.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")

        # 步骤 1: 处理文档
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            data = {"enable_ocr": "true", "enable_table": "true"}
            response = requests.post(
                f"{API_BASE_URL}/analyze",
                files=files,
                data=data,
                timeout=60  # 增加上传超时时间
            )

        assert response.status_code == 200, "Analysis failed"
        task_id = response.json()["task_id"]

        _poll_task_status(task_id)

        export_formats = ["json", "xlsx", "docx"]
        for fmt in export_formats:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/tasks/{task_id}/export/{fmt}",
                    timeout=30,
                )
                if response.status_code == 200:
                    print(f"{PASS} 导出 {fmt.upper()} 成功")
                    if fmt == "json":
                        data = response.json()
                        print(f"   内容类型: {type(data)}")
                    else:
                        print(f"   文件大小: {len(response.content)} bytes")
                else:
                    print(f"{WARN} 导出 {fmt.upper()} 失败: {response.status_code}")
            except Exception as e:
                print(f"{WARN} 导出 {fmt.upper()} 异常: {e}")


class TestEndToEndWorkflow:
    """端到端工作流测试 - 完整业务流程"""

    def test_full_workflow_document_processing(self):
        """
        完整工作流: 文档处理全流程
        1. 健康检查
        2. 查看可用引擎
        3. OCR 提取文本
        4. 模板列表（冻结时为 410）
        """
        print(f"\n{INFO} 端到端工作流: 文档处理全流程")

        # 步骤 1: 健康检查
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        assert response.status_code == 200, "Health check failed"
        health_data = response.json()
        assert health_data["status"] == "healthy", "Service not healthy"
        print(f"{PASS} 步骤 1: 健康检查通过")

        # 步骤 2: 查看可用引擎
        response = requests.get(f"{API_BASE_URL}/engines", timeout=5)
        assert response.status_code == 200, "Engines API failed"
        engines_data = response.json()
        print(f"{PASS} 步骤 2: 可用引擎查询成功")
        print(f"   OCR: {engines_data.get('ocr', {}).get('available', [])}")
        print(f"   Layout: {engines_data.get('layout', {}).get('available', [])}")

        # 步骤 3: OCR 提取文本（如果有测试文件）
        test_file = TEST_DATA_DIR / "images" / "scanned" / "scanned_page_01.jpg"
        if test_file.exists():
            with open(test_file, "rb") as f:
                files = {"file": (test_file.name, f, "image/jpeg")}
                response = requests.post(f"{API_BASE_URL}/ocr", files=files, timeout=30)

            if response.status_code == 200:
                ocr_data = response.json()
                print(f"{PASS} 步骤 3: OCR 提取成功")
                print(f"   提取文本长度: {len(ocr_data.get('text', ''))}")
            else:
                print(f"{WARN} 步骤 3: OCR 提取失败")
        else:
            print(f"{SKIP} 步骤 3: 跳过 OCR（测试文件不存在）")

        # 步骤 4: 模板列表
        response = requests.get(f"{API_BASE_URL}/templates", timeout=5)
        # Service-only profile deprecates template APIs with 410 Gone.
        if response.status_code == 410:
            print(f"{SKIP} 步骤 4: 模板接口已在 service-only 配置中弃用 (HTTP 410)")
            print(f"{PASS} 端到端工作流测试完成")
            return

        assert response.status_code == 200, "Templates API failed"
        templates_data = response.json()
        print(f"{PASS} 步骤 4: 模板列表查询成功")
        print(f"   可用模板数: {len(templates_data.get('templates', []))}")

        print(f"{PASS} 端到端工作流测试完成")


def check_server_running():
    """检查服务器是否运行"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("DocuVision - 端到端自动化测试")
    print("从用户使用角度测试系统功能")
    print("=" * 60)
    print()

    # 检查服务器是否运行
    if not check_server_running():
        print(f"{FAIL} 服务器未运行！")
        print("请先启动服务: python run.py")
        print("然后运行此测试脚本")
        sys.exit(1)

    print(f"{PASS} 服务器运行中，开始端到端测试...")
    print()

    # 运行所有测试
    pytest.main([__file__, "-v", "-s"])

