"""F1 split: pseudo-table filtering + leading-caption handling (PPStructureTableEngine).

Mechanical extraction out of ``table_service.py``, same shape as the P-028 F1 splits and
the ``table_ocr_blocks.py`` move: the three ``@staticmethod`` helpers below are
byte-identical to their previous definitions, moved under
:class:`TablePseudoFilterMixin` and reached through the engine's MRO, so call sites and
tests are unchanged.

They are pure logic (no ``self.*`` engine state). The only external dependency is
``figure_service._bbox_tuple`` / ``_h_overlap_ratio`` / ``_v_gap``, imported lazily inside
``_bind_table_captions`` exactly as before.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


class TablePseudoFilterMixin:
    """Pseudo-table filter + caption binding helpers for the PP-Structure table engine."""

    @staticmethod
    def _keep_layout_table(table: Dict[str, Any]) -> bool:
        """Return False for empty/tiny layout tables.

        ``_html_to_data`` may yield a grid of empty strings, or fail and leave
        only ``html``. Either case is a pseudo-table (header rule / axis line)
        and must not be kept just because HTML is present.
        """
        data = table.get("data") or []
        if not data:
            return False
        nonempty = sum(
            1 for row in data for c in (row or []) if c and str(c).strip()
        )
        if nonempty == 0:
            return False
        row_count = len(data)
        col_count = max((len(r) for r in data), default=0)
        if row_count < 3 and col_count < 3:
            return False
        return True

    @staticmethod
    def _strip_leading_caption_row(table: Dict[str, Any]) -> None:
        """Move a leading Table/Figure caption row onto ``table.caption``.

        After colspan expansion a single caption cell becomes
        ``['Table 1: ...', '', '']``. Count nonempty cells, not raw width,
        so a spanned caption is still stripped.
        """
        data = table.get("data") or []
        if not data or not data[0]:
            return
        nonempty = [str(c).strip() for c in data[0] if c and str(c).strip()]
        if not nonempty or len(nonempty) > 2:
            return
        first_text = " ".join(nonempty)
        if not re.match(r"^(Table|Figure)\s+\d+[:.]", first_text, re.IGNORECASE):
            return
        table["caption"] = first_text
        table["data"] = data[1:]
        if table.get("data"):
            table["rows"] = len(table["data"])
            table["columns"] = max(len(r) for r in table["data"]) if table["data"] else 0
        logger.info(f"stripped caption row -> {first_text[:50]}")

    @staticmethod
    def _bind_table_captions(
        tables: List[Dict[str, Any]],
        all_elements: List[Dict[str, Any]],
    ) -> None:
        """Bind ``table_caption`` elements to nearby tables in-place.

        Simplified reimplementation of PaddleX ``update_vision_child_blocks``
        for the table-caption case. A caption is consumed by the closest
        table on the same page with sufficient horizontal overlap and
        small vertical gap.
        """
        from app.services.figure_service import _bbox_tuple, _h_overlap_ratio, _v_gap

        caption_labels = {"table_caption", "figure_table_chart_title"}
        captions = [
            e for e in all_elements
            if str(e.get("type") or "").lower().strip() in caption_labels
        ]
        if not captions or not tables:
            return

        consumed: set = set()
        for tbl in tables:
            tbl_page = int(tbl.get("page", 1) or 1)
            tbl_bbox = tbl.get("bbox") or {}
            if not tbl_bbox:
                continue
            tbl_box = (
                float(tbl_bbox.get("x", 0)),
                float(tbl_bbox.get("y", 0)),
                float(tbl_bbox.get("x", 0)) + float(tbl_bbox.get("width", 0)),
                float(tbl_bbox.get("y", 0)) + float(tbl_bbox.get("height", 0)),
            )
            tbl_h = tbl_box[3] - tbl_box[1]
            best_cap = None
            best_gap = float("inf")

            for cap in captions:
                cap_id = cap.get("id")
                if cap_id in consumed:
                    continue
                if int(cap.get("page", 1) or 1) != tbl_page:
                    continue
                cap_box = _bbox_tuple(cap)
                if _h_overlap_ratio(tbl_box, cap_box) < 0.5:
                    continue
                gap = _v_gap(tbl_box, cap_box)
                cap_h = cap_box[3] - cap_box[1]
                threshold = 0.5 * max(tbl_h, cap_h) if max(tbl_h, cap_h) > 0 else 50.0
                if gap > threshold:
                    continue
                if gap < best_gap:
                    best_gap = gap
                    best_cap = cap

            if best_cap is not None:
                consumed.add(best_cap.get("id"))
                tbl["caption"] = best_cap.get("text") or ""
                tbl["caption_id"] = best_cap.get("id")

