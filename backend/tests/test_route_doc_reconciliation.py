"""Route-doc reconciliation (R-004 pack T3 / AC3): the committed
``docs/integrations/rest-api.md`` must mirror the runtime route surface
extracted from ``app.openapi()`` and stay pinned to the frozen route
inventory (``tests.test_route_inventory.EXPECTED_ROUTES``, 55).

Contract: 文档端点清单 == 冻结 55 == OpenAPI paths. The single WebSocket
route (``/api/v1/tasks/{task_id}/ws``) is not expressible in OpenAPI, so it is
taken from the runtime route table and counted on top of the OpenAPI
operations (54) — the same 54 + 1 split ``test_openapi_snapshot_full`` pins.

Also hosts the R-003/P-042 hardening API-level reconciliation (commit 006535a):
``POST /api/v1/batch`` must map a per_order_output_dir escaping
``settings.OUTPUT_DIR`` to HTTP 422, and accept a confined relative path,
and the R-004 T1 template reconciliation: every HTTP Request node in the n8n
templates (``docs/integrations/n8n/*.json``) must reference an endpoint that
exists in ``app.openapi()`` paths.

Write mode regenerates the markdown (mirrors ``test_openapi_snapshot_full``)::

    cd backend
    DOCUVISION_REST_DOC=write python -m pytest tests/test_route_doc_reconciliation.py -q

Check mode (default, no flags): rebuilds the markdown in memory and diffs it
line-by-line against the committed file — any drift turns red.

Local-face only: importing ``app.main`` starts no server and binds no port
(P-039 follow-up: imports without the paddle stack).
"""

from __future__ import annotations

import difflib
import json
import os
import re
from pathlib import Path

import pytest

# Pure-AST module (no app import, 0.0x s) — sanctioned cross-test import; see
# test_route_inventory.py docstring: route changes must update that frozen set
# *and* the OpenAPI snapshot, and now also this generated doc.
from tests.test_route_inventory import EXPECTED_COUNT, EXPECTED_ROUTES

_WRITE = os.environ.get("DOCUVISION_REST_DOC", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "write",
}

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATH = REPO_ROOT / "docs" / "integrations" / "rest-api.md"


def _route_surface() -> tuple[list[dict], list[str]]:
    """HTTP operations (``app.openapi()``) + WebSocket paths (runtime table).

    ``app.main`` is imported inside the function, test-scoped like
    ``test_openapi_snapshot_full``. Both outputs are deterministically sorted
    so the rendered markdown is byte-stable across runs.
    """
    from starlette.routing import WebSocketRoute

    from app.main import app

    schema = app.openapi()
    ops: list[dict] = []
    for path, methods in schema.get("paths", {}).items():
        for method, spec in methods.items():
            ops.append(
                {
                    "method": str(method).upper(),
                    "path": path,
                    "summary": str(
                        spec.get("summary") or spec.get("operationId") or ""
                    ),
                }
            )
    ops.sort(key=lambda op: (op["path"], op["method"]))
    ws_paths = sorted(
        route.path for route in app.routes if isinstance(route, WebSocketRoute)
    )
    return ops, ws_paths


def _cell(text: str) -> str:
    """Make text safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _render_markdown(ops: list[dict], ws_paths: list[str]) -> str:
    distinct_paths = {op["path"] for op in ops}
    total = len(ops) + len(ws_paths)
    ws_join = ", ".join(f"`{p}`" for p in ws_paths) or "（无）"
    lines: list[str] = [
        "# DocuVision REST API 全量文档（生成产物）",
        "",
        "> **generated** — 手改无效；对账用例 = "
        "`backend/tests/test_route_doc_reconciliation.py`（registry kind `full`，"
        "非写模式逐行 diff，漂移即红）。",
        "> 生成源 = 仓内 OpenAPI 快照闸（`app.openapi()` 运行时提取），"
        "冻结口径 = `backend/tests/test_route_inventory.py` EXPECTED_ROUTES。",
        "> 再生命令：`cd backend && DOCUVISION_REST_DOC=write "
        "python -m pytest tests/test_route_doc_reconciliation.py -q`",
        "",
        "## 端点计数",
        "",
        f"- OpenAPI distinct paths：{len(distinct_paths)}",
        f"- HTTP 端点（OpenAPI operations）：{len(ops)}",
        f"- WebSocket 端点（OpenAPI 不表达，取自运行时路由表）："
        f"{len(ws_paths)}（{ws_join}）",
        f"- **端点总数：{total}，对账锚 = "
        f"test_route_inventory.EXPECTED_COUNT（冻结 {EXPECTED_COUNT}）**",
        "",
        "## 端点全表（HTTP）",
        "",
        "| # | Method | Path | Summary |",
        "|---|--------|------|---------|",
    ]
    for idx, op in enumerate(ops, start=1):
        lines.append(
            f"| {idx} | {op['method']} | `{op['path']}` | {_cell(op['summary'])} |"
        )
    lines.extend(["", "## WebSocket", ""])
    for ws_path in ws_paths:
        lines.append(
            f"- `{ws_path}` — OpenAPI 规范不表达 WS，此行取自运行时路由表，"
            "计入端点总数。"
        )
    lines.extend(
        [
            "",
            "## 真源注记",
            "",
            "- 本文件为生成产物；端点真源 = 仓内 OpenAPI 快照闸"
            "（`test_openapi_snapshot_full`）+ 冻结路由清单"
            "（`test_route_inventory.EXPECTED_ROUTES`）。",
            "- 端点/字段细节以服务运行时的 `/openapi.json` 为唯一真源。",
            "- 漂移处置：改路由必须同步三处 —— 代码路由、"
            "`test_route_inventory.EXPECTED_ROUTES`、本文件（写模式再生）。",
            "- 相关文档：`docs/integrations/webhook-events.md`"
            "（webhook 事件类型全表：task.completed / batch.completed 载荷与 WS 对照）。",
            "",
        ]
    )
    return "\n".join(lines)


def _surface_pairs() -> set[tuple[str, str]]:
    ops, ws_paths = _route_surface()
    return (
        {(op["method"], op["path"]) for op in ops}
        | {("WS", ws_path) for ws_path in ws_paths}
    )


def test_rest_doc_endpoint_count_matches_inventory() -> None:
    ops, ws_paths = _route_surface()
    total = len(ops) + len(ws_paths)
    assert total == EXPECTED_COUNT, (
        f"endpoint count {total} != frozen EXPECTED_COUNT {EXPECTED_COUNT}"
    )
    surface = _surface_pairs()
    missing = sorted(EXPECTED_ROUTES - surface)
    unexpected = sorted(surface - EXPECTED_ROUTES)
    assert not missing and not unexpected, (
        "runtime route surface drifted from frozen inventory.\n"
        f"missing: {missing}\nunexpected: {unexpected}"
    )


def test_rest_doc_reconciliation() -> None:
    ops, ws_paths = _route_surface()
    rendered = _render_markdown(ops, ws_paths)

    if _WRITE:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(rendered, encoding="utf-8")
        pytest.skip(f"rest-api.md written: {DOC_PATH}")

    assert DOC_PATH.exists(), (
        f"{DOC_PATH} missing — regenerate with: cd backend && "
        "DOCUVISION_REST_DOC=write python -m pytest "
        "tests/test_route_doc_reconciliation.py -q"
    )
    committed = DOC_PATH.read_text(encoding="utf-8")
    if committed != rendered:
        diff = list(
            difflib.unified_diff(
                committed.splitlines(),
                rendered.splitlines(),
                fromfile=str(DOC_PATH),
                tofile="generated",
                lineterm="",
            )
        )
        preview = "\n".join(diff[:40])
        assert False, (
            "docs/integrations/rest-api.md drifted from the generated doc "
            f"(full diff {len(diff)} lines, first 40):\n{preview}"
        )


# ---------------------------------------------------------------------------
# R-003/P-042 hardening — API-level reconciliation (commit 006535a, R-004
# 对账补用例). POST /api/v1/batch (multipart) maps a per_order_output_dir that
# escapes settings.OUTPUT_DIR to HTTP 422, and accepts a confined relative
# path (200; the resolved absolute path is written back into batch.options).
# 真源：backend/app/routers/batch.py:185-204（_confine_per_order_dir → 422）、
# backend/app/services/per_order_export_service.py:37-67（realpath + commonpath
# containment，逃逸即 ValueError）。服务级 resolver 单测见
# test_batch_export_service.py:856；此处对账的是路由层 422 映射。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_create_rejects_per_order_dir_escape(monkeypatch, tmp_path) -> None:
    """越界 per_order_output_dir（.. 穿越 / base 外绝对路径）→ 路由 422，
    且不落任何批次（confine 发生在建目录/存文件之前，batch.py:196 < :219）。"""
    import httpx

    from app.core import config as config_module
    from app.main import app

    monkeypatch.setattr(
        config_module.settings, "OUTPUT_DIR", str(tmp_path / "output")
    )
    monkeypatch.setattr(
        config_module.settings, "UPLOAD_DIR", str(tmp_path / "uploads")
    )

    escape_dirs = [
        os.path.join("..", "..", "escape"),  # 相对 .. 穿越（POSIX/Windows 同形逃逸）
        str(tmp_path / "outside_abs"),  # base 之外的同盘绝对路径
    ]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=60
    ) as client:
        for raw_dir in escape_dirs:
            resp = await client.post(
                "/api/v1/batch",
                data={
                    "name": "recon-escape",
                    "options": json.dumps(
                        {"per_order": True, "per_order_output_dir": raw_dir}
                    ),
                },
                files={"files": ("sample.pdf", b"%PDF-1.4 recon", "application/pdf")},
            )
            assert resp.status_code == 422, (raw_dir, resp.status_code, resp.text)
            assert "OUTPUT_DIR" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_batch_create_accepts_confined_relative_per_order_dir(
    monkeypatch, tmp_path
) -> None:
    """合法相对路径（OUTPUT_DIR 内）→ 非 422；建批成功且不 auto-start
    （处理在独立 POST /api/v1/batch/{id}/start）；解析后的绝对路径写回
    batch.options（batch.py:199-204，派发侧永不见原始未验证路径）。"""
    import httpx

    from app.core import config as config_module
    from app.core import runtime
    from app.main import app

    output_dir = tmp_path / "output"
    monkeypatch.setattr(config_module.settings, "OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(
        config_module.settings, "UPLOAD_DIR", str(tmp_path / "uploads")
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=60
    ) as client:
        resp = await client.post(
            "/api/v1/batch",
            data={
                "name": "recon-confined",
                "options": json.dumps(
                    {"per_order": True, "per_order_output_dir": "per_order/watch"}
                ),
            },
            files={"files": ("sample.pdf", b"%PDF-1.4 recon", "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    try:
        assert body["status"] == "pending"
        resolved = os.path.realpath(str(output_dir / "per_order" / "watch"))
        assert body["options"]["per_order_output_dir"] == resolved
        assert body["total_tasks"] == 1
    finally:
        # 单例 batch_service（runtime.py:167）store 默认 None（attach 仅在
        # startup :194，ASGITransport 不跑 lifespan）→ 无磁盘持久化，清内存即可。
        runtime.batch_service.batches.pop(body["batch_id"], None)


# ---------------------------------------------------------------------------
# R-004 T1 对账收口: the n8n import templates must only reference DocuVision
# endpoints that exist. 真源 = app.openapi() paths（与 rest-api.md 同源）。
# 提取策略（按 n8n 勘察 n8nFormat）：URL 是 n8n 表达式 "=..."；前导
# ``{{ $env.DOCUVISION_BASE_URL }}`` 段 = base-url 占位符（剥掉）；
# ``{{ $json.FIELD }}`` 段 = 上游 item 字段 → openapi 路径参数 {FIELD}
# （字段名即参数名）；其余含 ``{{`` 的段无法静态解析 → 该节点如实跳过并
# 记录（绝不硬造路径）。结构断言另含 n8n 导入契约（name+nodes+connections、
# connections 闭合、settings.executionOrder=="v1"）与回调接收节点存在性。
# ---------------------------------------------------------------------------

N8N_TEMPLATE_DIR = REPO_ROOT / "docs" / "integrations" / "n8n"
N8N_TEMPLATES = ("docuvision-v1-generic.json", "docuvision-v1.1-outlook.json")
_N8N_HTTP_TYPE = "n8n-nodes-base.httpRequest"
_N8N_BASE_URL_RE = re.compile(r"\{\{\s*\$env\.[A-Za-z_][A-Za-z0-9_]*\s*\}\}")
_N8N_JSON_FIELD_RE = re.compile(r"\{\{\s*\$json\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def _n8n_http_refs(template_path: Path) -> tuple[list[tuple[str, str]], list[str]]:
    """(resolved (METHOD, openapi-path) refs, skipped-node reports) from one template."""
    data = json.loads(template_path.read_text(encoding="utf-8"))
    refs: list[tuple[str, str]] = []
    skipped: list[str] = []
    for node in data.get("nodes", []):
        if node.get("type") != _N8N_HTTP_TYPE:
            continue  # 非 HTTP 客户端节点（trigger/webhook 接收/code 等）不在对账域
        node_name = str(node.get("name") or "<unnamed>")
        where = f"{template_path.name}/{node_name}"
        params = node.get("parameters") or {}
        raw = str(params.get("url") or "")
        if not raw.startswith("="):
            skipped.append(f"{where}: url 不是 n8n 表达式（无 = 前缀），静态策略不覆盖")
            continue
        segments = [seg.strip() for seg in raw[1:].split("/")]
        out_segments: list[str] = []
        node_skipped = False
        for seg in segments:
            if not seg:
                continue
            field = _N8N_JSON_FIELD_RE.fullmatch(seg)
            if field:
                out_segments.append("{" + field.group(1) + "}")
                continue
            if _N8N_BASE_URL_RE.fullmatch(seg):
                continue  # base-url 占位符（协议+主机部分）
            if "{{" in seg:
                skipped.append(f"{where}: 段含无法静态解析的表达式 {seg!r}")
                node_skipped = True
                break
            out_segments.append(seg)
        if node_skipped:
            continue
        path = "/" + "/".join(out_segments) if out_segments else ""
        method = str(params.get("method") or "").upper()
        if not path.startswith("/") or not method:
            skipped.append(f"{where}: 归整后非法（method={method!r} path={path!r}）")
            continue
        refs.append((method, path))
    return refs, skipped


def test_n8n_template_endpoint_refs_in_openapi() -> None:
    """两个模板的每个 HTTP Request 节点 (method, url-path) 必须命中
    app.openapi() paths；无法静态解析的节点跳过并打印（运行口径见交付 notes，
    绝不硬造）。结构层另钉 n8n 导入契约。"""
    from app.main import app

    endpoint_index = {
        (str(method).upper(), path)
        for path, methods in app.openapi().get("paths", {}).items()
        for method in methods
    }
    resolved: list[tuple[str, str, str]] = []  # (template, METHOD, path)
    unresolved: list[str] = []

    for template_name in N8N_TEMPLATES:
        template_path = N8N_TEMPLATE_DIR / template_name
        data = json.loads(template_path.read_text(encoding="utf-8"))
        for key in ("name", "nodes", "connections"):
            assert key in data, f"{template_name}: 缺顶层键 {key}（n8n 完整导入必需）"
        settings_ = data.get("settings") or {}
        assert settings_.get("executionOrder") == "v1", (
            f"{template_name}: settings.executionOrder != 'v1'"
        )
        names = {str(n.get("name")) for n in data.get("nodes", [])}
        connections = data.get("connections") or {}
        for src, groups in connections.items():
            assert src in names, f"{template_name}: connections 源 {src!r} 不在 nodes"
            for group in (groups or {}).get("main", []) or []:
                for conn in group or []:
                    target = (conn or {}).get("node")
                    assert target in names, (
                        f"{template_name}: connections 目标 {target!r} 不在 nodes"
                    )
        assert any(
            n.get("type") == "n8n-nodes-base.webhook" for n in data.get("nodes", [])
        ), f"{template_name}: 缺 webhook 回调接收节点（task.completed 订阅的对应端）"

        refs, skipped = _n8n_http_refs(template_path)
        for method, path in refs:
            assert (method, path) in endpoint_index, (
                f"{template_name}: 模板端点引用漂移 {(method, path)} 不在 OpenAPI paths"
            )
            resolved.append((template_name, method, path))
        unresolved.extend(skipped)

    assert resolved, "两个模板未解析出任何 HTTP 端点引用（提取策略失效）"
    for template_name in N8N_TEMPLATES:
        assert any(r[0] == template_name for r in resolved), (
            f"{template_name}: 无任何已解析端点引用"
        )
    if unresolved:
        # 如实申报通道：跳过节点在失败输出与 -s 模式可见，绝不硬造路径
        print("n8n 模板静态解析跳过节点（不参与 openapi 对账）:")
        for item in unresolved:
            print(f"  - {item}")
