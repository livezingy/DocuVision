"""FormulaService failure grading tests.

Uses dynamic module loading to avoid app.services package side effects.
"""

from pathlib import Path
import importlib.util


_FORMULA_SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "formula_service.py"
_SPEC = importlib.util.spec_from_file_location("formula_service_for_tests", _FORMULA_SERVICE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load formula_service module from {_FORMULA_SERVICE_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
FormulaService = _MODULE.FormulaService


def test_formula_service_init_unavailable_grading() -> None:
    service = FormulaService(device="cpu")

    # Avoid importing paddlex in unit test.
    service._ensure_pipeline = lambda: False  # type: ignore[assignment]
    service._init_error = "mock init failure"

    result = service.recognize("dummy.png")

    assert result["ok"] is False
    assert result["error_code"] == "init_unavailable"
    assert result["error_level"] == "hard"
    assert result["failure_stage"] == "init"


def test_formula_service_gpu_runtime_grading() -> None:
    service = FormulaService(device="cpu")

    service._ensure_pipeline = lambda: True  # type: ignore[assignment]

    def _raise_gpu_error(*args, **kwargs):
        raise RuntimeError("CUBLAS_STATUS_NOT_INITIALIZED")

    service._run_once_with_rebuild = _raise_gpu_error  # type: ignore[assignment]

    result = service.recognize("dummy.png", two_stage_threshold_retry=False)

    assert result["ok"] is False
    assert result["error_code"] == "gpu_runtime_error"
    assert result["error_level"] == "hard"
    assert result["failure_stage"] == "inference"
