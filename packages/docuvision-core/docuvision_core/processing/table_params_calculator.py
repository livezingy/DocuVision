# core/processing/table_params_calculator.py
"""table params calculator module."""

from typing import Dict, Optional, Tuple
import numpy as np
from docuvision_core.utils.logger import AppLogger
import math


class TableParamsCalculator:
    """Docstring."""
    
    def __init__(self, feature_analyzer):
        """Docstring."""
        self.analyzer = feature_analyzer
        self.page = feature_analyzer.page
        self.logger = AppLogger.get_logger()
    
    
    def get_pdfplumber_params(self, table_type: str = 'bordered') -> Dict:
        """Docstring."""
        
        # Comment.
        h_lines = self.analyzer.line_analysis.get('horizontal_lines', [])
        v_lines = self.analyzer.line_analysis.get('vertical_lines', [])
        h_count = len(h_lines)
        v_count = len(v_lines)
        
        
        # Comment.
        if table_type == 'bordered':
            vertical_strategy = 'lines' if v_count >= 5 else 'text'
            horizontal_strategy = 'lines' if h_count >= 10 else 'text'
            
            
            self.logger.debug(
                f"Bordered table strategy: V={vertical_strategy}(count={v_count}), "
                f"H={horizontal_strategy}(count={h_count})"
            )
        else:
            vertical_strategy = 'text'
            horizontal_strategy = 'lines' if h_count >= 3 else 'text'
            
            
            self.logger.debug(
                f"Unbordered table strategy: V={vertical_strategy}, "
                f"H={horizontal_strategy}(count={h_count})"
            )
        
        # Comment.
        params = {
            'vertical_strategy': vertical_strategy,
            'horizontal_strategy': horizontal_strategy,
            # Parallel lines within snap_tolerance points will be merged to the same 
            # horizontal or vertical position.
            'snap_tolerance': 2,
            # Line segments on the same infinite line, and whose ends are within 
            # join_tolerance of one another, will be joined into a single line segment.
            'join_tolerance': 2,
            # The minimum length of a line segment that is considered to be part of a table edge.
            'edge_min_length': 3,
            # When combining edges into cells, orthogonal edges must be within 
            # intersection_tolerance points to be considered intersecting.
            'intersection_tolerance': 3,
            #When using "vertical_strategy": "text", at least min_words_vertical words must share the same alignment.
            'min_words_vertical': 1,
            #When using "horizontal_strategy": "text", at least min_words_horizontal words must share the same alignment.
            'min_words_horizontal': 1,
            #These text_-prefixed settings also apply to the table-identification algorithm when the text strategy is used. 
            # I.e., when that algorithm searches for words, it will expect the individual letters in each word to be
            #  no more than text_x_tolerance/text_y_tolerance points apart.
            'text_x_tolerance': 3,
            'text_y_tolerance': 5
        }
        
        # Comment.
        
        if self.analyzer.char_analysis.get('min_width', 0) > 0 and self.analyzer.char_analysis.get('min_height', 0) > 0:
            min_char_size = min(self.analyzer.char_analysis['min_width'], 
                               self.analyzer.char_analysis['min_height'])
            raw_snap_tolerance = min_char_size * 0.3
            
            # Comment.
            # Comment.
            if min_char_size > 10:
                max_snap_tolerance = 15
            elif min_char_size > 5:
                max_snap_tolerance = 10
            else:
                max_snap_tolerance = 10
            
            params['snap_tolerance'] = max(0.5, min(raw_snap_tolerance, max_snap_tolerance))
            
            
            self.logger.debug(
                f"snap_tolerance={params['snap_tolerance']:.2f} "
                f"(min_char_size={min_char_size:.2f})"
            )
        
        # Comment.
        if self.analyzer.char_analysis['min_width'] > 0 and self.analyzer.char_analysis['min_height'] > 0:
            min_char_size = min(self.analyzer.char_analysis['min_width'], 
                               self.analyzer.char_analysis['min_height'])
            params['join_tolerance'] = min_char_size * 0.3
            params['join_tolerance'] = max(1, min(params['join_tolerance'], 10))
            
            self.logger.debug(
                f"join_tolerance={params['join_tolerance']:.2f} "
                f"(min_char_size={min_char_size:.2f})"
            )
        
        # Comment.
        if self.analyzer.char_analysis['mode_width'] > 0 and self.analyzer.char_analysis['mode_height'] > 0:
            mode_char_size = max(self.analyzer.char_analysis['mode_width'], 
                                self.analyzer.char_analysis['mode_height'])
            params['edge_min_length'] = mode_char_size
            params['edge_min_length'] = max(1, min(params['edge_min_length'], 30))
            
            self.logger.debug(
                f"edge_min_length={params['edge_min_length']:.2f} "
                f"(mode_char_size={mode_char_size:.2f})"
            )
        elif self.analyzer.char_analysis['min_width'] > 0 or self.analyzer.char_analysis['min_height'] > 0:
            min_char_size = max(self.analyzer.char_analysis['min_width'], 
                               self.analyzer.char_analysis['min_height'])
            params['edge_min_length'] = min_char_size
            params['edge_min_length'] = max(1, min(params['edge_min_length'], 30))
            
            self.logger.debug(
                f"edge_min_length={params['edge_min_length']:.2f} "
                f"(min_char_size={min_char_size:.2f})"
            )
        
        # Comment.
        if self.analyzer.char_analysis['mode_width'] > 0 or self.analyzer.char_analysis['mode_height'] > 0:
            max_mode_size = max(self.analyzer.char_analysis['mode_width'], 
                               self.analyzer.char_analysis['mode_height'])
            params['intersection_tolerance'] = max_mode_size * 0.5
            params['intersection_tolerance'] = max(1, min(params['intersection_tolerance'], 10))
            
            self.logger.debug(
                f"intersection_tolerance={params['intersection_tolerance']:.2f} "
                f"(max_mode_size={max_mode_size:.2f})"
            )
        elif self.analyzer.char_analysis['min_width'] > 0 or self.analyzer.char_analysis['min_height'] > 0:
            max_min_size = max(self.analyzer.char_analysis['min_width'], 
                              self.analyzer.char_analysis['min_height'])
            params['intersection_tolerance'] = max_min_size * 0.5
            params['intersection_tolerance'] = max(1, min(params['intersection_tolerance'], 10))
            
            self.logger.debug(
                f"intersection_tolerance={params['intersection_tolerance']:.2f} "
                f"(max_min_size={max_min_size:.2f})"
            )
        
        # Comment.
        if self.analyzer.text_line_analysis['total_lines'] > 0:
            total_lines = self.analyzer.text_line_analysis['total_lines']
            # Comment.
            if total_lines < 10:
                min_words = max(1, min(int(total_lines * 0.2), 5))
            else:
                min_words = max(3, min(int(total_lines * 0.2), 10))
            params['min_words_vertical'] = min_words
            
            self.logger.debug(
                f"min_words_vertical={params['min_words_vertical']} "
                f"(total_lines={total_lines}, dynamic_range=True)"
            )
        
        # Comment.
        # Comment.
        if self.analyzer.char_analysis.get('mode_width', 0) > 0:
            base_tolerance = self.analyzer.char_analysis['mode_width'] * 1.5
            # Comment.
            max_tolerance = max(10, self.analyzer.char_analysis['mode_width'] * 3)
            params['text_x_tolerance'] = max(1, min(base_tolerance, max_tolerance))
            
            self.logger.debug(
                f"text_x_tolerance={params['text_x_tolerance']:.2f} "
                f"(mode_width={self.analyzer.char_analysis['mode_width']:.2f}, "
                f"max_tolerance={max_tolerance:.2f})"
            )
        elif self.analyzer.char_analysis.get('min_width', 0) > 0:
            base_tolerance = self.analyzer.char_analysis['min_width'] * 1.5
            # Comment.
            max_tolerance = max(10, self.analyzer.char_analysis['min_width'] * 3)
            params['text_x_tolerance'] = max(1, min(base_tolerance, max_tolerance))
            
            self.logger.debug(
                f"text_x_tolerance={params['text_x_tolerance']:.2f} "
                f"(min_width={self.analyzer.char_analysis['min_width']:.2f}, "
                f"max_tolerance={max_tolerance:.2f}, fallback=True)"
            )
        
        # Comment.
        if self.analyzer.text_line_analysis.get('min_line_height', 0) > 0:
            params['text_y_tolerance'] = self.analyzer.text_line_analysis['min_line_height'] * 0.2
            params['text_y_tolerance'] = max(1, min(params['text_y_tolerance'], 8))
            
            self.logger.debug(
                f"text_y_tolerance={params['text_y_tolerance']:.2f} "
                f"(min_line_height={self.analyzer.text_line_analysis['min_line_height']:.2f})"
            )
        
        # Comment.
        params_before_validation = params.copy()
        params = self._validate_params(params)
        
        
        self.logger.debug(f"Final pdfplumber params: {params}")
        
        return params
    
    
    def get_camelot_lattice_params(self, image_shape: Optional[Tuple] = None) -> Dict:
        """Docstring."""
        params = {
            'flavor': 'lattice',
            'line_scale': 40,
            'line_tol': 2,
            'joint_tol': 2
        }
        
        h_lines = self.analyzer.line_analysis['horizontal_lines']
        v_lines = self.analyzer.line_analysis['vertical_lines']
        h_lengths = self.analyzer.line_analysis['horizontal_lines_length']
        v_lengths = self.analyzer.line_analysis['vertical_lines_length']
        
        # Comment.
        h_short_threshold, v_short_threshold = self._calculate_adaptive_short_line_thresholds(
            h_lengths, v_lengths
        )
        
        short_h_count = len([l for l in h_lengths if l < h_short_threshold])
        short_v_count = len([l for l in v_lengths if l < v_short_threshold])
        short_h_ratio = short_h_count / len(h_lines) if h_lines else 0
        short_v_ratio = short_v_count / len(v_lines) if v_lines else 0
        
        self.logger.info(f"Dynamic thresholds - H: {h_short_threshold:.2f}, V: {v_short_threshold:.2f}")
        self.logger.info(f"Short line ratios - H: {short_h_ratio:.2f}, V: {short_v_ratio:.2f}")
        
        # Comment.
        if image_shape:
            line_widths = self.analyzer.line_analysis.get('line_widths', [])
            if line_widths and len(line_widths) > 0:
                # Comment.
                from docuvision_core.processing.page_feature_analyzer import PageFeatureAnalyzer
                mode_line_width = PageFeatureAnalyzer._get_mode_with_fallback(line_widths)
                if mode_line_width > 0:
                    # Comment.
                    pdf_to_image_ratio = min(image_shape[0] / self.page.height, 
                                            image_shape[1] / self.page.width)
                    
                    # Comment.
                    mode_line_width_image = mode_line_width * pdf_to_image_ratio
                    
                    # Comment.
                    desired_kernel_length = mode_line_width_image * 3
                    
                    # Comment.
                    if desired_kernel_length > 0:
                        line_scale_v = image_shape[0] / desired_kernel_length
                        line_scale_h = image_shape[1] / desired_kernel_length
                        # Comment.
                        line_scale = min(line_scale_v, line_scale_h)
                        
                        # Comment.
                        if mode_line_width < 0.5:
                            max_line_scale = 100
                        elif mode_line_width < 1.0:
                            max_line_scale = 75
                        else:
                            max_line_scale = 50
                        
                        params['line_scale'] = max(15, min(int(line_scale), max_line_scale))
                        
                        self.logger.debug(
                            f"line_scale={params['line_scale']} "
                            f"(mode_line_width={mode_line_width:.2f}pt, "
                            f"mode_line_width_image={mode_line_width_image:.2f}px, "
                            f"desired_kernel_length={desired_kernel_length:.2f}px, "
                            f"max_line_scale={max_line_scale})"
                        )
                    else:
                        params['line_scale'] = 40
                else:
                    params['line_scale'] = 40
            else:
                params['line_scale'] = 40
        
        # Comment.
        if self.analyzer.char_analysis['min_width'] > 0 and self.analyzer.char_analysis['min_height'] > 0:
            min_char_size = min(self.analyzer.char_analysis['min_width'], 
                               self.analyzer.char_analysis['min_height'])
            line_tol = min_char_size * 0.3
            params['line_tol'] = max(0.5, min(line_tol, 3))
            params['joint_tol'] = params['line_tol']  # joint_tol = line_tol
            
            self.logger.debug(
                f"line_tol=joint_tol={params['line_tol']:.2f} "
                f"(min_char_size={min_char_size:.2f})"
            )
        else:
            params['line_tol'] = 2
            params['joint_tol'] = 2
        
        return params
    
    
    def get_camelot_stream_params(self) -> Dict:
        """Docstring."""
        params = {
            'flavor': 'stream',
            'edge_tol': 50,
            'row_tol': 2,
            'column_tol': 0
        }
        
        # Comment.
        min_line_spacing = self.analyzer.text_line_analysis.get('min_line_spacing', 0)
        max_line_height = self.analyzer.text_line_analysis.get('max_line_height', 0)
        
        if min_line_spacing > 0 or max_line_height > 0:
            # Comment.
            edge_tol_min = min_line_spacing + max_line_height
            
            # Comment.
            edge_tol_max = self.page.height / 3
            
            # Comment.
            if self.analyzer.text_line_analysis.get('mode_line_spacing', 0) > 0:
                mode_line_spacing = self.analyzer.text_line_analysis['mode_line_spacing']
                mode_line_height = self.analyzer.text_line_analysis.get('mode_line_height', 0)
                if mode_line_height > 0:
                    edge_tol = mode_line_spacing * 3 + mode_line_height * 2
                else:
                    edge_tol = mode_line_spacing * 3 + max_line_height * 2
            else:
                # Comment.
                edge_tol = edge_tol_min
            
            # Comment.
            params['edge_tol'] = max(edge_tol_min, min(edge_tol, edge_tol_max))
            
            self.logger.debug(
                f"edge_tol={params['edge_tol']:.2f} "
                f"(min={edge_tol_min:.2f}, max={edge_tol_max:.2f}, "
                f"calculated={edge_tol:.2f})"
            )
        else:
            # Comment.
            params['edge_tol'] = 50
        
        # Comment.
        if self.analyzer.char_analysis.get('mode_height', 0) > 0:
            # Comment.
            params['row_tol'] = math.ceil(self.analyzer.char_analysis['mode_height'])
            # Comment.
            max_row_tol = self.analyzer.char_analysis['mode_height'] * 1.5
            params['row_tol'] = max(2, min(params['row_tol'], max_row_tol))
            
            self.logger.debug(
                f"row_tol={params['row_tol']:.2f} "
                f"(mode_char_height={self.analyzer.char_analysis['mode_height']:.2f}, "
                f"max_row_tol={max_row_tol:.2f})"
            )
        elif self.analyzer.char_analysis.get('min_height', 0) > 0:
            # Comment.
            params['row_tol'] = max(2, min(self.analyzer.char_analysis['min_height'], 10))
            
            self.logger.debug(
                f"row_tol={params['row_tol']:.2f} "
                f"(min_char_height={self.analyzer.char_analysis['min_height']:.2f}, fallback=True)"
            )
        else:
            params['row_tol'] = 2
        
        # Comment.
        if self.analyzer.char_analysis['min_width'] > 0:
            params['column_tol'] = self.analyzer.char_analysis['min_width']
            params['column_tol'] = max(0, min(params['column_tol'], 5))
            
            self.logger.debug(
                f"column_tol={params['column_tol']:.2f} "
                f"(min_char_width={self.analyzer.char_analysis['min_width']:.2f})"
            )
        else:
            params['column_tol'] = 0
        
        return params
    
    
    def _calculate_adaptive_short_line_thresholds(self, h_lengths, v_lengths) -> Tuple[float, float]:
        """Docstring."""
        if not h_lengths or not v_lengths:
            return 200, 150
        
        # Comment.
        h_q25 = np.percentile(h_lengths, 25)
        v_q25 = np.percentile(v_lengths, 25)
        
        # Comment.
        h_median = np.median(h_lengths)
        v_median = np.median(v_lengths)
        h_median_thresh = h_median * 0.6
        v_median_thresh = v_median * 0.6
        
        # Comment.
        h_mean = np.mean(h_lengths)
        v_mean = np.mean(v_lengths)
        h_std = np.std(h_lengths)
        v_std = np.std(v_lengths)
        h_std_thresh = max(h_mean - h_std, h_mean * 0.4)
        v_std_thresh = max(v_mean - v_std, v_mean * 0.4)
        
        # Comment.
        h_candidates = [h_q25, h_median_thresh, h_std_thresh]
        v_candidates = [v_q25, v_median_thresh, v_std_thresh]
        
        h_threshold = np.median(h_candidates)
        v_threshold = np.median(v_candidates)
        
        # Comment.
        h_threshold = max(30, min(h_threshold, h_median * 0.8))
        v_threshold = max(30, min(v_threshold, v_median * 0.8))
        
        return h_threshold, v_threshold
    
    
    def _validate_params(self, params: dict) -> dict:
        """Docstring."""
        # Comment.
        # Comment.
        bounds = {
            'snap_tolerance': (0.5, 15),
            'join_tolerance': (1, 10),
            'edge_min_length': (1, 30),
            'intersection_tolerance': (1, 10),
            'min_words_vertical': (1, 10),
            'min_words_horizontal': (1, 5),
            'text_x_tolerance': (1, 30),
            'text_y_tolerance': (1, 8)
        }
        
        validated = params.copy()
        
        for key, (min_val, max_val) in bounds.items():
            if key in validated:
                original_val = validated[key]
                validated[key] = max(min_val, min(validated[key], max_val))
                
                if validated[key] != original_val:
                    self.logger.debug(
                        f"(bounds: [{min_val}, {max_val}])"
                    )
        
        return validated

