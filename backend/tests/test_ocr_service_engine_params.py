"""OCR engine init-param contract: the OCR endpoint's pixel-frame guarantee (P-021).

``POST /api/v1/ocr`` is a frozen public contract, yet it does not *declare* the
coordinate space of ``text_blocks[].bbox/polygon``. The guarantee is implicit: the
polygons are in the **uploaded image's** pixel frame. That only holds if the engine
is constructed with ``use_doc_unwarping=False``, because unwarping is a non-linear
deformation (UVDoc) - with it on, the detector runs on a warped canvas and handing
its ``dt_polys`` back verbatim is a silent frame mismatch (measured on the cloud
2026-09-24: scale 1.11-1.23 varying per probe, rotation flattened). Every consumer
- overlay, crop, export, cross-source alignment - is then wrong with no error raised.

``layout_service._init_engine`` and ``formula_service`` already pin the flag; the OCR
path was the only one that did not. This test locks the reason so a refactor or a
PaddleOCR/paddlex upgrade cannot drop it unnoticed.

No Paddle/GPU required: ``paddle`` is stubbed in ``sys.modules`` and the module is
loaded from its file path - the same trick as ``test_layout_page_skip.py``.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Callable, Dict

import pytest

# Imported at module level by ocr_service (it only needs the name to exist here).
if "paddle" not in sys.modules:
    sys.modules["paddle"] = types.ModuleType("paddle")

_OCR_SERVICE_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "ocr_service.py"


class _RecordingPaddleOCR:
    """Stands in for ``paddleocr.PaddleOCR``; records every construction's kwargs."""

    calls: list = []

    def __init__(self, **kwargs: Any) -> None:
        _RecordingPaddleOCR.calls.append(kwargs)


def _load_ocr_service():
    """Load ``ocr_service.py`` by path (avoids importing the ``app`` package)."""
    spec = importlib.util.spec_from_file_location("ocr_service_engine_params_tests", _OCR_SERVICE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def engine_init_kwargs(monkeypatch) -> Callable[..., Dict[str, Any]]:
    """Run ``_init_engine()`` against a fake PaddleOCR and return the kwargs it saw."""
    fake_paddleocr = types.ModuleType("paddleocr")
    fake_paddleocr.__version__ = "3.3.2-fake"  # the real module logs this attribute
    fake_paddleocr.PaddleOCR = _RecordingPaddleOCR
    monkeypatch.setitem(sys.modules, "paddleocr", fake_paddleocr)
    _RecordingPaddleOCR.calls.clear()

    def _run(use_gpu: bool = False, lang: str = "ch") -> Dict[str, Any]:
        module = _load_ocr_service()
        engine = module.PaddleOCREngine(use_gpu=use_gpu, lang=lang)
        engine._init_engine()
        # Guard against asserting kwargs recorded on a swallowed failure path:
        # _init_engine catches Exception broadly and would leave _ready False.
        assert engine.is_ready(), "engine never reached the success branch"
        assert _RecordingPaddleOCR.calls, "PaddleOCR() was never constructed"
        return _RecordingPaddleOCR.calls[-1]

    return _run


def test_engine_init_pins_use_doc_unwarping_false(engine_init_kwargs):
    """P-021: without this, the endpoint returns polygons in a warped canvas."""
    kwargs = engine_init_kwargs()
    assert kwargs.get("use_doc_unwarping") is False, (
        "ocr_service._init_engine must construct PaddleOCR with "
        "use_doc_unwarping=False; otherwise text_blocks[].bbox/polygon are in the "
        "unwarped canvas instead of the uploaded image frame (P-021)."
    )


def test_engine_init_pins_unwarping_false_on_gpu_too(engine_init_kwargs):
    """The flag must not be tied to the device branch."""
    kwargs = engine_init_kwargs(use_gpu=True)
    assert kwargs.get("use_doc_unwarping") is False
    assert kwargs.get("device") == "gpu"


def test_engine_init_other_params_unchanged(engine_init_kwargs):
    """The rest of the dict is contract too: device spelling + doc-orientation off."""
    kwargs = engine_init_kwargs(use_gpu=False, lang="en")
    assert kwargs.get("device") == "cpu"  # PaddleOCR 3.x wants "cpu"/"gpu", not "gpu:0"
    assert kwargs.get("lang") == "en"
    assert kwargs.get("use_doc_orientation_classify") is False  # page rotation stays detectable
