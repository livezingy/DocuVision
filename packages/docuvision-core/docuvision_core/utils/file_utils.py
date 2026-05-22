# core/utils/file_utils.py
import os
import fitz
from PIL import Image
from typing import Generator
import re

def validate_writable(path: str) -> bool:
    """Validate if path is writable
    
    Args:
        path: Path to validate
        
    Returns:
        True if path is writable
        
    Raises:
        PermissionError: If path is not writable
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
        except OSError:
            raise PermissionError(f"Cannot create directory: {path}")
    
    test_file = os.path.join(path, '.write_test')
    try:
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except IOError:
        raise PermissionError(f"Path is not writable: {path}")

def pdf_to_images(pdf_path: str, dpi=300) -> Generator[tuple[int, Image.Image], None, None]:
    """Convert PDF to images
    
    Args:
        pdf_path: PDF file path
        dpi: Image resolution
        
    Returns:
        Generator yielding (page number, image) tuples
    
    Note:
        release resources after use
    """
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):  # Start from 1
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            yield page_num, img  # Return page number and image
            del pix  # Ensure pix is deleted to free resources

def sanitize_path(path: str) -> str:
    """Sanitize file path
    
    Args:
        path: Input path
        
    Returns:
        Sanitized path
    """
    return re.sub(r'[<>:"/\\|?*]', '', path).strip()

def validate_writable(path: str) -> bool:
    """Validate if path is writable with detailed error handling
    
    Args:
        path: Path to validate
        
    Returns:
        True if path is writable
        
    Raises:
        ValueError: If path is empty
        PermissionError: If path is not writable
        OSError: If path format is invalid
    """
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