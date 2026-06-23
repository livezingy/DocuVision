"""In-memory preview sessions with on-disk uploads for Lite document preview."""

from __future__ import annotations

import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.preview_renderer import resolve_page_count


class PreviewStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_from_upload(self, filename: str, content: bytes) -> tuple[str, int]:
        preview_id = str(uuid.uuid4())
        safe_name = Path(filename).name
        session_dir = self.base_dir / preview_id
        session_dir.mkdir(parents=True, exist_ok=True)
        file_path = session_dir / safe_name
        file_path.write_bytes(content)
        page_count = resolve_page_count(file_path)
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "preview_id": preview_id,
            "file_path": str(file_path),
            "file_name": safe_name,
            "page_count": page_count,
            "created_at": now,
        }
        with self._lock:
            self._sessions[preview_id] = record
        return preview_id, page_count

    def get(self, preview_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._sessions.get(preview_id)

    def delete(self, preview_id: str) -> bool:
        with self._lock:
            existed = preview_id in self._sessions
            self._sessions.pop(preview_id, None)
        session_dir = self.base_dir / preview_id
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        return existed


preview_store = PreviewStore(Path(settings.PREVIEW_DATA_DIR))
