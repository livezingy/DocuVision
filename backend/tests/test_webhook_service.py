"""Webhook HTTP delivery tests."""

import pytest

from app.services.webhook_service import WebhookRegistry


@pytest.mark.asyncio
async def test_dispatch_event_async_posts(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, "WEBHOOK_ENABLED", True)

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


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/hook",
        "http://10.1.2.3/hook",
        "http://192.168.0.1/hook",
        "http://169.254.169.254/hook",  # AWS metadata
        "http://172.16.0.1/hook",
        "http://[::1]/hook",
    ],
)
def test_register_rejects_private_ip(url: str) -> None:
    registry = WebhookRegistry()
    with pytest.raises(ValueError, match="private network"):
        registry.register(url, ["task.completed"])


def test_register_accepts_public_host() -> None:
    registry = WebhookRegistry()
    # example.com resolves to a public IP; should not raise.
    sub = registry.register("https://example.com/hook", ["task.completed"])
    assert sub.url == "https://example.com/hook"


@pytest.mark.asyncio
async def test_dispatch_disabled_returns_empty(monkeypatch) -> None:
    from app.core import config as config_module

    monkeypatch.setattr(config_module.settings, "WEBHOOK_ENABLED", False)
    registry = WebhookRegistry()
    registry.register("https://example.com/hook", ["task.completed"])

    def _fail_if_posted(**kwargs):
        raise AssertionError("must not POST when WEBHOOK_ENABLED=False")

    monkeypatch.setattr("httpx.AsyncClient", _fail_if_posted)

    results = await registry.dispatch_event_async("task.completed", {"task_id": "t1"})
    assert results == []
