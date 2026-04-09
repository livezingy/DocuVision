"""SealService grading and adapter tests.

Uses dynamic module loading to avoid app.services package side effects.
"""

from pathlib import Path
import importlib.util


_SEAL_SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "seal_service.py"
_SPEC = importlib.util.spec_from_file_location("seal_service_for_tests", _SEAL_SERVICE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Unable to load seal_service module from {_SEAL_SERVICE_PATH}")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
SealService = _MODULE.SealService
adapt_seal_results_for_backend = _MODULE.adapt_seal_results_for_backend


def test_seal_service_init_unavailable_grading() -> None:
    service = SealService(device="cpu")

    service._ensure_pipeline = lambda: False  # type: ignore[assignment]
    service._init_error = "mock init failure"

    result = service.recognize("dummy.png")

    assert result["ok"] is False
    assert result["error_code"] == "init_unavailable"
    assert result["error_level"] == "hard"
    assert result["failure_stage"] == "init"


def test_seal_service_gpu_runtime_grading() -> None:
    service = SealService(device="cpu")

    service._ensure_pipeline = lambda: True  # type: ignore[assignment]

    def _raise_gpu_error(*args, **kwargs):
        raise RuntimeError("CUDA out of memory")

    service._run_once_with_rebuild = _raise_gpu_error  # type: ignore[assignment]

    result = service.recognize("dummy.png")

    assert result["ok"] is False
    assert result["error_code"] == "gpu_runtime_error"
    assert result["error_level"] == "hard"
    assert result["failure_stage"] == "inference"


def test_adapt_seal_results_for_backend() -> None:
    unwrapped_results = [
        {
            "seal_res_list": [
                {
                    "label": "official_seal",
                    "shape": "circle",
                    "text_on_seal": "XX company",
                    "score": 0.93,
                    "dt_polys": [10, 20, 60, 80],
                }
            ]
        }
    ]

    adapted = adapt_seal_results_for_backend(unwrapped_results, page_number=1, reading_order_start=11)

    assert len(adapted["view_seals"]) == 1
    assert len(adapted["fused_seal_blocks"]) == 1

    view_item = adapted["view_seals"][0]
    assert view_item["kind"] == "seal"
    assert view_item["processing_status"] == "recognized"
    assert view_item["reading_order"] == 11
    assert view_item["payload"]["label"] == "official_seal"

    fused_item = adapted["fused_seal_blocks"][0]
    assert fused_item["type"] == "seal"
    assert fused_item["processing_status"] == "recognized"
    assert fused_item["source"] == "seal_recognition"
    assert fused_item["provenance"]["merge_strategy"] == "recognized_by_optional_engine"

    quality = adapted["quality_patch"]
    assert quality["seal_blocks_total"] == 1
    assert quality["seal_blocks_recognized"] == 1
    assert quality["seal_count"] == 1
