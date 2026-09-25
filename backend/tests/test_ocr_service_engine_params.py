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

No Paddle/GPU required: ``paddle`` and ``paddleocr`` are stubbed and the module is
loaded from its file path - the same trick as ``test_layout_page_skip.py``.

**The stubs must stay inside the fixture (``monkeypatch``), never at module level.**
pytest imports every test module at *collection* time, so a module-level
``sys.modules["paddle"]`` would still be installed while other files run - and it
silently defeats their "skip when Paddle is missing" guards. Here it made
``test_table_template_analyze.py::test_analyze_form_accepts_table_template`` stop
skipping (``pytest.importorskip("paddle")`` found the stub) and fail on the
``fastapi`` import that guard was indirectly protecting, reddening Phase A CI in a
file this change never touched. Caught by this test's own first CI run.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Callable, Dict

import pytest

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
    """Run ``_init_engine()`` against a fake PaddleOCR and return the kwargs it saw.

    ``monkeypatch.setitem`` scopes the stubs to the test that asks for them, so the
    engine can still be imported here (``ocr_service`` does ``import paddle``) without
    leaking a fake Paddle into the rest of the session.
    """
    fake_paddle = types.ModuleType("paddle")
    fake_paddleocr = types.ModuleType("paddleocr")
    fake_paddleocr.__version__ = "3.3.2-fake"  # the real module logs this attribute
    fake_paddleocr.PaddleOCR = _RecordingPaddleOCR
    monkeypatch.setitem(sys.modules, "paddle", fake_paddle)
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


def test_paddleocr_stub_is_not_installed_at_module_scope():
    """Regression for the CI failure this test caused: no stub may outlive a test.

    ``test_table_template_analyze.py`` skips itself via ``pytest.importorskip("paddle")``
    (guarding a ``fastapi`` import the light Phase A venv lacks), so a leaked ``paddle``
    stub makes that guard pass and the file fail. No fixture is active here, so this
    catches a future move back to module-level stubbing.

    Only the ``paddleocr`` marker is asserted: ``paddle`` alone is indistinguishable
    from the stub ``test_layout_page_skip.py`` intentionally leaves in ``sys.modules``.
    """
    assert getattr(sys.modules.get("paddleocr"), "__version__", None) != "3.3.2-fake"
