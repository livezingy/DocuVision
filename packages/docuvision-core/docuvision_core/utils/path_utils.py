# core/utils/path_utils.py
import os
import sys
import platform
from typing import Dict

OUTPUT_STRUCTURE = {
    'data': {
        'description': 'Extracted table data',
        'extensions': ['.csv', '.json']
    },
    'debug': {
        'description': 'Debug information',
        'extensions': ['.png', '.log']
    },
    'preview': {
        'description': 'Preview images',
        'extensions': ['.png']
    }
}

def get_output_structure():
    """Docstring."""
    return OUTPUT_STRUCTURE

def get_valid_extensions(subfolder: str) -> list:
    """Docstring."""
    if subfolder not in OUTPUT_STRUCTURE:
        raise ValueError(f"Invalid subfolder: {subfolder}")
    return OUTPUT_STRUCTURE[subfolder]['extensions'] 


def get_app_dir() -> str:
    """Docstring."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

def get_tesseract_bin() -> str:
    """Default Tesseract executable path for the current platform."""
    if sys.platform == 'win32':
        return os.path.join(get_app_dir(), 'tesseract', 'tesseract.exe')
    return 'tesseract'

def resolve_tesseract_cmd(configured_path: str | None = None) -> str:
    """Resolve a usable Tesseract binary (config path, PATH, or platform default)."""
    import shutil

    if configured_path and os.path.isfile(configured_path):
        return configured_path
    which = shutil.which("tesseract")
    if which:
        return which
    return get_tesseract_bin()

def get_tessdata_dir() -> str:
    """Docstring."""
    if sys.platform == 'win32':
        return os.path.join(get_app_dir(), 'tesseract', 'tessdata')
    return '/usr/share/tesseract-ocr/4.00/tessdata'

def get_output_paths(base_path: str) -> Dict[str, str]:
    """Docstring."""
    # Get output structure from configuration
    output_structure = get_output_structure()
    
    # Create paths dictionary
    paths = {
        subfolder: os.path.join(base_path, subfolder)
        for subfolder in output_structure.keys()
    }
    
    # Create directories if they don't exist
    for path in paths.values():
        os.makedirs(path, exist_ok=True)
        
    return paths

def get_output_subpath(params: dict, subfolder: str, filename: str = "") -> str:
    """Docstring."""
    output_structure = get_output_structure()
    output_path = params.get('output_path', '')
    file_path = params.get('current_filepath')
    if not output_path or not file_path:
        raise ValueError("params must contain output_path and current_filepath")
    pdf_stem = os.path.splitext(os.path.basename(file_path))[0]
    if subfolder not in output_structure:
        raise ValueError(f"Invalid subfolder: {subfolder}")
    full_dir = os.path.join(output_path, subfolder, pdf_stem)
    os.makedirs(full_dir, exist_ok=True)
    if filename:
        return os.path.join(full_dir, filename)
    else:
        return full_dir