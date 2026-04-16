import asyncio

from app.services.kie_service import DocumentKIEService


def test_extract_fields_receives_inputs(monkeypatch):
    svc = DocumentKIEService()

    # Mock engine to avoid spawning subprocess
    class MockEngine:
        def analyze(self, file_path):
            return {"fields": {"MockField": "v"}}

    monkeypatch.setattr(DocumentKIEService, "_get_engine", lambda self, dt: MockEngine())

    async def run_test():
        res = await svc.extract_fields(
            "somepath.pdf",
            "invoice",
            preprocessed_image_path="/tmp/preproc.jpg",
            layout={"elements": []},
            table_meta={"tables_returned": 0},
        )
        assert isinstance(res, dict)
        assert "fields" in res
        assert res.get("debug_input", {}).get("preprocessed_image_path") == "/tmp/preproc.jpg"

    asyncio.run(run_test())
