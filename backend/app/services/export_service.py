"""Export Service facade - multi-format document export.

Keeps ``ExportService`` (JSON/CSV/Excel/structured-JSON plus ``__init__``
owning ``output_dir``) and composes the Markdown/DOCX render mixins
(S1 batch 10 split of the former monolith); the pure table-format helpers
live in ``export_table_format.py`` and are re-exported here.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

from loguru import logger

from app.core.config import settings
from app.services.export_render_docx import DocxRenderMixin
from app.services.export_render_markdown import MarkdownRenderMixin
from app.services.export_table_format import (  # noqa: F401 (re-export; pack_export_service + tests import from here)
    excel_safe_cell,
    format_table_csv_banner,
    format_table_export_title,
    table_confidence_pct,
)


class ExportService(MarkdownRenderMixin, DocxRenderMixin):
    """
    Export Service for multiple output formats
    
    Supported formats:
    - JSON: Full structured data
    - CSV: Table data
    - Markdown: Formatted document
    - Word (DOCX): Microsoft Word document
    - Excel (XLSX): Spreadsheet with tables
    """
    def __init__(self):
        self.output_dir = settings.OUTPUT_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    async def to_json(
        self, 
        result: Dict[str, Any], 
        task_id: str,
        pretty: bool = True
    ) -> str:
        """
        Export full result to JSON file
        
        Args:
            result: Processing result dictionary
            task_id: Task identifier
            pretty: Whether to format JSON with indentation
        
        Returns:
            Path to exported JSON file
        """
        output_path = os.path.join(self.output_dir, f"{task_id}_result.json")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            if pretty:
                json.dump(result, f, ensure_ascii=False, indent=2)
            else:
                json.dump(result, f, ensure_ascii=False)
        
        logger.info(f"Exported JSON to {output_path}")
        return output_path

    async def to_csv(
        self, 
        result: Dict[str, Any], 
        task_id: str,
        include_all_tables: bool = True
    ) -> str:
        """
        Export tables to CSV file
        
        Args:
            result: Processing result dictionary
            task_id: Task identifier
            include_all_tables: Whether to include all tables in one file
        
        Returns:
            Path to exported CSV file
        """
        output_path = os.path.join(self.output_dir, f"{task_id}_tables.csv")
        
        tables = result.get('tables', [])
        
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            
            for idx, table in enumerate(tables):
                if 'data' in table and table['data']:
                    writer.writerow([format_table_csv_banner(idx + 1, table)])
                    caption = str(table.get("caption") or "").strip()
                    if caption:
                        writer.writerow([excel_safe_cell(f"Caption: {caption}")])
                    for row in table['data']:
                        writer.writerow([excel_safe_cell(c) for c in row])
                    
                    # Separator between tables
                    writer.writerow([])
        
        logger.info(f"Exported CSV to {output_path}")
        return output_path

    async def to_excel(self, result: Dict[str, Any], task_id: str) -> str:
        """
        Export tables to Excel file
        
        Args:
            result: Processing result dictionary
            task_id: Task identifier
        
        Returns:
            Path to exported XLSX file
        """
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas not installed, cannot export Excel")
            raise RuntimeError("pandas not installed")
        
        output_path = os.path.join(self.output_dir, f"{task_id}_tables.xlsx")
        
        tables = result.get('tables', [])
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = {
                'Property': ['File Name', 'Processed At', 'Total Pages', 'Total Tables'],
                'Value': [
                    result.get('document_info', {}).get('file_name', 'N/A'),
                    result.get('document_info', {}).get('processed_at', 'N/A'),
                    str(result.get('document_info', {}).get('pages', 'N/A')),
                    str(len(tables))
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Individual table sheets
            for idx, table in enumerate(tables):
                if 'data' in table and table['data']:
                    data = table['data']
                    
                    if len(data) > 1:
                        header = [excel_safe_cell(c) for c in data[0]]
                        num_cols = len(header)
                        normalized_data = []
                        for row in data[1:]:
                            safe_row = [excel_safe_cell(c) for c in row]
                            normalized_row = (safe_row + [''] * num_cols)[:num_cols]
                            normalized_data.append(normalized_row)
                        df = pd.DataFrame(normalized_data, columns=header)
                    else:
                        df = pd.DataFrame([[excel_safe_cell(c) for c in row] for row in data])
                    
                    sheet_name = f"Table_{idx + 1}"
                    df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=1)
                    worksheet = writer.sheets.get(sheet_name)
                    if worksheet is None:
                        worksheet = writer.book[sheet_name]
                    worksheet.cell(row=1, column=1, value=format_table_export_title(idx + 1, table))
        
        logger.info(f"Exported Excel to {output_path}")
        return output_path

    async def to_structured_json(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Export to Azure Document Intelligence compatible JSON format
        
        Args:
            result: Processing result dictionary
        
        Returns:
            Structured JSON dictionary in Azure DI format
        """
        return {
            "apiVersion": "1.0.0",
            "modelId": "docuvision-general",
            "content": result.get('layout', {}).get('elements', []),
            "pages": [
                {
                    "pageNumber": page.get('page'),
                    "width": 0,
                    "height": 0,
                    "unit": "pixel",
                    "elements": [
                        e for e in result.get('layout', {}).get('elements', [])
                        if e.get('page') == page.get('page')
                    ]
                }
                for page in result.get('layout', {}).get('page_layouts', [])
            ],
            "tables": [
                {
                    "rowCount": t.get('rows', 0),
                    "columnCount": t.get('columns', 0),
                    "cells": self._convert_table_cells(t),
                    "boundingRegions": [{
                        "pageNumber": t.get('page', 1),
                        "polygon": []
                    }]
                }
                for t in result.get('tables', [])
            ],
            "keyValuePairs": result.get('extracted_fields', {}),
            "styles": [],
            "languages": ["en"],
            "contentFormat": "text"
        }

    def _convert_table_cells(self, table: Dict) -> List[Dict]:
        """Convert table data to cell format"""
        cells = []
        data = table.get('data', [])
        
        for row_idx, row in enumerate(data):
            for col_idx, cell_text in enumerate(row):
                cells.append({
                    "rowIndex": row_idx,
                    "columnIndex": col_idx,
                    "content": str(cell_text),
                    "kind": "columnHeader" if row_idx == 0 else "content"
                })
        
        return cells
