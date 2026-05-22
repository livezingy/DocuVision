# tests/conftest.py
"""conftest module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
import numpy as np
from PIL import Image

#
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_page():
    page = Mock()
    page.width = 612.0
    page.height = 792.0
    page.page_number = 1
    return page


@pytest.fixture
def mock_feature_analyzer():
    analyzer = Mock()
    
    #
    analyzer.char_analysis = {
        'min_width': 5.0,
        'min_height': 8.0,
        'mode_width': 6.0,
        'mode_height': 10.0
    }
    
    #
    analyzer.text_line_analysis = {
        'total_lines': 20,
        'min_line_height': 8.0,
        'mode_line_height': 10.0,
        'max_line_height': 12.0,
        'min_line_spacing': 2.0,
        'mode_line_spacing': 3.0
    }
    
    #
    analyzer.line_analysis = {
        'horizontal_lines': [Mock(), Mock()],
        'vertical_lines': [Mock(), Mock()],
        'horizontal_lines_length': [100.0, 150.0],
        'vertical_lines_length': [200.0, 250.0],
        'line_widths': [0.5, 1.0, 1.5]
    }
    
    #
    analyzer.page = Mock()
    analyzer.page.width = 612.0
    analyzer.page.height = 792.0
    
    #
    analyzer.predict_table_type = Mock(return_value='bordered')
    
    return analyzer


@pytest.fixture
def sample_image():
    #
    img = Image.new('RGB', (800, 600), color='white')
    return img


@pytest.fixture
def sample_pdf_path(tmp_path):
    return str(tmp_path / "test.pdf")


@pytest.fixture
def mock_camelot_table():
    table = Mock()
    table.df = Mock()
    table.bbox = [100, 100, 500, 400]
    table.parsing_report = {'accuracy': 95.0, 'whitespace': 5.0}
    return table


@pytest.fixture
def mock_pdfplumber_table():
    table = Mock()
    table.bbox = (100, 100, 500, 400)
    table.extract = Mock(return_value=[['Cell1', 'Cell2'], ['Cell3', 'Cell4']])
    return table
