"""Queue persistence layer.

A thin, protocol-based abstraction over a SQLite store used by
``BatchService``, ``HitlReviewQueue``, and ``AnalyzeJobStore`` to survive
process restarts.

Design notes:
- Single-file SQLite (WAL mode) with three tables: ``batch_jobs``,
  ``hitl_reviews``, and ``analyze_jobs``.
- Nested fields (``options``/``tasks``/``payload``/``edited_fields``/``quality``)
  are stored as JSON text columns; the store maps dict fields <-> table
  columns via an internal ``_TABLE_SCHEMA`` registry.
- Writes are serialized with a ``threading.Lock`` to avoid ``database is
  locked`` under concurrent task-completion callbacks. Callers that run in an
  async context should use the ``asyncio.to_thread`` wrapper at the service
  layer (see ``BatchService._persist_async`` / ``HitlReviewQueue._persist_async``
  / ``AnalyzeJobStore._persist_async``) to avoid blocking the event loop.
- ``CREATE TABLE IF NOT EXISTS`` on init makes first start idempotent; no
  Alembic migration is required.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple


class QueueStore(Protocol):
    """Minimal key-value-ish queue persistence protocol."""

    def save(self, table: str, key: str, document: dict) -> None: ...

    def load(self, table: str, key: str) -> Optional[dict]: ...

    def load_all(self, table: str) -> List[dict]: ...

    def delete(self, table: str, key: str) -> None: ...


# Per-table column registry. The first column is the primary key.
# Nested/variable-shape fields are stored as JSON text.
_TABLE_SCHEMA: Dict[str, Tuple[str, ...]] = {
    "batch_jobs": (
        "batch_id",
        "name",
        "status",
        "options",
        "tasks",
        "total_tasks",
        "completed_tasks",
        "failed_tasks",
        "created_at",
        "started_at",
        "completed_at",
    ),
    "hitl_reviews": (
        "review_id",
        "task_id",
        "file_name",
        "reason",
        "payload",
        "edited_fields",
        "status",
        "created_at",
        "resolved_at",
    ),
    "analyze_jobs": (
        "task_id",
        "status",
        "file_name",
        "file_path",
        "created_at",
        "completed_at",
        "options",
        "result_path",
        "quality",
    ),
}

# Columns stored as JSON text (rather than plain scalars).
_JSON_COLUMNS: Dict[str, set] = {
    "batch_jobs": {"options", "tasks"},
    "hitl_reviews": {"payload", "edited_fields"},
    "analyze_jobs": {"options", "quality"},
}

# DDL for each table. The first column is the primary key.
_DDL: Dict[str, str] = {
    "batch_jobs": (
        "CREATE TABLE IF NOT EXISTS batch_jobs (\n"
        "  batch_id        TEXT PRIMARY KEY,\n"
        "  name            TEXT NOT NULL,\n"
        "  status          TEXT NOT NULL,\n"
        "  options         TEXT NOT NULL DEFAULT '{}',\n"
        "  tasks           TEXT NOT NULL DEFAULT '[]',\n"
        "  total_tasks     INTEGER NOT NULL DEFAULT 0,\n"
        "  completed_tasks INTEGER NOT NULL DEFAULT 0,\n"
        "  failed_tasks    INTEGER NOT NULL DEFAULT 0,\n"
        "  created_at      TEXT NOT NULL,\n"
        "  started_at      TEXT,\n"
        "  completed_at    TEXT\n"
        ")"
    ),
    "hitl_reviews": (
        "CREATE TABLE IF NOT EXISTS hitl_reviews (\n"
        "  review_id     TEXT PRIMARY KEY,\n"
        "  task_id       TEXT NOT NULL,\n"
        "  file_name     TEXT NOT NULL,\n"
        "  reason        TEXT NOT NULL,\n"
        "  payload       TEXT NOT NULL DEFAULT '{}',\n"
        "  edited_fields TEXT,\n"
        "  status        TEXT NOT NULL DEFAULT 'pending',\n"
        "  created_at    TEXT NOT NULL,\n"
        "  resolved_at   TEXT\n"
        ")"
    ),
    "analyze_jobs": (
        "CREATE TABLE IF NOT EXISTS analyze_jobs (\n"
        "  task_id       TEXT PRIMARY KEY,\n"
        "  status        TEXT NOT NULL,\n"
        "  file_name     TEXT NOT NULL DEFAULT '',\n"
        "  file_path     TEXT NOT NULL DEFAULT '',\n"
        "  created_at    TEXT NOT NULL,\n"
        "  completed_at  TEXT,\n"
        "  options       TEXT NOT NULL DEFAULT '{}',\n"
        "  result_path   TEXT,\n"
        "  quality       TEXT\n"
        ")"
    ),
}


class SqliteQueueStore:
    """Single-file SQLite backed implementation of ``QueueStore``.

    Uses WAL journal mode for better read/write concurrency and a
    ``threading.Lock`` to serialize writes from concurrent task callbacks.
    A single connection is reused for the lifetime of the store; sqlite3
    connections are thread-local by default, so we open with
    ``check_same_thread=False`` and guard all access with the lock.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage txns explicitly
        )
        self._conn.row_factory = sqlite3.Row
        self._init_pragmas_and_tables()

    def _init_pragmas_and_tables(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            for ddl in _DDL.values():
                self._conn.execute(ddl)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _pk_column(table: str) -> str:
        return _TABLE_SCHEMA[table][0]

    @staticmethod
    def _encode(table: str, document: dict) -> dict:
        """Encode dict fields into sqlite-storable values (JSON for nested)."""
        json_cols = _JSON_COLUMNS.get(table, set())
        out: Dict[str, Any] = {}
        for col in _TABLE_SCHEMA[table]:
            if col not in document:
                continue
            value = document[col]
            if col in json_cols:
                out[col] = json.dumps(value, ensure_ascii=False, default=str)
            else:
                out[col] = value
        return out

    @staticmethod
    def _decode(table: str, row: sqlite3.Row) -> dict:
        """Decode a sqlite Row back into a dict (JSON for nested)."""
        json_cols = _JSON_COLUMNS.get(table, set())
        out: Dict[str, Any] = {}
        for col in _TABLE_SCHEMA[table]:
            if col not in row.keys():
                continue
            value = row[col]
            if col in json_cols:
                if value is None:
                    out[col] = None
                elif value == "":
                    out[col] = {} if col in {"options", "payload", "quality"} else []
                else:
                    try:
                        out[col] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        out[col] = {} if col in {"options", "payload", "quality"} else []
            else:
                out[col] = value
        return out

    # ------------------------------------------------------------------
    # QueueStore protocol
    # ------------------------------------------------------------------
    def save(self, table: str, key: str, document: dict) -> None:
        if table not in _TABLE_SCHEMA:
            raise ValueError(f"Unknown table: {table}")
        cols = _TABLE_SCHEMA[table]
        pk = cols[0]
        encoded = self._encode(table, document)
        # Ensure pk is set
        encoded[pk] = key
        col_names = list(encoded.keys())
        placeholders = ",".join("?" for _ in col_names)
        col_list = ",".join(col_names)
        update_list = ",".join(f"{c}=excluded.{c}" for c in col_names if c != pk)
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
            f" ON CONFLICT({pk}) DO UPDATE SET {update_list}"
        )
        params = tuple(encoded[c] for c in col_names)
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def load(self, table: str, key: str) -> Optional[dict]:
        if table not in _TABLE_SCHEMA:
            raise ValueError(f"Unknown table: {table}")
        pk = self._pk_column(table)
        with self._lock:
            cur = self._conn.execute(f"SELECT * FROM {table} WHERE {pk}=?", (key,))
            row = cur.fetchone()
        return self._decode(table, row) if row is not None else None

    def load_all(self, table: str) -> List[dict]:
        if table not in _TABLE_SCHEMA:
            raise ValueError(f"Unknown table: {table}")
        with self._lock:
            cur = self._conn.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
        return [self._decode(table, r) for r in rows]

    def delete(self, table: str, key: str) -> None:
        if table not in _TABLE_SCHEMA:
            raise ValueError(f"Unknown table: {table}")
        pk = self._pk_column(table)
        with self._lock:
            self._conn.execute(f"DELETE FROM {table} WHERE {pk}=?", (key,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
