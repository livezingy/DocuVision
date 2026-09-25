"""F2 LAYOUT_TYPES coverage test.

``layout_service.py`` imports ``paddle`` / ``cv2`` at module top, which are not
available in the local Python env. We stub them in ``sys.modules`` **for the duration of
the module load only** (``unittest.mock.patch.dict``) so the class-level ``LAYOUT_TYPES``
dict can be inspected without loading any model - and without leaking a fake ``paddle``
into the rest of the pytest session (P-023; ``check_stub_scope``).

Official basis: PP-DocLayout-L defines 23 categories
https://huggingface.co/PaddlePaddle/PP-DocLayout-L
and findings §2.
"""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest.mock
from pathlib import Path

# paddle needs a few attributes referenced at import time? layout_service only
# does `import paddle` (no attribute use at top). cv2 is used inside methods.
# numpy is available locally.
_STUBS = {_mod: types.ModuleType(_mod) for _mod in ("paddle", "cv2")}

_LAYOUT_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "layout_service.py"
_spec = importlib.util.spec_from_file_location("layout_service_for_tests", _LAYOUT_PATH)
assert _spec is not None and _spec.loader is not None
_layout_mod = importlib.util.module_from_spec(_spec)
with unittest.mock.patch.dict(sys.modules, _STUBS):
    _spec.loader.exec_module(_layout_mod)
PPStructureEngine = _layout_mod.PPStructureEngine


# Official 23 categories (PP-DocLayout-L) that must be present in LAYOUT_TYPES.
REQUIRED_LABELS = [
    "paragraph_title", "doc_title", "text", "number", "abstract", "content",
    "figure_table_chart_title", "formula", "table", "reference", "footnote",
    "header", "algorithm", "footer", "seal", "chart", "formula_number",
    "aside_text", "image", "figure_caption", "table_caption",
    "header_image", "footer_image",
]


def test_layout_types_covers_official_23() -> None:
    lt = PPStructureEngine.LAYOUT_TYPES
    missing = [lbl for lbl in REQUIRED_LABELS if lbl not in lt]
    assert not missing, f"LAYOUT_TYPES missing official labels: {missing}"


def test_layout_types_footnote_present_and_distinct() -> None:
    # F2: footnote must be its own entry (JD high-value), not folded into footer.
    lt = PPStructureEngine.LAYOUT_TYPES
    assert "footnote" in lt
    assert lt["footnote"] != lt["footer"], "footnote must not alias footer"


def test_layout_types_title_aliases_kept() -> None:
    # Legacy aliases kept for backward compat with older callers.
    lt = PPStructureEngine.LAYOUT_TYPES
    assert "title" in lt
    assert "equation" in lt
    # But paragraph_title / doc_title are now distinct.
    assert lt["paragraph_title"] != lt["doc_title"]
