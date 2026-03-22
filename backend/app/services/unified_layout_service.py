"""
Unified Layout Analysis Service
统一版面分析服务，将PaddleOCR PPStructureV3的输出转换为标准化格式
"""

import uuid
from typing import Optional, List, Dict
from app.models.layout_result import (
    LayoutElement, LayoutBbox, LayoutAnalysisResult,
    LayoutElementType
)


class UnifiedLayoutService:
    """统一的版面分析服务"""

    # PaddleOCR元素类型映射到标准类型
    TYPE_MAPPING = {
        "text": LayoutElementType.TEXT,
        "title": LayoutElementType.TITLE,
        "subtitle": LayoutElementType.SUBTITLE,
        "section_header": LayoutElementType.SECTION_HEADER,
        "table": LayoutElementType.TABLE,
        "table_header": LayoutElementType.TABLE_HEADER,
        "table_caption": LayoutElementType.TABLE,
        "figure": LayoutElementType.FIGURE,
        "figure_caption": LayoutElementType.FIGURE,
        "image": LayoutElementType.IMAGE,
        "page_header": LayoutElementType.PAGE_HEADER,
        "page_footer": LayoutElementType.PAGE_FOOTER,
        "footnote": LayoutElementType.FOOTNOTE,
        "formula": LayoutElementType.FORMULA,
        "list_item": LayoutElementType.LIST_ITEM,
        # Additional labels from PaddleOCR 3.3.x parsing_res_list (confirmed via probe)
        "header": LayoutElementType.PAGE_HEADER,
        "header_image": LayoutElementType.PAGE_HEADER,
        "footer": LayoutElementType.PAGE_FOOTER,
        "footer_image": LayoutElementType.PAGE_FOOTER,
        "equation": LayoutElementType.FORMULA,
        "list": LayoutElementType.LIST_ITEM,
        "paragraph": LayoutElementType.TEXT,
        "number": LayoutElementType.TEXT,
        "aside_text": LayoutElementType.TEXT,
        "reference": LayoutElementType.TEXT,
        "doc_index": LayoutElementType.TEXT,
    }

    # 元素类型颜色配置（用于前端渲染）
    TYPE_COLORS = {
        LayoutElementType.TEXT: "#4A90E2",           # 蓝色
        LayoutElementType.TITLE: "#F5A623",         # 橙色
        LayoutElementType.SUBTITLE: "#BD10E0",      # 紫色
        LayoutElementType.SECTION_HEADER: "#7ED321",# 绿色
        LayoutElementType.TABLE: "#FF6B6B",         # 红色
        LayoutElementType.TABLE_HEADER: "#FF4757",  # 深红
        LayoutElementType.FIGURE: "#2E86C1",        # 深蓝
        LayoutElementType.IMAGE: "#16A085",         # 青色
        LayoutElementType.PAGE_HEADER: "#C0392B",   # 棕红
        LayoutElementType.PAGE_FOOTER: "#8E44AD",   # 深紫
        LayoutElementType.FOOTNOTE: "#95A5A6",      # 灰色
        LayoutElementType.FORMULA: "#E67E22",       # 棕色
        LayoutElementType.LIST_ITEM: "#3498DB",     # 浅蓝
    }

    def analyze_paddleocr_result(
        self,
        paddleocr_result,  # PPStructureV3返回的LayoutParsingResultV2对象或dict
        image_info: Optional[Dict] = None,
        page_number: int = 1
    ) -> LayoutAnalysisResult:
        """
        分析PaddleOCR PPStructureV3的结果，转换为标准格式

        Args:
            paddleocr_result: PPStructureV3返回的LayoutParsingResultV2对象或字典
            image_info: 图像信息 {width, height, ...}
            page_number: 页码

        Returns:
            LayoutAnalysisResult: 标准化的版面分析结果
        """
        result = LayoutAnalysisResult()
        elements: Dict[str, LayoutElement] = {}

        # 调试日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[UnifiedLayout] Starting analysis, input type: {type(paddleocr_result)}")

        # 如果没有提供image_info，从result获取
        if image_info is None:
            if isinstance(paddleocr_result, dict):
                image_info = paddleocr_result.get('image_info', {'width': 0, 'height': 0})
            else:
                image_info = getattr(paddleocr_result, 'image_info', {'width': 0, 'height': 0})

        logger.info(f"[UnifiedLayout] Image info: {image_info}")

        # Fast-path: the project layout service already converts PPStructureV3 output into
        # a dict with `elements` (reading-order sorted, bbox in {x,y,width,height}).
        # This is the most stable representation across PaddleOCR 3.x variations.
        if isinstance(paddleocr_result, dict) and isinstance(paddleocr_result.get("elements"), list):
            for idx, elem_in in enumerate(paddleocr_result.get("elements", [])):
                if not isinstance(elem_in, dict):
                    continue

                element_type_str = str(elem_in.get("type", "text")).lower()
                element_type = self.TYPE_MAPPING.get(element_type_str, LayoutElementType.TEXT)

                bbox_in = elem_in.get("bbox") or {}
                try:
                    x1 = float(bbox_in.get("x", 0.0))
                    y1 = float(bbox_in.get("y", 0.0))
                    w = float(bbox_in.get("width", 0.0))
                    h = float(bbox_in.get("height", 0.0))
                    bbox = LayoutBbox(x1=x1, y1=y1, x2=x1 + w, y2=y1 + h)
                except Exception:
                    bbox = LayoutBbox(x1=0, y1=0, x2=0, y2=0)

                confidence = 0.0
                try:
                    confidence = float(elem_in.get("confidence", 0.0))
                except Exception:
                    confidence = 0.0

                content = elem_in.get("text") or elem_in.get("content") or None

                elem_id = str(elem_in.get("id") or f"elem_{idx}")
                elem = LayoutElement(
                    element_id=elem_id,
                    element_type=element_type,
                    bbox=bbox,
                    confidence=confidence,
                    content=content,
                    page_number=int(elem_in.get("page") or page_number),
                    z_index=self._calculate_z_index(bbox, image_info),
                    table_rows=None,
                    table_cols=None,
                )
                elements[elem_id] = elem

            result.elements = sorted(
                elements.values(),
                key=lambda e: (e.page_number, e.z_index, e.bbox.y1, e.bbox.x1),
            )
            result.metadata = {
                "image_info": image_info,
                "page_number": page_number,
                "total_elements": len(result.elements),
                "analysis_timestamp": str(self._get_timestamp()),
                "source": "layout_service_elements",
            }
            return result

        # ==================== 第一步：处理layout_dets（区域检测）====================
        # layout_dets包含各种类型的区域：text, title, table, figure等
        layout_dets = None
        if isinstance(paddleocr_result, dict):
            layout_dets = paddleocr_result.get('layout_dets')
        else:
            layout_dets = getattr(paddleocr_result, 'layout_dets', None)

        logger.info(f"[UnifiedLayout] layout_dets type: {type(layout_dets)}, length: {len(layout_dets) if layout_dets else 0}")

        if layout_dets:
            for det in layout_dets:
                elem_id = f"layout_{len(elements)}"

                # 提取边界框和置信度
                bbox = self._extract_bbox_from_det(det)
                confidence = getattr(det, 'confidence', 0.95)

                # 获取元素类型
                element_type_str = getattr(det, 'class_name', 'text').lower()
                element_type = self.TYPE_MAPPING.get(
                    element_type_str,
                    LayoutElementType.TEXT
                )

                # 特殊处理：表格
                is_table = element_type == LayoutElementType.TABLE
                table_rows = None
                table_cols = None

                elem = LayoutElement(
                    element_id=elem_id,
                    element_type=element_type,
                    bbox=bbox,
                    confidence=confidence,
                    page_number=page_number,
                    z_index=self._calculate_z_index(bbox, image_info),
                    table_rows=table_rows if is_table else None,
                    table_cols=table_cols if is_table else None,
                )

                elements[elem_id] = elem

        # ==================== 第二步：处理layout_items（详细内容）====================
        # layout_items包含每个区域的详细内容
        layout_items = None
        if isinstance(paddleocr_result, dict):
            layout_items = paddleocr_result.get("layout_items")
        else:
            layout_items = getattr(paddleocr_result, "layout_items", None)

        if layout_items:
            for idx, item in enumerate(layout_items):
                elem_id = f"item_{idx}"

                # 提取内容
                content = None
                if hasattr(item, 'text'):
                    content = item.text
                elif isinstance(item, dict) and 'text' in item:
                    content = item['text']

                # 提取bbox (layout_items通常有bbox)
                if hasattr(item, 'bbox'):
                    bbox = self._bbox_to_layout_bbox(item.bbox)
                elif isinstance(item, dict) and 'bbox' in item:
                    bbox = self._bbox_to_layout_bbox(item['bbox'])
                else:
                    continue  # 跳过没有bbox的item

                confidence = getattr(item, 'confidence', 0.9)

                # 确定元素类型
                element_type = LayoutElementType.TEXT
                if hasattr(item, 'category_id'):
                    category = item.category_id
                    element_type = self.TYPE_MAPPING.get(str(category), LayoutElementType.TEXT)

                elem = LayoutElement(
                    element_id=elem_id,
                    element_type=element_type,
                    bbox=bbox,
                    confidence=confidence,
                    content=content,
                    page_number=page_number,
                    z_index=self._calculate_z_index(bbox, image_info),
                )

                elements[elem_id] = elem

        # ==================== 第三步：处理tables（表格数据）====================
        # tables包含表格结构信息
        tables_in = None
        if isinstance(paddleocr_result, dict):
            tables_in = paddleocr_result.get("tables")
        else:
            tables_in = getattr(paddleocr_result, "tables", None)

        if tables_in:
            for table_idx, table_data in enumerate(tables_in):
                # 在前面的layout_dets中找到对应的表格元素
                # 这里假设表格元素已经在layout_dets中了

                # 获取表格行列数
                try:
                    table_rows = len(table_data.get('data', [])) if isinstance(table_data, dict) else 0
                    table_cols = len(table_data.get('data', [[]])[0]) if table_rows > 0 else 0
                except Exception:
                    table_rows = 0
                    table_cols = 0

                # 更新对应的表格元素
                for elem in elements.values():
                    if elem.element_type == LayoutElementType.TABLE:
                        if elem.table_rows is None:  # 还没有设置
                            elem.table_rows = table_rows
                            elem.table_cols = table_cols
                            break

        # ==================== 结果聚合 ====================
        result.elements = sorted(
            elements.values(),
            key=lambda e: (e.page_number, e.z_index, e.bbox.y1, e.bbox.x1)
        )

        result.metadata = {
            "image_info": image_info,
            "page_number": page_number,
            "total_elements": len(result.elements),
            "analysis_timestamp": str(self._get_timestamp()),
        }

        return result

    def _extract_bbox_from_det(self, det) -> LayoutBbox:
        """从PaddleOCR detection对象提取bbox"""
        if hasattr(det, 'bbox'):
            bbox = det.bbox
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                return LayoutBbox(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3])

        # 尝试从其他属性提取
        if hasattr(det, 'box'):
            box = det.box
            if isinstance(box, (list, tuple)) and len(box) >= 4:
                return LayoutBbox(x1=box[0], y1=box[1], x2=box[2], y2=box[3])

        # 默认返回零bbox
        return LayoutBbox(x1=0, y1=0, x2=0, y2=0)

    def _bbox_to_layout_bbox(self, bbox_data) -> LayoutBbox:
        """将各种格式的bbox转换为LayoutBbox"""
        if isinstance(bbox_data, (list, tuple)):
            if len(bbox_data) >= 4:
                # 检查第一个元素是否是序列（polygon格式）或数字（bbox格式）
                if isinstance(bbox_data[0], (list, tuple)):
                    # [[x,y], [x,y], [x,y], [x,y]]格式
                    xs = [p[0] for p in bbox_data]
                    ys = [p[1] for p in bbox_data]
                    return LayoutBbox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))
                else:
                    # [x1, y1, x2, y2]格式
                    return LayoutBbox(x1=bbox_data[0], y1=bbox_data[1],
                                     x2=bbox_data[2], y2=bbox_data[3])

        return LayoutBbox(x1=0, y1=0, x2=0, y2=0)

    def _calculate_z_index(self, bbox: LayoutBbox, image_info: Dict) -> int:
        """计算元素的纵深顺序（基于位置）"""
        if not image_info or 'height' not in image_info:
            return 0

        image_height = image_info.get('height', 1)
        # 从上到下，从左到右
        relative_top = bbox.y1 / image_height if image_height > 0 else 0
        z_index = int(relative_top * 1000)
        return z_index

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()

    @staticmethod
    def get_element_color(element_type: LayoutElementType) -> str:
        """获取元素类型的颜色"""
        return UnifiedLayoutService.TYPE_COLORS.get(
            element_type,
            "#808080"  # 默认灰色
        )
