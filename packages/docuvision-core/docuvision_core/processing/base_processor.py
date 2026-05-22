# core/processing/base_processor.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from docuvision_core.utils.logger import AppLogger
from typing import Optional,Tuple, List, Dict
import pandas as pd
import os
from datetime import datetime
import time
from PIL import Image
from docuvision_core.utils.path_utils import get_output_subpath



class BaseProcessor(ABC):
    """Docstring."""
    
    def __init__(self):
        """Docstring."""
        self.logger = AppLogger.get_logger()
        

            
    @abstractmethod
    def process(self, file_path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Docstring."""
        pass
        
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Docstring."""
        try:
            # Basic parameter validation
            if not isinstance(params, dict):
                self.logger.error("Parameters must be a dictionary")
                return False
                
            # Add specific validation as needed
            return True
            
        except Exception as e:
            self.logger.error(f"Parameter validation failed: {str(e)}")
            return False
            
    def log_operation(self, operation: str, data: Optional[Dict] = None):
        """Docstring."""
        self.logger.log_operation(operation, data)
        
    def log_error(self, error: Exception, data: Optional[Dict] = None):
        """Docstring."""
        self.logger.log_exception(error, data)

    def _handle_export(self, results: Dict, params: Dict) -> str:
        """Docstring."""
        try:
            if not results or not results.get('tables'):
                self.logger.warning("No table data to export")
                return ""
                
            # Get export parameters
            export_format = params.get('export_format', 'csv')  # Default to CSV
            output_path = params.get('output_path', '')
            
            if not output_path:
                raise ValueError("Output path must be specified")
            
            # Get data subfolder path
            from docuvision_core.utils.path_utils import get_output_subpath
            
            # Generate filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_tables.{export_format}"
            filepath = get_output_subpath(params,'data',filename)

            # Export data
            if export_format == 'csv':
                self._export_tables_csv(results['tables'], filepath)
            elif export_format == 'json':
                self._export_tables_json(results['tables'], filepath)
                
            self.logger.info(f"Data exported successfully: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Export failed: {str(e)}", exc_info=True)
            return ""
            
    def _export_tables_csv(self, tables: List[Dict], filepath: str):
        """Docstring."""
        try:
            # Create output directory
            output_dir = os.path.dirname(filepath)
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            
            # Export each table
            for i, table in enumerate(tables):
                # Comment.
                if isinstance(table, dict) and 'table' in table:
                    # Comment.
                    wrapper = table['table']
                    if hasattr(wrapper, 'df') and hasattr(wrapper.df, 'to_dict'):
                        # Comment.
                        table_data = {
                            'data': wrapper.df.to_dict('records'),
                            'columns': wrapper.df.columns.tolist()
                        }
                    else:
                        self.logger.warning(f"Invalid table wrapper at index {i}")
                        continue
                elif isinstance(table, dict) and 'data' in table and 'columns' in table:
                    # Comment.
                    table_data = table
                else:
                    self.logger.warning(f"Skipping invalid table data at index {i}: {type(table)}")
                    continue
                    
                try:
                    # Create DataFrame
                    df = pd.DataFrame(
                        table_data['data'],
                        columns=table_data['columns']
                    )
                    
                    # Generate filename
                    csv_file = os.path.join(
                        output_dir,
                        f"{base_name}_table_{i+1}.csv"
                    )
                    
                    # Export to CSV
                    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                    
                except Exception as e:
                    self.logger.error(f"Failed to export table {i+1} to CSV: {str(e)}")
                    continue
                
            self.logger.info(f"CSV export successful: {output_dir}")
            
        except Exception as e:
            self.logger.error(f"CSV export failed: {str(e)}", exc_info=True)
            raise
            
    def _export_tables_json(self, tables: List[Dict], filepath: str):
        """Docstring."""
        try:
            import json
            
            # Prepare data for JSON export
            export_data = []
            for i, table in enumerate(tables):
                if not isinstance(table, dict) or 'data' not in table or 'columns' not in table:
                    self.logger.warning(f"Skipping invalid table data at index {i}")
                    continue
                    
                try:
                    # Create DataFrame
                    df = pd.DataFrame(
                        table['data'],
                        columns=table['columns']
                    )
                    
                    # Convert to dictionary
                    table_data = {
                        'table_index': i + 1,
                        'columns': table['columns'],
                        'data': df.to_dict('records'),
                        'metadata': {
                            'page': table.get('page', 0),
                            'confidence': table.get('confidence', 0.0),
                            'bbox': table.get('bbox', [])
                        }
                    }
                    export_data.append(table_data)
                    
                except Exception as e:
                    self.logger.error(f"Failed to process table {i+1} for JSON export: {str(e)}")
                    continue
            
            # Export to JSON
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"JSON export successful: {filepath}")
            
        except Exception as e:
            self.logger.error(f"JSON export failed: {str(e)}", exc_info=True)
            raise
            
    def preview_tables(self, page_num: int, page_image: Image.Image, params: dict, table_areas: List[tuple]) -> Image.Image:
        """Docstring."""
        output_dir = os.path.join(
            params['output_path'],
            f"{os.path.splitext(os.path.basename(params['current_file']))[0]}_marked_images"
        )
        os.makedirs(output_dir, exist_ok=True)
            
        # Draw and save marked image
        marked_image = self._draw_table_areas(page_image.copy(), table_areas)
        marked_image.save(f"{output_dir}/page_{page_num+1}_marked.png")
        
    def _draw_table_areas(self, image: Image.Image, boxes: list) -> Image.Image:
        """Docstring."""
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        for box in boxes:
            draw.rectangle(box, outline="red", width=3)
        return image
    
    

    





