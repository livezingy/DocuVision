"""Google Sheets direct-write for batch exports (R-003/P-042 T1+T3, AC2).

Binds to ``batch.completed``: the routers layer composes this service into the
batch ``on_complete`` closure (``routers/batch.py`` — the same injection
pattern that dissolved the batch->infra frozen edge; routers may import any
service), so the whole batch's mapping-result rows land in the target
worksheet once the batch finishes, each row carrying ``task_id``.

Idempotency (AC2): rows are upserted per ``task_id`` — when the same task
re-runs (``retry_failed_tasks`` -> resume -> ``batch.completed`` fires again),
that task's existing rows are replaced in place and never duplicated.
``BatchTask.task_id`` is a uuid4 (``batch_service.py:125``), so rewrites from
different batches sharing a worksheet can never collide.

Credentials: injected as a parameter (service-account JSON *path* only). The
real value lives in the operator's local ``.env``
(``GOOGLE_SERVICE_ACCOUNT_FILE`` / ``GOOGLE_APPLICATION_CREDENTIALS`` alias)
and never enters the repo, logs, return values or exception text (kernel red
line): client/wrapping errors are re-raised as sanitized ``RuntimeError`` with
the original context dropped (``from None``). ``gspread`` is imported lazily
so the services layer imports clean without it. The gspread client gets an
explicit requests timeout (``HTTPClient.set_timeout``; 6.2.1 defaults to
``None`` = unbounded) so a hung endpoint cannot stall the calling thread —
the dispatch runs off the event loop via ``asyncio.to_thread``
(``routers/batch.py``), where an unbounded hang would still leak a worker
thread per batch.

Row source: the mapping result (``mapped_table_rows``, T2 stamp honored) —
the same rows the MappedRows xlsx face carries, with identity columns
``batch_id`` / ``task_id`` / ``file_name`` prepended, so the T4
same-source-same-value comparison lines up field by field.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from app.services.batch_service import BatchJob, BatchTask, TaskStatus

__all__ = ["build_sheets_rows", "export_batch_to_sheets"]

# Identity columns always first; field columns follow in mapping-result order.
_IDENTITY_COLUMNS = ("batch_id", "task_id", "file_name")
_DEFAULT_WORKSHEET = "MappedRows"

# Per-call HTTPS cap (connect, read) seconds, via HTTPClient.set_timeout.
# gspread 6.2.1 defaults to None = requests' unbounded wait; without this a
# hung endpoint leaks one blocked thread per batch (review round 1).
_GSPREAD_REQUEST_TIMEOUT_SECONDS = (10, 60)

# Test seam: builds the gspread client from the credential file path.
ClientBuilder = Callable[[str], Any]


def build_sheets_rows(batch: BatchJob) -> Tuple[List[str], List[Dict[str, str]]]:
    """(header, rows) for the Sheets export from the batch's mapping result.

    Column order: identity columns first, then the mapping-result field
    columns (``mapped_table_fields`` stamp wins; legacy first-seen order
    otherwise — identical to the MappedRows xlsx face). Completed tasks only;
    empty when the batch produced no mapping rows.
    """
    # same-domain family reuse (batch): the export face's column derivation.
    from app.services.batch_export_service import _mapped_rows_columns

    plain: List[Dict[str, Any]] = []
    keyed: List[Tuple[BatchTask, Dict[str, Any]]] = []
    for task in batch.tasks:
        if task.status != TaskStatus.COMPLETED or not isinstance(task.result, dict):
            continue
        mapped = task.result.get("mapped_table_rows")
        if not isinstance(mapped, list):
            continue
        for entry in mapped:
            if isinstance(entry, dict):
                row = dict(entry)
                row["file_name"] = task.file_name
                plain.append(row)
                keyed.append((task, row))

    if not plain:
        return [], []
    field_columns = [c for c in _mapped_rows_columns(batch, plain) if c != "file_name"]
    header: List[str] = list(_IDENTITY_COLUMNS) + field_columns

    rows: List[Dict[str, str]] = []
    for task, row in keyed:
        out: Dict[str, str] = {
            "batch_id": batch.batch_id,
            "task_id": task.task_id,
            "file_name": task.file_name,
        }
        for col in field_columns:
            value = row.get(col, "")
            out[col] = "" if value is None else str(value)
        rows.append(out)
    return header, rows


def _open_client(builder: ClientBuilder, credentials_file: str) -> Any:
    """Build the gspread client; failures are sanitized so credential-file
    paths / contents can never surface in error text."""
    try:
        return builder(credentials_file)
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001 — sanitized on purpose (credential red line)
        raise RuntimeError(
            f"sheets export failed: gspread client error ({type(exc).__name__})"
        ) from None


def _ensure_worksheet(
    spreadsheet: Any,
    worksheet_name: str,
    header: List[str],
) -> Tuple[Any, bool]:
    """Return (worksheet, created). Creates a generous grid when missing."""
    import gspread

    try:
        return spreadsheet.worksheet(worksheet_name), False
    except gspread.WorksheetNotFound:
        pass
    except Exception as exc:  # noqa: BLE001 — sanitized (credential red line)
        raise RuntimeError(
            f"sheets export failed: worksheet lookup error ({type(exc).__name__})"
        ) from None
    try:
        created = spreadsheet.add_worksheet(
            worksheet_name, rows=1000, cols=max(len(header) + 8, 26)
        )
    except Exception as exc:  # noqa: BLE001 — sanitized
        raise RuntimeError(
            f"sheets export failed: worksheet create error ({type(exc).__name__})"
        ) from None
    return created, True


def _upsert_rows(
    worksheet: Any,
    header: List[str],
    rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Task-scoped upsert (AC2): existing rows whose ``task_id`` cell matches
    a task of this export are replaced (bottom-up deletion), the fresh rows
    are appended. Fresh/empty sheets get header+rows in one write. A foreign
    header fails closed — never guess, never clobber."""
    matrix = [[row[c] for c in header] for row in rows]
    existing = worksheet.get_all_values()
    existing_header = [str(c).strip() for c in existing[0]] if existing else []
    if not any(existing_header):
        worksheet.update(values=[header] + matrix, range_name="A1")
        return {"appended": len(matrix), "replaced_tasks": 0, "created_header": True}

    if existing_header[: len(header)] != header:
        raise RuntimeError(
            "sheets export failed: worksheet header mismatch — align the "
            "sheet with the batch mapping template or use a fresh worksheet"
        )

    key_index = header.index("task_id")
    current_task_ids = {row["task_id"] for row in rows}
    stale: List[int] = []  # 1-based sheet rows; data starts at 2
    for sheet_index, sheet_row in enumerate(existing[1:], start=2):
        cell = (
            str(sheet_row[key_index]).strip()
            if key_index < len(sheet_row)
            else ""
        )
        if cell in current_task_ids:
            stale.append(sheet_index)
    for sheet_index in sorted(stale, reverse=True):
        worksheet.delete_rows(sheet_index)
    worksheet.append_rows(matrix)
    return {
        "appended": len(matrix),
        "replaced_tasks": len(current_task_ids),
        "created_header": False,
    }


def export_batch_to_sheets(
    batch: BatchJob,
    *,
    credentials_file: str,
    spreadsheet_id: str,
    worksheet_name: str = _DEFAULT_WORKSHEET,
    client_builder: Optional[ClientBuilder] = None,
) -> Dict[str, Any]:
    """Upsert the batch's mapping-result rows into the target worksheet.

    Credentials travel by parameter only and are never logged / returned /
    embedded in errors. Batches without mapping rows are a no-op (summary
    carries ``skipped``). Returns a summary dict with no credential material.
    """
    if not str(credentials_file or "").strip():
        raise RuntimeError("sheets export failed: no service-account credentials configured")
    if not str(spreadsheet_id or "").strip():
        raise RuntimeError("sheets export failed: no target spreadsheet configured")

    header, rows = build_sheets_rows(batch)
    if not header:
        return {
            "worksheet": worksheet_name,
            "appended": 0,
            "replaced_tasks": 0,
            "skipped": "no mapping rows",
        }

    builder: ClientBuilder = client_builder or _build_client
    client = _open_client(builder, credentials_file)
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet, created = _ensure_worksheet(spreadsheet, worksheet_name, header)
    summary = _upsert_rows(worksheet, header, rows)
    summary.update({"worksheet": worksheet_name, "created_worksheet": created})
    return summary


def _build_client(credentials_file: str) -> Any:
    """Lazily import gspread and build the service-account client with an
    explicit per-call timeout (real path; tests monkeypatch this seam — no
    network in unit tests)."""
    import gspread

    client = gspread.service_account(filename=credentials_file)
    client.http_client.set_timeout(_GSPREAD_REQUEST_TIMEOUT_SECONDS)
    return client
