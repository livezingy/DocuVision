"""Unit tests for the trial API-key middleware (GLM trial P0-1).

Pure FastAPI stub app — no Paddle/heavy imports involved. These tests run
locally (contract layer, per .cursor/rules/004).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app.core.trial_auth import TrialAuthMiddleware


def _build_app(api_key: str) -> FastAPI:
    app = FastAPI()

    # Mirror production ordering: auth added BEFORE CORS so CORS stays
    # outside and decorates 401s.
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(TrialAuthMiddleware, api_key=api_key)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/api/v1/ping")
    async def ping():
        return {"pong": True}

    @app.websocket("/api/v1/ws")
    async def ws_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("hello")
        await websocket.close()

    return app


class TestAuthDisabled:
    def test_open_when_no_key_configured(self):
        client = TestClient(_build_app(""))
        resp = client.get("/api/v1/ping")
        assert resp.status_code == 200
        assert resp.json()["pong"] is True


class TestAuthEnabled:
    def test_missing_key_rejected_401(self):
        client = TestClient(_build_app("secret-key"))
        resp = client.get("/api/v1/ping")
        assert resp.status_code == 401
        assert "API key required" in resp.json()["detail"]

    def test_wrong_key_rejected_401(self):
        client = TestClient(_build_app("secret-key"))
        resp = client.get("/api/v1/ping", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_correct_key_passes(self):
        client = TestClient(_build_app("secret-key"))
        resp = client.get("/api/v1/ping", headers={"X-API-Key": "secret-key"})
        assert resp.status_code == 200

    def test_health_open_without_key(self):
        client = TestClient(_build_app("secret-key"))
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_cors_headers_decorate_401(self):
        client = TestClient(_build_app("secret-key"))
        resp = client.get(
            "/api/v1/ping",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 401
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_websocket_key_via_query_param(self):
        client = TestClient(_build_app("secret-key"))
        with client.websocket_connect("/api/v1/ws?key=secret-key") as ws:
            assert ws.receive_text() == "hello"

    def test_websocket_rejected_without_key(self):
        client = TestClient(_build_app("secret-key"))
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws"):
                pass  # pragma: no cover — handshake must be rejected

    def test_websocket_rejected_with_wrong_key(self):
        client = TestClient(_build_app("secret-key"))
        with pytest.raises(Exception):
            with client.websocket_connect("/api/v1/ws?key=wrong"):
                pass  # pragma: no cover

    def test_static_and_root_paths_open(self):
        client = TestClient(_build_app("secret-key"))
        # Root "/" is not under /api/ — must stay open for the SPA.
        assert client.get("/").status_code in (200, 404)
        # /docs and /openapi.json stay open for probes.
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200
