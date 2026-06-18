# core/models/table_visualize.py
"""table visualize module."""
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import matplotlib
# Comment.
# Comment.
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Patch
import numpy as np
import os
from docuvision_core.utils.logger import AppLogger


class TableVisualize:
    """Docstring."""
    
    def __init__(self):
        self.logger = AppLogger.get_logger()
        # Comment.
        self.colors = ["red", "blue", "green", "yellow", "orange", "violet", "brown", "pink"]
    
    def visualize_detected_tables(self, img: Image.Image, det_tables: List[Dict], save_path: Optional[str] = None) -> bool:
        """Docstring."""
        try:
            plt.figure(figsize=(20, 20))
            plt.imshow(img, interpolation="lanczos")
            ax = plt.gca()

            for det_table in det_tables:
                bbox = det_table['bbox']
                if det_table['label'] == 'table':
                    facecolor = (1, 0, 0.45)
                    edgecolor = (1, 0, 0.45)
                    alpha = 0.3
                    linewidth = 2
                    hatch = '//////'
                elif det_table['label'] == 'table rotated':
                    facecolor = (0.95, 0.6, 0.1)
                    edgecolor = (0.95, 0.6, 0.1)
                    alpha = 0.3
                    linewidth = 2
                    hatch = '//////'
                else:
                    continue

                rect = patches.Rectangle(bbox[:2], bbox[2] - bbox[0], bbox[3] - bbox[1], linewidth=linewidth,
                                         edgecolor='none', facecolor=facecolor, alpha=0.1)
                ax.add_patch(rect)
                rect = patches.Rectangle(bbox[:2], bbox[2] - bbox[0], bbox[3] - bbox[1], linewidth=linewidth,
                                         edgecolor=edgecolor, facecolor='none', linestyle='-', alpha=alpha)
                ax.add_patch(rect)
                rect = patches.Rectangle(bbox[:2], bbox[2] - bbox[0], bbox[3] - bbox[1], linewidth=0,
                                         edgecolor=edgecolor, facecolor='none', linestyle='-', hatch=hatch, alpha=0.2)
                ax.add_patch(rect)

            plt.xticks([], [])
            plt.yticks([], [])
            legend_elements = [Patch(facecolor=(1, 0, 0.45), edgecolor=(1, 0, 0.45), label='Table', hatch='//////', alpha=0.3),
                               Patch(facecolor=(0.95, 0.6, 0.1), edgecolor=(0.95, 0.6, 0.1), label='Table (rotated)', hatch='//////', alpha=0.3)]
            plt.legend(handles=legend_elements, bbox_to_anchor=(0.5, -0.02), loc='upper center', borderaxespad=0,
                       fontsize=10, ncol=2)
            plt.gcf().set_size_inches(10, 10)
            plt.axis('off')
            plt.title("Detected Tables", fontsize=16, fontweight='bold')
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"Table detection visualization saved to: {save_path}")
            
            plt.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Table visualization failed: {str(e)}")
            return False

    def visualize_cell_detection(self, table_image: Image.Image, cell_coordinates: List[Dict], save_path: Optional[str] = None) -> bool:
        """Docstring."""
        
        try:
            # Comment.
            if table_image.mode != 'RGB':
                table_image = table_image.convert('RGB')
            
            # Comment.
            img_width, img_height = table_image.size
            
            
            # Comment.
            fig_width = 16
            fig_height = fig_width * img_height / img_width
            
            plt.figure(figsize=(fig_width, fig_height))
            plt.imshow(table_image)
            ax = plt.gca()
            
            # Comment.
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)
            
            self.logger.info(f"Visualizing {len(cell_coordinates)} rows of cells on image size {img_width}x{img_height}")

            invalid_count = 0
            valid_count = 0
            
            for row_idx, row_data in enumerate(cell_coordinates):
                row_cells = row_data['cells']
                self.logger.debug(f"Row {row_idx}: {len(row_cells)} cells")
                
                for col_idx, cell_data in enumerate(row_cells):
                    cell_bbox = cell_data['cell']
                    
                    
                    if len(cell_bbox) >= 4:
                        x1, y1, x2, y2 = cell_bbox
                        
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
                            invalid_count += 1
                            self.logger.warning(f"Invalid cell bbox at R{row_idx+1}C{col_idx+1}: {cell_bbox}")
                            continue
                        
                        valid_count += 1
                        
                        # Comment.
                        color = self.colors[(row_idx + col_idx) % len(self.colors)]
                        
                        # Comment.
                        rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                               linewidth=2, edgecolor=color, facecolor='none', alpha=0.8)
                        ax.add_patch(rect)
                        
                        # Comment.
                        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                        ax.text(center_x, center_y, f'R{row_idx+1}C{col_idx+1}', 
                               ha='center', va='center', fontsize=8, 
                               bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.7))
                    else:
                        invalid_count += 1
                        self.logger.warning(f"Invalid cell bbox format at R{row_idx+1}C{col_idx+1}: {cell_bbox}")
            
            
            plt.axis('off')
            plt.title("Cell Detection Results", fontsize=16, fontweight='bold')
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"Cell detection visualization saved to: {save_path}")
            
            plt.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Cell visualization failed: {str(e)}")
            return False

    def visualize_table_structure(self, table_image: Image.Image, table_data: Dict, save_path: Optional[str] = None) -> bool:
        """Docstring."""
        try:
            # Comment.
            if table_image.mode != 'RGB':
                table_image = table_image.convert('RGB')
            
            # Comment.
            img_width, img_height = table_image.size
            
            # Comment.
            fig_width = 16
            fig_height = fig_width * img_height / img_width
            
            plt.figure(figsize=(fig_width, fig_height))
            plt.imshow(table_image)
            ax = plt.gca()
            
            # Comment.
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)
            
            # Comment.
            table_rows = table_data.get('table_rows', [])
            table_cols = table_data.get('table_cols', [])
            special_labels = table_data.get('special_labels', {})
            
            self.logger.info(f"Visualizing table structure: {len(table_rows)} rows, {len(table_cols)} cols on image size {img_width}x{img_height}")
            
            # Comment.
            self._draw_table_grid(ax, table_rows, table_cols, img_width, img_height)
            
            # Comment.
            self._draw_special_labels(ax, special_labels, img_width, img_height)
            
            # Comment.
            self._draw_spanning_cells(ax, special_labels.get('spanning_cells', []), img_width, img_height)
            
            plt.axis('off')
            plt.title("Table Structure Visualization", fontsize=16, fontweight='bold')
            
            # Comment.
            self._add_legend(ax)
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.logger.info(f"Table structure visualization saved to: {save_path}")
            
            plt.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Table structure visualization failed: {str(e)}")
            return False

    def _draw_table_grid(self, ax, table_rows: List[Dict], table_cols: List[Dict], img_width: int, img_height: int):
        """Docstring."""
        try:
            # Comment.
            for i, row in enumerate(table_rows):
                bbox = row.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # Comment.
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid row bbox {i+1}: {bbox}")
                        continue
                    
                    # Comment.
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=1, edgecolor='blue', facecolor='none', alpha=0.3)
                    ax.add_patch(rect)
                    
                    # Comment.
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(center_x, max(0, y1 - 10), f'Row {i+1}', 
                           ha='center', va='bottom', fontsize=8, color='blue')
            
            # Comment.
            for i, col in enumerate(table_cols):
                bbox = col.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # Comment.
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid col bbox {i+1}: {bbox}")
                        continue
                    
                    # Comment.
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=1, edgecolor='green', facecolor='none', alpha=0.3)
                    ax.add_patch(rect)
                    
                    # Comment.
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(max(0, x1 - 10), center_y, f'Col {i+1}', 
                           ha='right', va='center', fontsize=8, color='green')
                           
        except Exception as e:
            self.logger.error(f"Error drawing table grid: {str(e)}")

    def _draw_special_labels(self, ax, special_labels: Dict, img_width: int, img_height: int):
        """Docstring."""
        try:
            # Comment.
            column_headers = special_labels.get('column_headers', [])
            for i, header in enumerate(column_headers):
                bbox = header.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # Comment.
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid column header bbox {i+1}: {bbox}")
                        continue
                    
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=2, edgecolor='red', facecolor='red', alpha=0.2)
                    ax.add_patch(rect)
                    
                    # Comment.
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(center_x, center_y, 'Header', 
                           ha='center', va='center', fontsize=8, color='red', weight='bold')
            
            # Comment.
            row_headers = special_labels.get('projected_row_headers', [])
            for i, header in enumerate(row_headers):
                bbox = header.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # Comment.
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid row header bbox {i+1}: {bbox}")
                        continue
                    
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=2, edgecolor='orange', facecolor='orange', alpha=0.2)
                    ax.add_patch(rect)
                    
                    # Comment.
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(center_x, center_y, 'Row Header', 
                           ha='center', va='center', fontsize=8, color='orange', weight='bold')
                           
        except Exception as e:
            self.logger.error(f"Error drawing special labels: {str(e)}")

    def _draw_spanning_cells(self, ax, spanning_cells: List[Dict], img_width: int, img_height: int):
        """Docstring."""
        try:
            for i, cell in enumerate(spanning_cells):
                bbox = cell.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # Comment.
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid spanning cell bbox {i+1}: {bbox}")
                        continue
                    
                    # Comment.
                    span_type = cell.get('span_type', 'normal')
                    col_span = cell.get('col_span', 1)
                    row_span = cell.get('row_span', 1)
                    
                    if span_type == 'both':
                        color = 'purple'
                        hatch = '///'
                    elif span_type == 'column':
                        color = 'cyan'
                        hatch = '|||'
                    elif span_type == 'row':
                        color = 'magenta'
                        hatch = '---'
                    else:
                        color = 'gray'
                        hatch = None
                    
                    # Comment.
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=3, edgecolor=color, facecolor=color, alpha=0.3)
                    if hatch:
                        rect.set_hatch(hatch)
                    ax.add_patch(rect)
                    
                    # Comment.
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    span_text = f'Span: {row_span}x{col_span}'
                    ax.text(center_x, center_y, span_text, 
                           ha='center', va='center', fontsize=8, color=color, weight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
                           
        except Exception as e:
            self.logger.error(f"Error drawing spanning cells: {str(e)}")

    def _add_legend(self, ax):
        """Docstring."""
        try:
            legend_elements = [
                Patch(facecolor='blue', edgecolor='blue', alpha=0.3, label='Table Rows'),
                Patch(facecolor='green', edgecolor='green', alpha=0.3, label='Table Columns'),
                Patch(facecolor='red', edgecolor='red', alpha=0.2, label='Column Headers'),
                Patch(facecolor='orange', edgecolor='orange', alpha=0.2, label='Row Headers'),
                Patch(facecolor='purple', edgecolor='purple', alpha=0.3, hatch='///', label='Both Spanning'),
                Patch(facecolor='cyan', edgecolor='cyan', alpha=0.3, hatch='|||', label='Column Spanning'),
                Patch(facecolor='magenta', edgecolor='magenta', alpha=0.3, hatch='---', label='Row Spanning')
            ]
            
            ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1, 1), fontsize=8)
            
        except Exception as e:
            self.logger.error(f"Error adding legend: {str(e)}")

    def create_comprehensive_visualization(self, table_image: Image.Image, table_data: Dict, 
                                         cell_coordinates: List[Dict] = None, 
                                         save_dir: str = "tests/results") -> Dict[str, str]:
        """
        
        Args:
            
        Returns:
        """
        try:
            # Comment.
            os.makedirs(save_dir, exist_ok=True)
            
            saved_files = {}
            
            # Comment.
            structure_path = os.path.join(save_dir, "table_structure_visualization.png")
            if self.visualize_table_structure(table_image, table_data, structure_path):
                saved_files['structure'] = structure_path
            
            # Comment.
            if cell_coordinates:
                cell_path = os.path.join(save_dir, "cell_detection_visualization.png")
                if self.visualize_cell_detection(table_image, cell_coordinates, cell_path):
                    saved_files['cells'] = cell_path
            
            # Comment.
            special_path = os.path.join(save_dir, "special_labels_visualization.png")
            if self._visualize_special_labels_only(table_image, table_data, special_path):
                saved_files['special'] = special_path
            
            self.logger.info(f"Comprehensive visualization completed. Saved files: {list(saved_files.keys())}")
            return saved_files
            
        except Exception as e:
            self.logger.error(f"Comprehensive visualization failed: {str(e)}")
            return {}

    def _visualize_special_labels_only(self, table_image: Image.Image, table_data: Dict, save_path: str) -> bool:
        """Docstring."""
        try:
            # Comment.
            if table_image.mode != 'RGB':
                table_image = table_image.convert('RGB')
            
            # Comment.
            img_width, img_height = table_image.size
            
            # Comment.
            fig_width = 12
            fig_height = fig_width * img_height / img_width
            
            plt.figure(figsize=(fig_width, fig_height))
            plt.imshow(table_image)
            ax = plt.gca()
            
            # Comment.
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)
            
            special_labels = table_data.get('special_labels', {})
            
            # Comment.
            self._draw_special_labels(ax, special_labels, img_width, img_height)
            
            # Comment.
            self._draw_spanning_cells(ax, special_labels.get('spanning_cells', []), img_width, img_height)
            
            plt.axis('off')
            plt.title("Special Labels Visualization", fontsize=16, fontweight='bold')
            
            # Comment.
            self._add_legend(ax)
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Special labels visualization saved to: {save_path}")
            
            plt.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Special labels visualization failed: {str(e)}")
            return False
