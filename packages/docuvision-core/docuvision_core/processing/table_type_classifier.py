# core/processing/table_type_classifier.py
"""table type classifier module."""

from typing import Literal
import numpy as np
from docuvision_core.utils.logger import AppLogger


class TableTypeClassifier:
    """Docstring."""
    
    def __init__(self, feature_analyzer, page):
        """Docstring."""
        self.analyzer = feature_analyzer
        self.page = page
        self.logger = AppLogger.get_logger()
    
    
    def _classification_result(
        self,
        table_type: Literal['bordered', 'unbordered'],
        score: float,
        method: str,
        h_count: int,
        v_count: int,
        line_concentration: float | None = None,
        area_ratio: float | None = None,
        direction_balance: float | None = None,
    ) -> dict:
        return {
            'table_type': table_type,
            'score': float(score),
            'method': method,
            'h_lines': h_count,
            'v_lines': v_count,
            'line_concentration': line_concentration,
            'area_ratio': area_ratio,
            'direction_balance': direction_balance,
        }

    def classify(self) -> dict:
        """Classify table type with detailed metrics for UI / profile API."""
        horizontal_lines = self.analyzer.line_analysis['horizontal_lines']
        vertical_lines = self.analyzer.line_analysis['vertical_lines']
        h_count = len(horizontal_lines)
        v_count = len(vertical_lines)

        if h_count < 3 or v_count < 3:
            return self._classification_result(
                'unbordered', 0.0, 'quick_filter', h_count, v_count
            )

        dynamic_threshold = self._calculate_dynamic_threshold()

        if h_count > dynamic_threshold and v_count > dynamic_threshold:
            h_aligned = self._quick_alignment_check(horizontal_lines, 'horizontal')
            v_aligned = self._quick_alignment_check(vertical_lines, 'vertical')
            if h_aligned > 0.6 and v_aligned > 0.6:
                balance = min(h_count, v_count) / max(h_count, v_count)
                return self._classification_result(
                    'bordered',
                    1.0,
                    'alignment',
                    h_count,
                    v_count,
                    direction_balance=balance,
                )

        all_lines = horizontal_lines + vertical_lines
        all_x = []
        all_y = []
        for line in all_lines:
            all_x.extend([line['x0'], line['x1']])
            all_y.extend([line['y0'], line['y1']])

        x_median = np.median(all_x)
        y_median = np.median(all_y)
        x_mad = np.median([abs(x - x_median) for x in all_x])
        y_mad = np.median([abs(y - y_median) for y in all_y])

        x_lower = x_median - 1.5 * x_mad
        x_upper = x_median + 1.5 * x_mad
        y_lower = y_median - 1.5 * y_mad
        y_upper = y_median + 1.5 * y_mad

        main_region_area = (x_upper - x_lower) * (y_upper - y_lower)
        page_area = self.page.width * self.page.height

        main_region_lines = 0
        for line in all_lines:
            line_x_min = min(line['x0'], line['x1'])
            line_x_max = max(line['x0'], line['x1'])
            line_y_min = min(line['y0'], line['y1'])
            line_y_max = max(line['y0'], line['y1'])
            if (line_x_max >= x_lower and line_x_min <= x_upper and
                    line_y_max >= y_lower and line_y_min <= y_upper):
                main_region_lines += 1

        line_concentration = main_region_lines / len(all_lines)
        area_ratio = main_region_area / page_area if page_area else 0.0
        direction_balance = (
            min(h_count, v_count) / max(h_count, v_count) if max(h_count, v_count) > 0 else 0.0
        )
        final_score = (
            line_concentration * 0.6 +
            (1.0 - area_ratio) * 0.2 +
            direction_balance * 0.2
        )
        table_type: Literal['bordered', 'unbordered'] = (
            'bordered' if final_score > 0.6 else 'unbordered'
        )
        return self._classification_result(
            table_type,
            final_score,
            'mad',
            h_count,
            v_count,
            line_concentration=line_concentration,
            area_ratio=area_ratio,
            direction_balance=direction_balance,
        )

    def predict_table_type(self) -> Literal['bordered', 'unbordered']:
        """Docstring."""
        return self.classify()['table_type']
    
    
    def _quick_alignment_check(self, lines, direction):
        """Docstring."""
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        write_debug_log(
            location="table_type_classifier.py:254",
            message="alignment check entry",
            data={
                "lines_count": len(lines),
                "direction": direction
            },
            hypothesis_id="D"
        )
        # #endregion
        
        if len(lines) < 3:
            # #region agent log
            write_debug_log(
                location="table_type_classifier.py:269",
                message="alignment check: insufficient lines",
                data={"lines_count": len(lines), "min_required": 3},
                hypothesis_id="D"
            )
            # #endregion
            return 0.0
        
        # Comment.
        coord_key = 'y0' if direction == 'horizontal' else 'x0'
        coords = sorted([line[coord_key] for line in lines])
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:273",
            message="coordinates extracted and sorted",
            data={
                "direction": direction,
                "coord_key": coord_key,
                "coords_count": len(coords),
                "coord_range": [min(coords), max(coords)] if coords else None
            },
            hypothesis_id="D"
        )
        # #endregion
        
        # Comment.
        tolerance = 3
        
        groups = []
        current_group = [coords[0]]
        
        # Comment.
        for i in range(1, len(coords)):
            if coords[i] - current_group[-1] <= tolerance:
                current_group.append(coords[i])
            else:
                groups.append(current_group)
                current_group = [coords[i]]
        groups.append(current_group)
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:289",
            message="coordinates grouped",
            data={
                "direction": direction,
                "tolerance": tolerance,
                "groups_count": len(groups),
                "group_sizes": [len(g) for g in groups],
                "max_group_size": max(len(g) for g in groups) if groups else 0
            },
            hypothesis_id="D"
        )
        # #endregion
        
        # Comment.
        max_group_size = max(len(g) for g in groups)
        alignment_ratio = max_group_size / len(coords)
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:293",
            message="alignment ratio calculated",
            data={
                "direction": direction,
                "max_group_size": max_group_size,
                "total_coords": len(coords),
                "alignment_ratio": alignment_ratio
            },
            hypothesis_id="D"
        )
        # #endregion
        
        return alignment_ratio
    
    def _calculate_dynamic_threshold(self):
        """Docstring."""
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        write_debug_log(
            location="table_type_classifier.py:297",
            message="dynamic threshold calculation entry",
            data={
                "page_width": float(self.page.width),
                "page_height": float(self.page.height)
            },
            hypothesis_id="D"
        )
        # #endregion
        
        # Comment.
        a4_width = 595.0
        a4_height = 842.0
        a4_area = a4_width * a4_height
        base_threshold = 10
        
        # Comment.
        page_area = self.page.width * self.page.height
        
        # Comment.
        area_ratio = page_area / a4_area
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:319",
            message="area ratio calculated",
            data={
                "a4_area": a4_area,
                "page_area": float(page_area),
                "area_ratio": float(area_ratio)
            },
            hypothesis_id="D"
        )
        # #endregion
        
        # Comment.
        # Comment.
        raw_threshold = base_threshold * np.sqrt(area_ratio)
        dynamic_threshold = int(raw_threshold)
        
        # Comment.
        dynamic_threshold = max(10, min(dynamic_threshold, 30))
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:323",
            message="dynamic threshold calculated and clamped",
            data={
                "base_threshold": base_threshold,
                "raw_threshold": float(raw_threshold),
                "final_threshold": dynamic_threshold,
                "was_clamped": dynamic_threshold != int(raw_threshold) or dynamic_threshold < 10 or dynamic_threshold > 30
            },
            hypothesis_id="D"
        )
        # #endregion
        
        self.logger.debug(
            f"Dynamic threshold calculation: page size={self.page.width:.1f}x{self.page.height:.1f}pt, "
            f"area ratio={area_ratio:.2f}, threshold={dynamic_threshold}"
        )
        
        return dynamic_threshold

