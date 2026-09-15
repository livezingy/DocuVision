#!/usr/bin/env python3
"""Static file server for the Playwright UI e2e suite (FRONT-U1).

Why not ``python -m http.server``: that is a ThreadingHTTPServer, but ``socketserver``'s
default accept backlog is **5**. The app loads ~12 files per page (index.html, 7 modules,
shared scripts, css) and Playwright's default worker count is cores/2 - on this 20-core
host that is 10 browsers, i.e. 100+ near-simultaneous connections. The backlog overflows,
the kernel refuses connections, and ``app.js`` itself fails to load in some pages:

    [requestfailed] .../app.js?v=20260915-b0b :: net::ERR_CONNECTION_REFUSED

Measured 2026-09-15 on the B0b baseline: 2 of 14 tests failed per parallel run (12 passed);
on B1a 3-6 of 14, with a different set each time; serial runs were always 14/14. In the
failing pages ``#documentPage`` still held the raw index.html placeholder comment, i.e. the
app had never booted at all - which is why clicks appeared to "do nothing".

Raising the accept backlog fixes the cause instead of hiding it. ``allow_reuse_address``
keeps back-to-back Playwright runs from tripping over TIME_WAIT sockets.

Usage: python scripts/e2e_static_server.py [port]   (serves the repository root)
"""

from __future__ import annotations

import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKLOG = 256


class QuietHandler(SimpleHTTPRequestHandler):
    """Serve files without the per-request log spam."""

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003 - stdlib signature
        return


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = BACKLOG
    allow_reuse_address = True


def main(argv: list[str]) -> int:
    port = int(argv[1]) if len(argv) > 1 else 8000
    handler = functools.partial(QuietHandler, directory=str(REPO_ROOT))
    with Server(("127.0.0.1", port), handler) as httpd:
        print(
            f"[e2e_static_server] serving {REPO_ROOT} on http://127.0.0.1:{port} "
            f"(backlog={BACKLOG})",
            flush=True,
        )
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
