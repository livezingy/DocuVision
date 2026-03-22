#!/usr/bin/env python3
"""
Test Script: Layout Analysis Standalone Fix Verification

This script tests whether the FormData boolean encoding fix resolves the issue
where layout analysis alone fails to extract content.

Test Scenarios:
1. ✅ Layout Analysis ONLY (enable_layout=1, enable_ocr=0, enable_table=0)
2. ✅ OCR ONLY (enable_layout=0, enable_ocr=1, enable_table=0)
3. ✅ Table Extraction ONLY (enable_layout=0, enable_ocr=0, enable_table=1)
4. ✅ All Enabled (enable_layout=1, enable_ocr=1, enable_table=1)

Expected Results:
- Before fix: Scenario 1 would return empty elements
- After fix: All scenarios should work correctly

Usage:
    python test_layout_fix.py

Run this script on the cloud server where PaddleOCR is installed.
"""

import requests
import json
import time
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
TEST_IMAGE_PATH = r"D:\3_PROJECTS\DocuVision\test_data\images\scanned\scanned_page_02.jpg"

# Test cases
TEST_CASES = [
    {
        "name": "Layout Analysis ONLY",
        "options": {
            "enable_layout": True,
            "enable_ocr": False,
            "enable_table": False,
            "enable_nlp": False
        },
        "expected_min_elements": 1,  # Should detect at least 1 layout element
        "description": "Tests if layout analysis works standalone"
    },
    {
        "name": "OCR Recognition ONLY",
        "options": {
            "enable_layout": False,
            "enable_ocr": True,
            "enable_table": False,
            "enable_nlp": False
        },
        "expected_min_text_blocks": 1,  # Should detect at least 1 text block
        "description": "Tests if OCR works standalone (baseline check)"
    },
    {
        "name": "Table Extraction ONLY",
        "options": {
            "enable_layout": False,
            "enable_ocr": False,
            "enable_table": True,
            "enable_nlp": False
        },
        "expected_min_tables": 0,  # May or may not have tables, just check it doesn't crash
        "description": "Tests if table extraction works standalone"
    },
    {
        "name": "All Features Enabled",
        "options": {
            "enable_layout": True,
            "enable_ocr": True,
            "enable_table": True,
            "enable_nlp": False
        },
        "expected_min_elements": 1,
        "expected_min_text_blocks": 1,
        "description": "Tests full pipeline integration"
    }
]


def upload_and_analyze(file_path: str, options: dict) -> dict:
    """
    Upload file and analyze with specified options.

    Returns:
        dict: Analysis result or error information
    """
    try:
        # Prepare form data
        files = {'file': open(file_path, 'rb')}

        # CRITICAL: Send booleans as "1"/"0" strings for FastAPI parsing
        data = {}
        for key, value in options.items():
            if isinstance(value, bool):
                data[key] = '1' if value else '0'
            elif value is not None:
                data[key] = str(value)

        print(f"\n📤 Uploading file with options:")
        for key, value in data.items():
            print(f"   {key}: {value} ({type(value).__name__})")

        # Make request
        response = requests.post(
            f"{API_BASE_URL}/analyze",
            files=files,
            data=data,
            timeout=120  # 2 minute timeout for processing
        )

        files['file'].close()

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }

        task_info = response.json()
        task_id = task_info.get('task_id')

        if not task_id:
            return {
                "success": False,
                "error": "No task_id in response"
            }

        # Poll for results
        print(f"⏳ Waiting for task {task_id} to complete...")
        max_poll_attempts = 60  # Poll for up to 60 seconds
        poll_interval = 1  # 1 second between polls

        for attempt in range(max_poll_attempts):
            time.sleep(poll_interval)

            status_response = requests.get(
                f"{API_BASE_URL}/tasks/{task_id}",
                timeout=10
            )

            if status_response.status_code != 200:
                continue

            task_status = status_response.json()
            status = task_status.get('status')
            progress = task_status.get('progress', 0)

            print(f"   Progress: {progress}% | Status: {status}")

            if status == 'completed':
                return {
                    "success": True,
                    "task_id": task_id,
                    "result": task_status.get('result'),
                    "full_response": task_status
                }
            elif status == 'failed':
                return {
                    "success": False,
                    "error": task_status.get('message', 'Unknown error')
                }
            elif status == 'cancelled':
                return {
                    "success": False,
                    "error": "Task cancelled"
                }

        return {
            "success": False,
            "error": f"Timeout after {max_poll_attempts} seconds"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def validate_result(test_name: str, result: dict, expectations: dict) -> tuple:
    """
    Validate if result meets expectations.

    Returns:
        tuple: (passed: bool, message: str)
    """
    if not result:
        return False, "❌ No result returned"

    # Check layout elements
    if 'expected_min_elements' in expectations:
        layout = result.get('layout', {})
        elements = layout.get('elements', [])
        expected_count = expectations['expected_min_elements']

        if len(elements) < expected_count:
            return False, f"❌ Expected ≥{expected_count} layout elements, got {len(elements)}"

        print(f"   ✅ Layout elements: {len(elements)} (expected ≥{expected_count})")

        # Log element types
        type_counts = {}
        for elem in elements:
            elem_type = elem.get('type', 'unknown')
            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

        print(f"   📊 Element types: {type_counts}")

    # Check OCR text blocks
    if 'expected_min_text_blocks' in expectations:
        text_blocks = result.get('text_blocks', [])
        expected_count = expectations['expected_min_text_blocks']

        if len(text_blocks) < expected_count:
            return False, f"❌ Expected ≥{expected_count} text blocks, got {len(text_blocks)}"

        print(f"   ✅ Text blocks: {len(text_blocks)} (expected ≥{expected_count})")

        # Show sample text
        if text_blocks:
            sample_text = text_blocks[0].get('text', '')[:50]
            print(f"   📝 Sample: '{sample_text}...'")

    # Check tables
    if 'expected_min_tables' in expectations:
        tables = result.get('tables', [])
        expected_count = expectations['expected_min_tables']

        if len(tables) < expected_count:
            return False, f"❌ Expected ≥{expected_count} tables, got {len(tables)}"

        print(f"   ✅ Tables: {len(tables)} (expected ≥{expected_count})")

    return True, "✅ All expectations met"


def run_tests():
    """Run all test cases and generate report."""

    print("=" * 80)
    print("LAYOUT ANALYSIS STANDALONE FIX - VERIFICATION TEST")
    print("=" * 80)
    print(f"\n📁 Test Image: {TEST_IMAGE_PATH}")
    print(f"🔗 API URL: {API_BASE_URL}")
    print(f"📋 Test Cases: {len(TEST_CASES)}\n")

    # Verify file exists
    if not Path(TEST_IMAGE_PATH).exists():
        print(f"❌ ERROR: Test image not found: {TEST_IMAGE_PATH}")
        return

    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n{'=' * 80}")
        print(f"TEST CASE {i}/{len(TEST_CASES)}: {test_case['name']}")
        print(f"{'=' * 80}")
        print(f"📝 Description: {test_case['description']}")

        # Run test
        result = upload_and_analyze(TEST_IMAGE_PATH, test_case['options'])

        if not result['success']:
            print(f"\n❌ TEST FAILED: {result['error']}")
            results.append({
                "test": test_case['name'],
                "passed": False,
                "error": result['error']
            })
            continue

        # Validate result
        print(f"\n🔍 Validating results...")
        passed, message = validate_result(
            test_case['name'],
            result.get('result'),
            test_case
        )

        print(f"\n{message}")

        results.append({
            "test": test_case['name'],
            "passed": passed,
            "details": result.get('result'),
            "full_response": result.get('full_response')
        })

    # Generate summary report
    print(f"\n{'=' * 80}")
    print("TEST SUMMARY REPORT")
    print(f"{'=' * 80}")

    passed_count = sum(1 for r in results if r['passed'])
    total_count = len(results)

    print(f"\nPassed: {passed_count}/{total_count}")

    for result in results:
        status_icon = "✅" if result['passed'] else "❌"
        print(f"\n{status_icon} {result['test']}")

        if not result['passed']:
            print(f"   Error: {result.get('error', 'Unknown')}")

    # Detailed results
    print(f"\n{'=' * 80}")
    print("DETAILED RESULTS")
    print(f"{'=' * 80}")

    for result in results:
        print(f"\n{result['test']}:")

        if result['passed']:
            details = result.get('details', {})

            if 'layout' in details:
                elements = details['layout'].get('elements', [])
                print(f"  • Layout elements: {len(elements)}")

            if 'text_blocks' in details:
                text_blocks = details.get('text_blocks', [])
                print(f"  • Text blocks: {len(text_blocks)}")

            if 'tables' in details:
                tables = details.get('tables', [])
                print(f"  • Tables: {len(tables)}")
        else:
            print(f"  ❌ Failed: {result.get('error', 'Unknown error')}")

    # Save results to file
    report_file = "layout_fix_test_results.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "summary": {
                "passed": passed_count,
                "total": total_count,
                "success_rate": f"{(passed_count/total_count*100):.1f}%" if total_count > 0 else "N/A"
            },
            "results": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n💾 Full results saved to: {report_file}")
    print(f"\n{'=' * 80}")

    if passed_count == total_count:
        print("🎉 ALL TESTS PASSED! The fix is working correctly.")
    else:
        print("⚠️  SOME TESTS FAILED. Further investigation needed.")

    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    run_tests()
