"""Trial API-key authentication middleware (GLM trial P0-1).

Guards every ``/api/v1/*`` route (HTTP and WebSocket) when
``DOCUVISION_TRIAL_API_KEY`` is configured. Local development without the
key keeps the previous open behaviour; a configured key fails closed
(HTTP 401 / WS handshake rejection).

Design notes
------------
- Implemented as pure ASGI middleware so WebSocket handshakes are covered:
  the browser ``WebSocket`` API cannot send custom headers, so the ws scope
  accepts the key via the ``?key=`` query parameter instead.
- Health/docs/openapi paths stay open for probes (preflight, uptime).
- Starlette ordering: this middleware must be added BEFORE the CORS
  middleware ``add_middleware`` call so CORS stays outermost and still
  decorates 401 responses with CORS headers. Preflight OPTIONS requests
  are answered by the CORS layer before reaching this middleware.
- Key comparison uses ``hmac.compare_digest`` to avoid timing oracles.
"""

from __future__ import annotations

import hmac
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from loguru import logger

# Paths that stay open without a key (probes and docs).
OPEN_PATH_PREFIXES = (
    "/docs",
    "/redoc",
    "/openapi.json",
)
OPEN_PATH_EXACT = (
    "/",
    "/health",
    "/api/v1/health",
)

_KEY_HEADER = b"x-api-key"
_KEY_QUERY_PARAM = "key"


def _api_key_from_scope(scope: Dict[str, Any]) -> Optional[str]:
    """Extract the candidate key from headers (http) or query string (ws)."""
    headers = scope.get("headers") or []
    for name, value in headers:
        if name.lower() == _KEY_HEADER:
            try:
                return value.decode("utf-8", errors="replace")
            except Exception:  # pragma: no cover - defensive
                return None
    # WebSocket (and tolerant HTTP fallback): ?key=...
    raw_qs = scope.get("query_string")
    if raw_qs:
        try:
            params = parse_qs(raw_qs.decode("utf-8", errors="replace"))
        except Exception:  # pragma: no cover - defensive
            return None
        values = params.get(_KEY_QUERY_PARAM)
        if values:
            return values[0]
    return None


def _path_is_open(path: str) -> bool:
    if path in OPEN_PATH_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in OPEN_PATH_PREFIXES)


def _path_needs_guard(path: str) -> bool:
    """Only /api/v1/* business routes are guarded; static frontend stays open."""
    return path.startswith("/api/")


async def _send_json_response(send: Any, status: int, payload: Dict[str, Any]) -> None:
    import json as _json

    body = _json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"cache-control", b"no-store"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class TrialAuthMiddleware:
    """ASGI middleware enforcing the trial API key (http + websocket scopes)."""

    def __init__(self, app: Any, api_key: str = "") -> None:
        self.app = app
        self.api_key = (api_key or "").strip()

    async def __call__(self, scope: Dict[str, Any], receive: Any, send: Any) -> None:
        if not self.api_key:
            await self.app(scope, receive, send)
            return

        scope_type = scope.get("type")
        path = scope.get("path", "")

        if scope_type == "http":
            if scope.get("method") == "OPTIONS" or _path_is_open(path) or not _path_needs_guard(path):
                await self.app(scope, receive, send)
                return
            provided = _api_key_from_scope(scope) or ""
            if hmac.compare_digest(provided.encode("utf-8"), self.api_key.encode("utf-8")):
                await self.app(scope, receive, send)
                return
            logger.warning(
                "trial_auth: rejected unauthenticated request | path={} remote={}",
                path,
                scope.get("client", ("?",))[0] if scope.get("client") else "?",
            )
            await _send_json_response(
                send,
                401,
                {
                    "detail": "API key required. Provide the X-API-Key header "
                    "(or ?key= for WebSocket connections)."
                },
            )
            return

        if scope_type == "websocket":
            provided = _api_key_from_scope(scope) or ""
            if hmac.compare_digest(provided.encode("utf-8"), self.api_key.encode("utf-8")):
                await self.app(scope, receive, send)
                return
            logger.warning(
                "trial_auth: rejected unauthenticated websocket | path={}",
                path,
            )
            # Reject the handshake (server answers HTTP 403).
            await send({"type": "websocket.close", "code": 1008, "reason": "API key required"})
            return

        # Other scopes (lifespan etc.) pass through untouched.
        await self.app(scope, receive, send)
