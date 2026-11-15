"""Unit tests for batch CSV export helpers."""

from datetime import datetime

from app.services.batch_export_service import build_kie_csv_rows, render_csv
from app.services.batch_service import BatchJob, BatchTask, BatchStatus, TaskStatus


def _sample_batch() -> BatchJob:
    batch = BatchJob(
        batch_id="test-batch",
        name="demo",
        status=BatchStatus.COMPLETED,
        options={"document_type": "invoice", "enable_kie": True},
        created_at=datetime.now(),
    )
    batch.total_tasks = 2
    t1 = BatchTask(task_id="t1", file_path="/a.png", file_name="a.png", status=TaskStatus.COMPLETED)
    t1.result = {
        "kie_fields": {"invoice_number": "INV-1", "total": "10"},
        "quality": {"kie_stage": "completed", "kie_production_hit": True, "kie_fields_count": 2},
    }
    t2 = BatchTask(task_id="t2", file_path="/b.png", file_name="b.png", status=TaskStatus.FAILED)
    t2.error = "boom"
    batch.tasks = [t1, t2]
    batch.completed_tasks = 1
    batch.failed_tasks = 1
    return batch


def test_build_kie_csv_has_core_columns() -> None:
    batch = _sample_batch()
    header, rows = build_kie_csv_rows(batch)
    assert "file_name" in header
    assert "kie_production_hit" in header
    assert len(rows) == 2
    csv_text = render_csv(header, rows)
    assert "INV-1" in csv_text
    assert "boom" in csv_text


def test_build_kie_csv_validation_passed_only() -> None:
    batch = _sample_batch()
    batch.tasks[0].result["kie_validation"] = {"validation_passed": False}
    header, rows = build_kie_csv_rows(batch, options={"validation_passed_only": True})
    assert len(rows) == 0

    batch.tasks[0].result["kie_validation"] = {"validation_passed": True}
    header, rows = build_kie_csv_rows(batch, options={"validation_passed_only": True})
    assert len(rows) == 1


def test_build_batch_xlsx_bytes() -> None:
    from app.services.batch_export_service import build_batch_xlsx_bytes

    batch = _sample_batch()
    batch.tasks[0].result["tables"] = [
        {"data": [["ColA", "ColB"], ["1", "2"]]},
    ]
    payload = build_batch_xlsx_bytes(batch, mode="all")
    assert isinstance(payload, bytes)
    assert len(payload) > 100
    assert payload[:2] == b"PK"


def test_build_batch_xlsx_includes_mapped_rows_sheet() -> None:
    from app.services.batch_export_service import build_batch_xlsx_bytes
    import pandas as pd
    import io

    batch = _sample_batch()
    batch.tasks[0].result["mapped_table_rows"] = [
        {"transaction_date": "2024-01-01", "amount": "1.00", "file_name": "a.png"},
    ]
    payload = build_batch_xlsx_bytes(batch, mode="all")
    sheets = pd.ExcelFile(io.BytesIO(payload)).sheet_names
    assert "MappedRows" in sheets


# ---------------------------------------------------------------------------
# R-003/P-042 T2 (AC1 backend half): customer schema column mapping —
# config solidified once (template store / inline options) -> batch effective
# -> MappedRows export columns driven by the mapping result. All fixture
# fields are fictional; nothing is written into the tracked template dir.

_PO_SCHEMA = {
    "document_type": "custom",
    "name": "po_line_schema",
    "description": "PO line mapping (fictional fixture fields)",
    "fields": [
        {"name": "po_number", "type": "string", "aliases": ["PO #", "PO Number"]},
        {"name": "quantity", "aliases": ["Qty"]},
        {"name": "unit_price", "aliases": ["Unit Price"]},
        {"name": "line_total", "aliases": ["Total"]},
    ],
}

_PO_TABLE = {
    "data": [
        ["PO #", "Qty", "Unit Price", "Total"],
        ["PO-1001", "2", "10.50", "21.00"],
        ["PO-1002", "", "5.00", "5.00"],
    ],
    "page": 1,
}


def _solidify_template(monkeypatch, tmp_path, template_id="po_line_schema"):
    """Persist a fictional customer schema through the existing template store
    (monkeypatched to tmp_path — the tracked YAML dir is never written)."""
    from app.services.kie import schema_templates

    monkeypatch.setattr(schema_templates, "_TEMPLATE_DIR", tmp_path)
    monkeypatch.setattr(schema_templates, "_runtime_templates", {})
    schema_templates.save_template(template_id, dict(_PO_SCHEMA))
    # drop the in-process copy so load_template re-reads the persisted YAML
    schema_templates._runtime_templates.pop(template_id, None)
    return template_id


def test_schema_mapping_config_survives_template_store_roundtrip(tmp_path, monkeypatch) -> None:
    import yaml

    from app.services.kie import schema_templates
    from app.services.kie.schema_mapping import build_mapping_config

    template_id = _solidify_template(monkeypatch, tmp_path)

    persisted = yaml.safe_load((tmp_path / f"{template_id}.yaml").read_text(encoding="utf-8"))
    assert persisted["name"] == "po_line_schema"
    assert schema_templates.load_template(template_id) == persisted

    config = build_mapping_config(schema_templates.load_template(template_id), template_id)
    assert config is not None
    assert config["output_fields"] == ["po_number", "quantity", "unit_price", "line_total"]
    assert config["aliases"]["po_number"] == ("po_number", "PO #", "PO Number")


def test_schema_mapping_resolved_from_batch_options_maps_tables(tmp_path, monkeypatch) -> None:
    from app.services.kie.schema_mapping import apply_schema_mapping, resolve_mapping_config

    _solidify_template(monkeypatch, tmp_path)
    options = {"table_template": "po_line_schema"}

    config = resolve_mapping_config(options)
    assert config is not None
    assert config["template_id"] == "po_line_schema"

    mapped = apply_schema_mapping([dict(_PO_TABLE)], config)
    assert len(mapped) == 2
    assert mapped[0]["po_number"] == "PO-1001"
    assert mapped[0]["unit_price"] == "10.50"
    assert mapped[0]["template"] == "po_line_schema"
    for field in config["output_fields"]:
        assert field in mapped[0]
        assert field in mapped[1]
    # empty cell still yields the configured column (schema order kept)
    assert mapped[1]["quantity"] == ""


def test_schema_mapping_inline_custom_schema_resolves() -> None:
    import json

    from app.services.kie.schema_mapping import resolve_mapping_config

    config = resolve_mapping_config(
        {"kie_custom_schema": {"fields": [{"name": "po_number", "aliases": ["PO #"]}]}}
    )
    assert config is not None
    assert config["output_fields"] == ["po_number"]

    config = resolve_mapping_config(
        {"kie_custom_schema": json.dumps({"fields": [{"name": "invoice_total"}]})}
    )
    assert config is not None
    assert config["output_fields"] == ["invoice_total"]


def test_schema_mapping_fail_closed_and_custom_doc_gating(tmp_path, monkeypatch) -> None:
    from app.services.kie.schema_mapping import apply_schema_mapping, resolve_mapping_config

    assert resolve_mapping_config({}) is None
    assert resolve_mapping_config({"table_template": "no_such_template"}) is None
    assert resolve_mapping_config({"kie_custom_schema": "not-json"}) is None
    assert resolve_mapping_config({"kie_custom_schema": {"fields": []}}) is None

    _solidify_template(monkeypatch, tmp_path)
    # custom-document fallback keys only fire for document_type custom/template
    assert resolve_mapping_config({"template_id": "po_line_schema"}) is None
    gated = resolve_mapping_config({"template_id": "po_line_schema", "document_type": "custom"})
    assert gated is not None

    # no alias hit -> no rows (never fabricated columns)
    config = resolve_mapping_config({"table_template": "po_line_schema"})
    unmapped_table = {"data": [["A", "B"], ["1", "2"]]}
    assert apply_schema_mapping([unmapped_table], config) == []


def test_table_step_custom_schema_one_config_whole_batch(tmp_path, monkeypatch) -> None:
    """One template id on the batch options -> every task maps and stamps the
    same schema field order (wired through the real table_step)."""
    import asyncio

    from app.orchestration.steps.extraction import table_step

    def fake_extract_with_meta(file_path, **kwargs):
        return {"tables": [dict(_PO_TABLE)], "meta": {"engine_used": "mock"}}

    async def call_maybe_async(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.services = {
                "table_service": type(
                    "T", (), {"extract_with_meta": staticmethod(fake_extract_with_meta)}
                )(),
            }

        def ensure_not_cancelled(self, ctx):
            return None

        async def update_progress(self, ctx, pct, msg):
            return None

        async def call_maybe_async(self, func, *args, **kwargs):
            return await call_maybe_async(func, *args, **kwargs)

    _solidify_template(monkeypatch, tmp_path)
    options = {"enable_table": True, "table_template": "po_line_schema"}

    results = []
    for file_name in ("a.png", "b.png"):
        ctx = {
            "task_id": f"t-{file_name}",
            "task": {"file_name": file_name},
            "file_path": str(tmp_path / file_name),
            "options": dict(options),
            "result": {"document_info": {}},
            "orchestrator": _FakeOrchestrator(),
        }
        asyncio.run(table_step(ctx))
        results.append(ctx["result"])

    for result in results:
        assert result["table_template"] == "po_line_schema"
        assert result["mapped_table_fields"] == [
            "po_number",
            "quantity",
            "unit_price",
            "line_total",
        ]
        rows = result["mapped_table_rows"]
        assert len(rows) == 2
        assert rows[0]["po_number"] == "PO-1001"
    # one config for the whole batch — identical stamped field order per task
    assert results[0]["mapped_table_fields"] == results[1]["mapped_table_fields"]


def test_build_batch_xlsx_mapped_rows_columns_driven_by_schema_config() -> None:
    import io

    import pandas as pd

    from app.services.batch_export_service import build_batch_xlsx_bytes

    batch = _sample_batch()
    fields = ["po_number", "quantity", "unit_price", "line_total"]
    batch.tasks[0].result["mapped_table_fields"] = fields
    batch.tasks[0].result["mapped_table_rows"] = [
        {
            "template": "po_line_schema",
            "source_table_index": 0,
            "page": 1,
            "row_index": 0,
            "po_number": "PO-1001",
            "quantity": "2",
            "unit_price": "10.50",
            "line_total": "21.00",
        },
    ]
    payload = build_batch_xlsx_bytes(batch, mode="all")
    sheet = pd.ExcelFile(io.BytesIO(payload)).parse("MappedRows")
    columns = sheet.columns.tolist()
    assert columns[: len(fields) + 1] == ["file_name"] + fields
    assert sheet.iloc[0]["po_number"] == "PO-1001"
    assert sheet.iloc[0]["file_name"] == "a.png"


def test_build_batch_xlsx_mapped_rows_legacy_order_without_stamp() -> None:
    import io

    import pandas as pd

    from app.services.batch_export_service import build_batch_xlsx_bytes

    batch = _sample_batch()
    batch.tasks[0].result["mapped_table_rows"] = [
        {"transaction_date": "2024-01-01", "amount": "1.00", "file_name": "a.png"},
    ]
    payload = build_batch_xlsx_bytes(batch, mode="all")
    sheet = pd.ExcelFile(io.BytesIO(payload)).parse("MappedRows")
    # legacy first-seen key order is kept when no schema fields are stamped
    assert sheet.columns.tolist() == ["transaction_date", "amount", "file_name"]


# ---------------------------------------------------------------------------
# R-003/P-042 T1+T3 (AC2): Google Sheets direct write — gspread import level,
# batch.completed binding, task_id rows, idempotent per-task upsert. All
# credentials/ids below are fictional; the gspread client is faked via the
# service's monkeypatch seam (no network, no real credential material).

_FAKE_CREDENTIALS_FILE = "C:/fake-credentials/nonexistent-service-account.json"
_FAKE_SPREADSHEET_ID = "fake-spreadsheet-id-123"


def test_gspread_import_level_and_pinned_version() -> None:
    import gspread

    assert gspread.__version__ == "6.2.1"
    # the seams the service relies on exist in the pinned API
    assert hasattr(gspread, "WorksheetNotFound")
    assert hasattr(gspread.service_account, "__call__")
    # 6.2.1 has no constructor timeout parameter — the sanctioned seam is
    # HTTPClient.set_timeout (review round 1: requests defaults to unbounded)
    assert hasattr(gspread.HTTPClient, "set_timeout")


def test_build_client_sets_explicit_request_timeout(monkeypatch) -> None:
    """The gspread client must never run with the default unbounded timeout:
    a hung endpoint would block the asyncio.to_thread worker indefinitely."""
    import gspread

    from app.services import sheets_export_service

    applied = []

    class _FakeHttpClient:
        def set_timeout(self, value):
            applied.append(value)

    class _FakeClient:
        def __init__(self):
            self.http_client = _FakeHttpClient()

    monkeypatch.setattr(gspread, "service_account", lambda filename: _FakeClient())
    sheets_export_service._build_client("C:/fake/credentials.json")
    assert applied == [sheets_export_service._GSPREAD_REQUEST_TIMEOUT_SECONDS]


def _sheets_batch() -> BatchJob:
    """Two completed tasks carrying stamped mapping rows (T2 stamp honored)."""
    fields = ["po_number", "quantity", "unit_price", "line_total"]

    def _mapped_row(row_index: int, po_number: str, quantity: str, unit_price: str, line_total: str):
        return {
            "template": "po_line_schema",
            "source_table_index": 0,
            "page": 1,
            "row_index": row_index,
            "po_number": po_number,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        }

    batch = BatchJob(
        batch_id="sheet-batch",
        name="sheets-demo",
        status=BatchStatus.COMPLETED,
        options={"table_template": "po_line_schema"},
        created_at=datetime.now(),
    )
    batch.total_tasks = 2
    t1 = BatchTask(
        task_id="sheet-task-1", file_path="/a.png", file_name="a.png", status=TaskStatus.COMPLETED
    )
    t1.result = {
        "mapped_table_fields": fields,
        "mapped_table_rows": [
            _mapped_row(0, "PO-1001", "2", "10.50", "21.00"),
            _mapped_row(1, "PO-1002", "", "5.00", "5.00"),
        ],
    }
    t2 = BatchTask(
        task_id="sheet-task-2", file_path="/b.png", file_name="b.png", status=TaskStatus.COMPLETED
    )
    t2.result = {
        "mapped_table_fields": fields,
        "mapped_table_rows": [_mapped_row(0, "PO-1003", "1", "7.25", "7.25")],
    }
    batch.tasks = [t1, t2]
    batch.completed_tasks = 2
    batch.failed_tasks = 0
    return batch


class _FakeWorksheet:
    """In-memory gspread worksheet double (snapshot read + mutating writes)."""

    def __init__(self) -> None:
        self.rows: list = []
        self.calls: list = []

    def get_all_values(self):
        self.calls.append("get_all_values")
        return [list(r) for r in self.rows]

    def update(self, values, range_name=None, **kwargs):
        self.calls.append(f"update:{range_name}")
        start = 0
        if range_name and range_name.startswith("A"):
            start = max(int(range_name[1:]) - 1, 0)
        while len(self.rows) < start + len(values):
            self.rows.append([])
        for offset, row_values in enumerate(values):
            self.rows[start + offset] = list(row_values)

    def append_rows(self, values, **kwargs):
        self.calls.append("append_rows")
        self.rows.extend([list(r) for r in values])

    def delete_rows(self, start_index, end_index=None):
        self.calls.append(f"delete_rows:{start_index}:{end_index}")
        end = end_index if end_index is not None else start_index
        del self.rows[start_index - 1 : end]


class _FakeSpreadsheet:
    def __init__(self, worksheet=None) -> None:
        self._worksheet = worksheet
        self.created: list = []

    def worksheet(self, title):
        import gspread

        if self._worksheet is None:
            raise gspread.WorksheetNotFound(title)
        return self._worksheet

    def add_worksheet(self, title, rows, cols, index=None):
        self.created.append(title)
        self._worksheet = _FakeWorksheet()
        return self._worksheet


def _fake_builder(spreadsheet, build_calls=None):
    class _FakeClient:
        def open_by_key(self, key):
            return spreadsheet

    def builder(credentials_file):
        # the credential path is consumed but never recorded (red line: no
        # credential material in logs / return values / test artifacts)
        if build_calls is not None:
            build_calls.append("build_client")
        return _FakeClient()

    return builder


def test_build_sheets_rows_carry_identity_and_mapping_columns() -> None:
    from app.services.sheets_export_service import build_sheets_rows

    batch = _sheets_batch()
    header, rows = build_sheets_rows(batch)
    assert header[:3] == ["batch_id", "task_id", "file_name"]
    assert header[3:7] == ["po_number", "quantity", "unit_price", "line_total"]
    assert len(rows) == 3
    assert rows[0]["task_id"] == "sheet-task-1"
    assert rows[0]["batch_id"] == "sheet-batch"
    assert rows[0]["file_name"] == "a.png"
    assert rows[0]["po_number"] == "PO-1001"
    assert rows[1]["quantity"] == ""  # empty cell keeps the configured column
    assert rows[2]["task_id"] == "sheet-task-2"


def test_sheets_export_first_write_lands_header_and_rows(monkeypatch) -> None:
    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    worksheet = _FakeWorksheet()
    spreadsheet = _FakeSpreadsheet(worksheet)
    build_calls: list = []
    monkeypatch.setattr(
        sheets_export_service, "_build_client", _fake_builder(spreadsheet, build_calls)
    )

    summary = export_batch_to_sheets(
        _sheets_batch(),
        credentials_file=_FAKE_CREDENTIALS_FILE,
        spreadsheet_id=_FAKE_SPREADSHEET_ID,
    )

    assert summary["appended"] == 3
    assert summary["replaced_tasks"] == 0
    assert summary["worksheet"] == "MappedRows"
    assert summary["created_header"] is True
    assert build_calls == ["build_client"]  # builder ran; path never recorded
    assert worksheet.rows[0][:3] == ["batch_id", "task_id", "file_name"]
    assert worksheet.rows[0][3:7] == ["po_number", "quantity", "unit_price", "line_total"]
    data_rows = worksheet.rows[1:]
    assert len(data_rows) == 3
    assert data_rows[0][1] == "sheet-task-1"
    assert data_rows[2][1] == "sheet-task-2"
    assert data_rows[0][3] == "PO-1001"


def test_sheets_export_idempotent_same_task_no_duplicate_rows(monkeypatch) -> None:
    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    worksheet = _FakeWorksheet()
    monkeypatch.setattr(
        sheets_export_service, "_build_client", _fake_builder(_FakeSpreadsheet(worksheet))
    )
    batch = _sheets_batch()

    first = export_batch_to_sheets(
        batch, credentials_file=_FAKE_CREDENTIALS_FILE, spreadsheet_id=_FAKE_SPREADSHEET_ID
    )
    assert first["appended"] == 3

    # batch.completed fires again for the same batch (retry -> resume path)
    second = export_batch_to_sheets(
        batch, credentials_file=_FAKE_CREDENTIALS_FILE, spreadsheet_id=_FAKE_SPREADSHEET_ID
    )
    assert second["appended"] == 3
    assert second["replaced_tasks"] == 2

    data_rows = worksheet.rows[1:]
    assert len(data_rows) == 3  # header + exactly one set of rows — no duplicates
    t1_rows = [r for r in data_rows if r[1] == "sheet-task-1"]
    t2_rows = [r for r in data_rows if r[1] == "sheet-task-2"]
    assert len(t1_rows) == 2
    assert len(t2_rows) == 1
    assert any("delete_rows" in call for call in worksheet.calls)


def test_sheets_export_replaces_shrunk_row_set_on_rerun(monkeypatch) -> None:
    """A task re-run yielding fewer rows must not leave stale rows behind."""
    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    worksheet = _FakeWorksheet()
    monkeypatch.setattr(
        sheets_export_service, "_build_client", _fake_builder(_FakeSpreadsheet(worksheet))
    )
    batch = _sheets_batch()
    export_batch_to_sheets(
        batch, credentials_file=_FAKE_CREDENTIALS_FILE, spreadsheet_id=_FAKE_SPREADSHEET_ID
    )
    assert len(worksheet.rows) == 4  # header + 3 data rows

    # task 1 re-processed: now yields a single mapped row (was two)
    batch.tasks[0].result["mapped_table_rows"] = [batch.tasks[0].result["mapped_table_rows"][0]]
    export_batch_to_sheets(
        batch, credentials_file=_FAKE_CREDENTIALS_FILE, spreadsheet_id=_FAKE_SPREADSHEET_ID
    )

    data_rows = worksheet.rows[1:]
    t1_rows = [r for r in data_rows if r[1] == "sheet-task-1"]
    assert len(t1_rows) == 1  # stale second row replaced, not duplicated
    assert t1_rows[0][3] == "PO-1001"


def test_sheets_export_preserves_other_tasks_rows(monkeypatch) -> None:
    from app.services import sheets_export_service
    from app.services.sheets_export_service import build_sheets_rows, export_batch_to_sheets

    header, _ = build_sheets_rows(_sheets_batch())
    foreign_row = ["other-batch", "other-task-uuid", "other.png"] + [""] * (len(header) - 3)
    foreign_row[header.index("po_number")] = "PO-FOREIGN"
    worksheet = _FakeWorksheet()
    worksheet.rows = [list(header), foreign_row]
    monkeypatch.setattr(
        sheets_export_service, "_build_client", _fake_builder(_FakeSpreadsheet(worksheet))
    )

    export_batch_to_sheets(
        _sheets_batch(), credentials_file=_FAKE_CREDENTIALS_FILE, spreadsheet_id=_FAKE_SPREADSHEET_ID
    )

    data_rows = worksheet.rows[1:]
    foreign_left = [r for r in data_rows if r[1] == "other-task-uuid"]
    assert len(foreign_left) == 1  # rows of other tasks are never touched
    assert foreign_left[0][header.index("po_number")] == "PO-FOREIGN"
    assert len([r for r in data_rows if r[1].startswith("sheet-task-")]) == 3


def test_sheets_export_header_mismatch_fail_closed(monkeypatch) -> None:
    import pytest

    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    worksheet = _FakeWorksheet()
    worksheet.rows = [["wrong", "header"], ["x", "y"]]
    monkeypatch.setattr(
        sheets_export_service, "_build_client", _fake_builder(_FakeSpreadsheet(worksheet))
    )

    with pytest.raises(RuntimeError, match="header mismatch"):
        export_batch_to_sheets(
            _sheets_batch(),
            credentials_file=_FAKE_CREDENTIALS_FILE,
            spreadsheet_id=_FAKE_SPREADSHEET_ID,
        )
    # fail closed: the mismatched sheet is left untouched (no clobber)
    assert worksheet.rows == [["wrong", "header"], ["x", "y"]]
    assert not any("append_rows" in call or "delete_rows" in call for call in worksheet.calls)


def test_sheets_export_auto_creates_missing_worksheet(monkeypatch) -> None:
    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    spreadsheet = _FakeSpreadsheet(worksheet=None)
    monkeypatch.setattr(sheets_export_service, "_build_client", _fake_builder(spreadsheet))

    summary = export_batch_to_sheets(
        _sheets_batch(),
        credentials_file=_FAKE_CREDENTIALS_FILE,
        spreadsheet_id=_FAKE_SPREADSHEET_ID,
        worksheet_name="ExportTab",
    )

    assert summary["created_worksheet"] is True
    assert spreadsheet.created == ["ExportTab"]
    assert summary["worksheet"] == "ExportTab"
    worksheet = spreadsheet._worksheet
    assert worksheet.rows[0][:3] == ["batch_id", "task_id", "file_name"]
    assert len(worksheet.rows) == 4


def test_sheets_export_no_mapping_rows_is_noop(monkeypatch) -> None:
    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    def _never_called(credentials_file):
        raise AssertionError("client builder must not run when there are no rows")

    monkeypatch.setattr(sheets_export_service, "_build_client", _never_called)
    summary = export_batch_to_sheets(
        _sample_batch(),  # t2 failed, t1 has no mapped rows
        credentials_file=_FAKE_CREDENTIALS_FILE,
        spreadsheet_id=_FAKE_SPREADSHEET_ID,
    )
    assert summary["appended"] == 0
    assert summary.get("skipped") == "no mapping rows"


def test_sheets_export_credentials_never_surface(monkeypatch) -> None:
    import pytest

    from app.services import sheets_export_service
    from app.services.sheets_export_service import export_batch_to_sheets

    # no credentials configured -> fail closed before any client build
    def _never_called(credentials_file):
        raise AssertionError("client builder must not run without credentials")

    monkeypatch.setattr(sheets_export_service, "_build_client", _never_called)
    with pytest.raises(RuntimeError, match="no service-account credentials"):
        export_batch_to_sheets(
            _sheets_batch(), credentials_file="", spreadsheet_id=_FAKE_SPREADSHEET_ID
        )

    # a failing builder (e.g. missing key file with the path in its message)
    # must surface sanitized — path/credential material never in error text
    def _boom(credentials_file):
        raise FileNotFoundError(2, "No such file or directory", credentials_file)

    monkeypatch.setattr(sheets_export_service, "_build_client", _boom)
    with pytest.raises(RuntimeError) as exc_info:
        export_batch_to_sheets(
            _sheets_batch(),
            credentials_file=_FAKE_CREDENTIALS_FILE,
            spreadsheet_id=_FAKE_SPREADSHEET_ID,
        )
    message = str(exc_info.value)
    assert "fake-credentials" not in message
    assert "nonexistent-service-account" not in message
    assert "service_account.json" not in message


def test_batch_completed_hook_dispatches_webhook_and_sheets_export(monkeypatch) -> None:
    """The routers-layer composed closure binds batch.completed -> webhook +
    opt-in Sheets export (routers may import any service — no S1b edge)."""
    import asyncio

    from app.core.config import settings
    from app.routers import batch as batch_router
    from app.services import sheets_export_service

    batch = _sheets_batch()
    batch.options = {
        "sheets_export": {"spreadsheet_id": _FAKE_SPREADSHEET_ID, "worksheet": "ExportTab"}
    }

    dispatched: list = []

    async def fake_webhook(payload):
        dispatched.append(("webhook", payload.get("batch_id")))

    monkeypatch.setattr(batch_router, "_dispatch_batch_completed_webhook", fake_webhook)

    class _FakeBatchService:
        def get_batch(self, batch_id):
            return batch if batch_id == batch.batch_id else None

    monkeypatch.setattr(batch_router, "batch_service", _FakeBatchService())
    monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", _FAKE_CREDENTIALS_FILE)

    seen: dict = {}

    def fake_export(batch_arg, *, credentials_file, spreadsheet_id, worksheet_name, **kwargs):
        seen["spreadsheet_id"] = spreadsheet_id
        seen["worksheet_name"] = worksheet_name
        seen["credentials_param_only"] = isinstance(credentials_file, str) and bool(credentials_file)
        return {"appended": 3}

    monkeypatch.setattr(sheets_export_service, "export_batch_to_sheets", fake_export)

    asyncio.run(batch_router._on_batch_completed({"batch_id": "sheet-batch"}))

    assert dispatched == [("webhook", "sheet-batch")]
    assert seen == {
        "spreadsheet_id": _FAKE_SPREADSHEET_ID,
        "worksheet_name": "ExportTab",
        "credentials_param_only": True,
    }


def test_batch_completed_hook_skips_sheets_without_config(monkeypatch) -> None:
    import asyncio

    from app.core.config import settings
    from app.routers import batch as batch_router
    from app.services import sheets_export_service

    batch = _sheets_batch()
    batch.options = {}  # no sheets_export opt-in

    dispatched: list = []

    async def fake_webhook(payload):
        dispatched.append(("webhook", payload.get("batch_id")))

    monkeypatch.setattr(batch_router, "_dispatch_batch_completed_webhook", fake_webhook)

    class _FakeBatchService:
        def get_batch(self, batch_id):
            return batch if batch_id == batch.batch_id else None

    monkeypatch.setattr(batch_router, "batch_service", _FakeBatchService())
    monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", _FAKE_CREDENTIALS_FILE)

    def _never_called(*args, **kwargs):
        raise AssertionError("sheets export must not run without batch options opt-in")

    monkeypatch.setattr(sheets_export_service, "export_batch_to_sheets", _never_called)

    asyncio.run(batch_router._on_batch_completed({"batch_id": "sheet-batch"}))
    assert dispatched == [("webhook", "sheet-batch")]  # webhook unaffected (AC4)

    # credentials empty -> export skipped even when the batch opts in
    batch.options = {"sheets_export": {"spreadsheet_id": _FAKE_SPREADSHEET_ID}}
    monkeypatch.setattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "")
    asyncio.run(batch_router._on_batch_completed({"batch_id": "sheet-batch"}))
    assert len(dispatched) == 2


# ---------------------------------------------------------------------------
# R-003/P-042 T5 (AC6): per-order CSV split export — batch-level per_order
# opt-in, one CSV per order via render_csv, deterministic filenames
# (file-level idempotency: re-run overwrites, never duplicates), configurable
# ERP-watch directory.

def test_build_order_csv_per_order_columns_and_split() -> None:
    from app.services.per_order_export_service import build_order_csv

    batch = _sheets_batch()
    order_t1 = build_order_csv(batch, batch.tasks[0])
    order_t2 = build_order_csv(batch, batch.tasks[1])
    assert order_t1 is not None and order_t2 is not None
    header_t1, rows_t1 = order_t1
    header_t2, rows_t2 = order_t2
    # every order file carries the identical header set ("set format")
    assert header_t1 == header_t2
    assert header_t1[0] == "file_name"
    assert header_t1[1:5] == ["po_number", "quantity", "unit_price", "line_total"]
    # split correctness: rows only from the owning order
    assert len(rows_t1) == 2
    assert all(r["file_name"] == "a.png" for r in rows_t1)
    assert len(rows_t2) == 1
    assert rows_t2[0]["file_name"] == "b.png"
    assert rows_t1[0]["po_number"] == "PO-1001"
    assert rows_t2[0]["po_number"] == "PO-1003"


def test_build_order_csv_no_mapping_rows_returns_none() -> None:
    from app.services.per_order_export_service import build_order_csv

    batch = _sheets_batch()
    batch.tasks[0].result.pop("mapped_table_rows")
    assert build_order_csv(batch, batch.tasks[0]) is None
    assert build_order_csv(batch, batch.tasks[1]) is not None


def test_export_batch_per_order_writes_one_csv_per_order(tmp_path) -> None:
    import os

    from app.services.batch_export_service import render_csv
    from app.services.per_order_export_service import build_order_csv, export_batch_per_order

    batch = _sheets_batch()
    summary = export_batch_per_order(batch, str(tmp_path))

    assert summary["written"] == 2
    assert summary["skipped_tasks"] == []
    assert sorted(os.listdir(tmp_path)) == ["a.csv", "b.csv"]
    # reuse proof: file bytes are exactly render_csv output for that order
    for task, name in ((batch.tasks[0], "a.csv"), (batch.tasks[1], "b.csv")):
        header, rows = build_order_csv(batch, task)
        assert (tmp_path / name).read_bytes() == render_csv(header, rows).encode("utf-8")
    order_by_task = {o["task_id"]: o for o in summary["orders"]}
    assert order_by_task["sheet-task-1"]["rows"] == 2
    assert order_by_task["sheet-task-2"]["rows"] == 1


def test_export_batch_per_order_file_idempotent_on_rerun(tmp_path) -> None:
    import os

    from app.services.per_order_export_service import export_batch_per_order

    batch = _sheets_batch()
    first = export_batch_per_order(batch, str(tmp_path))
    snapshots = {
        o["order_file"]: open(o["order_file"], "rb").read() for o in first["orders"]
    }

    # batch.completed fires again for the same batch (retry -> resume path)
    second = export_batch_per_order(batch, str(tmp_path))

    assert sorted(os.listdir(tmp_path)) == ["a.csv", "b.csv"]  # no duplicate files
    assert [o["order_file"] for o in second["orders"]] == [
        o["order_file"] for o in first["orders"]
    ]
    for path, content in snapshots.items():
        assert open(path, "rb").read() == content  # same path overwritten in place


def test_export_batch_per_order_duplicate_stem_suffix_deterministic(tmp_path) -> None:
    import os

    from app.services.per_order_export_service import export_batch_per_order

    batch = _sheets_batch()
    batch.tasks[1].file_name = "a.png"  # duplicate stem with task 1
    first = export_batch_per_order(batch, str(tmp_path))
    names = sorted(os.listdir(tmp_path))
    assert len(names) == 2
    assert all("a.csv" != name for name in names)  # collision resolved, no clobber
    assert all(name.endswith(".csv") for name in names)

    second = export_batch_per_order(batch, str(tmp_path))
    assert sorted(os.listdir(tmp_path)) == names  # same names on rerun (deterministic)
    assert [o["order_file"] for o in second["orders"]] == [
        o["order_file"] for o in first["orders"]
    ]
    assert len({o["task_id"] for o in second["orders"]}) == 2  # both orders landed
    contents = [open(tmp_path / name, "rb").read() for name in names]
    assert contents[0] != contents[1]  # each file keeps only its own order's rows


def test_export_batch_per_order_skips_orders_without_rows(tmp_path) -> None:
    import os

    from app.services.per_order_export_service import export_batch_per_order

    batch = _sheets_batch()
    batch.tasks[1].result.pop("mapped_table_rows")
    summary = export_batch_per_order(batch, str(tmp_path))
    assert summary["written"] == 1
    assert summary["skipped_tasks"] == ["sheet-task-2"]
    assert os.listdir(tmp_path) == ["a.csv"]  # no empty CSV for the ERP


def test_export_batch_per_order_no_orders_writes_nothing(tmp_path) -> None:
    import os

    from app.services.per_order_export_service import export_batch_per_order

    batch = _sample_batch()  # no mapped rows at all
    summary = export_batch_per_order(batch, str(tmp_path))
    assert summary["written"] == 0
    assert summary["skipped_tasks"] == ["t1", "t2"]
    assert os.listdir(tmp_path) == []  # nothing written


def test_batch_completed_hook_per_order_export(tmp_path, monkeypatch) -> None:
    import asyncio

    from app.routers import batch as batch_router
    from app.services import per_order_export_service

    batch = _sheets_batch()
    batch.options = {"per_order": True, "per_order_output_dir": str(tmp_path)}
    dispatched: list = []

    async def fake_webhook(payload):
        dispatched.append(("webhook", payload.get("batch_id")))

    monkeypatch.setattr(batch_router, "_dispatch_batch_completed_webhook", fake_webhook)

    class _FakeBatchService:
        def get_batch(self, batch_id):
            return batch if batch_id == batch.batch_id else None

    monkeypatch.setattr(batch_router, "batch_service", _FakeBatchService())

    seen: dict = {}

    def fake_export(batch_arg, output_dir):
        seen["batch_id"] = batch_arg.batch_id
        seen["output_dir"] = output_dir
        return {"written": 2}

    monkeypatch.setattr(per_order_export_service, "export_batch_per_order", fake_export)

    asyncio.run(batch_router._on_batch_completed({"batch_id": "sheet-batch"}))
    assert dispatched == [("webhook", "sheet-batch")]  # webhook unaffected (AC4)
    assert seen == {"batch_id": "sheet-batch", "output_dir": str(tmp_path)}


def test_batch_completed_hook_per_order_fallback_dir_and_opt_out(monkeypatch) -> None:
    import asyncio
    import os

    from app.core.config import settings
    from app.routers import batch as batch_router
    from app.services import per_order_export_service

    batch = _sheets_batch()
    batch.options = {"per_order": True}  # no explicit dir -> OUTPUT_DIR fallback
    dispatched: list = []

    async def fake_webhook(payload):
        dispatched.append(payload.get("batch_id"))

    monkeypatch.setattr(batch_router, "_dispatch_batch_completed_webhook", fake_webhook)

    class _FakeBatchService:
        def get_batch(self, batch_id):
            return batch if batch_id == batch.batch_id else None

    monkeypatch.setattr(batch_router, "batch_service", _FakeBatchService())

    seen: dict = {}

    def fake_export(batch_arg, output_dir):
        seen["output_dir"] = output_dir
        return {"written": 2}

    monkeypatch.setattr(per_order_export_service, "export_batch_per_order", fake_export)

    asyncio.run(batch_router._on_batch_completed({"batch_id": "sheet-batch"}))
    assert seen["output_dir"] == os.path.join(settings.OUTPUT_DIR, "per_order", "sheet-batch")

    # opt-out: no per_order flag -> export skipped, webhook still fires (AC4)
    batch.options = {}

    def _never(*args, **kwargs):
        raise AssertionError("per-order export must not run without opt-in")

    monkeypatch.setattr(per_order_export_service, "export_batch_per_order", _never)
    asyncio.run(batch_router._on_batch_completed({"batch_id": "sheet-batch"}))
    assert len(dispatched) == 2
