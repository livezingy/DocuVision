"""Webhook HTTP delivery tests."""

import pytest

from app.services.webhook_service import WebhookRegistry


@pytest.mark.asyncio
async def test_dispatch_event_async_posts(monkeypatch) -> None:
    registry = WebhookRegistry()
    registry.register("https://example.com/hook", ["task.completed"], secret="testsecret")

    posted = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, content=None, headers=None):
            posted.append({"url": url, "content": content, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: FakeClient())

    results = await registry.dispatch_event_async("task.completed", {"task_id": "t1"})
    assert len(results) == 1
    assert results[0]["delivered"] is True
    assert posted[0]["url"] == "https://example.com/hook"
    assert b"task_id" in posted[0]["content"]
