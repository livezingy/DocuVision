"""n8n loop smoke — backend half-loop self-verification (R-004 pack §2 T4).

Ying starts the backend (``python run.py`` on :8000, pack §5 前置三件:
WEBHOOK_ENABLED=true + 非空 WEBHOOK_ADMIN_TOKEN)，然后::

    python scripts/integrations/n8n_loop_smoke.py --base-url http://localhost:8000 \
        [--file test_data/testfiles/invoices/sample-invoice.png]

Flow: built-in local HTTP receiver -> POST /api/v1/webhooks register
(callback -> receiver) -> POST /api/v1/analyze --file creates the task ->
await task.completed callback -> GET result endpoint -> assert payload
fields == governance.py 真源 -> exit 0/1. Non-pytest standalone script
(never collected; never touches pytest).

**n8n docker 侧导入实测仍按 pack §5 手动（本机无 docker，UNRUN）**——本脚本
只自证后端半环（webhook 派发 + 结果端点），不覆盖 n8n 侧。

凭据纪律: admin token 只从环境变量 ``DOCUVISION_WEBHOOK_ADMIN_TOKEN`` 读
（缺失即退出并提示，绝不硬编码/打印）；webhook secret 由脚本随机生成并
仅用于 HMAC 验签，同样零打印。

SSRF 闸现实（webhook_service.py:21-30 段表拦回环+全部私网段，注册入口
:89-90 -> 400）：同机回调地址必须公网可解析才能注册成功。实测（2026-11-15，
本机 Win32）：0.0.0.0 不在段表（注册可通过）但 Windows 连接 0.0.0.0 报
WinError 10049（派发不可达）——该缺口不可用。私网机器跑本脚本会得到
结构性诊断退出（ remediation：--callback-host 指公网可达地址，或由
Ying/AgentE 决策旁路开关后重评）。
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

DEFAULT_FILE = "test_data/testfiles/invoices/sample-invoice.png"
TOKEN_ENV = "DOCUVISION_WEBHOOK_ADMIN_TOKEN"
HOOK_PATH = "/hook"

# Mirror of webhook_service.py:21-30 — used only for LOCAL pre-diagnosis;
# the server's 400 remains ground truth.
_BLOCKED_NETS = [
    ipaddress.ip_network(n)
    for n in (
        "127.0.0.0/8", "10.0.0.0/8", "169.254.0.0/16", "192.168.0.0/16",
        "172.16.0.0/12", "::1/128", "fc00::/7", "fe80::/10",
    )
]


class _Receiver:
    """Minimal HTTP receiver capturing webhook deliveries (raw bytes + headers)."""

    def __init__(self, bind_addr: str, port: int) -> None:
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (stdlib API)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length)
                outer.capture(body, {k: v for k, v in self.headers.items()})
                payload = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):  # silence per-request stderr
                pass

        self.server = ThreadingHTTPServer((bind_addr, port), _Handler)
        self.port = self.server.server_address[1]
        self.events: list[dict] = []
        self.lock = threading.Lock()
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def capture(self, body: bytes, headers: dict) -> None:
        with self.lock:
            self.events.append({"body": body, "headers": headers})

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def snapshot(self) -> list[dict]:
        with self.lock:
            return list(self.events)


def _detect_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # UDP connect: no packet sent
        return s.getsockname()[0]
    finally:
        s.close()


def _host_resolves_private(host: str) -> bool | None:
    """True/False when the host resolves to literal IPs; None if unresolvable."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return any(ip in net for net in _BLOCKED_NETS)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return None
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if any(ip in net for net in _BLOCKED_NETS):
            return True
    return False


def _fail(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="R-004 T4 backend half-loop webhook smoke")
    parser.add_argument("--base-url", required=True, help="e.g. http://localhost:8000")
    parser.add_argument("--file", default=DEFAULT_FILE, help=f"document to analyze (default: {DEFAULT_FILE})")
    parser.add_argument("--callback-host", default=None, help="host for the callback URL (must resolve non-private from the backend)")
    parser.add_argument("--receiver-port", type=int, default=0, help="receiver port (default: ephemeral)")
    parser.add_argument("--events", default="task.completed", help="events to subscribe (default: task.completed)")
    parser.add_argument("--timeout", type=int, default=180, help="max seconds to await the callback")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        print(f"[FAIL] 环境变量 {TOKEN_ENV} 缺失/为空（注册闸②需要；生成即弃，勿进 git/日志）")
        return 1

    if not os.path.isfile(args.file):
        return _fail(f"--file 不存在: {args.file}")

    callback_host = args.callback_host or _detect_local_ip()
    if _host_resolves_private(callback_host):
        print("[FAIL] SSRF 闸结构性诊断：回调地址解析到回环/私网段，POST /api/v1/webhooks 必被 "
              "webhook_service.py:21-30/:89-90 拦为 400（同机私有地址均不可注册）。")
        print("       remediation: ① --callback-host 指向后端视角公网可达地址（云箱公网 IP 可行）；"
              "② 或 Ying/AgentE 决策旁路开关（pack §5 与闸冲突）；③ 实测 0.0.0.0 缺口不可用"
              "（注册可过但 Windows 派发 WinError 10049）。")
        return 1

    receiver = _Receiver("0.0.0.0", args.receiver_port)
    receiver.start()
    callback_url = f"http://{callback_host}:{receiver.port}{HOOK_PATH}"
    secret = os.urandom(16).hex()
    print(f"[1/7] receiver ready on :{receiver.port} (callback={callback_url}, secret=<generated, not printed>)")

    client = httpx.Client(timeout=30.0)
    subscription_id = ""
    task_id = ""
    try:
        try:
            health = client.get(f"{base}/api/v1/health")
        except httpx.HTTPError as exc:
            return _fail(f"后端不可达: {base}（先起后端 python run.py）— {type(exc).__name__}")
        if health.status_code != 200:
            return _fail(f"后端不可达/异常: GET {base}/api/v1/health -> {health.status_code}（先起后端 python run.py）")
        print(f"[2/7] preflight OK: {base}/api/v1/health -> 200")

        reg = client.post(
            f"{base}/api/v1/webhooks",
            data={"url": callback_url, "events": args.events, "secret": secret},
            headers={"X-DocuVision-Admin-Token": token},
        )
        if reg.status_code == 404:
            return _fail("注册 404：WEBHOOK_ENABLED=false（前置三件①；config.py:102-105 默认 False）")
        if reg.status_code == 401:
            return _fail("注册 401：admin token 不匹配/未配置（前置三件②；fail-closed webhooks.py:24-45；token 值不打印）")
        if reg.status_code == 400:
            detail = str(reg.json().get("detail", ""))
            if "private network" in detail:
                return _fail(f"注册 400 私网拦截（闸③ webhooks.py:89-90）：{detail} —— 见头部 SSRF 说明")
            return _fail(f"注册 400：{detail}")
        if reg.status_code != 200:
            return _fail(f"注册失败: {reg.status_code} {reg.text[:200]}")
        subscription_id = reg.json().get("subscription_id", "")
        print(f"[3/7] registered: subscription_id={subscription_id} events={args.events}")

        file_name = os.path.basename(args.file)
        mime = mimetypes.guess_type(args.file)[0] or "application/octet-stream"
        with open(args.file, "rb") as fh:
            analyze = client.post(
                f"{base}/api/v1/analyze",
                files={"file": (file_name, fh.read(), mime)},
                data={"document_type": "auto"},  # bool Form 字段不传（analyzer.py:160-161 注释：true/false 字符串会验证报错）
            )
        if analyze.status_code != 200:
            return _fail(f"analyze 失败: {analyze.status_code} {analyze.text[:200]}")
        task_id = analyze.json().get("task_id", "")
        if not task_id:
            return _fail("analyze 响应缺 task_id（analyzer.py:139 契约）")
        print(f"[4/7] task created via /api/v1/analyze: task_id={task_id} file={file_name}")

        deadline = time.time() + args.timeout
        callback = None
        final_status = ""
        while time.time() < deadline:
            for evt in receiver.snapshot():
                try:
                    body = json.loads(evt["body"].decode("utf-8"))
                except Exception:
                    continue
                if body.get("event") == "task.completed" and (body.get("payload") or {}).get("task_id") == task_id:
                    callback = {"body": body, "raw": evt["body"], "headers": evt["headers"]}
                    break
            status_resp = client.get(f"{base}/api/v1/tasks/{task_id}")
            final_status = (status_resp.json() or {}).get("status", "") if status_resp.status_code == 200 else final_status
            if callback is not None or final_status in {"completed", "failed", "cancelled"}:
                break
            time.sleep(2.0)

        if callback is None:
            if final_status == "failed":
                return _fail("任务 failed（失败路径不派发 task.completed，governance 仅 completed 派发 :120-128）——检查后端 GPU/OCR 能力")
            return _fail(f"超时 {args.timeout}s 未收到 task.completed 回调（终态={final_status or '未知'}；"
                         "查 receiver 无投递 → 派发侧被禁/订阅 events 不匹配/回调不可达）")

        print("[5/7] task.completed callback captured")
        if final_status != "completed":
            return _fail(f"对账不一致：回调已到但任务终态={final_status}（期望 completed，T2 锚 governance.py:85/:115/:120-128）")

        body = callback["body"]
        missing = [k for k in ("event", "payload", "timestamp") if k not in body]
        if missing:
            return _fail(f"信封缺字段 {missing}（真源 webhook_service.py:138）")
        payload = body["payload"] or {}
        expect = {
            "task_id": task_id,
            "file_name": file_name,
            "status": "completed",
            "validation_passed": payload.get("validation_passed"),
        }
        if payload != expect:
            return _fail(f"载荷 != governance.py:122-127 真源\n  got:    {json.dumps(payload, ensure_ascii=False)}\n  expect: {json.dumps(expect, ensure_ascii=False)}")
        if payload["validation_passed"] not in (True, False, None):
            return _fail("validation_passed 必须为 bool|null（governance.py:126）")

        sig = callback["headers"].get("X-DocuVision-Signature", "")
        expected_sig = hmac.new(secret.encode("utf-8"), callback["raw"], hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return _fail("HMAC-SHA256 验签失败（真源 webhook_service.py:145-147；secret 不打印）")
        print("[6/7] payload == governance 真源 + HMAC 验签通过 (validation_passed=%s)" % payload["validation_passed"])

        result = client.get(f"{base}/api/v1/tasks/{task_id}/result")
        if result.status_code != 200:
            return _fail(f"结果端点非 200: {result.status_code} {result.text[:200]}（result 闸 tasks_content.py:35-36）")
        if not isinstance(result.json(), dict):
            return _fail("结果端点响应非 JSON object")
        print("[7/7] GET /api/v1/tasks/%s/result -> 200 (JSON object)" % task_id)

        client.delete(f"{base}/api/v1/tasks/{task_id}")  # best-effort cleanup
        print("[PASS] backend half-loop verified: register -> dispatch -> callback -> payload -> result")
        return 0
    finally:
        client.close()
        receiver.stop()


if __name__ == "__main__":
    sys.exit(main())
