"""KIE 子包轻量 smoke（不依赖 pytest）。

PaddleNLP UIE 链已移除；本脚本仅校验仍保留的 ``value_typer`` 等无权重逻辑。
运行：``python -m tests.kie._smoke_check``
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path


def _add_app_to_path() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(backend_dir))


_add_app_to_path()


def check_value_typer() -> None:
    from app.services.kie.value_typer import ValueTyper

    assert ValueTyper.to_date("19/2/2024") == "2024-02-19"
    assert ValueTyper.to_date("2024-02-19") == "2024-02-19"
    assert ValueTyper.to_date("19-Feb-2024") == "2024-02-19"
    assert ValueTyper.to_date("not-a-date") is None

    cv = ValueTyper.to_currency("GBP 180.00")
    assert cv is not None and cv.amount == 180.0 and cv.currencyCode == "GBP"
    cv2 = ValueTyper.to_currency("£100")
    assert cv2 is not None and cv2.amount == 100.0 and cv2.currencyCode == "GBP"

    assert ValueTyper.to_number("1,024.50") == 1024.5
    print("[OK] value_typer")


def main() -> int:
    try:
        check_value_typer()
        print("\nAll smoke checks passed.")
        return 0
    except AssertionError as exc:
        traceback.print_exc()
        print(f"\nSMOKE FAILURE: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        traceback.print_exc()
        print(f"\nSMOKE ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
