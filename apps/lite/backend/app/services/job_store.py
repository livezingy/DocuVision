"""In-memory and on-disk job store for Lite async tasks."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.schemas.lite_result import JobStatus, LiteJobProgress


class JobStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict[str, Any]] = {}

    def create(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        record = {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "progress": LiteJobProgress().model_dump(),
            "metadata": metadata or {},
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = record
        (self.base_dir / job_id).mkdir(parents=True, exist_ok=True)
        return job_id

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job.update(fields)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()

    def save_result(self, job_id: str, result: Dict[str, Any]) -> None:
        self.update(job_id, status=JobStatus.SUCCEEDED.value, result=result)
        path = self.base_dir / job_id / "result.json"
        path.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")

    def save_upload(self, job_id: str, filename: str, content: bytes) -> Path:
        safe_name = Path(filename).name
        path = self.base_dir / job_id / safe_name
        path.write_bytes(content)
        return path

    def delete(self, job_id: str) -> bool:
        with self._lock:
            existed = job_id in self._jobs
            self._jobs.pop(job_id, None)
        job_dir = self.base_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return existed

    def export_dir(self, job_id: str) -> Path:
        path = self.base_dir / job_id / "exports"
        path.mkdir(parents=True, exist_ok=True)
        return path


job_store = JobStore(Path(settings.JOB_DATA_DIR))
