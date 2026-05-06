"""WordIndexer：从 PP-StructureV3 layout 输出按 reading_order 拼全文，
并同步记录每个 word 的 (offset, length, polygon, page_number)，
为 UIE 字符级 offset 反查 BoundingRegion / Span 提供索引。

由于 PP-StructureV3 当前主要输出 block 级 text + polygon（无 word 粒度），
WordIndexer 优先吃 elem.words / elem.lines；若仅有 elem.text + elem.polygon
则将整段当一个 'word' 处理（粗粒度 fallback）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.services.kie.azure_schema import BoundingRegion, Span


@dataclass
class _Word:
    text: str
    offset: int
    length: int
    polygon: List[float]
    page_number: int


def _normalize_polygon(poly: Any, bbox: Any = None) -> List[float]:
    """统一 polygon 为 8 点扁平列表 [x1,y1,x2,y2,x3,y3,x4,y4]。

    支持以下输入：
    - [x1,y1,x2,y2,x3,y3,x4,y4]   8 数 flat
    - [x1,y1,x2,y2]                4 数 bbox
    - {"x","y","width","height"}   layout_service bbox dict
    - {"x0","y0","x1","y1"}        Azure 风格 bbox dict
    """
    # 直接 flat list / tuple
    if isinstance(poly, (list, tuple)):
        if len(poly) == 8:
            try:
                return [float(v) for v in poly]
            except (TypeError, ValueError):
                pass
        if len(poly) == 4:
            try:
                x0, y0, x1, y1 = (float(v) for v in poly)
                return [x0, y0, x1, y0, x1, y1, x0, y1]
            except (TypeError, ValueError):
                pass

    # 嵌套 [[x,y],[x,y],...]
    if isinstance(poly, (list, tuple)) and len(poly) >= 4:
        flat: List[float] = []
        try:
            for pt in poly[:4]:
                if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                    flat.extend([float(pt[0]), float(pt[1])])
                else:
                    flat = []
                    break
            if len(flat) == 8:
                return flat
        except (TypeError, ValueError):
            pass

    # 退到 bbox dict
    src = bbox if isinstance(bbox, dict) else (poly if isinstance(poly, dict) else None)
    if isinstance(src, dict):
        if "width" in src or "height" in src:
            x0 = float(src.get("x", 0))
            y0 = float(src.get("y", 0))
            x1 = x0 + float(src.get("width", 0))
            y1 = y0 + float(src.get("height", 0))
        else:
            x0 = float(src.get("x0", src.get("x", 0)))
            y0 = float(src.get("y0", src.get("y", 0)))
            x1 = float(src.get("x1", x0))
            y1 = float(src.get("y1", y0))
        return [x0, y0, x1, y0, x1, y1, x0, y1]

    return []


class WordIndexer:
    """OCR 全文 + offset → polygon 索引。"""

    def __init__(self, content: str, words: List[_Word]):
        self.content = content
        self.words = words

    @classmethod
    def from_layout(cls, layout_result: Optional[Dict[str, Any]]) -> "WordIndexer":
        if not isinstance(layout_result, dict):
            return cls(content="", words=[])
        elements = layout_result.get("elements", [])
        if not isinstance(elements, list):
            return cls(content="", words=[])

        sorted_elems = sorted(
            (e for e in elements if isinstance(e, dict)),
            key=cls._element_sort_key,
        )

        parts: List[str] = []
        words: List[_Word] = []
        cursor = 0

        for elem in sorted_elems:
            page_num = int(elem.get("page", elem.get("page_number", 1)) or 1)

            tokens = cls._extract_tokens(elem)
            for tok_text, tok_polygon in tokens:
                t = tok_text.strip()
                if not t:
                    continue
                # 与上一个 token 之间插入空格（首个 token 或紧跟 \n 时不插）
                if parts and not parts[-1].endswith("\n"):
                    parts.append(" ")
                    cursor += 1
                words.append(
                    _Word(
                        text=t,
                        offset=cursor,
                        length=len(t),
                        polygon=tok_polygon,
                        page_number=page_num,
                    )
                )
                parts.append(t)
                cursor += len(t)

            # block 间换行
            if parts and not parts[-1].endswith("\n"):
                parts.append("\n")
                cursor += 1

        # cursor 精确等于 content 的 char index，rstrip 后续不再追加 word
        content = "".join(parts).rstrip("\n")
        return cls(content=content, words=words)

    @staticmethod
    def _element_sort_key(elem: Dict[str, Any]) -> Tuple[int, int, float, float]:
        """按 (page, reading_order, y, x) 排序，缺失字段时回退到 bbox 坐标。"""
        page = int(elem.get("page", elem.get("page_number", 1)) or 1)
        ro = elem.get("reading_order")
        if ro is None:
            ro = 10**6  # reading_order 缺失则后排
        bbox = elem.get("bbox") or {}
        y = float(bbox.get("y", bbox.get("y0", 0))) if isinstance(bbox, dict) else 0.0
        x = float(bbox.get("x", bbox.get("x0", 0))) if isinstance(bbox, dict) else 0.0
        return (page, int(ro), y, x)

    @staticmethod
    def _extract_tokens(elem: Dict[str, Any]) -> List[Tuple[str, List[float]]]:
        """从 layout element 抽 (text, polygon) 序列。

        优先级：elem.words > elem.lines > elem.text + elem.polygon。
        """
        out: List[Tuple[str, List[float]]] = []

        # 1) word 级
        words = elem.get("words")
        if isinstance(words, list) and words:
            for w in words:
                if not isinstance(w, dict):
                    continue
                t = str(w.get("text", "") or "").strip()
                if not t:
                    continue
                poly = _normalize_polygon(w.get("polygon"), w.get("bbox"))
                out.append((t, poly))
            if out:
                return out

        # 2) line 级
        lines = elem.get("lines")
        if isinstance(lines, list) and lines:
            for line in lines:
                if not isinstance(line, dict):
                    continue
                t = str(line.get("text", "") or "").strip()
                if not t:
                    continue
                poly = _normalize_polygon(line.get("polygon"), line.get("bbox"))
                out.append((t, poly))
            if out:
                return out

        # 3) block 级整段（PP-StructureV3 现状）
        text = str(elem.get("text", "") or "").strip()
        if text:
            poly = _normalize_polygon(elem.get("polygon_preprocessed"), elem.get("bbox"))
            return [(text, poly)]

        return []

    def lookup_by_offset(self, start: int, end: int) -> Tuple[List[BoundingRegion], List[Span]]:
        """返回覆盖 [start, end) 区间的所有 word 的 BoundingRegion 与合并后的 Span。

        没有命中任何 word 时，返回 ([], [])。
        """
        if start < 0 or end <= start:
            return [], []

        hit_words = [
            w for w in self.words
            if w.offset < end and (w.offset + w.length) > start
        ]
        if not hit_words:
            return [], []

        regions = [
            BoundingRegion(pageNumber=w.page_number, polygon=w.polygon)
            for w in hit_words
            if w.polygon
        ]
        spans = [
            Span(
                offset=hit_words[0].offset,
                length=(hit_words[-1].offset + hit_words[-1].length) - hit_words[0].offset,
            )
        ]
        return regions, spans

    def lookup_by_text(self, text: str) -> Tuple[List[BoundingRegion], List[Span]]:
        """文本子串反查（fallback：UIE start/end 失效时使用）。"""
        if not text:
            return [], []
        idx = self.content.find(text)
        if idx < 0:
            return [], []
        return self.lookup_by_offset(idx, idx + len(text))
