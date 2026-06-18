# core/models/table_parser.py
"""table parser module."""
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import pandas as pd
import asyncio, string
from docuvision_core.models.table_models import TableModels
from docuvision_core.utils.logger import AppLogger
import numpy as np
import os

# Comment.
# Comment.
os.environ.setdefault('OPENCV_IO_ENABLE_OPENEXR', '0')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('DISPLAY', '')

try:
    import cv2
    # Comment.
    try:
        cv2.setNumThreads(1)
    except:
        pass
except ImportError as e:
    # Comment.
    import warnings
    warnings.warn(f"Failed to import cv2: {e}. Some features may be unavailable.")
    cv2 = None
from collections import Counter
from itertools import tee, count
from docuvision_core.utils.path_utils import get_app_dir
import easyocr
from docuvision_core.utils.easyocr_config import get_easyocr_reader
from tqdm.auto import tqdm
import csv
import os, torch



class TableParser:
    """Docstring."""
    def __init__(self, app_config):
        self.models_config = app_config.get('table_models', {})
        self.logger = AppLogger.get_logger()
        self.base_dir = get_app_dir()

        try:
            self.models = TableModels(self.models_config)
        except Exception as e:
            self.logger.error(f"TableParser initialization error: {str(e)}", exc_info=True)
            self.models = None

        parser_cfg = app_config.get('table_parser', {})
        self.structure_border_width = parser_cfg.get('structure_border_width', 5)
        self.structure_preprocess = parser_cfg.get('structure_preprocess', True)
        self.structure_expand_rowcol = parser_cfg.get('structure_expand_rowcol', 5)
        self.cell_ocr_enabled = parser_cfg.get('cell_ocr_enabled', True)
        self.table_ocr_engine = (parser_cfg.get('table_ocr_engine') or 'easyocr').lower()
        self.table_ocr_languages = parser_cfg.get('table_ocr_languages') or ['eng']
    


    async def parser_image(self, image: Image.Image, params: Optional[dict] = None) -> dict:
        """Docstring."""
        try:
            # Comment.
            if not self.models:
                self.logger.error("TableParser.models is None, cannot detect tables")
                return {'success': False, 'error': 'TableParser models not initialized', 'tables': []}
            
            # Comment.
            if not image or not hasattr(image, 'size'):
                self.logger.error("Invalid image provided to parser_image")
                return {'success': False, 'error': 'Invalid image', 'tables': []}
            self.logger.info("TableParser.models is initialized")
            boxes, scores, labels = self.models.detect_tables(image)
            self.logger.info(f"Detected {len(boxes) if boxes is not None else 0} tables in image")
            # Comment.
            boxes_is_empty = (
                boxes is None or
                (hasattr(boxes, 'size') and getattr(boxes, 'size') == 0) or
                (hasattr(boxes, '__len__') and len(boxes) == 0)
            )
            if boxes_is_empty:
                self.logger.info("No tables detected in image")
                return {'success': True, 'error': None, 'tables': []}
            # Comment.
            try:
                boxes_arr = np.asarray(boxes)
            except Exception:
                boxes_arr = boxes
            try:
                scores_arr = np.asarray(scores).reshape(-1) 
            except Exception:
                scores_arr = scores
            
            tables = []
            invalid_bbox_count = 0
            valid_bbox_count = 0
            
            for i, bbox in enumerate(boxes_arr):
                try:
                    
                    # Comment.
                    bbox_arr = np.asarray(bbox).reshape(-1)
                    
                    
                    if bbox_arr.shape[0] < 4:
                        invalid_bbox_count += 1
                        self.logger.warning(f"Invalid bbox shape: {bbox}, skipping")
                        continue
                    
                    x1, y1, x2, y2 = map(float, bbox_arr[:4])
                    
                    # Comment.
                    img_width, img_height = image.size
                    
                    # Comment.
                    violations = {
                        "x1_ge_x2": x1 >= x2,
                        "y1_ge_y2": y1 >= y2,
                        "x1_lt_0": x1 < 0,
                        "y1_lt_0": y1 < 0,
                        "x2_gt_width": x2 > img_width,
                        "y2_gt_height": y2 > img_height
                    }
                    is_valid = not any(violations.values())
                    
                    
                    if not is_valid:
                        invalid_bbox_count += 1
                        self.logger.warning(f"Invalid bbox: {bbox}, skipping")
                        continue
                    
                    valid_bbox_count += 1
                    
                    table_img = image.crop((x1, y1, x2, y2))
                    table_info = await self.parse_table(table_img, (x1, y1, x2, y2), params, image)
                    if table_info:
                        try:
                            # Comment.
                            detection_confidence = float(scores_arr[i]) if (hasattr(scores_arr, '__len__') and i < len(scores_arr)) else 1.0
                        except Exception:
                            detection_confidence = 1.0
                        
                        # Comment.
                        structure_confidence = table_info.get('structure_confidence', 0.8)
                        
                        # Comment.
                        weighted_score = 0.6 * detection_confidence + 0.4 * structure_confidence
                        
                        # Comment.
                        table_info['detection_confidence'] = detection_confidence
                        table_info['structure_confidence'] = structure_confidence
                        table_info['score'] = weighted_score
                        table_info['bbox'] = (x1, y1, x2, y2)
                        
                        tables.append(table_info)
                except Exception as e:
                    self.logger.error(f"Error processing table {i}: {str(e)}")
                    continue
                    
            
            self.logger.info(f"Successfully parsed {len(tables)} tables from image")
            return {'success': True, 'error': None, 'tables': tables}
            
        except Exception as e:
            self.logger.error(f"Error parsing image: {e}", exc_info=True)
            return {'success': False, 'error': str(e), 'tables': []}


    async def parse_table(self, table_image: Image.Image, bbox: Tuple[float, float, float, float], params: Optional[dict] = None, original_image: Image.Image = None) -> Optional[dict]:
        """Docstring."""
        try:
            # Comment.
            if not self.models:
                self.logger.error("TableParser.models is None, cannot parse table")
                return None
            
            # Comment.
            if not table_image or not hasattr(table_image, 'size'):
                self.logger.error("Invalid table_image provided to parse_table")
                return None
            
            pipeline = TableExtractionPipeline(
                cell_ocr_enabled=self.cell_ocr_enabled,
                table_ocr_engine=self.table_ocr_engine,
                table_ocr_languages=self.table_ocr_languages,
            )
            # Use params or fallback to self.config        
            border_width = self.structure_border_width
            preprocess = self.structure_preprocess
            expand_rowcol = self.structure_expand_rowcol
            self.logger.debug(f"TableParser.parse_table params: border_width={border_width}, preprocess={preprocess}, expand_rowcol={expand_rowcol}")
            
            # Comment.
            try:
                self.logger.info("Using recognize_structure main processing method")
                tables = await pipeline.start_process_with_whole_ocr(
                    table_image, self.models, preprocess, original_image, bbox)
                """ tables = asyncio.run(pipeline.start_process(
                    input_Image=table_image,
                    padd_top=border_width, padd_left=border_width, padd_bottom=border_width, padd_right=border_width,
                    expand_rowcol_bbox_top=expand_rowcol, expand_rowcol_bbox_bottom=expand_rowcol,
                    preprocess=preprocess,
                    models=self.models
                )) """
                self.logger.debug(f"TableParser.parse_table got {len(tables) if tables else 0} tables from pipeline")
                    
            except Exception as e:
                self.logger.error(f"Main pipeline processing failed: {str(e)}")
                return None

            # Comment.
            tables_is_empty = (
                tables is None or
                (hasattr(tables, 'size') and getattr(tables, 'size') == 0) or
                (hasattr(tables, '__len__') and len(tables) == 0)
            )
            if tables_is_empty:
                self.logger.warning("No tables returned from pipeline")
                return None
                
            table = tables[0]
            if isinstance(table, pd.DataFrame):
                return {
                    'data': table.to_dict('records'),
                    'columns': table.columns.tolist(),
                    'confidence': 1.0,
                    'structure_confidence': 0.8,
                    'bbox': bbox
                }
            elif isinstance(table, dict) and 'data' in table and 'columns' in table:
                # Comment.
                if 'structure_confidence' not in table:
                    table['structure_confidence'] = 0.8
                return table
            elif hasattr(table, 'data') and hasattr(table, 'columns'):
                return {
                    'data': table.data,
                    'columns': table.columns,
                    'confidence': getattr(table, 'confidence', 1.0),
                    'structure_confidence': getattr(table, 'structure_confidence', 0.8),
                    'bbox': bbox
                }
            else:
                self.logger.warning(f"Unknown table format returned: {type(table)}")
                return None
                
        except Exception as e:
            self.logger.error(f"TableParser.parse_table error: {str(e)}", exc_info=True)
            return None


class TableExtractionPipeline():

    def __init__(
        self,
        *,
        cell_ocr_enabled: bool = True,
        table_ocr_engine: str = "easyocr",
        table_ocr_languages: Optional[List[str]] = None,
    ):
        self.cell_ocr_enabled = cell_ocr_enabled
        self.table_ocr_engine = (table_ocr_engine or "easyocr").lower()
        self.table_ocr_languages = table_ocr_languages or ["eng"]

    @staticmethod
    def _easyocr_language_codes(languages: List[str]) -> List[str]:
        mapping = {"eng": "en", "en": "en"}
        return [mapping.get(lang, lang) for lang in languages]

    def ocr_whole_table(self, table_image, models, table_data=None):
        """Docstring."""
        try:
            import numpy as np

            processed_image = table_image
            engine = self.table_ocr_engine
            languages = self.table_ocr_languages

            if engine == "tesseract":
                import pytesseract

                tess_lang = "+".join(languages) if languages else "eng"
                ocr_data = pytesseract.image_to_data(
                    processed_image,
                    lang=tess_lang,
                    config="--psm 6",
                    output_type=pytesseract.Output.DICT,
                )
                ocr_results = []
                for i in range(len(ocr_data["text"])):
                    text = ocr_data["text"][i].strip()
                    conf = int(ocr_data["conf"][i])
                    if text and conf > 0:
                        x = ocr_data["left"][i]
                        y = ocr_data["top"][i]
                        w = ocr_data["width"][i]
                        h = ocr_data["height"][i]
                        ocr_results.append(
                            {
                                "text": text,
                                "bbox": [x, y, x + w, y + h],
                                "confidence": conf / 100.0,
                                "word_id": i,
                            }
                        )
            else:
                reader = get_easyocr_reader(self._easyocr_language_codes(languages))
                img_array = np.array(processed_image)
                result = reader.readtext(img_array)
                ocr_results = []
                for item in result:
                    bbox_points = item[0]
                    text = item[1]
                    confidence = item[2]
                    x_coords = [point[0] for point in bbox_points]
                    y_coords = [point[1] for point in bbox_points]
                    x1, x2 = min(x_coords), max(x_coords)
                    y1, y2 = min(y_coords), max(y_coords)
                    ocr_results.append(
                        {
                            "text": text,
                            "bbox": [x1, y1, x2, y2],
                            "confidence": confidence,
                        }
                    )
            
            AppLogger.get_logger().info(f"Whole table OCR found {len(ocr_results)} text elements")
            return ocr_results
            
        except Exception as e:
            AppLogger.get_logger().error(f"Whole table OCR failed: {str(e)}")
            return []
    
    def extract_cells_with_spanning_support(self, table_image, cell_coordinates, special_labels=None, models=None):
        """Docstring."""
        try:
            import easyocr
            from docuvision_core.utils.easyocr_config import get_easyocr_reader
            import numpy as np
            import pytesseract
            # Comment.
            # pytesseract.pytesseract.tesseract_cmd = config.get('tesseract_path')
            
            # Initialize EasyOCR reader with local model configuration
            reader = get_easyocr_reader(['en'])
            
            # Step 1: Create spanning cell map
            spanning_cell_map = {}
            if special_labels and 'spanning_cells' in special_labels:
                for spanning_cell in special_labels['spanning_cells']:
                    spanning_bbox = spanning_cell['bbox']
                    covered_cells = self.calculate_spanning_cell_coverage(spanning_bbox, cell_coordinates)
                    
                    if covered_cells:
                        # Use the top-left cell as the key
                        top_left_cell = covered_cells[0]
                        spanning_cell_map[top_left_cell] = {
                            'bbox': spanning_bbox,
                            'covered_cells': covered_cells
                        }
                        AppLogger.get_logger().info(f"Spanning cell at {top_left_cell} covers {len(covered_cells)} cells: {covered_cells}")
            
            # Step 2: Process each cell
            data = {}
            max_num_columns = 0
            
            for row_idx, row_data in enumerate(cell_coordinates):
                row_text = []
                row_cells = row_data['cells']
                
                for col_idx, cell_data in enumerate(row_cells):
                    cell_key = (row_idx, col_idx)
                    
                    # Check if this cell is part of a spanning cell
                    if cell_key in spanning_cell_map:
                        # This is the top-left cell of a spanning cell
                        spanning_info = spanning_cell_map[cell_key]
                        spanning_bbox = spanning_info['bbox']
                        
                        # Crop the spanning cell area
                        x1, y1, x2, y2 = spanning_bbox
                        
                        # Comment.
                        if x1 >= x2 or y1 >= y2:
                            text = ""
                            AppLogger.get_logger().warning(f"Invalid spanning cell bbox: {spanning_bbox}")
                        else:
                            # Comment.
                            x1 = max(0, int(x1))
                            y1 = max(0, int(y1))
                            x2 = min(table_image.width, int(x2))
                            y2 = min(table_image.height, int(y2))
                            
                            # Comment.
                            if x2 <= x1 or y2 <= y1:
                                text = ""
                                AppLogger.get_logger().warning(f"Spanning cell bbox results in invalid crop: ({x1},{y1},{x2},{y2})")
                            else:
                                try:
                                    # Crop spanning cell image
                                    spanning_img = table_image.crop((x1, y1, x2, y2))
                                    
                                    # Comment.
                                    if spanning_img.width < 10 or spanning_img.height < 10:
                                        text = ""
                                        AppLogger.get_logger().debug(f"Spanning cell [{row_idx+1},{col_idx+1}] too small: {spanning_img.size}")
                                    else:
                                        # OCR the spanning cell
                                        img_array = np.array(spanning_img)
                                        result = reader.readtext(img_array)                                        
                                        
                                        if len(result) > 0:
                                            text = " ".join([x[1] for x in result])
                                            AppLogger.get_logger().info(f"Spanning cell [{row_idx+1},{col_idx+1}] OCR: '{text}'")
                                        else:
                                            text = ""
                                            AppLogger.get_logger().info(f"Spanning cell [{row_idx+1},{col_idx+1}] OCR: no text found")
                                        
                                        # OCR the cell with pytesseract
                                        #text = pytesseract.image_to_string(spanning_img, lang='eng')

                                except Exception as e:
                                    text = ""
                                    AppLogger.get_logger().error(f"Error processing spanning cell [{row_idx+1},{col_idx+1}]: {str(e)}")
                        
                        row_text.append(text)
                        
                    elif self._is_cell_covered_by_spanning(cell_key, spanning_cell_map):
                        # This cell is covered by a spanning cell, mark as merged
                        row_text.append("__MERGED__")
                        AppLogger.get_logger().debug(f"Cell [{row_idx+1},{col_idx+1}] is covered by spanning cell")
                        
                    else:
                        # Regular cell processing
                        cell_bbox = cell_data['cell']
                        x1, y1, x2, y2 = cell_bbox
                        
                        # Comment.
                        if x1 >= x2 or y1 >= y2:
                            text = ""
                            AppLogger.get_logger().warning(f"Invalid cell bbox at [{row_idx+1},{col_idx+1}]: {cell_bbox}")
                        else:
                            # Comment.
                            x1 = max(0, int(x1))
                            y1 = max(0, int(y1))
                            x2 = min(table_image.width, int(x2))
                            y2 = min(table_image.height, int(y2))
                            
                            # Comment.
                            if x2 <= x1 or y2 <= y1:
                                text = ""
                                AppLogger.get_logger().warning(f"Cell bbox at [{row_idx+1},{col_idx+1}] results in invalid crop: ({x1},{y1},{x2},{y2})")
                            else:
                                try:
                                    # Crop cell image
                                    cell_img = table_image.crop((x1, y1, x2, y2))
                                    
                                    # Comment.
                                    if cell_img.width < 10 or cell_img.height < 10:
                                        text = ""
                                        AppLogger.get_logger().debug(f"Cell [{row_idx+1},{col_idx+1}] too small: {cell_img.size}")
                                    else:
                                        # OCR the cell
                                        img_array = np.array(cell_img)
                                        result = reader.readtext(img_array)
                                        
                                        if len(result) > 0:
                                            text = " ".join([x[1] for x in result])
                                            AppLogger.get_logger().info(f"Cell [{row_idx+1},{col_idx+1}] OCR: '{text}'")
                                        else:
                                            text = ""
                                            AppLogger.get_logger().info(f"Cell [{row_idx+1},{col_idx+1}] OCR: no text found")
                                    # OCR the cell with pytesseract
                                    # text = pytesseract.image_to_string(spanning_img, lang='eng')        
                                except Exception as e:
                                    text = ""
                                    AppLogger.get_logger().error(f"Error processing cell [{row_idx+1},{col_idx+1}]: {str(e)}")
                        
                        row_text.append(text)
                
                # Update max columns
                if len(row_text) > max_num_columns:
                    max_num_columns = len(row_text)
                
                data[row_idx] = row_text
            
            # Step 3: Normalize row lengths
            AppLogger.get_logger().info(f"Max number of columns: {max_num_columns}")
            for row_idx, row_data in data.items():
                if len(row_data) != max_num_columns:
                    # Pad with empty strings
                    row_data.extend(["" for _ in range(max_num_columns - len(row_data))])
                    data[row_idx] = row_data
            
            AppLogger.get_logger().info(f"Extracted text from {len(data)} rows with spanning cell support")
            return data
            
        except Exception as e:
            AppLogger.get_logger().error(f"Cell extraction with spanning support failed: {str(e)}")
            import traceback
            AppLogger.get_logger().error(f"Error details: {traceback.format_exc()}")
            return {}
    
    def _is_cell_covered_by_spanning(self, cell_key, spanning_cell_map):
        """Docstring."""
        for spanning_info in spanning_cell_map.values():
            if cell_key in spanning_info['covered_cells'][1:]:  # Skip the first cell (top-left)
                return True
        return False
    
    def map_text_to_cells(self, ocr_results, cell_coordinates, special_labels=None):
        """Docstring."""
        try:
            cell_text_map = {}
            covered_cells = set()  # Track cells covered by spanning cells
            
            # Comment.
            available_ocr_results = []
            for i, ocr_result in enumerate(ocr_results):
                ocr_copy = ocr_result.copy()
                ocr_copy['assigned'] = False
                ocr_copy['original_index'] = i
                available_ocr_results.append(ocr_copy)
            
            # Step 1: Process spanning cells first if provided
            if special_labels and 'spanning_cells' in special_labels:
                spanning_cells = special_labels['spanning_cells']
                AppLogger.get_logger().info(f"Processing {len(spanning_cells)} spanning cells")
                
                for spanning_cell in spanning_cells:
                    spanning_bbox = spanning_cell['bbox']
                    
                    AppLogger.get_logger().debug(f"Processing spanning cell bbox: {spanning_bbox}")
                    
                    # Comment.
                    matched_texts, covered_cell_indices = self.enhanced_spanning_cell_text_matching(
                        spanning_bbox, available_ocr_results, cell_coordinates
                    )
                    
                    if matched_texts and covered_cell_indices:
                        # Comment.
                        # Comment.
                        text_rows = self.cluster_texts_by_rows(matched_texts)
                        
                        # Comment.
                        combined_text = self.aggregate_multiline_texts(text_rows)
                        
                        # Comment.
                        avg_confidence = sum(t['confidence'] for t in matched_texts) / len(matched_texts)
                        
                        # Comment.
                        top_left_cell = covered_cell_indices[0]
                        cell_text_map[top_left_cell] = {
                            'text': combined_text,
                            'confidence': avg_confidence,
                            'text_count': len(matched_texts),
                            'is_spanning': True
                        }
                        
                        # Comment.
                        for cell_idx in covered_cell_indices[1:]:
                            cell_text_map[cell_idx] = {
                                'text': '__MERGED__',
                                'confidence': 0.0,
                                'text_count': 0,
                                'is_spanning': True
                            }
                        
                        covered_cells.update(covered_cell_indices)
                        
                        # Comment.
                        for matched_text in matched_texts:
                            if 'original_index' in matched_text:
                                available_ocr_results[matched_text['original_index']]['assigned'] = True
                        
                        AppLogger.get_logger().info(
                            f"Enhanced spanning cell text: '{combined_text}' -> cell {top_left_cell}, "
                            f"covers {len(covered_cell_indices)} cells, matched {len(matched_texts)} text elements"
                        )
                    else:
                        AppLogger.get_logger().warning(f"Spanning cell found no text or no covered cells. "
                                                      f"Matched texts: {len(matched_texts)}, Covered cells: {len(covered_cell_indices)}")
            
            # Step 2: Process remaining cells using optimized algorithm
            # Comment.
            sorted_cells = self.sort_cells_by_position(cell_coordinates, covered_cells)
            # Comment.
            for row_idx, row_data in enumerate(cell_coordinates):
                for col_idx, cell_data in enumerate(row_data['cells']):
                    cell_key = (row_idx, col_idx)
                    if cell_key not in covered_cells:
                        # Comment.
                        pass
            
            # Comment.
            text_rows = self.cluster_ocr_texts_by_rows(available_ocr_results)
            # Comment.
            pass
            
            # Comment.
            remaining_cell_text_map = self.optimized_cell_text_matching(
                sorted_cells, text_rows, available_ocr_results
            )
            
            # Comment.
            cell_text_map.update(remaining_cell_text_map)

            
            AppLogger.get_logger().info(f"Mapped text to {len(cell_text_map)} cells")
            return cell_text_map
            
        except Exception as e:
            AppLogger.get_logger().error(f"Text mapping failed: {str(e)}")
            return {}
    
    def sort_cells_by_position(self, cell_coordinates, covered_cells):
        """Docstring."""
        sorted_cells = []
        for row_idx, row_data in enumerate(cell_coordinates):
            for col_idx, cell_data in enumerate(row_data['cells']):
                cell_key = (row_idx, col_idx)
                if cell_key not in covered_cells:
                    sorted_cells.append({
                        'position': cell_key,
                        'bbox': cell_data['cell'],
                        'row_idx': row_idx,
                        'col_idx': col_idx
                    })
        
        # Comment.
        sorted_cells.sort(key=lambda cell: (cell['bbox'][1], cell['bbox'][0]))
        return sorted_cells

    def cluster_ocr_texts_by_rows(self, available_ocr_results, row_threshold=20):
        """Docstring."""
        if not available_ocr_results:
            return {}
        
        # Comment.
        sorted_ocr = sorted(available_ocr_results, key=lambda ocr: ocr['bbox'][1])
        
        # Comment.
        text_rows = {}
        current_row = 0
        current_y_center = None
        
        for ocr in sorted_ocr:
            y_center = (ocr['bbox'][1] + ocr['bbox'][3]) / 2
            
            if current_y_center is None or abs(y_center - current_y_center) <= row_threshold:
                # Comment.
                if current_row not in text_rows:
                    text_rows[current_row] = []
                text_rows[current_row].append(ocr)
                current_y_center = y_center if current_y_center is None else (current_y_center + y_center) / 2
            else:
                # Comment.
                current_row += 1
                text_rows[current_row] = [ocr]
                current_y_center = y_center
        
        return text_rows

    def optimized_cell_text_matching(self, sorted_cells, text_rows, available_ocr_results):
        """Docstring."""
        cell_text_map = {}
        
        for cell in sorted_cells:
            cell_bbox = cell['bbox']
            cell_key = cell['position']
            row_idx = cell['row_idx']
            
            # Comment.
            candidate_texts = []
            
            # Comment.
            if row_idx in text_rows:
                candidate_texts.extend(text_rows[row_idx])
            
            # Comment.
            for offset in [-1, 1]:
                adjacent_row = row_idx + offset
                if adjacent_row in text_rows:
                    candidate_texts.extend(text_rows[adjacent_row])

            # Comment.
            
            # Comment.
            if not candidate_texts:
                candidate_texts = available_ocr_results
            
            # Comment.
            cell_texts = []
            cell_confidences = []
            
            for ocr_result in candidate_texts:
                if ocr_result.get('assigned', False):
                    continue
                    
                ocr_bbox = ocr_result['bbox']
                
                # Comment.
                is_contained = self.is_bbox_contained(ocr_bbox, cell_bbox)
                
                if is_contained:
                    cell_texts.append(ocr_result['text'])
                    cell_confidences.append(ocr_result['confidence'])
                    ocr_result['assigned'] = True
                else:
                    iou = self.calculate_iou(cell_bbox, ocr_bbox)
                    if iou > 0.25:
                        cell_texts.append(ocr_result['text'])
                        cell_confidences.append(ocr_result['confidence'])
                        ocr_result['assigned'] = True
                # Comment.
            # Comment.
            if cell_texts:
                combined_text = ' '.join(cell_texts)
                avg_confidence = sum(cell_confidences) / len(cell_confidences)
                cell_text_map[cell_key] = {
                    'text': combined_text,
                    'confidence': avg_confidence,
                    'text_count': len(cell_texts),
                    'is_spanning': False
                }
            else:
                cell_text_map[cell_key] = {
                    'text': '',
                    'confidence': 0.0,
                    'text_count': 0,
                    'is_spanning': False
                }
        
        return cell_text_map

    def is_bbox_contained(self, inner_bbox, outer_bbox):
        """Docstring."""
        try:
            inner_x1, inner_y1, inner_x2, inner_y2 = inner_bbox
            outer_x1, outer_y1, outer_x2, outer_y2 = outer_bbox
            
            return (inner_x1 >= outer_x1 and inner_y1 >= outer_y1 and 
                    inner_x2 <= outer_x2 and inner_y2 <= outer_y2)
        except Exception as e:
            AppLogger.get_logger().error(f"Bbox containment check failed: {str(e)}")
            return False

    
    def calculate_iou(self, bbox1, bbox2):
        """Docstring."""

        #'text': 'Decrenaed', 'bbox': [310, 14, 360, 22]
        #Cell bbox: [303.6546325683594, 10.498663902282715, 359.3522033691406, 35.0746955871582]
        try:
            # Calculate intersection coordinates
            x1 = max(bbox1[0], bbox2[0])
            y1 = max(bbox1[1], bbox2[1])
            x2 = min(bbox1[2], bbox2[2])
            y2 = min(bbox1[3], bbox2[3])
            
            # Check if there's an intersection
            if x2 <= x1 or y2 <= y1:
                return 0.0
            
            # Calculate intersection area
            intersection_area = (x2 - x1) * (y2 - y1)
            
            # Calculate union area
            bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
            bbox2_area = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
            union_area = bbox1_area + bbox2_area - intersection_area
            
            # Calculate IoU
            if union_area > 0:
                return intersection_area / union_area
            else:
                return 0.0
                
        except Exception as e:
            AppLogger.get_logger().error(f"IoU calculation failed: {str(e)}")
            return 0.0

    def calculate_spanning_cell_coverage(self, spanning_bbox, cell_coordinates):
        """Docstring."""
        try:
            covered_cells = []
            x1, y1, x2, y2 = spanning_bbox
            
            for row_idx, row_data in enumerate(cell_coordinates):
                for col_idx, cell_data in enumerate(row_data['cells']):
                    cell_bbox = cell_data['cell']
                    cell_x1, cell_y1, cell_x2, cell_y2 = cell_bbox
                    
                    # Check if cell is covered by spanning cell using IoU
                    iou = self.calculate_iou(spanning_bbox, cell_bbox)
                    
                    # Use multiple criteria for spanning cell coverage
                    # 1. IoU threshold
                    # 2. Center point inside
                    # 3. Significant overlap (more than 50% of cell area)
                    cell_center_x = (cell_x1 + cell_x2) / 2
                    cell_center_y = (cell_y1 + cell_y2) / 2
                    is_center_inside = (spanning_bbox[0] <= cell_center_x <= spanning_bbox[2] and 
                                       spanning_bbox[1] <= cell_center_y <= spanning_bbox[3])
                    
                    # Calculate overlap percentage
                    cell_area = (cell_x2 - cell_x1) * (cell_y2 - cell_y1)
                    if cell_area > 0:
                        overlap_x1 = max(cell_x1, spanning_bbox[0])
                        overlap_y1 = max(cell_y1, spanning_bbox[1])
                        overlap_x2 = min(cell_x2, spanning_bbox[2])
                        overlap_y2 = min(cell_y2, spanning_bbox[3])
                        
                        if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                            overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                            overlap_percentage = overlap_area / cell_area
                        else:
                            overlap_percentage = 0
                    else:
                        overlap_percentage = 0
                    
                    # Use multiple criteria: IoU >= 0.3 OR center inside OR significant overlap
                    if iou >= 0.3 or is_center_inside or overlap_percentage >= 0.5:
                        covered_cells.append((row_idx, col_idx))
            
            # Sort by row first, then by column (top-left to bottom-right)
            covered_cells.sort(key=lambda x: (x[0], x[1]))
            
            AppLogger.get_logger().debug(f"Spanning cell {spanning_bbox} covers {len(covered_cells)} cells: {covered_cells}")
            return covered_cells
            
        except Exception as e:
            AppLogger.get_logger().error(f"Error calculating spanning cell coverage: {str(e)}")
            return []

    def calculate_spanning_cell_union_region(self, spanning_bbox, cell_coordinates):
        """Docstring."""
        try:
            covered_cells = self.calculate_spanning_cell_coverage(spanning_bbox, cell_coordinates)
            
            if not covered_cells:
                return spanning_bbox, covered_cells
            
            # Comment.
            min_x = float('inf')
            min_y = float('inf')
            max_x = float('-inf')
            max_y = float('-inf')
            
            for row_idx, col_idx in covered_cells:
                if row_idx < len(cell_coordinates) and col_idx < len(cell_coordinates[row_idx]['cells']):
                    cell_bbox = cell_coordinates[row_idx]['cells'][col_idx]['cell']
                    min_x = min(min_x, cell_bbox[0])
                    min_y = min(min_y, cell_bbox[1])
                    max_x = max(max_x, cell_bbox[2])
                    max_y = max(max_y, cell_bbox[3])
            
            union_bbox = [min_x, min_y, max_x, max_y]
            return union_bbox, covered_cells
            
        except Exception as e:
            AppLogger.get_logger().error(f"Union region calculation failed: {str(e)}")
            return spanning_bbox, []

    def expand_bbox_with_tolerance(self, bbox, tolerance_pixels=3):
        """Docstring."""
        try:
            x1, y1, x2, y2 = bbox
            return [
                max(0, x1 - tolerance_pixels),
                max(0, y1 - tolerance_pixels),
                x2 + tolerance_pixels,
                y2 + tolerance_pixels
            ]
        except Exception as e:
            AppLogger.get_logger().error(f"Bbox expansion failed: {str(e)}")
            return bbox

    def cluster_texts_by_rows(self, matched_texts, row_threshold=10):
        """Docstring."""
        try:
            if not matched_texts:
                return []
            
            # Comment.
            text_with_centers = []
            for text in matched_texts:
                bbox = text['bbox']
                center_y = (bbox[1] + bbox[3]) / 2
                text_with_centers.append((center_y, text))
            
            # Comment.
            text_with_centers.sort(key=lambda x: x[0])
            
            # Comment.
            text_rows = []
            current_row = []
            current_row_y = None
            
            for center_y, text in text_with_centers:
                if current_row_y is None or abs(center_y - current_row_y) <= row_threshold:
                    # Comment.
                    current_row.append(text)
                    current_row_y = center_y
                else:
                    # Comment.
                    if current_row:
                        text_rows.append(current_row)
                    current_row = [text]
                    current_row_y = center_y
            
            # Comment.
            if current_row:
                text_rows.append(current_row)
            
            return text_rows
            
        except Exception as e:
            AppLogger.get_logger().error(f"Text row clustering failed: {str(e)}")
            return [matched_texts] if matched_texts else []

    def sort_texts_within_row(self, row_texts):
        """Docstring."""
        try:
            # Comment.
            return sorted(row_texts, key=lambda text: text['bbox'][0])
        except Exception as e:
            AppLogger.get_logger().error(f"Text sorting within row failed: {str(e)}")
            return row_texts

    def smart_merge_texts_in_row(self, sorted_texts, merge_threshold=5):
        """Docstring."""
        try:
            if not sorted_texts:
                return ""
            
            if len(sorted_texts) == 1:
                return sorted_texts[0]['text']
            
            merged_parts = []
            current_text = sorted_texts[0]['text']
            current_bbox = sorted_texts[0]['bbox']
            
            for i in range(1, len(sorted_texts)):
                next_text = sorted_texts[i]['text']
                next_bbox = sorted_texts[i]['bbox']
                
                # Comment.
                gap = next_bbox[0] - current_bbox[2]
                
                if gap <= merge_threshold:
                    # Comment.
                    current_text += next_text
                    # Comment.
                    current_bbox = [current_bbox[0], min(current_bbox[1], next_bbox[1]),
                                  next_bbox[2], max(current_bbox[3], next_bbox[3])]
                else:
                    # Comment.
                    current_text += " " + next_text
                    current_bbox = [current_bbox[0], min(current_bbox[1], next_bbox[1]),
                                  next_bbox[2], max(current_bbox[3], next_bbox[3])]
            
            return current_text
            
        except Exception as e:
            AppLogger.get_logger().error(f"Smart text merging failed: {str(e)}")
            return " ".join([t['text'] for t in sorted_texts])

    def aggregate_multiline_texts(self, text_rows):
        """Docstring."""
        try:
            if not text_rows:
                return ""
            
            if len(text_rows) == 1:
                # Comment.
                return self.smart_merge_texts_in_row(text_rows[0])
            
            # Comment.
            row_texts = []
            for row in text_rows:
                # Comment.
                sorted_row = self.sort_texts_within_row(row)
                merged_row_text = self.smart_merge_texts_in_row(sorted_row)
                if merged_row_text.strip():
                    row_texts.append(merged_row_text)
            
            # Comment.
            return "\n".join(row_texts)
            
        except Exception as e:
            AppLogger.get_logger().error(f"Multiline text aggregation failed: {str(e)}")
            return ""

    def enhanced_spanning_cell_text_matching(self, spanning_bbox, ocr_results, cell_coordinates):
        """Docstring."""
        try:
            # Comment.
            union_bbox, covered_cells = self.calculate_spanning_cell_union_region(
                spanning_bbox, cell_coordinates
            )
            
            # Comment.
            expanded_bbox = self.expand_bbox_with_tolerance(union_bbox, tolerance_pixels=3)
            
            # Comment.
            matched_texts = []
            for ocr_result in ocr_results:
                # Comment.
                if ocr_result.get('assigned', False):
                    continue
                    
                ocr_bbox = ocr_result['bbox']
                
                # Comment.
                is_fully_inside = (ocr_bbox[0] >= expanded_bbox[0] and 
                                  ocr_bbox[1] >= expanded_bbox[1] and 
                                  ocr_bbox[2] <= expanded_bbox[2] and 
                                  ocr_bbox[3] <= expanded_bbox[3])
                
                # Comment.
                iou_with_expanded = self.calculate_iou(ocr_bbox, expanded_bbox)
                
                # Comment.
                center_x = (ocr_bbox[0] + ocr_bbox[2]) / 2
                center_y = (ocr_bbox[1] + ocr_bbox[3]) / 2
                center_inside = (expanded_bbox[0] <= center_x <= expanded_bbox[2] and 
                                expanded_bbox[1] <= center_y <= expanded_bbox[3])
                
                # Comment.
                iou_with_original = self.calculate_iou(ocr_bbox, spanning_bbox)
                
                # Comment.
                if (is_fully_inside or 
                    iou_with_expanded >= 0.2 or 
                    center_inside or 
                    iou_with_original >= 0.3):
                    
                    matched_texts.append(ocr_result)
                    AppLogger.get_logger().debug(
                        f"Matched text '{ocr_result['text']}' to spanning cell: "
                        f"inside={is_fully_inside}, iou_expanded={iou_with_expanded:.3f}, "
                        f"center_inside={center_inside}, iou_original={iou_with_original:.3f}"
                    )
            
            return matched_texts, covered_cells
            
        except Exception as e:
            AppLogger.get_logger().error(f"Enhanced spanning cell text matching failed: {str(e)}")
            return [], []
    

    def outputs_to_objects(self, outputs, img_size, id2label):
        def box_cxcywh_to_xyxy(x):
            x_c, y_c, w, h = x.unbind(-1)
            b = [(x_c - 0.5 * w), (y_c - 0.5 * h), (x_c + 0.5 * w), (y_c + 0.5 * h)]
            return torch.stack(b, dim=1)

        def rescale_bboxes(out_bbox, size):
            img_w, img_h = size
            b = box_cxcywh_to_xyxy(out_bbox)
            b = b * torch.tensor([img_w, img_h, img_w, img_h], dtype=torch.float32)
            return b

        # Add "no object" to id2label if not present
        if len(id2label) not in id2label:
            id2label[len(id2label)] = "no object"

        m = outputs.logits.softmax(-1).max(-1)
        pred_labels = list(m.indices.detach().cpu().numpy())[0]
        pred_scores = list(m.values.detach().cpu().numpy())[0]
        pred_bboxes = outputs['pred_boxes'].detach().cpu()[0]
        pred_bboxes = [elem.tolist() for elem in rescale_bboxes(pred_bboxes, img_size)]

        # Comment.

        objects = []
        for label, score, bbox in zip(pred_labels, pred_scores, pred_bboxes):
            try:
                class_label = id2label[int(label)]
            except KeyError:
                # Comment.
                continue
            if not class_label == 'no object':
                objects.append({'label': class_label, 'score': float(score),
                                'bbox': [float(elem) for elem in bbox]})

        return objects

    def get_cell_coordinates_by_row(self, table_data):
        rows = [entry for entry in table_data if entry['label'] == 'table row']
        columns = [entry for entry in table_data if entry['label'] == 'table column']
        rows.sort(key=lambda x: x['bbox'][1])
        columns.sort(key=lambda x: x['bbox'][0])

        def find_cell_coordinates(row, column):
            cell_bbox = [column['bbox'][0], row['bbox'][1], column['bbox'][2], row['bbox'][3]]
            return cell_bbox

        cell_coordinates = []
        for row in rows:
            row_cells = []
            for column in columns:
                cell_bbox = find_cell_coordinates(row, column)
                row_cells.append({'column': column['bbox'], 'cell': cell_bbox})
            row_cells.sort(key=lambda x: x['column'][0])
            cell_coordinates.append({'row': row['bbox'], 'cells': row_cells, 'cell_count': len(row_cells)})
        cell_coordinates.sort(key=lambda x: x['row'][1])
        return cell_coordinates
    
    async def start_process_with_whole_ocr(self, input_Image, models, preprocess=True, original_image=None, table_bbox=None):
        """Docstring."""
        try:
            AppLogger.get_logger().info("Starting improved structure recognition processing pipeline.")
            
            if models is None:
                raise ValueError("TableModels instance must be provided.")
            
            
            # Comment.
            model, outputs, image_size = models.recognize_structure(input_Image)
            
            # Comment.
            table_data = self.outputs_to_objects(outputs, image_size, model.config.id2label)
            
            if not table_data:
                AppLogger.get_logger().info("No structure detected using direct method, returning empty result")
                return []
            
            AppLogger.get_logger().info(f"Direct detection found {len(table_data)} table structure objects")
            
            # Step 2: Process special labels (column headers, row headers, spanning cells)
            special_labels = self.process_special_labels(table_data, input_Image)
            AppLogger.get_logger().info(f"Processed special labels: {len(special_labels['column_headers'])} headers, "
                                      f"{len(special_labels['projected_row_headers'])} row headers, "
                                      f"{len(special_labels['spanning_cells'])} spanning cells")
            
            # Step 3: Get cell coordinates using direct method
            AppLogger.get_logger().info("Getting cell coordinates using direct method...")
            cell_coordinates = self.get_cell_coordinates_by_row(table_data)
            
            if not cell_coordinates:
                AppLogger.get_logger().info("No cell coordinates found using direct method, returning empty result")
                return []
            
            AppLogger.get_logger().info(f"Direct method generated {len(cell_coordinates)} rows of cell coordinates")

            # Step 4: Generate visualizations using direct detection results
            if original_image is not None and table_bbox is not None:
                AppLogger.get_logger().info("Generating visualizations with direct detection results...")
                self.generate_visualizations(
                    original_image, table_data, cell_coordinates, special_labels, table_bbox
                )
            
            # Step 4: Use cell-based OCR with spanning cell support when enabled
            AppLogger.get_logger().info("Using cell-based OCR with spanning cell support")
            cell_ocr_data = []
            if self.cell_ocr_enabled:
                cell_ocr_data = self.extract_cells_with_spanning_support(
                    input_Image, cell_coordinates, special_labels, models
                )

            if cell_ocr_data:
                AppLogger.get_logger().info("Creating DataFrame from cell-based OCR results")
                max_cols = max(len(row_data) for row_data in cell_ocr_data.values()) if cell_ocr_data else 0
                max_rows = len(cell_ocr_data)
                df_data = []
                for row_idx in range(max_rows):
                    if row_idx in cell_ocr_data:
                        row_data = []
                        for col_idx in range(max_cols):
                            if col_idx < len(cell_ocr_data[row_idx]):
                                cell_text = cell_ocr_data[row_idx][col_idx]
                                if cell_text == "__MERGED__":
                                    row_data.append("")
                                else:
                                    row_data.append(cell_text)
                            else:
                                row_data.append("")
                        df_data.append(row_data)
                    else:
                        df_data.append([""] * max_cols)
                columns = [f"Column_{i+1}" for i in range(max_cols)]
                df = pd.DataFrame(df_data, columns=columns)
                AppLogger.get_logger().info(f"Created DataFrame with shape: {df.shape}")
                return [df]

            AppLogger.get_logger().warning(
                "No OCR results from cell-based extraction, falling back to whole table OCR"
            )
            ocr_results = self.ocr_whole_table(input_Image, models, table_data)
            if not ocr_results:
                AppLogger.get_logger().warning("No OCR results from whole table either")
                return []
            
            # Use original mapping approach
            cell_text_map = self.map_text_to_cells(ocr_results, cell_coordinates, special_labels)
            
            # Create DataFrame from mapped results
            max_cols = max(len(row_data['cells']) for row_data in cell_coordinates) if cell_coordinates else 0
            max_rows = len(cell_coordinates)
            
            # Convert cell_text_map to DataFrame format with merged cell handling
            df_data = []
            for row_idx in range(max_rows):
                row_data = []
                for col_idx in range(max_cols):
                    cell_key = (row_idx, col_idx)
                    if cell_key in cell_text_map:
                        cell_info = cell_text_map[cell_key]
                        # Handle merged cells
                        if cell_info['text'] == '__MERGED__':
                            row_data.append('')  # Empty for merged cells
                        else:
                            row_data.append(cell_info['text'])
                    else:
                        row_data.append('')
                df_data.append(row_data)
            
            # Create DataFrame
            columns = [f"Column_{i+1}" for i in range(max_cols)]
            df = pd.DataFrame(df_data, columns=columns)
            
            # Log DataFrame creation
            AppLogger.get_logger().info(f"Created DataFrame with shape: {df.shape}")
            AppLogger.get_logger().info(f"DataFrame columns: {list(df.columns)}")
            AppLogger.get_logger().info(f"DataFrame first few rows:\n{df.head()}")
            
            AppLogger.get_logger().info("Improved structure recognition processing pipeline finished.")
            return [df]
            
            # Step 5: Create DataFrame from cell-based OCR results
            AppLogger.get_logger().info("Creating DataFrame from cell-based OCR results")
            
            # Convert cell_ocr_data to DataFrame format
            max_cols = max(len(row_data) for row_data in cell_ocr_data.values()) if cell_ocr_data else 0
            max_rows = len(cell_ocr_data)
            
            df_data = []
            for row_idx in range(max_rows):
                if row_idx in cell_ocr_data:
                    row_data = []
                    for col_idx in range(max_cols):
                        if col_idx < len(cell_ocr_data[row_idx]):
                            cell_text = cell_ocr_data[row_idx][col_idx]
                            # Handle merged cells
                            if cell_text == '__MERGED__':
                                row_data.append('')  # Empty for merged cells
                            else:
                                row_data.append(cell_text)
                        else:
                            row_data.append('')
                    df_data.append(row_data)
                else:
                    # Fill with empty strings if row is missing
                    df_data.append([''] * max_cols)
            
            # Create DataFrame
            columns = [f"Column_{i+1}" for i in range(max_cols)]
            df = pd.DataFrame(df_data, columns=columns)
            
            # Log DataFrame creation
            AppLogger.get_logger().info(f"Created DataFrame with shape: {df.shape}")
            AppLogger.get_logger().info(f"DataFrame columns: {list(df.columns)}")
            AppLogger.get_logger().info(f"DataFrame first few rows:\n{df.head()}")
            
            AppLogger.get_logger().info("Improved structure recognition processing pipeline finished.")
            return [df]
            
        except Exception as e:
            AppLogger.get_logger().error(f"Improved structure recognition processing pipeline failed: {str(e)}")
            import traceback
            AppLogger.get_logger().error(f"Error details: {traceback.format_exc()}")
            return []



    def generate_visualizations(self, original_image, table_data, cell_coordinates, special_labels, table_bbox):
        """Docstring."""
        try:
            from docuvision_core.models.table_visualize import TableVisualize
            visualizer = TableVisualize()

            # Comment.
            x1, y1, x2, y2 = table_bbox
            
            # Comment.
            visualization_data = {
                'table_rows': self._adjust_bboxes_to_original([obj for obj in table_data if obj['label'] == 'table row'], x1, y1),
                'table_cols': self._adjust_bboxes_to_original([obj for obj in table_data if obj['label'] == 'table column'], x1, y1),
                'special_labels': self._adjust_special_labels_to_original(special_labels, x1, y1)
            }
            
            # Comment.
            adjusted_cell_coordinates = self._adjust_cell_coordinates_to_original(cell_coordinates, x1, y1)
            
            # Comment.
            import os
            output_dir = "tests/results"
            os.makedirs(output_dir, exist_ok=True)
            
            # Comment.
            AppLogger.get_logger().info("Generating direct detection visualizations on original image...")
            saved_files = visualizer.create_comprehensive_visualization(
                original_image, 
                visualization_data, 
                adjusted_cell_coordinates,
                save_dir=output_dir
            )
            
            if saved_files:
                AppLogger.get_logger().info(f"Direct detection visualization files saved: {list(saved_files.keys())}")
                for key, path in saved_files.items():
                    AppLogger.get_logger().info(f"  {key}: {path}")
            else:
                AppLogger.get_logger().warning("No direct detection visualization files were generated")
                
        except Exception as viz_error:
            AppLogger.get_logger().error(f"Direct detection visualization generation failed: {str(viz_error)}")
            import traceback
            AppLogger.get_logger().error(f"Visualization error details: {traceback.format_exc()}")

    
    
    def _adjust_bboxes_to_original(self, objects, offset_x, offset_y):
        """Docstring."""
        adjusted_objects = []
        for obj in objects:
            adjusted_obj = obj.copy()
            if 'bbox' in adjusted_obj:
                bbox = adjusted_obj['bbox']
                adjusted_obj['bbox'] = [
                    bbox[0] + offset_x,  # x1
                    bbox[1] + offset_y,  # y1
                    bbox[2] + offset_x,  # x2
                    bbox[3] + offset_y   # y2
                ]
            adjusted_objects.append(adjusted_obj)
        return adjusted_objects
    
    def _adjust_special_labels_to_original(self, special_labels, offset_x, offset_y):
        """Docstring."""
        adjusted_labels = {}
        for key, labels in special_labels.items():
            adjusted_labels[key] = self._adjust_bboxes_to_original(labels, offset_x, offset_y)
        return adjusted_labels
    
    def _adjust_cell_coordinates_to_original(self, cell_coordinates, offset_x, offset_y):
        """Docstring."""
        adjusted_coordinates = []
        for row_data in cell_coordinates:
            adjusted_row = row_data.copy()
            
            # Adjust row bbox
            if 'row' in adjusted_row:
                row_bbox = adjusted_row['row']
                adjusted_row['row'] = [
                    row_bbox[0] + offset_x,
                    row_bbox[1] + offset_y,
                    row_bbox[2] + offset_x,
                    row_bbox[3] + offset_y
                ]
            
            # Adjust cell bboxes
            if 'cells' in adjusted_row:
                adjusted_cells = []
                for cell_data in adjusted_row['cells']:
                    adjusted_cell = cell_data.copy()
                    
                    # Adjust column bbox
                    if 'column' in adjusted_cell:
                        col_bbox = adjusted_cell['column']
                        adjusted_cell['column'] = [
                            col_bbox[0] + offset_x,
                            col_bbox[1] + offset_y,
                            col_bbox[2] + offset_x,
                            col_bbox[3] + offset_y
                        ]
                    
                    # Adjust cell bbox
                    if 'cell' in adjusted_cell:
                        cell_bbox = adjusted_cell['cell']
                        adjusted_cell['cell'] = [
                            cell_bbox[0] + offset_x,
                            cell_bbox[1] + offset_y,
                            cell_bbox[2] + offset_x,
                            cell_bbox[3] + offset_y
                        ]
                    
                    adjusted_cells.append(adjusted_cell)
                adjusted_row['cells'] = adjusted_cells
            
            adjusted_coordinates.append(adjusted_row)
        return adjusted_coordinates
    
    def process_special_labels(self, objects, table_image):
        """Docstring."""
        try:
            processed_objects = {
                'normal_cells': [],
                'column_headers': [],
                'projected_row_headers': [],
                'spanning_cells': []
            }
            
            # Classify different types of labels
            for obj in objects:
                label = obj['label']
                # Comment.
                if label == 'table column header':
                    # Comment.
                    split_headers = self._split_large_column_header(obj, table_image)
                    if split_headers:
                        processed_objects['column_headers'].extend(split_headers)
                        # Comment.
                    else:
                        processed_objects['column_headers'].append(obj)
                elif label == 'table projected row header':
                    processed_objects['projected_row_headers'].append(obj)
                elif label == 'table spanning cell':
                    processed_objects['spanning_cells'].append(obj)
                elif label in ['table row', 'table column']:
                    processed_objects['normal_cells'].append(obj)
            
            # Apply special processing only for spanning cells
            processed_objects['spanning_cells'] = self.process_spanning_cells(
                processed_objects['spanning_cells'], table_image
            )
            
            AppLogger.get_logger().info(f"Processed special labels: {len(processed_objects['column_headers'])} headers, "
                                      f"{len(processed_objects['projected_row_headers'])} row headers, "
                                      f"{len(processed_objects['spanning_cells'])} spanning cells")
            
            return processed_objects
            
        except Exception as e:
            AppLogger.get_logger().error(f"Special labels processing failed: {str(e)}")
            return {
                'normal_cells': objects,
                'column_headers': [],
                'projected_row_headers': [],
                'spanning_cells': []
            }
    
    # ===== Helpers for short-term subheader handling =====
    def _bbox_union(self, bboxes):
        if not bboxes:
            return None
        min_x = min(b[0] for b in bboxes)
        min_y = min(b[1] for b in bboxes)
        max_x = max(b[2] for b in bboxes)
        max_y = max(b[3] for b in bboxes)
        return [min_x, min_y, max_x, max_y]

    
    def _split_large_column_header(self, header_obj, table_image):
        """Docstring."""
        bbox = header_obj['bbox']
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        
        # Comment.
        # Comment.
        if width < 120:
            return None
        
        # Comment.
        
        # Comment.
        try:
            # Comment.
            header_crop = table_image.crop((x1, y1, x2, y2))
            
            # Comment.
            import easyocr
            from docuvision_core.utils.easyocr_config import get_easyocr_reader
            reader = get_easyocr_reader(['en'])
            img_array = np.array(header_crop)
            ocr_results = reader.readtext(img_array)
            
            # Comment.
            
            if len(ocr_results) < 2:
                # Comment.
                return None
            
            # Comment.
            text_regions = []
            for item in ocr_results:
                bbox_points = item[0]
                text = item[1]
                confidence = item[2]
                
                # Comment.
                x_coords = [point[0] for point in bbox_points]
                y_coords = [point[1] for point in bbox_points]
                rel_x1, rel_x2 = min(x_coords), max(x_coords)
                rel_y1, rel_y2 = min(y_coords), max(y_coords)
                
                # Comment.
                abs_x1 = x1 + rel_x1
                abs_y1 = y1 + rel_y1
                abs_x2 = x1 + rel_x2
                abs_y2 = y1 + rel_y2
                
                text_regions.append({
                    'text': text,
                    'bbox': [abs_x1, abs_y1, abs_x2, abs_y2],
                    'confidence': confidence
                })
            
            # Comment.
            text_regions.sort(key=lambda r: r['bbox'][0])
            
            # Comment.
            gaps = []
            for i in range(1, len(text_regions)):
                prev_x2 = text_regions[i-1]['bbox'][2]
                curr_x1 = text_regions[i]['bbox'][0]
                gap = curr_x1 - prev_x2
                gaps.append(gap)
            
            avg_gap = sum(gaps) / len(gaps) if gaps else 0
            # Comment.
            
            # Comment.
            if avg_gap < 10:
                # Comment.
                return None
            
            # Comment.
            split_headers = []
            for i, region in enumerate(text_regions):
                # Comment.
                margin = 5
                expanded_bbox = [
                    max(x1, region['bbox'][0] - margin),
                    max(y1, region['bbox'][1] - margin),
                    min(x2, region['bbox'][2] + margin),
                    min(y2, region['bbox'][3] + margin)
                ]
                
                split_header = {
                    'label': 'table column header',
                    'bbox': expanded_bbox,
                    'score': header_obj['score'] * region['confidence']
                }
                split_headers.append(split_header)
                # Comment.
            
            return split_headers
            
        except Exception as e:
            # Comment.
            return None
    
    
    def process_spanning_cells(self, cells, table_image):
        """Docstring."""
        try:
            if not cells:
                return []
            
            # Validate spanning cells
            valid_spanning_cells = []
            for cell in cells:
                bbox = cell['bbox']
                x1, y1, x2, y2 = bbox
                
                # Check if cell size is reasonable
                width = x2 - x1
                height = y2 - y1
                
                # Spanning cells should be larger than standard cells
                if width > table_image.width * 0.1 and height > table_image.height * 0.05:
                    valid_spanning_cells.append(cell)
            
            # Process overlapping spanning cells
            non_overlapping_cells = self.resolve_overlapping_spanning_cells(valid_spanning_cells)
            
            # Calculate span information
            enhanced_cells = []
            for cell in non_overlapping_cells:
                enhanced_cell = self.calculate_span_info(cell, table_image)
                enhanced_cells.append(enhanced_cell)
            
            return enhanced_cells
            
        except Exception as e:
            AppLogger.get_logger().error(f"Spanning cells processing failed: {str(e)}")
            return cells
    
    
    def resolve_overlapping_spanning_cells(self, cells):
        """Docstring."""
        if not cells:
            return []
        
        # Sort by area (larger cells first)
        cells.sort(key=lambda x: (x['bbox'][2] - x['bbox'][0]) * (x['bbox'][3] - x['bbox'][1]), reverse=True)
        
        non_overlapping = []
        for cell in cells:
            is_overlapping = False
            for existing_cell in non_overlapping:
                if self.calculate_iou(cell['bbox'], existing_cell['bbox']) > 0.5:
                    is_overlapping = True
                    break
            
            if not is_overlapping:
                non_overlapping.append(cell)
        
        return non_overlapping
    
    def calculate_span_info(self, cell, table_image):
        """Docstring."""
        bbox = cell['bbox']
        x1, y1, x2, y2 = bbox
        
        # Estimate standard cell size
        estimated_cell_width = table_image.width / 10  # Assume 10 columns
        estimated_cell_height = table_image.height / 20  # Assume 20 rows
        
        # Calculate span counts
        col_span = max(1, int((x2 - x1) / estimated_cell_width))
        row_span = max(1, int((y2 - y1) / estimated_cell_height))
        
        # Add span information
        cell['col_span'] = col_span
        cell['row_span'] = row_span
        cell['span_type'] = self.determine_span_type(col_span, row_span)
        
        return cell
    
    def determine_span_type(self, col_span, row_span):
        """Docstring."""
        if col_span > 1 and row_span > 1:
            return "both"  # Both row and column spanning
        elif col_span > 1:
            return "column"  # Column spanning only
        elif row_span > 1:
            return "row"  # Row spanning only
        else:
            return "normal"  # Normal cell

    

    def extract_cells_by_coordinates(self, table_image, cell_coordinates, models, preprocess=True):
        """Docstring."""
        try:
            all_cell_texts = []
            
            for row_idx, row_data in enumerate(cell_coordinates):
                row_cells = row_data['cells']
                for col_idx, cell_data in enumerate(row_cells):
                    cell_bbox = cell_data['cell']
                    x1, y1, x2, y2 = cell_bbox
                    
                    # Comment.
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0:
                        all_cell_texts.append(("", 0.0))
                        AppLogger.get_logger().debug(f"Invalid cell bbox at row {row_idx}, col {col_idx}: {cell_bbox}")
                        continue
                    
                    # Comment.
                    cell_img = table_image.crop((x1, y1, x2, y2))
                    
                    # Comment.
                    if preprocess:
                        cell_img = self.enhance_cell_image(cell_img)
                    
                    # Comment.
                    text, confidence = self._ocr_cell_improved(cell_img, models)
                    
                    # Comment.
                    AppLogger.get_logger().info(f"Cell [{row_idx+1},{col_idx+1}] OCR: '{text}' (confidence: {confidence:.2f})")
                    
                    all_cell_texts.append((text, confidence))
            
            return all_cell_texts
            
        except Exception as e:
            AppLogger.get_logger().error(f"Cell extraction by coordinates failed: {str(e)}")
            return []

    
    def apply_ocr(self, cell_coordinates, cropped_table):
        data = dict()
        max_num_columns = 0
        #model_path = os.environ.get('EASYOCR_MODULE_PATH', None)
        reader = get_easyocr_reader(['en'])
        for idx, row in enumerate(tqdm(cell_coordinates)):
            row_text = []
            for cell_idx, cell in enumerate(row["cells"]):
                try:
                    # Comment.
                    bbox = cell["cell"]
                    if len(bbox) != 4:
                        AppLogger.get_logger().warning(f"Invalid bbox format: {bbox}")
                        row_text.append("")
                        continue
                    
                    x1, y1, x2, y2 = bbox
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0:
                        AppLogger.get_logger().warning(f"Invalid bbox coordinates: {bbox}")
                        row_text.append("")
                        continue
                    
                    # Comment.
                    cell_image = cropped_table.crop(bbox)
                    
                    # Comment.
                    if cell_image.size[0] <= 0 or cell_image.size[1] <= 0:
                        AppLogger.get_logger().warning(f"Invalid cropped image size: {cell_image.size}")
                        row_text.append("")
                        continue
                    
                    # Comment.
                    cell_array = np.array(cell_image)
                    if cell_array.size == 0:
                        AppLogger.get_logger().warning("Empty cell array")
                        row_text.append("")
                        continue
                    
                    # Comment.
                    if len(cell_array.shape) == 3 and cell_array.shape[2] == 3:
                        # Comment.
                        if cell_array.shape[0] < 10 or cell_array.shape[1] < 10:
                            AppLogger.get_logger().warning(f"Cell image too small: {cell_array.shape}")
                            row_text.append("")
                            continue
                        
                        # Comment.
                        if cell_array.dtype != np.uint8:
                            cell_array = cell_array.astype(np.uint8)
                    else:
                        AppLogger.get_logger().warning(f"Invalid cell array shape: {cell_array.shape}")
                        row_text.append("")
                        continue
                    
                    # Comment.
                    result = reader.readtext(cell_array)
                    if len(result) > 0:
                        text = " ".join([x[1] for x in result])
                        row_text.append(text)
                    else:
                        row_text.append("")
                        
                except Exception as e:
                    # Comment.
                    error_msg = f"OCR failed for cell {cell_idx} in row {idx}: {str(e)}"
                    AppLogger.get_logger().error(error_msg)
                    
                    # Comment.
                    try:
                        bbox = cell["cell"]
                        AppLogger.get_logger().debug(f"Failed cell bbox: {bbox}")
                        AppLogger.get_logger().debug(f"Cell image size: {cell_image.size}")
                        AppLogger.get_logger().debug(f"Cell array shape: {cell_array.shape}")
                    except:
                        pass
                    
                    row_text.append("")
                    
            if len(row_text) > max_num_columns:
                max_num_columns = len(row_text)
            data[idx] = row_text
            AppLogger.get_logger().info(f"Row {idx} OCR: {row_text}")

        # Comment.
        for row, row_data in data.copy().items():
            if len(row_data) != max_num_columns:
                row_data = row_data + ["" for _ in range(max_num_columns - len(row_data))]
            data[row] = row_data
        return data
        



    def _ocr_cell_improved(self, cell_img, models):
        """Docstring."""
        try:
            import pytesseract
            
            # Comment.
            psm_modes = [6, 8, 13]
            best_text = ""
            best_confidence = 0.0
            
            for psm in psm_modes:
                try:
                    # Comment.
                    config = f'--psm {psm} -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,;:!?()[]{{}}/\\|-_=+*&%$#@~`"\''
                    
                    ocr_data = pytesseract.image_to_data(
                        cell_img, 
                        lang='eng', 
                        config=config, 
                        output_type=pytesseract.Output.DICT
                    )
                    
                    # Comment.
                    words = []
                    confidences = []
                    for i, word in enumerate(ocr_data['text']):
                        conf = ocr_data['conf'][i]
                        if word.strip() and conf > 0:
                            words.append(word.strip())
                            confidences.append(conf)
                    
                    if words:
                        text = ' '.join(words).strip()
                        avg_confidence = sum(confidences) / len(confidences) / 100.0
                        
                        # Comment.
                        if avg_confidence > best_confidence:
                            best_text = text
                            best_confidence = avg_confidence
                            
                except Exception as e:
                    AppLogger.get_logger().debug(f"PSM {psm} failed: {str(e)}")
                    continue
            
            # Comment.
            if not best_text:
                try:
                    text = pytesseract.image_to_string(cell_img, lang='eng', config='--psm 6')
                    best_text = text.strip()
                    best_confidence = 0.5
                except:
                    pass
            
            return best_text, best_confidence
            
        except Exception as e:
            AppLogger.get_logger().error(f"Improved OCR failed: {str(e)}")
            return "", 0.0

    
    

    def clean_dataframe(self, df):
        # Remove unwanted characters from DataFrame and improve OCR text quality
        try:
            for col in df.columns:
                # Comment.
                df[col] = df[col].str.replace("'", '', regex=True)
                df[col] = df[col].str.replace('"', '', regex=True)
                df[col] = df[col].str.replace(r'\\]', '', regex=True)
                df[col] = df[col].str.replace(r'\\\[', '', regex=True)
                df[col] = df[col].str.replace('{', '', regex=True)
                df[col] = df[col].str.replace('}', '', regex=True)
                
                # Comment.
                df[col] = df[col].str.replace(r'\|+', '|', regex=True)
                df[col] = df[col].str.replace(r'\s+', ' ', regex=True)
                df[col] = df[col].str.strip()
                
                # Comment.
                df[col] = df[col].str.replace(r'2oi22', '2012', regex=True)
                df[col] = df[col].str.replace(r'4z34', '4034', regex=True)
                df[col] = df[col].str.replace(r'2osz', '2032', regex=True)
                df[col] = df[col].str.replace(r'4171', '4071', regex=True)
                
                # Comment.
                df[col] = df[col].replace('', None)
                
            AppLogger.get_logger().debug(f"Cleaned DataFrame columns: {df.columns.tolist()}")
            AppLogger.get_logger().debug(f"DataFrame shape after cleaning: {df.shape}")
        except Exception as e:
            AppLogger.get_logger().error(f"Error cleaning DataFrame: {str(e)}")
            # Comment.
        return df

    def create_dataframe(self, cells_pytess_result:list, max_cols:int, max_rows:int, special_labels:dict=None):
        # Assemble DataFrame from OCR results
        headers = cells_pytess_result[:max_cols]
        cells_list = cells_pytess_result[max_cols:]
        
        # Comment.
        def extract_text_from_ocr_result(ocr_result):
            """Docstring."""
            if isinstance(ocr_result, tuple) and len(ocr_result) == 2:
                # Comment.
                text, confidence = ocr_result
                return str(text) if text is not None else ""
            elif isinstance(ocr_result, str):
                # Comment.
                return ocr_result
            else:
                # Comment.
                return str(ocr_result) if ocr_result is not None else ""
        
        # Comment.
        processed_headers = []
        for header in headers:
            text = extract_text_from_ocr_result(header)
            # Comment.
            cleaned_text = text.strip()
            if not cleaned_text or cleaned_text == '':
                cleaned_text = f'Column_{len(processed_headers) + 1}'
            processed_headers.append(cleaned_text)
        
        # Comment.
        new_headers = TableParserUtils.uniquify(processed_headers, (f' {x!s}' for x in string.ascii_lowercase))
        
        # Comment.
        processed_cells = []
        for cell in cells_list:
            text = extract_text_from_ocr_result(cell)
            processed_cells.append(text)
        
        expected_cells = max_cols * max_rows
        # Defensive: if OCR cell count is not as expected, pad or truncate
        if len(processed_cells) < expected_cells:
            AppLogger.get_logger().debug(f"Cell count ({len(processed_cells)}) less than expected ({expected_cells}), padding with empty strings.")
            processed_cells += [''] * (expected_cells - len(processed_cells))
        elif len(processed_cells) > expected_cells:
            AppLogger.get_logger().debug(f"Cell count ({len(processed_cells)}) greater than expected ({expected_cells}), truncating.")
            processed_cells = processed_cells[:expected_cells]
        
        # Comment.
        try:
            # Comment.
            actual_cols = min(max_cols, len(new_headers))
            actual_rows = max_rows
            
            # Comment.
            if len(processed_cells) < actual_cols * actual_rows:
                actual_rows = (len(processed_cells) + actual_cols - 1) // actual_cols
            
            AppLogger.get_logger().debug(f"Creating DataFrame: {actual_rows} rows x {actual_cols} cols")
            
            df = pd.DataFrame("", index=range(0, actual_rows), columns=new_headers[:actual_cols])
            
            # Comment.
            cell_idx = 0
            for nrows in range(actual_rows):
                for ncols in range(actual_cols):
                    if cell_idx < len(processed_cells):
                        df.iat[nrows, ncols] = processed_cells[cell_idx]
                        cell_idx += 1
                    else:
                        # Comment.
                        df.iat[nrows, ncols] = ""
                        
        except Exception as e:
            AppLogger.get_logger().error(f"DataFrame creation failed: {str(e)}")
            # Comment.
            df = pd.DataFrame("", index=range(0, 1), columns=['Column_1'])
        
        # Comment.
        AppLogger.get_logger().debug(f"Final DataFrame shape: {df.shape}")
        
        AppLogger.get_logger().debug(f"Created DataFrame with shape: {df.shape}")
        AppLogger.get_logger().debug(f"Headers: {new_headers}")
        AppLogger.get_logger().debug(f"First row: {df.iloc[0].tolist() if len(df) > 0 else 'Empty'}")
        
        df = self.clean_dataframe(df)
        
        # Comment.
        if special_labels:
            return {
                'data': df.to_dict('records'),
                'columns': df.columns.tolist(),
                'metadata': {
                    'column_headers': special_labels.get('column_headers', []),
                    'projected_row_headers': special_labels.get('projected_row_headers', []),
                    'spanning_cells': special_labels.get('spanning_cells', []),
                    'table_shape': df.shape
                }
            }
        else:
            return df

    def enhance_cell_image(self, img: Image.Image) -> Image.Image:
        """Docstring."""
        # You can add more enhancement steps here as needed
        #img = TableParserUtils.super_res(img)
        img = TableParserUtils.sharpen_image(img)
        img = TableParserUtils.binarizeBlur_image(img)
        return img

    

    def box_cxcywh_to_xyxy(self, x):
        """Docstring."""
        x_c, y_c, w, h = x.unbind(-1)
        b = [(x_c - 0.5 * w), (y_c - 0.5 * h), (x_c + 0.5 * w), (y_c + 0.5 * h)]
        return torch.stack(b, dim=1)


    def rescale_bboxes(self, out_bbox, size):
        """Docstring."""
        img_w, img_h = size
        b = self.box_cxcywh_to_xyxy(out_bbox)
        AppLogger.get_logger().debug(f"Before scaling - bbox shape: {b.shape}, img_size: {size}")
        AppLogger.get_logger().debug(f"Sample bbox before scaling: {b[0] if len(b) > 0 else 'empty'}")
        b = b * torch.tensor([img_w, img_h, img_w, img_h], dtype=torch.float32)
        AppLogger.get_logger().debug(f"Sample bbox after scaling: {b[0] if len(b) > 0 else 'empty'}")
        return b


    def outputs_to_objects(self, outputs, img_size, id2label):
        """Docstring."""
        # Add "no object" to id2label if not present
        if len(id2label) not in id2label:
            id2label[len(id2label)] = "no object"

        m = outputs.logits.softmax(-1).max(-1)
        pred_labels = list(m.indices.detach().cpu().numpy())[0]
        pred_scores = list(m.values.detach().cpu().numpy())[0]
        pred_bboxes = outputs['pred_boxes'].detach().cpu()[0]
        pred_bboxes = [elem.tolist() for elem in self.rescale_bboxes(pred_bboxes, img_size)]

        objects = []
        for label, score, bbox in zip(pred_labels, pred_scores, pred_bboxes):
            try:
                class_label = id2label[int(label)]
            except KeyError:
                continue
            if not class_label == 'no object':
                objects.append({'label': class_label, 'score': float(score),
                                'bbox': [float(elem) for elem in bbox]})

        return objects
        


        
class TableParserUtils:
    @staticmethod
    def PIL_to_cv(pil_img):
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    @staticmethod
    def cv_to_PIL(cv_img):
        return Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

    @staticmethod
    async def pytess(cell_pil_img, table_models, lang='eng'):
        text = table_models.ocr_cell(cell_pil_img, lang=lang)
        return text
        

    @staticmethod
    def sharpen_image(pil_img):
        img = TableParserUtils.PIL_to_cv(pil_img)
        sharpen_kernel = np.array([[-1, -1, -1], [-1,  9, -1], [-1, -1, -1]])
        sharpen = cv2.filter2D(img, -1, sharpen_kernel)
        pil_img = TableParserUtils.cv_to_PIL(sharpen)
        return pil_img

    @staticmethod
    def uniquify(seq, suffs = count(1)):
        not_unique = [k for k,v in Counter(seq).items() if v>1]
        suff_gens = dict(zip(not_unique, tee(suffs, len(not_unique))))
        for idx,s in enumerate(seq):
            try:
                suffix = str(next(suff_gens[s]))
            except KeyError:
                continue
            else:
                # Comment.
                if isinstance(seq[idx], tuple):
                    seq[idx] = seq[idx] + (suffix,)
                else:
                    seq[idx] += suffix
        return seq

    @staticmethod
    def binarizeBlur_image(pil_img):
        image = TableParserUtils.PIL_to_cv(pil_img)
        thresh = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY_INV)[1]
        result = cv2.GaussianBlur(thresh, (5,5), 0)
        result = 255 - result
        return TableParserUtils.cv_to_PIL(result)





