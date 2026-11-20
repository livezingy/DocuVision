"""Webhook HTTP delivery tests."""

import asyncio
from datetime import datetime

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


# ---------------------------------------------------------------------------
# T2 对账断言 (R-004 pack v1.2 §2 T2 / review P1-1, pinned form):
# webhook ``task.completed`` 触发 ⟺ WS 侧出现 status="completed"
# （"succeeded" 仅取数别名，从不写入 task.status）。同一完成路径双捕获：
# stub orchestrator.send_event + stub webhook_registry 捕获 dispatch_event_async
# —— 不真连网、不起服务器、pytest 不触 :8000。
# 真源：finalize 派发 backend/app/orchestration/steps/governance.py:120-128
# （status :85 / persist :111-113 / WS :115 / webhook :120-128）；
# 广播帧形 backend/app/core/runtime.py:379-403；当前帧形
# backend/app/routers/tasks.py:92-110；别名双闸 jobs.py:52-55 +
# tasks_content.py:35-36。全表见 docs/integrations/webhook-events.md §6。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kie_validation,expected_flag",
    [
        ({"validation_passed": True}, True),
        (None, None),
    ],
)
async def test_finalize_step_fires_webhook_and_ws_completed_together(
    monkeypatch, kie_validation, expected_flag
) -> None:
    """同一 finalize 路径双捕获：WS 帧与 webhook 同源同发（对账核心 ⟺）。"""
    from app.orchestration.steps import governance
    from app.services import webhook_service

    async def _fake_persist(task):
        return None

    monkeypatch.setattr(
        "app.orchestration.steps.governance.resolve_document_page_count",
        lambda file_path, result: 3,
    )
    monkeypatch.setattr(
        "app.services.persistence.analyze_job_store.persist_task_safe",
        _fake_persist,
    )

    task = {
        "task_id": "t-dual",
        "file_name": "sample.pdf",
        "status": "processing",
        "progress": 90,
        "message": "PII mask applied",
        "result": {"kie_validation": kie_validation} if kie_validation else {},
    }
    ws_events = []

    class _StubOrchestrator:
        def ensure_not_cancelled(self, ctx):
            return None

        async def send_event(self, task_id, event_type, message, progress=None):
            ws_events.append(
                {
                    "task_id": task_id,
                    "type": event_type,
                    "message": message,
                    "progress": progress,
                }
            )

    dispatched = []

    class _StubRegistry:
        async def dispatch_event_async(self, event, payload, **kwargs):
            dispatched.append((event, payload))
            return []

    monkeypatch.setattr(webhook_service, "webhook_registry", _StubRegistry())

    ctx = {
        "task_id": "t-dual",
        "task": task,
        "file_path": "unused.pdf",
        "result": task["result"],
        "orchestrator": _StubOrchestrator(),
    }

    await governance.finalize_step(ctx)

    # 同一 finalize：任务实写值 = "completed"（governance.py:85；"succeeded" 从不写入）
    assert task["status"] == "completed"
    # WS 侧（同路径）：send_event("completed", "Processing completed", 100)（governance.py:115）
    assert ws_events == [
        {
            "task_id": "t-dual",
            "type": "completed",
            "message": "Processing completed",
            "progress": 100,
        }
    ]
    # webhook 侧（同路径）：task.completed + 载荷字段集钉死（governance.py:122-127）
    assert dispatched == [
        (
            "task.completed",
            {
                "task_id": "t-dual",
                "file_name": "sample.pdf",
                "status": "completed",
                "validation_passed": expected_flag,
            },
        )
    ]
    # ⟺：两侧各恰好一次 —— 同一完成路径上不存在单侧触发
    assert len(ws_events) == 1 and len(dispatched) == 1


@pytest.mark.asyncio
async def test_succeeded_alias_accepted_by_result_gates() -> None:
    """归一别名断言："succeeded" 通过双 result 闸（jobs.py:52-55 /
    tasks_content.py:35-36），与实写值 "completed" 等价收货；状态读取端点
    与 WS 当前帧同源（tasks.py:99 读 task["status"]）。进程内 ASGI，不起服务器。"""
    import httpx

    from app.core import runtime
    from app.main import app

    tid = "t-alias"
    runtime.tasks[tid] = {
        "task_id": tid,
        "status": "succeeded",
        "progress": 100,
        "message": "Processing completed",
        "created_at": datetime.now(),
        "result": {"view": {}},
        "envelope": {"job_id": tid, "status": "succeeded", "version": "1.0"},
    }
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test", timeout=60
        ) as client:
            # 别名 "succeeded" 通过双闸
            assert (await client.get(f"/api/v1/tasks/{tid}/result")).status_code == 200
            assert (await client.get(f"/api/v1/jobs/{tid}/result")).status_code == 200
            # 实写值 "completed"（governance.py:85）同样通过同一双闸
            runtime.tasks[tid]["status"] = "completed"
            assert (await client.get(f"/api/v1/tasks/{tid}/result")).status_code == 200
            assert (await client.get(f"/api/v1/jobs/{tid}/result")).status_code == 200
            # 任务状态端点 = WS 当前帧的 status 来源（tasks.py:98-99）
            r_status = await client.get(f"/api/v1/tasks/{tid}")
            assert r_status.status_code == 200
            assert r_status.json()["status"] == "completed"
    finally:
        runtime.tasks.pop(tid, None)


def test_ws_route_emits_pinned_completed_frames() -> None:
    """WS 路由实链路（进程内 TestClient，无 lifespan/TCP）：
    重放帧 = 广播真形 {"type":"completed",...}（无 "status" 键，runtime.py:381-397）；
    当前帧分支 = 钉死形态 {"type":"status","status":"completed"}（tasks.py:92-108）。"""
    from starlette.testclient import TestClient

    from app.core import runtime
    from app.core.runtime import _send_event
    from app.main import app

    tid = "t-ws-recon"
    runtime.tasks[tid] = {
        "task_id": tid,
        "status": "completed",
        "progress": 100,
        "message": "Processing completed",
        "created_at": datetime.now(),
    }
    # 先用真广播函数落 history（此刻无连接，仅 dict 操作，不跨事件循环发帧）
    asyncio.run(_send_event(tid, "completed", "Processing completed", 100))
    client = TestClient(app)
    try:
        # 会话1：重放路径 —— 当前帧同 id 已随重放发出而被跳过（tasks.py:105-110）
        with client.websocket_connect(f"/api/v1/tasks/{tid}/ws") as ws:
            replayed = ws.receive_json()
        assert replayed["type"] == "completed"
        assert replayed["message"] == "Processing completed"
        assert replayed["progress"] == 100
        assert replayed["id"] == 1
        # 广播帧形（runtime.py:381-387）：无 "status" 键 —— "status" 只在当前帧分支
        assert "status" not in replayed

        # 会话2：当前帧分支 —— 清 history 留 counter（>max_sent_id=0）→ tasks.py:105-108
        runtime.task_event_history.pop(tid, None)
        with client.websocket_connect(f"/api/v1/tasks/{tid}/ws?since=0") as ws:
            current = ws.receive_json()
        assert current["type"] == "status"
        # 钉死形态：{"type":"status","status":"completed"}
        assert current["status"] == "completed"
        assert current["id"] == 1
        assert current["progress"] == 100
    finally:
        runtime.tasks.pop(tid, None)
        runtime.task_event_history.pop(tid, None)
        runtime.task_event_counters.pop(tid, None)
        runtime.task_websockets.pop(tid, None)
