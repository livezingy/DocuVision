# core/utils/file_utils.py
import os
import fitz
from PIL import Image
from typing import Generator
import re

def validate_writable(path: str) -> bool:
"""file utils module."""
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):  # Start from 1
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            yield page_num, img  # Return page number and image
            del pix  # Ensure pix is deleted to free resources

def sanitize_path(path: str) -> str:
    """Docstring."""
    return re.sub(r'[<>:"/\\|?*]', '', path).strip()

def validate_writable(path: str) -> bool:
    """Docstring."""
    if not path:
        raise ValueError("Output path cannot be empty")
    
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except PermissionError:
        raise PermissionError(f"Permission denied: {path}")
    except OSError as e:
        raise OSError(f"Invalid path format: {e}")