"""
Frontend Display Issue Diagnostic Script
Run this to collect information about text spacing and layout display issues.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))


def check_text_normalization():
    """Test current text normalization behavior"""
    print("=" * 80)
    print("TEXT NORMALIZATION TEST")
    print("=" * 80)

    try:
        from app.services.layout_service import LayoutService

        service = LayoutService()

        test_cases = [
            # (input, expected_behavior)
            ("Hello World", "Should preserve normal spacing"),
            ("FuelSaving", "Should split camelCase"),
            ("FuelSavingTechnologies", "Should split multiple capitals"),
            ("Test123Data", "Should separate numbers from letters"),
            ("CO2Emission", "Should handle acronyms"),
            ("  Multiple   Spaces  ", "Should normalize multiple spaces"),
            ("Line1\nLine2", "Should handle line breaks"),
        ]

        print("\nTesting _normalize_text() method:")
        for test_input, expectation in test_cases:
            result = service._normalize_text(test_input)
            status = "✓" if result != test_input else "⚠"
            print(f"{status} Input:    '{test_input}'")
            print(f"  Output:   '{result}'")
            print(f"  Expected: {expectation}")
            print()

    except Exception as e:
        print(f"✗ Error testing text normalization: {e}")
        import traceback
        traceback.print_exc()


def check_layout_parsing():
    """Simulate layout parsing with mock data"""
    print("=" * 80)
    print("LAYOUT PARSING SIMULATION")
    print("=" * 80)

    # Mock PPStructureV3 output structure
    mock_result = [{
        'type': 'text',
        'bbox': [100, 50, 300, 80],
        'score': 0.95,
        'res': [
            ('Fuel', 0.99),
            ('Saving', 0.98),
            ('Technologies', 0.97)
        ]
    }]

    try:
        from app.services.layout_service import LayoutService

        service = LayoutService()

        # Simulate _parse_result call
        print("\nParsing mock layout result...")
        elements = service._parse_result(mock_result, page_num=1)

        if elements:
            elem = elements[0]
            print(f"✓ Parsed element: type={elem['type']}")
            print(f"  Bbox: {elem['bbox']}")
            print(f"  Text: '{elem.get('text', 'N/A')}'")
            print(f"  Confidence: {elem.get('confidence', 0)}")
        else:
            print("✗ No elements parsed from mock result")

    except Exception as e:
        print(f"✗ Error in layout parsing simulation: {e}")
        import traceback
        traceback.print_exc()


def check_api_response_format():
    """Check if API response format matches frontend expectations"""
    print("=" * 80)
    print("API RESPONSE FORMAT CHECK")
    print("=" * 80)

    # Expected frontend format
    expected_format = {
        "elements": [
            {
                "id": "p1_e0",
                "page": 1,
                "type": "text",
                "bbox": {"x": 100, "y": 50, "width": 200, "height": 30},
                "text": "Sample text",
                "confidence": 0.95
            }
        ],
        "metadata": {
            "total_elements": 1
        }
    }

    print("\nExpected frontend format:")
    import json
    print(json.dumps(expected_format, indent=2))

    # Check what backend actually returns
    try:
        from app.services.layout_service import LayoutService

        service = LayoutService()

        # Mock a more complete result
        mock_result = [{
            'type': 'text',
            'bbox': [100, 50, 300, 80],
            'score': 0.95,
            'res': [('Hello', 0.99), ('World', 0.98)]
        }]

        elements = service._parse_result(mock_result, page_num=1)

        actual_response = {
            "elements": elements,
            "metadata": {
                "total_elements": len(elements)
            }
        }

        print("\nActual backend output:")
        # Convert to dict for JSON serialization
        serializable_elements = []
        for elem in elements:
            if hasattr(elem, 'to_dict'):
                serializable_elements.append(elem.to_dict())
            elif isinstance(elem, dict):
                serializable_elements.append(elem)

        print(json.dumps({
            "elements": serializable_elements,
            "metadata": {"total_elements": len(serializable_elements)}
        }, indent=2))

    except Exception as e:
        print(f"✗ Error checking API response format: {e}")


def check_frontend_files():
    """Check if frontend files exist and have rendering logic"""
    print("=" * 80)
    print("FRONTEND FILE CHECK")
    print("=" * 80)

    frontend_files = [
        "frontend/index.html",
        "frontend/app.js",
        "frontend/layout-annotation.js",
        "frontend/styles.css"
    ]

    for file_path in frontend_files:
        full_path = Path(__file__).parent / file_path
        if full_path.exists():
            print(f"✓ Found: {file_path}")

            # Check for key functions
            if file_path.endswith('.js'):
                content = full_path.read_text(encoding='utf-8')

                if 'app.js' in file_path:
                    if 'renderLayout' in content or 'drawLayout' in content:
                        print(f"  ✓ Has layout rendering function")
                    else:
                        print(f"  ⚠ No layout rendering function found")

                    if 'fetch' in content or 'axios' in content:
                        print(f"  ✓ Has API call logic")

                if 'layout-annotation.js' in file_path:
                    if 'canvas' in content.lower():
                        print(f"  ✓ Uses canvas element")
                    if 'draw' in content.lower():
                        print(f"  ✓ Has drawing logic")
        else:
            print(f"✗ Missing: {file_path}")


def recommend_fixes():
    """Provide recommendations based on diagnostic results"""
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY & RECOMMENDATIONS")
    print("=" * 80)

    print("""
Based on the diagnostic results above:

TEXT SPACING ISSUES:
If text shows words concatenated (e.g., "FuelSaving" instead of "Fuel Saving"):
→ Fix location: backend/app/services/layout_service.py::_normalize_text()
→ Also check: backend/app/modules/layout_analysis/engines/ppstructure_engine.py::_parse_result()
→ Solution: Enhance regex patterns to detect word boundaries in camelCase/PascalCase

LAYOUT NOT DISPLAYING:
If layout regions are detected but not shown in frontend:
→ Check 1: Verify API response bbox format matches frontend expectations
→ Check 2: Inspect browser console for JavaScript errors
→ Check 3: Verify canvas coordinate scaling (image size vs canvas size)
→ Fix locations:
   - Backend: backend/app/main.py (API endpoint /api/analyze)
   - Frontend: frontend/app.js (rendering logic)
   - Frontend: frontend/layout-annotation.js (canvas drawing)

NEXT STEPS:
1. Run this script to understand current behavior
2. Review docs/FRONTEND_DISPLAY_FIX_PLAN.md for detailed action plan
3. Start with Phase 1: Add debug logging
4. Then proceed to Phase 2: Text spacing fixes
5. Finally Phase 3: Layout display fixes
""")


def main():
    """Run all diagnostics"""
    print("\n" + "=" * 80)
    print("FRONTEND DISPLAY ISSUE DIAGNOSTIC")
    print("=" * 80)
    print()

    check_text_normalization()
    print()
    check_layout_parsing()
    print()
    check_api_response_format()
    print()
    check_frontend_files()
    print()
    recommend_fixes()


if __name__ == "__main__":
    main()
