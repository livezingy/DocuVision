import asyncio

from app.orchestration.document_pipeline_orchestrator import table_step, kie_step, DocumentPipelineOrchestrator


def make_orchestrator(services):
    async def noop_update_progress(ctx, progress, message):
        return None

    async def call_maybe_async(func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return func(*args, **kwargs)

    def is_cancelled(task_id):
        return False

    def build_page_image_meta(file_path, task_id=None, page_num=1):
        return {"width_px": 1000, "height_px": 1000}

    return DocumentPipelineOrchestrator(
        services=services,
        send_event=lambda *a, **k: asyncio.sleep(0),
        is_cancelled=is_cancelled,
        call_maybe_async=call_maybe_async,
        build_page_image_meta=build_page_image_meta,
    )


def test_kie_called_after_table(tmp_path):
    # Prepare mocks and context
    table_called = {}
    def fake_extract_with_meta(file_path, **kwargs):
        table_called['called'] = True
        return {"tables": [], "meta": {"engine_used": "mock"}}

    kie_called = {}
    def fake_kie_extract(file_path, document_type, **kwargs):
        kie_called['args'] = (file_path, document_type, kwargs)
        return {"fields": {"InvoiceId": "1234"}}

    services = {
        "table_service": type("T", (), {"extract_with_meta": staticmethod(fake_extract_with_meta)})(),
        "kie_service": type("K", (), {"extract_fields": staticmethod(fake_kie_extract)})(),
    }

    orch = make_orchestrator(services)

    task = {"file_path": str(tmp_path / "doc.pdf"), "file_name": "doc.pdf", "options": {"enable_table": True, "enable_kie": True, "document_type": "invoice"}}
    result = {"document_info": {"page_image_meta": {}}}

    ctx = {
        "task_id": "t1",
        "task": task,
        "file_path": task["file_path"],
        "options": task.get("options", {}),
        "result": result,
        "orchestrator": orch,
        "start_time": None,
    }

    # ensure preprocessed_image_path present
    ctx["task"]["preprocessed_image_path"] = "/tmp/preproc.jpg"

    # Run table_step then kie_step
    asyncio.run(table_step(ctx))
    asyncio.run(kie_step(ctx))

    # Asserts
    assert table_called.get('called', False) is True
    assert "kie_input" in ctx["result"]
    assert kie_called.get('args') is not None
    # The kwargs passed to kie should include preprocessed_image_path
    _, _, kwargs = kie_called['args']
    assert kwargs.get('preprocessed_image_path') == "/tmp/preproc.jpg"
