# core/utils/param_config.py
"""
Parameter Configuration Utilities

Provides parameter definitions, validation, and configuration management
for PDFPlumber and Camelot table extraction parameters.
"""

from typing import Dict, Optional, Tuple, Literal, Any
from enum import Enum


class ParamMode(Enum):
    """Parameter configuration mode"""
    DEFAULT = "default"
    AUTO = "auto"
    CUSTOM = "custom"


# PDFPlumber parameter definitions
PDFPLUMBER_PARAM_DEFS = {
    'snap_tolerance': {
        'type': float,
        'default': 2.0,
        'range': (0.5, 10.0),
        'description': 'Parallel lines within snap_tolerance points will be merged to the same horizontal or vertical position.'
    },
    'join_tolerance': {
        'type': float,
        'default': 2.0,
        'range': (1.0, 10.0),
        'description': 'Line segments on the same infinite line, and whose ends are within join_tolerance of one another, will be joined into a single line segment.'
    },
    'edge_min_length': {
        'type': float,
        'default': 3.0,
        'range': (1.0, 30.0),
        'description': 'The minimum length of a line segment that is considered to be part of a table edge.'
    },
    'intersection_tolerance': {
        'type': float,
        'default': 3.0,
        'range': (1.0, 10.0),
        'description': 'When combining edges into cells, orthogonal edges must be within intersection_tolerance points to be considered intersecting.'
    },
    'min_words_vertical': {
        'type': int,
        'default': 1,
        'range': (1, 10),
        'description': 'When using "vertical_strategy": "text", at least min_words_vertical words must share the same alignment.'
    },
    'min_words_horizontal': {
        'type': int,
        'default': 1,
        'range': (1, 10),
        'description': 'When using "horizontal_strategy": "text", at least min_words_horizontal words must share the same alignment.'
    },
    'text_x_tolerance': {
        'type': float,
        'default': 3.0,
        'range': (1.0, 10.0),
        'description': 'When the text strategy is used, individual letters in each word will be expected to be no more than text_x_tolerance points apart horizontally.'
    },
    'text_y_tolerance': {
        'type': float,
        'default': 5.0,
        'range': (1.0, 8.0),
        'description': 'When the text strategy is used, individual letters in each word will be expected to be no more than text_y_tolerance points apart vertically.'
    },
    'vertical_strategy': {
        'type': str,
        'default': 'lines',
        'options': ['lines', 'text', 'explicit'],
        'description': 'Strategy for detecting vertical table edges.'
    },
    'horizontal_strategy': {
        'type': str,
        'default': 'lines',
        'options': ['lines', 'text', 'explicit'],
        'description': 'Strategy for detecting horizontal table edges.'
    }
}

# Camelot Lattice parameter definitions
CAMELOT_LATTICE_PARAM_DEFS = {
    'line_scale': {
        'type': int,
        'default': 40,
        'range': (15, 50),
        'description': 'Line scale factor for line detection in lattice mode.'
    },
    'line_tol': {
        'type': float,
        'default': 2.0,
        'range': (0.5, 3.0),
        'description': 'Tolerance for line detection in lattice mode.'
    },
    'joint_tol': {
        'type': float,
        'default': 2.0,
        'range': (0.5, 3.0),
        'description': 'Tolerance for joint detection in lattice mode.'
    }
}

# Camelot Stream parameter definitions
CAMELOT_STREAM_PARAM_DEFS = {
    'edge_tol': {
        'type': float,
        'default': 50.0,
        'range': (10.0, 200.0),
        'description': 'Tolerance for edge detection in stream mode.'
    },
    'row_tol': {
        'type': float,
        'default': 2.0,
        'range': (1.0, 10.0),
        'description': 'Tolerance for row detection in stream mode.'
    },
    'column_tol': {
        'type': float,
        'default': 0.0,
        'range': (0.0, 5.0),
        'description': 'Tolerance for column detection in stream mode.'
    }
}


def validate_pdfplumber_params(params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate PDFPlumber parameters
    
    Args:
        params: Parameters to validate
        
    Returns:
        Tuple of (is_valid, error_message, validated_params)
    """
    validated = {}
    errors = []
    
    for key, value in params.items():
        if key not in PDFPLUMBER_PARAM_DEFS:
            errors.append(f"Unknown parameter: {key}")
            continue
        
        param_def = PDFPLUMBER_PARAM_DEFS[key]
        param_type = param_def['type']
        
        # Type check
        try:
            if param_type == int:
                value = int(value)
            elif param_type == float:
                value = float(value)
            elif param_type == str:
                value = str(value)
        except (ValueError, TypeError):
            errors.append(f"Parameter {key} must be of type {param_type.__name__}")
            continue
        
        # Range/options check
        if 'range' in param_def:
            min_val, max_val = param_def['range']
            if value < min_val or value > max_val:
                errors.append(f"Parameter {key} must be in range [{min_val}, {max_val}], got {value}")
                # Clamp to valid range
                value = max(min_val, min(value, max_val))
        elif 'options' in param_def:
            if value not in param_def['options']:
                errors.append(f"Parameter {key} must be one of {param_def['options']}, got {value}")
                # Use default if invalid
                value = param_def['default']
        
        validated[key] = value
    
    if errors:
        return False, "; ".join(errors), validated
    
    return True, None, validated


def validate_camelot_lattice_params(params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate Camelot Lattice parameters
    
    Args:
        params: Parameters to validate
        
    Returns:
        Tuple of (is_valid, error_message, validated_params)
    """
    validated = {}
    errors = []
    
    for key, value in params.items():
        if key == 'flavor':
            validated[key] = value
            continue
            
        if key not in CAMELOT_LATTICE_PARAM_DEFS:
            errors.append(f"Unknown parameter: {key}")
            continue
        
        param_def = CAMELOT_LATTICE_PARAM_DEFS[key]
        param_type = param_def['type']
        
        # Type check
        try:
            if param_type == int:
                value = int(value)
            elif param_type == float:
                value = float(value)
        except (ValueError, TypeError):
            errors.append(f"Parameter {key} must be of type {param_type.__name__}")
            continue
        
        # Range check
        if 'range' in param_def:
            min_val, max_val = param_def['range']
            if value < min_val or value > max_val:
                errors.append(f"Parameter {key} must be in range [{min_val}, {max_val}], got {value}")
                # Clamp to valid range
                value = max(min_val, min(value, max_val))
        
        validated[key] = value
    
    if errors:
        return False, "; ".join(errors), validated
    
    return True, None, validated


def validate_camelot_stream_params(params: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Validate Camelot Stream parameters
    
    Args:
        params: Parameters to validate
        
    Returns:
        Tuple of (is_valid, error_message, validated_params)
    """
    validated = {}
    errors = []
    
    for key, value in params.items():
        if key == 'flavor':
            validated[key] = value
            continue
            
        if key not in CAMELOT_STREAM_PARAM_DEFS:
            errors.append(f"Unknown parameter: {key}")
            continue
        
        param_def = CAMELOT_STREAM_PARAM_DEFS[key]
        param_type = param_def['type']
        
        # Type check
        try:
            if param_type == int:
                value = int(value)
            elif param_type == float:
                value = float(value)
        except (ValueError, TypeError):
            errors.append(f"Parameter {key} must be of type {param_type.__name__}")
            continue
        
        # Range check
        if 'range' in param_def:
            min_val, max_val = param_def['range']
            if value < min_val or value > max_val:
                errors.append(f"Parameter {key} must be in range [{min_val}, {max_val}], got {value}")
                # Clamp to valid range
                value = max(min_val, min(value, max_val))
        
        validated[key] = value
    
    if errors:
        return False, "; ".join(errors), validated
    
    return True, None, validated


def get_default_pdfplumber_params() -> Dict[str, Any]:
    """Get default PDFPlumber parameters"""
    return {key: def_['default'] for key, def_ in PDFPLUMBER_PARAM_DEFS.items()}


def get_default_camelot_lattice_params() -> Dict[str, Any]:
    """Get default Camelot Lattice parameters"""
    params = {key: def_['default'] for key, def_ in CAMELOT_LATTICE_PARAM_DEFS.items()}
    # 必须包含flavor参数，确保使用正确的模式
    params['flavor'] = 'lattice'
    return params


def get_default_camelot_stream_params() -> Dict[str, Any]:
    """Get default Camelot Stream parameters"""
    params = {key: def_['default'] for key, def_ in CAMELOT_STREAM_PARAM_DEFS.items()}
    # 必须包含flavor参数，否则Camelot可能默认使用lattice模式
    params['flavor'] = 'stream'
    return params

