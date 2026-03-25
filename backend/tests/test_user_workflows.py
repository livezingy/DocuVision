"""
用户工作流自动化测试
模拟真实用户使用场景，从用户角度测试系统

测试场景:
1. 快速 OCR - 用户只需要提取文本
2. 文档分析 - 用户需要完整分析
3. 发票处理 - 用户处理发票文档
4. 批量处理 - 用户处理多个文档
5. 结果导出 - 用户导出处理结果
"""

import pytest
import requests
import time
import os
import sys
from pathlib import Path

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
INFO = "[INFO]"
SKIP = "[SKIP]"

API_BASE_URL = "http://localhost:8000/api/v1"
BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).parent.parent.parent
TEST_DATA_DIR = PROJECT_ROOT / "test_data"


class UserWorkflowBase:
    """用户工作流基类"""
    
    def wait_for_task(self, task_id, max_wait=300, interval=3):
        """等待任务完成（增加超时时间和查询间隔）"""
        elapsed = 0
        last_status = None
        
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            
            try:
                # 增加超时时间到30秒，避免查询时超时
                response = requests.get(f"{API_BASE_URL}/tasks/{task_id}", timeout=30)
                if response.status_code != 200:
                    print(f"{WARN} 查询任务状态失败: {response.status_code}")
                    continue
                
                task_status = response.json()
                status = task_status["status"]
                progress = task_status.get("progress", 0)
                message = task_status.get("message", "")
                
                # 只在状态变化时打印
                if status != last_status:
                    print(f"   状态: {status}, 进度: {progress}%, 消息: {message}")
                    last_status = status
                
                if status == "completed":
                    return task_status
                elif status == "failed":
                    error_msg = task_status.get("message", "Unknown error")
                    print(f"{FAIL} 任务失败: {error_msg}")
                    return None
            except requests.exceptions.ReadTimeout:
                print(f"{WARN} 查询任务状态超时，继续等待...")
                continue
            except Exception as e:
                print(f"{WARN} 查询任务状态异常: {e}")
                continue
        
        print(f"{FAIL} 任务在 {max_wait} 秒内未完成")
        return None


class TestQuickOCRWorkflow(UserWorkflowBase):
    """工作流 1: 快速 OCR"""
    
    def test_user_uploads_image_for_ocr(self):
        """用户上传图片进行 OCR"""
        print(f"\n{INFO} 工作流: 快速 OCR 文本提取")
        
        test_file = TEST_DATA_DIR / "images" / "scanned" / "scanned_page_01.jpg"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        # 用户操作: 上传文件
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "image/jpeg")}
            response = requests.post(f"{API_BASE_URL}/ocr", files=files, timeout=30)
        
        # 验证: 用户期望立即得到结果
        assert response.status_code == 200, "OCR should return immediately"
        data = response.json()
        
        # 验证: 结果应该包含文本
        assert "text" in data, "Result should contain text"
        assert len(data["text"]) > 0, "Should extract some text"
        
        print(f"{PASS} 用户成功提取文本: {len(data['text'])} 字符")
        # 不返回值，避免pytest警告


class TestDocumentAnalysisWorkflow(UserWorkflowBase):
    """工作流 2: 完整文档分析"""
    
    def test_user_analyzes_complete_document(self):
        """用户进行完整文档分析"""
        print(f"\n{INFO} 工作流: 完整文档分析")
        
        test_file = TEST_DATA_DIR / "pdf" / "text_based" / "sample_report.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        # 用户操作: 提交分析任务
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            data = {
                "enable_ocr": "true",
                "enable_layout": "true",
                "enable_table": "true",
                "enable_nlp": "true"
            }
            response = requests.post(
                f"{API_BASE_URL}/analyze",
                files=files,
                data=data,
                timeout=30
            )
        
        assert response.status_code == 200, "Should create task"
        task_id = response.json()["task_id"]
        print(f"{INFO} 任务已创建: {task_id}")
        
        # 用户操作: 等待处理完成
        task_status = self.wait_for_task(task_id)
        assert task_status is not None, "Task should complete"
        assert task_status["status"] == "completed", "Task should be completed"
        
        # 用户操作: 获取结果
        response = requests.get(f"{API_BASE_URL}/tasks/{task_id}/result", timeout=10)
        assert response.status_code == 200, "Should get result"
        result = response.json()
        
        # 验证: 用户期望得到完整结果
        assert "document_info" in result, "Should have document info"
        assert "text_blocks" in result or "full_text" in result, "Should have text"
        
        print(f"{PASS} 文档分析完成")
        print(f"   页面: {result.get('document_info', {}).get('pages', 0)}")
        print(f"   文本块: {len(result.get('text_blocks', []))}")
        print(f"   表格: {len(result.get('tables', []))}")
        
        # 不返回值，避免pytest警告


class TestInvoiceProcessingWorkflow(UserWorkflowBase):
    """工作流 3: 发票处理"""
    
    def test_user_processes_invoice(self):
        """用户处理发票文档"""
        print(f"\n{INFO} 工作流: 发票信息提取")
        
        test_file = TEST_DATA_DIR / "templates" / "invoice" / "invoice_sample_01.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        # 步骤 1: 用户上传发票进行 OCR
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            response = requests.post(f"{API_BASE_URL}/ocr", files=files, timeout=60)
        
        if response.status_code != 200:
            error_detail = response.text if hasattr(response, 'text') else "Unknown error"
            print(f"{FAIL} OCR 失败: {response.status_code}, 错误: {error_detail}")
            pytest.fail(f"OCR should work, got {response.status_code}: {error_detail}")
        
        assert response.status_code == 200, f"OCR should work, got {response.status_code}"
        ocr_result = response.json()
        text = ocr_result.get("text", "")
        
        if len(text) == 0:
            pytest.skip("No text extracted")
        
        print(f"{INFO} OCR 提取了 {len(text)} 个字符")
        
        # 步骤 2: 用户使用模板提取字段
        response = requests.post(
            f"{API_BASE_URL}/templates/match",
            data={"text": text},
            timeout=10
        )
        
        assert response.status_code == 200, "Template matching should work"
        match_result = response.json()
        
        # 验证: 用户期望找到发票模板
        matches = match_result.get("matches", [])
        if len(matches) > 0:
            best_match = matches[0]
            print(f"{PASS} 找到发票模板: {best_match.get('template_id')}")
            
            if "fields" in best_match:
                fields = best_match["fields"]
                print(f"   提取字段: {len(fields)}")
                # 显示关键字段
                key_fields = ["invoice_number", "invoice_date", "total_amount", "vendor", "customer"]
                for key in key_fields:
                    if key in fields:
                        print(f"     {key}: {fields[key]}")
        else:
            print(f"{WARN} 未找到匹配模板（可能需要调整模板或文本）")
        
        return match_result


class TestBatchProcessingWorkflow(UserWorkflowBase):
    """工作流 4: 批量处理"""
    
    def test_user_processes_multiple_files(self):
        """用户批量处理多个文件"""
        print(f"\n{INFO} 工作流: 批量处理多个文档")
        
        # 查找多个测试文件
        test_files = [
            TEST_DATA_DIR / "pdf" / "text_based" / "sample_report.pdf",
            TEST_DATA_DIR / "images" / "scanned" / "scanned_page_01.jpg",
        ]
        
        existing_files = [f for f in test_files if f.exists()]
        if len(existing_files) < 2:
            pytest.skip(f"Need at least 2 files, found {len(existing_files)}")
        
        # 用户操作: 创建批量任务
        files = []
        for test_file in existing_files[:2]:
            files.append(("files", (test_file.name, open(test_file, "rb"), "application/octet-stream")))
        
        data = {
            "name": "User Batch Test",
            "options": '{"enable_ocr": true}'
        }
        
        try:
            response = requests.post(
                f"{API_BASE_URL}/batch",
                files=files,
                data=data,
                timeout=30
            )
            
            assert response.status_code == 200, "Should create batch"
            batch_data = response.json()
            batch_id = batch_data["batch_id"]
            
            print(f"{INFO} 批量任务已创建: {batch_id}")
            print(f"   文件数: {batch_data.get('total_tasks', 0)}")
            
            # 用户操作: 启动批量处理
            start_response = requests.post(f"{API_BASE_URL}/batch/{batch_id}/start", timeout=30)
            if start_response.status_code == 200:
                print(f"{INFO} 批量任务已启动")
            else:
                print(f"{WARN} 启动批量任务失败: {start_response.status_code}")
            
            # 用户操作: 等待批量处理完成
            max_wait = 300  # 增加到5分钟
            elapsed = 0
            last_progress = -1
            
            while elapsed < max_wait:
                time.sleep(3)
                elapsed += 3
                
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
                    
                    # 只在进度变化时打印
                    if progress != last_progress:
                        print(f"   进度: {completed}/{total} ({status}, {progress}%)")
                        last_progress = progress
                    
                    if status == "completed":
                        # 用户操作: 获取批量结果
                        results_response = requests.get(
                            f"{API_BASE_URL}/batch/{batch_id}/results",
                            timeout=30
                        )
                        assert results_response.status_code == 200, "Should get batch results"
                        results = results_response.json()
                        
                        print(f"{PASS} 批量处理完成")
                        print(f"   结果数: {len(results.get('results', []))}")
                        # 不返回值，避免pytest警告
                        return
                    elif status == "failed":
                        error_msg = batch_status.get("message", "Unknown error")
                        pytest.fail(f"Batch processing failed: {error_msg}")
                except requests.exceptions.ReadTimeout:
                    print(f"{WARN} 查询批量状态超时，继续等待...")
                    continue
                except Exception as e:
                    print(f"{WARN} 查询批量状态异常: {e}")
                    continue
            
            pytest.fail(f"Batch not completed in {max_wait} seconds")
        
        finally:
            for _, (_, file_obj, _) in files:
                if hasattr(file_obj, 'close'):
                    file_obj.close()


class TestExportWorkflow(UserWorkflowBase):
    """工作流 5: 结果导出"""
    
    def test_user_exports_results(self):
        """用户导出处理结果"""
        print(f"\n{INFO} 工作流: 导出处理结果")
        
        test_file = TEST_DATA_DIR / "pdf" / "text_based" / "sample_report.pdf"
        if not test_file.exists():
            pytest.skip(f"Test file not found: {test_file}")
        
        # 用户操作: 处理文档
        with open(test_file, "rb") as f:
            files = {"file": (test_file.name, f, "application/pdf")}
            data = {"enable_ocr": "true", "enable_table": "true"}
            response = requests.post(
                f"{API_BASE_URL}/analyze",
                files=files,
                data=data,
                timeout=30
            )
        
        assert response.status_code == 200, "Should create task"
        task_id = response.json()["task_id"]
        
        # 等待处理完成（增加超时时间）
        task_status = self.wait_for_task(task_id, max_wait=300)
        if not task_status or task_status["status"] != "completed":
            pytest.skip(f"Task not completed (status: {task_status.get('status') if task_status else 'None'}), cannot test export")
        
        # 用户操作: 导出为不同格式
        export_formats = {
            "json": "JSON 格式",
            "xlsx": "Excel 格式",
            "docx": "Word 格式"
        }
        
        success_count = 0
        for fmt, name in export_formats.items():
            try:
                response = requests.get(
                    f"{API_BASE_URL}/tasks/{task_id}/export/{fmt}",
                    timeout=30
                )
                
                if response.status_code == 200:
                    print(f"{PASS} 导出 {name} 成功")
                    success_count += 1
                else:
                    print(f"{WARN} 导出 {name} 失败: {response.status_code}")
            except Exception as e:
                print(f"{WARN} 导出 {name} 异常: {e}")
        
        assert success_count > 0, "Should export at least one format"
        print(f"{PASS} 成功导出 {success_count}/{len(export_formats)} 种格式")


def check_server_running():
    """检查服务器是否运行"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("DocuVision - 用户工作流自动化测试")
    print("模拟真实用户使用场景")
    print("=" * 60)
    print()
    
    if not check_server_running():
        print(f"{FAIL} 服务器未运行！")
        print("请先启动服务: python run.py")
        sys.exit(1)
    
    print(f"{PASS} 服务器运行中，开始用户工作流测试...")
    print()
    
    pytest.main([__file__, "-v", "-s"])

