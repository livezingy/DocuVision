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
    
    
    def predict_table_type(self) -> Literal['bordered', 'unbordered']:
        """Docstring."""
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        write_debug_log(
            location="table_type_classifier.py:39",
            message="predict_table_type entry",
            data={},
            hypothesis_id="D"
        )
        # #endregion
        
        horizontal_lines = self.analyzer.line_analysis['horizontal_lines']
        vertical_lines = self.analyzer.line_analysis['vertical_lines']
        h_count = len(horizontal_lines)
        v_count = len(vertical_lines)
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:55",
            message="line counts for quick filter",
            data={
                "h_count": h_count,
                "v_count": v_count,
                "total_lines": h_count + v_count
            },
            hypothesis_id="D"
        )
        # #endregion
        
        # Comment.
        
        # Comment.
        if h_count < 3 or v_count < 3:
            # #region agent log
            write_debug_log(
                location="table_type_classifier.py:61",
                message="quick filter: unbordered (insufficient lines)",
                data={
                    "h_count": h_count,
                    "v_count": v_count,
                    "h_threshold_met": h_count >= 3,
                    "v_threshold_met": v_count >= 3
                },
                hypothesis_id="D"
            )
            # #endregion
            self.logger.info(
            )
            return 'unbordered'
        
        # Comment.
        # Comment.
        dynamic_threshold = self._calculate_dynamic_threshold()
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:69",
            message="dynamic threshold calculated",
            data={
                "dynamic_threshold": dynamic_threshold,
                "h_count": h_count,
                "v_count": v_count,
                "h_exceeds_threshold": h_count > dynamic_threshold,
                "v_exceeds_threshold": v_count > dynamic_threshold
            },
            hypothesis_id="D"
        )
        # #endregion
        
        if h_count > dynamic_threshold and v_count > dynamic_threshold:
            # Comment.
            h_aligned = self._quick_alignment_check(horizontal_lines, 'horizontal')
            v_aligned = self._quick_alignment_check(vertical_lines, 'vertical')
            
            # #region agent log
            write_debug_log(
                location="table_type_classifier.py:72",
                message="alignment check results",
                data={
                    "h_aligned": h_aligned,
                    "v_aligned": v_aligned,
                    "both_aligned": h_aligned > 0.6 and v_aligned > 0.6
                },
                hypothesis_id="D"
            )
            # #endregion
            
            if h_aligned > 0.6 and v_aligned > 0.6:
                # #region agent log
                write_debug_log(
                    location="table_type_classifier.py:75",
                    message="quick filter: bordered (many lines and aligned)",
                    data={
                        "h_count": h_count,
                        "v_count": v_count,
                        "h_aligned": h_aligned,
                        "v_aligned": v_aligned,
                        "dynamic_threshold": dynamic_threshold
                    },
                    hypothesis_id="D"
                )
                # #endregion
                self.logger.info(
                    f"[Quick Judgment] Many lines and aligned (H:{h_aligned:.2f}, V:{v_aligned:.2f}, "
                )
                return 'bordered'
        
        # Comment.
        # Comment.
        
        all_lines = horizontal_lines + vertical_lines
        
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        try:
            write_debug_log(
                location="table_type_classifier.py:164",
                message="entering standard judgment layer",
                data={
                    "all_lines_count": len(all_lines),
                    "h_count": h_count,
                    "v_count": v_count,
                    "dynamic_threshold": dynamic_threshold
                },
                hypothesis_id="D"
            )
        except Exception as e:
            self.logger.warning(f"Debug log write failed at standard judgment entry: {e}")
        # #endregion
        
        all_x = []
        all_y = []
        for line in all_lines:
            all_x.extend([line['x0'], line['x1']])
            all_y.extend([line['y0'], line['y1']])
        
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        try:
            write_debug_log(
                location="table_type_classifier.py:171",
                message="line coordinates extracted",
                data={
                    "x_coords_count": len(all_x),
                    "y_coords_count": len(all_y),
                    "x_range": [float(min(all_x)), float(max(all_x))] if all_x else None,
                    "y_range": [float(min(all_y)), float(max(all_y))] if all_y else None
                },
                hypothesis_id="D"
            )
        except Exception as e:
            self.logger.warning(f"Debug log write failed at coordinates extraction: {e}")
        # #endregion
        
        # Comment.
        x_median = np.median(all_x)
        y_median = np.median(all_y)
        
        x_mad = np.median([abs(x - x_median) for x in all_x])
        y_mad = np.median([abs(y - y_median) for y in all_y])
        
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        try:
            write_debug_log(
                location="table_type_classifier.py:175",
                message="MAD values calculated",
                data={
                    "x_median": float(x_median),
                    "y_median": float(y_median),
                    "x_mad": float(x_mad),
                    "y_mad": float(y_mad),
                    "x_mad_valid": bool(x_mad > 0),
                    "y_mad_valid": bool(y_mad > 0)
                },
                hypothesis_id="D"
            )
        except Exception as e:
            self.logger.warning(f"Debug log write failed at MAD calculation: {e}")
        # #endregion
        
        # Comment.
        x_lower = x_median - 1.5 * x_mad
        x_upper = x_median + 1.5 * x_mad
        y_lower = y_median - 1.5 * y_mad
        y_upper = y_median + 1.5 * y_mad
        
        # Comment.
        main_region_area = (x_upper - x_lower) * (y_upper - y_lower)
        page_area = self.page.width * self.page.height
        
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        try:
            write_debug_log(
                location="table_type_classifier.py:183",
                message="concentration region calculated",
                data={
                    "x_bounds": [float(x_lower), float(x_upper)],
                    "y_bounds": [float(y_lower), float(y_upper)],
                    "main_region_area": float(main_region_area),
                    "page_area": float(page_area),
                    "page_size": [float(self.page.width), float(self.page.height)]
                },
                hypothesis_id="D"
            )
        except Exception as e:
            self.logger.warning(f"Debug log write failed at concentration region: {e}")
        # #endregion
        
        # Comment.
        main_region_lines = 0
        for line in all_lines:
            line_x_min = min(line['x0'], line['x1'])
            line_x_max = max(line['x0'], line['x1'])
            line_y_min = min(line['y0'], line['y1'])
            line_y_max = max(line['y0'], line['y1'])
            
            # Comment.
            if (line_x_max >= x_lower and line_x_min <= x_upper and
                line_y_max >= y_lower and line_y_min <= y_upper):
                main_region_lines += 1
        
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        try:
            write_debug_log(
                location="table_type_classifier.py:199",
                message="lines in concentration region counted",
                data={
                    "main_region_lines": main_region_lines,
                    "total_lines": len(all_lines),
                    "lines_outside_region": len(all_lines) - main_region_lines
                },
                hypothesis_id="D"
            )
        except Exception as e:
            self.logger.warning(f"Debug log write failed at lines counting: {e}")
        # #endregion
        
        # Comment.
        line_concentration = main_region_lines / len(all_lines)
        area_ratio = main_region_area / page_area
        
        # Comment.
        direction_balance = min(h_count, v_count) / max(h_count, v_count) if max(h_count, v_count) > 0 else 0
        
        # Comment.
        final_score = (
            line_concentration * 0.6 +
            (1.0 - area_ratio) * 0.2 +
            direction_balance * 0.2
        )
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:123",
            message="standard judgment metrics calculated",
            data={
                "line_concentration": line_concentration,
                "area_ratio": area_ratio,
                "direction_balance": direction_balance,
                "final_score": final_score,
                "threshold": 0.6,
                "is_bordered": final_score > 0.6
            },
            hypothesis_id="D"
        )
        # #endregion
        
        self.logger.info(
            f"[Standard Judgment] concentration={line_concentration:.2f}, "
            f"area_ratio={area_ratio:.2f}, balance={direction_balance:.2f}, "
            f"score={final_score:.2f}"
        )
        
        is_bordered = final_score > 0.6
        
        # #region agent log
        write_debug_log(
            location="table_type_classifier.py:142",
            message="final prediction",
            data={
                "predicted_type": "bordered" if is_bordered else "unbordered",
                "final_score": final_score
            },
            hypothesis_id="D"
        )
        # #endregion
        
        return 'bordered' if is_bordered else 'unbordered'
    
    
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

