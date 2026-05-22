# core/utils/debug_utils.py
"""
Debug 模式工具函数
用于统一管理调试日志记录

使用方法！
    from docuvision_core.utils.debug_utils import write_debug_log
    
    write_debug_log(
        location="file.py:42",
        message="函数执行",
        data={"param1": value1, "param2": value2},
        hypothesis_id="A"
    )
"""
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Debug 日志文件路径（与系统配置一致）
# 路径：项目根目录/.cursor/debug.log
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
    写入调试日志（NDJSON 格式！
    
    日志会被追加分.cursor/debug.log 文件中，格式一NDJSON（每行一一JSON 对象！
    
    Args:
        location: 代码位置，格开"file.py:line"，例如"table_processor.py:147"
        message: 日志消息，简要描述当前状怀
        data: 附加数据字典，包含需要记录的关键变量倀
        hypothesis_id: 假设ID（可选），用于关联到特定的调试假设，例如 "A", "B", "C"
        session_id: 会话ID，默认为 "debug-session"
        run_id: 运行ID，用于区分不同的运行，例如"run1", "post-fix"
    
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
        - 函数会静默失败，不会抛出异常，避免影响主流程
        - 确保 .cursor 目录存在（会自动创建！
        - 日志格式符合 NDJSON 标准，便于后续分枀
    """
    try:
        log_entry = {
            "timestamp": int(time.time() * 1000),  # 毫秒时间成
            "location": location,
            "message": message,
            "data": data or {},
            "sessionId": session_id,
            "runId": run_id,
        }
        
        # 如果提供了假设ID，添加到日志一
        if hypothesis_id:
            log_entry["hypothesisId"] = hypothesis_id
        
        # 确保目录存在
        DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # 追加写入 NDJSON（每行一一JSON 对象！
        with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
    except Exception:
        # 静默失败，避免影响主流程
        # 在生产环境中，可以考虑记录到标准日心
        pass


def clear_debug_log() -> bool:
    """
    清空调试日志文件
    
    Returns:
        bool: 是否成功清空
    
    Note:
        通常在每次新的调试运行前调用，确保日志文件干净
    """
    try:
        if DEBUG_LOG_PATH.exists():
            DEBUG_LOG_PATH.unlink()
        return True
    except Exception:
        return False


def read_debug_log() -> list:
    """
    读取调试日志文件
    
    Returns:
        list: 日志条目列表，每个元素是一个字公
    
    Note:
        用于分析日志，评估假讀
    """
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
                        # 跳过无效的JSON 行
                        continue
        
        return logs
    except Exception:
        return []

