# core/models/table_visualize.py
"""
TableVisualize: 表格检测和结构可视化模�?
从table_parser.py中独立出来的可视化功能，包括�?
1. 模型检测可视化
2. 单元格检测和处理可视�?
3. 表格结构可视化（包括合并单元格）
"""
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import matplotlib
# 使用 Agg 后端（非交互式），避�?Qt 字体系统问题
# Agg 后端只用于保存图片，不依�?Qt，适合后台处理
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Patch
import numpy as np
import os
from docuvision_core.utils.logger import AppLogger


class TableVisualize:
    """表格可视化类，提供各种表格检测和结构可视化功�?""
    
    def __init__(self):
        self.logger = AppLogger.get_logger()
        # 颜色列表用于可视�?
        self.colors = ["red", "blue", "green", "yellow", "orange", "violet", "brown", "pink"]
    
    def visualize_detected_tables(self, img: Image.Image, det_tables: List[Dict], save_path: Optional[str] = None) -> bool:
        """
        可视化检测到的表格，参�?TestTransformer.py 的实�?
        
        Args:
            img: 原始图像
            det_tables: 检测到的表格列�?
            save_path: 保存路径，如果为None则不保存
            
        Returns:
            bool: 是否成功
        """
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
        """
        可视化单元格检测结�?
        
        Args:
            table_image: 表格图像
            cell_coordinates: 单元格坐标列�?
            save_path: 保存路径，如果为None则不保存
            
        Returns:
            bool: 是否成功
        """
        # #region agent log
        from docuvision_core.utils.debug_utils import write_debug_log
        try:
            write_debug_log(
                location="table_visualize.py:92",
                message="visualize_cell_detection entry",
                data={
                    "cell_coordinates_count": len(cell_coordinates),
                    "image_mode": table_image.mode if table_image else None
                },
                hypothesis_id="J"
            )
        except Exception as e:
            self.logger.warning(f"Debug log write failed at visualize_cell_detection entry: {e}")
        # #endregion
        
        try:
            # 确保图像是RGB格式
            if table_image.mode != 'RGB':
                table_image = table_image.convert('RGB')
            
            # 获取图像尺寸
            img_width, img_height = table_image.size
            
            # #region agent log
            try:
                write_debug_log(
                    location="table_visualize.py:110",
                    message="image size extracted",
                    data={
                        "img_width": img_width,
                        "img_height": img_height,
                        "image_mode": table_image.mode
                    },
                    hypothesis_id="J"
                )
            except Exception as e:
                self.logger.warning(f"Debug log write failed at image size: {e}")
            # #endregion
            
            # 设置图形尺寸，保持宽高比
            fig_width = 16
            fig_height = fig_width * img_height / img_width
            
            plt.figure(figsize=(fig_width, fig_height))
            plt.imshow(table_image)
            ax = plt.gca()
            
            # 设置坐标轴范围，确保与图像尺寸一�?
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)  # 注意：matplotlib的y轴是倒置�?
            
            self.logger.info(f"Visualizing {len(cell_coordinates)} rows of cells on image size {img_width}x{img_height}")

            invalid_count = 0
            valid_count = 0
            
            for row_idx, row_data in enumerate(cell_coordinates):
                row_cells = row_data['cells']
                self.logger.debug(f"Row {row_idx}: {len(row_cells)} cells")
                
                for col_idx, cell_data in enumerate(row_cells):
                    cell_bbox = cell_data['cell']
                    
                    # #region agent log
                    try:
                        write_debug_log(
                            location="table_visualize.py:131",
                            message="cell bbox before validation",
                            data={
                                "row": row_idx,
                                "col": col_idx,
                                "bbox": cell_bbox,
                                "bbox_type": type(cell_bbox).__name__,
                                "bbox_len": len(cell_bbox) if hasattr(cell_bbox, '__len__') else None
                            },
                            hypothesis_id="J"
                        )
                    except Exception as e:
                        self.logger.warning(f"Debug log write failed at bbox before validation: {e}")
                    # #endregion
                    
                    if len(cell_bbox) >= 4:
                        x1, y1, x2, y2 = cell_bbox
                        
                        # 验证坐标的合理�?
                        violations = {
                            "x1_ge_x2": x1 >= x2,
                            "y1_ge_y2": y1 >= y2,
                            "x1_lt_0": x1 < 0,
                            "y1_lt_0": y1 < 0,
                            "x2_gt_width": x2 > img_width,
                            "y2_gt_height": y2 > img_height
                        }
                        is_valid = not any(violations.values())
                        
                        # #region agent log
                        try:
                            write_debug_log(
                                location="table_visualize.py:136",
                                message="cell bbox validation result",
                                data={
                                    "row": row_idx,
                                    "col": col_idx,
                                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                                    "img_size": [img_width, img_height],
                                    "is_valid": is_valid,
                                    "violations": violations
                                },
                                hypothesis_id="J"
                            )
                        except Exception as e:
                            self.logger.warning(f"Debug log write failed at bbox validation: {e}")
                        # #endregion
                        
                        if not is_valid:
                            invalid_count += 1
                            self.logger.warning(f"Invalid cell bbox at R{row_idx+1}C{col_idx+1}: {cell_bbox}")
                            continue
                        
                        valid_count += 1
                        
                        # 使用不同颜色绘制单元�?
                        color = self.colors[(row_idx + col_idx) % len(self.colors)]
                        
                        # 绘制单元格边�?
                        rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                               linewidth=2, edgecolor=color, facecolor='none', alpha=0.8)
                        ax.add_patch(rect)
                        
                        # 添加单元格标�?
                        center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                        ax.text(center_x, center_y, f'R{row_idx+1}C{col_idx+1}', 
                               ha='center', va='center', fontsize=8, 
                               bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.7))
                    else:
                        invalid_count += 1
                        # #region agent log
                        try:
                            write_debug_log(
                                location="table_visualize.py:154",
                                message="invalid bbox format",
                                data={
                                    "row": row_idx,
                                    "col": col_idx,
                                    "bbox": cell_bbox,
                                    "bbox_len": len(cell_bbox) if hasattr(cell_bbox, '__len__') else None
                                },
                                hypothesis_id="J"
                            )
                        except Exception as e:
                            self.logger.warning(f"Debug log write failed at invalid format: {e}")
                        # #endregion
                        self.logger.warning(f"Invalid cell bbox format at R{row_idx+1}C{col_idx+1}: {cell_bbox}")
            
            # #region agent log
            try:
                write_debug_log(
                    location="table_visualize.py:156",
                    message="cell detection visualization completed",
                    data={
                        "valid_count": valid_count,
                        "invalid_count": invalid_count,
                        "total_cells": valid_count + invalid_count
                    },
                    hypothesis_id="J"
                )
            except Exception as e:
                self.logger.warning(f"Debug log write failed at completion: {e}")
            # #endregion
            
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
        """
        可视化表格结构，包括合并单元�?
        
        Args:
            table_image: 表格图像
            table_data: 表格数据，包含特殊标签处理结果和表格行列信息
            save_path: 保存路径，如果为None则不保存
            
        Returns:
            bool: 是否成功
        """
        try:
            # 确保图像是RGB格式
            if table_image.mode != 'RGB':
                table_image = table_image.convert('RGB')
            
            # 获取图像尺寸
            img_width, img_height = table_image.size
            
            # 设置图形尺寸，保持宽高比
            fig_width = 16
            fig_height = fig_width * img_height / img_width
            
            plt.figure(figsize=(fig_width, fig_height))
            plt.imshow(table_image)
            ax = plt.gca()
            
            # 设置坐标轴范围，确保与图像尺寸一�?
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)  # 注意：matplotlib的y轴是倒置�?
            
            # 获取表格结构信息
            table_rows = table_data.get('table_rows', [])
            table_cols = table_data.get('table_cols', [])
            special_labels = table_data.get('special_labels', {})
            
            self.logger.info(f"Visualizing table structure: {len(table_rows)} rows, {len(table_cols)} cols on image size {img_width}x{img_height}")
            
            # 绘制基本表格网格
            self._draw_table_grid(ax, table_rows, table_cols, img_width, img_height)
            
            # 绘制特殊标签
            self._draw_special_labels(ax, special_labels, img_width, img_height)
            
            # 绘制合并单元�?
            self._draw_spanning_cells(ax, special_labels.get('spanning_cells', []), img_width, img_height)
            
            plt.axis('off')
            plt.title("Table Structure Visualization", fontsize=16, fontweight='bold')
            
            # 添加图例
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
        """绘制基本表格网格"""
        try:
            # 绘制�?
            for i, row in enumerate(table_rows):
                bbox = row.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # 验证坐标的合理�?
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid row bbox {i+1}: {bbox}")
                        continue
                    
                    # 绘制行边�?
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=1, edgecolor='blue', facecolor='none', alpha=0.3)
                    ax.add_patch(rect)
                    
                    # 添加行标�?
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(center_x, max(0, y1 - 10), f'Row {i+1}', 
                           ha='center', va='bottom', fontsize=8, color='blue')
            
            # 绘制�?
            for i, col in enumerate(table_cols):
                bbox = col.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # 验证坐标的合理�?
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid col bbox {i+1}: {bbox}")
                        continue
                    
                    # 绘制列边�?
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=1, edgecolor='green', facecolor='none', alpha=0.3)
                    ax.add_patch(rect)
                    
                    # 添加列标�?
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(max(0, x1 - 10), center_y, f'Col {i+1}', 
                           ha='right', va='center', fontsize=8, color='green')
                           
        except Exception as e:
            self.logger.error(f"Error drawing table grid: {str(e)}")

    def _draw_special_labels(self, ax, special_labels: Dict, img_width: int, img_height: int):
        """绘制特殊标签（列标题、行标题等）"""
        try:
            # 绘制列标�?
            column_headers = special_labels.get('column_headers', [])
            for i, header in enumerate(column_headers):
                bbox = header.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # 验证坐标的合理�?
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid column header bbox {i+1}: {bbox}")
                        continue
                    
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=2, edgecolor='red', facecolor='red', alpha=0.2)
                    ax.add_patch(rect)
                    
                    # 添加标签
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(center_x, center_y, 'Header', 
                           ha='center', va='center', fontsize=8, color='red', weight='bold')
            
            # 绘制行标�?
            row_headers = special_labels.get('projected_row_headers', [])
            for i, header in enumerate(row_headers):
                bbox = header.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # 验证坐标的合理�?
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid row header bbox {i+1}: {bbox}")
                        continue
                    
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=2, edgecolor='orange', facecolor='orange', alpha=0.2)
                    ax.add_patch(rect)
                    
                    # 添加标签
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    ax.text(center_x, center_y, 'Row Header', 
                           ha='center', va='center', fontsize=8, color='orange', weight='bold')
                           
        except Exception as e:
            self.logger.error(f"Error drawing special labels: {str(e)}")

    def _draw_spanning_cells(self, ax, spanning_cells: List[Dict], img_width: int, img_height: int):
        """绘制合并单元�?""
        try:
            for i, cell in enumerate(spanning_cells):
                bbox = cell.get('bbox', [])
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox
                    
                    # 验证坐标的合理�?
                    if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
                        self.logger.warning(f"Invalid spanning cell bbox {i+1}: {bbox}")
                        continue
                    
                    # 根据合并类型选择颜色和样�?
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
                    
                    # 绘制合并单元�?
                    rect = patches.Rectangle((x1, y1), x2 - x1, y2 - y1, 
                                           linewidth=3, edgecolor=color, facecolor=color, alpha=0.3)
                    if hatch:
                        rect.set_hatch(hatch)
                    ax.add_patch(rect)
                    
                    # 添加合并信息标签
                    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
                    span_text = f'Span: {row_span}x{col_span}'
                    ax.text(center_x, center_y, span_text, 
                           ha='center', va='center', fontsize=8, color=color, weight='bold',
                           bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))
                           
        except Exception as e:
            self.logger.error(f"Error drawing spanning cells: {str(e)}")

    def _add_legend(self, ax):
        """添加图例"""
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
        创建综合可视化，包括所有类型的可视�?
        
        Args:
            table_image: 表格图像
            table_data: 表格数据
            cell_coordinates: 单元格坐标（可选）
            save_dir: 保存目录
            
        Returns:
            Dict[str, str]: 保存的文件路径字�?
        """
        try:
            # 确保保存目录存在
            os.makedirs(save_dir, exist_ok=True)
            
            saved_files = {}
            
            # 1. 表格结构可视�?
            structure_path = os.path.join(save_dir, "table_structure_visualization.png")
            if self.visualize_table_structure(table_image, table_data, structure_path):
                saved_files['structure'] = structure_path
            
            # 2. 单元格检测可视化（如果提供了单元格坐标）
            if cell_coordinates:
                cell_path = os.path.join(save_dir, "cell_detection_visualization.png")
                if self.visualize_cell_detection(table_image, cell_coordinates, cell_path):
                    saved_files['cells'] = cell_path
            
            # 3. 特殊标签可视�?
            special_path = os.path.join(save_dir, "special_labels_visualization.png")
            if self._visualize_special_labels_only(table_image, table_data, special_path):
                saved_files['special'] = special_path
            
            self.logger.info(f"Comprehensive visualization completed. Saved files: {list(saved_files.keys())}")
            return saved_files
            
        except Exception as e:
            self.logger.error(f"Comprehensive visualization failed: {str(e)}")
            return {}

    def _visualize_special_labels_only(self, table_image: Image.Image, table_data: Dict, save_path: str) -> bool:
        """仅可视化特殊标签"""
        try:
            # 确保图像是RGB格式
            if table_image.mode != 'RGB':
                table_image = table_image.convert('RGB')
            
            # 获取图像尺寸
            img_width, img_height = table_image.size
            
            # 设置图形尺寸，保持宽高比
            fig_width = 12
            fig_height = fig_width * img_height / img_width
            
            plt.figure(figsize=(fig_width, fig_height))
            plt.imshow(table_image)
            ax = plt.gca()
            
            # 设置坐标轴范围，确保与图像尺寸一�?
            ax.set_xlim(0, img_width)
            ax.set_ylim(img_height, 0)  # 注意：matplotlib的y轴是倒置�?
            
            special_labels = table_data.get('special_labels', {})
            
            # 绘制特殊标签
            self._draw_special_labels(ax, special_labels, img_width, img_height)
            
            # 绘制合并单元�?
            self._draw_spanning_cells(ax, special_labels.get('spanning_cells', []), img_width, img_height)
            
            plt.axis('off')
            plt.title("Special Labels Visualization", fontsize=16, fontweight='bold')
            
            # 添加图例
            self._add_legend(ax)
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Special labels visualization saved to: {save_path}")
            
            plt.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Special labels visualization failed: {str(e)}")
            return False
