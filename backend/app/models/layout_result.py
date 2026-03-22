"""
Layout Analysis Result Models
统一的版面分析结果格式
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime


class LayoutElementType(str, Enum):
    """版面元素类型（对标Azure DI + 扩展）"""
    TEXT = "text"
    TITLE = "title"
    SUBTITLE = "subtitle"
    SECTION_HEADER = "section_header"
    TABLE = "table"
    TABLE_HEADER = "table_header"
    TABLE_CELL = "table_cell"
    FIGURE = "figure"
    IMAGE = "image"
    PAGE_HEADER = "page_header"
    PAGE_FOOTER = "page_footer"
    FOOTNOTE = "footnote"
    FORMULA = "formula"
    LIST_ITEM = "list_item"


@dataclass
class LayoutBbox:
    """标准化的边界框表示"""
    x1: float
    y1: float
    x2: float
    y2: float

    def to_list(self) -> List[float]:
        """转换为 [x1, y1, x2, y2] 列表"""
        return [self.x1, self.y1, self.x2, self.y2]

    def to_polygon(self) -> List[float]:
        """转换为 polygon 格式 [x1,y1,x2,y1,x2,y2,x1,y2]"""
        return [self.x1, self.y1, self.x2, self.y1,
                self.x2, self.y2, self.x1, self.y2]

    def get_center(self) -> tuple:
        """获取中心点坐标"""
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def get_area(self) -> float:
        """获取面积"""
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def get_width(self) -> float:
        """获取宽度"""
        return self.x2 - self.x1

    def get_height(self) -> float:
        """获取高度"""
        return self.y2 - self.y1


@dataclass
class LayoutElement:
    """单个版面元素"""
    element_id: str                         # 唯一标识
    element_type: LayoutElementType         # 元素类型
    bbox: LayoutBbox                        # 边界框
    confidence: float                       # 置信度 [0, 1]
    content: Optional[str] = None           # 内容文本

    # 元数据
    page_number: int = 1                    # 页码
    z_index: int = 0                        # 纵深顺序（用于确定前后关系）
    is_rotated: bool = False                # 是否旋转
    rotation_angle: float = 0.0             # 旋转角度

    # 关系
    parent_id: Optional[str] = None         # 父元素ID（用于嵌套）
    child_ids: List[str] = field(default_factory=list)  # 子元素IDs

    # 特殊字段
    table_rows: Optional[int] = None        # 表格行数
    table_cols: Optional[int] = None        # 表格列数
    is_header: bool = False                 # 是否是表头

    def to_dict(self) -> Dict:
        """转换为字典用于JSON序列化"""
        return {
            "element_id": self.element_id,
            "element_type": self.element_type.value,
            "bbox": self.bbox.to_list(),
            "polygon": self.bbox.to_polygon(),
            "confidence": round(self.confidence, 4),
            "content": self.content,
            "page_number": self.page_number,
            "z_index": self.z_index,
            "is_rotated": self.is_rotated,
            "rotation_angle": self.rotation_angle,
            "parent_id": self.parent_id,
            "child_ids": self.child_ids,
            "table_rows": self.table_rows,
            "table_cols": self.table_cols,
            "is_header": self.is_header,
            # 计算字段
            "area": round(self.bbox.get_area(), 0),
            "width": round(self.bbox.get_width(), 0),
            "height": round(self.bbox.get_height(), 0),
            "center": [round(c, 1) for c in self.bbox.get_center()]
        }


@dataclass
class LayoutAnalysisResult:
    """版面分析的统一输出格式"""
    elements: List[LayoutElement] = field(default_factory=list)  # 所有版面元素
    metadata: Dict = field(default_factory=dict)                 # 元数据

    def to_dict(self) -> Dict:
        """转换为JSON-friendly格式"""
        return {
            "elements": [elem.to_dict() for elem in self.elements],
            "metadata": self.metadata,
            "statistics": self._get_statistics()
        }

    def _get_statistics(self) -> Dict:
        """统计信息"""
        stats = {
            "total_elements": len(self.elements),
            "by_type": {}
        }

        for elem in self.elements:
            type_name = elem.element_type.value
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1

        return stats

    def get_elements_by_type(self, element_type: LayoutElementType) -> List[LayoutElement]:
        """按类型筛选元素"""
        return [e for e in self.elements if e.element_type == element_type]

    def get_elements_by_page(self, page_number: int) -> List[LayoutElement]:
        """按页码筛选元素"""
        return [e for e in self.elements if e.page_number == page_number]

    def get_element_by_id(self, element_id: str) -> Optional[LayoutElement]:
        """按ID查找元素"""
        for elem in self.elements:
            if elem.element_id == element_id:
                return elem
        return None
