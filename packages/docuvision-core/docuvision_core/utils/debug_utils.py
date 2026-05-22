# core/utils/debug_utils.py
"""debug utils module."""
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Comment.
# Comment.
DEBUG_LOG_PATH = Path(__file__).parent.parent.parent / ".cursor" / "debug.log"


def write_debug_log(
    location: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    hypothesis_id: Optional[str] = None,
    session_id: str = "debug-session",
    run_id: str = "run1"
) -> None:
    """
    
    
    Args:
    
    Example:
        >>> write_debug_log(
        ...     location="table_processor.py:147",
        ...     message="process_pdf_page entry",
        ...     data={"method": "pdfplumber", "flavor": "lines"},
        ...     hypothesis_id="A"
        ... )
        
        >>> write_debug_log(
        ...     location="table_params_calculator.py:60",
        ...     message="line_tolerance calculated",
        ...     data={"line_tolerance": 5.2, "is_valid": True},
        ...     hypothesis_id="B",
        ...     run_id="post-fix"
        ... )
    
    Note:
    """
    try:
        log_entry = {
            "timestamp": int(time.time() * 1000),
            "location": location,
            "message": message,
            "data": data or {},
            "sessionId": session_id,
            "runId": run_id,
        }
        
        # Comment.
        if hypothesis_id:
            log_entry["hypothesisId"] = hypothesis_id
        
        # Comment.
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Comment.
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    except Exception:
        # Comment.
        # Comment.
        pass


def clear_debug_log() -> bool:
    """Docstring."""
    try:
        if DEBUG_LOG_PATH.exists():
            DEBUG_LOG_PATH.unlink()
        return True
    except Exception:
        return False


def read_debug_log() -> list:
    """Docstring."""
    try:
        if not DEBUG_LOG_PATH.exists():
            return []
        
        logs = []
        with open(DEBUG_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        log_entry = json.loads(line)
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        # Comment.
                        continue
        
        return logs
    except Exception:
        return []

