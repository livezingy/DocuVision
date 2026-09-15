#!/usr/bin/env python3
"""Frontend coupling analysis (v1.8.3) - stdlib only, library module.

Shared by ``scripts/check_frontend_baseline.py`` (C0 gate + edge export) and kept in
its own module so both files stay inside the 500-line script budget.

Data - domain->function map, state owners, boot sequence, module import whitelist,
known cross-domain edges - lives in ``scripts/frontend_domain_map.json`` so a triage
decision (for example promoting notifications/api-base to leaf-service modules in
B1) is a data edit instead of a code edit.

Attribution model: the file is partitioned at every top-level chunk start (a column-0
line beginning with an identifier: ``function f() {``, ``const X = ...``, or the
``document.addEventListener('DOMContentLoaded' ...)`` block). Only function chunks own
per-function lines, so top-level assembly code can never be mis-attributed to the
function above it - that bug inflated the first edge scan from 53 to 232 rows.

This is a line heuristic, not a JS parser. It is exact enough for call-site and read
counting and it reproduces the design's giant-function start lines.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOMAIN_MAP = REPO_ROOT / "scripts" / "frontend_domain_map.json"
APP_JS = REPO_ROOT / "frontend" / "app.js"
MODULES_DIR = REPO_ROOT / "frontend" / "modules"

DEFAULT_IMPORT_WHITELIST: dict[str, list[str]] = {
    "dirs": ["frontend/modules/utils/"],
    "files": ["frontend/modules/preview-state.js"],
    "prefixes": ["frontend/shared/"],
}

_FN_DECL_RE = re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")
_CHUNK_START_RE = re.compile(r"^[A-Za-z_$]")
_CALL_SITE_RE = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(")
_DOM_RE = re.compile(r"(?<![.\w$])(document|window)\s*\.")


def load_data() -> dict:
    if not DOMAIN_MAP.is_file():
        print(f"[frontend_coupling] missing {DOMAIN_MAP}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(DOMAIN_MAP.read_text(encoding="utf-8"))


DATA = load_data()
FRONTEND_DOMAINS: dict[str, list[str]] = DATA["domains"]
UTILS_MODULES: dict[str, list[str]] = DATA["utils_modules"]
STATE_OWNERS: dict[str, list[str]] = DATA["state_owners"]
BOOT_SEQUENCE: list[str] = DATA["boot_sequence"]
KNOWN_EDGE_PAIRS = {tuple(pair) for pair in DATA["known_edge_pairs"]}
IMPORT_WHITELIST: dict[str, list[str]] = DATA.get(
    "module_import_whitelist", DEFAULT_IMPORT_WHITELIST
)
DOMAINS: dict[str, list[str]] = {**FRONTEND_DOMAINS, **UTILS_MODULES}
NAME_TO_DOMAIN = {name: dom for dom, names in DOMAINS.items() for name in names}
STATE_OWNER = {name: dom for dom, names in STATE_OWNERS.items() for name in names}


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def app_lines() -> list[str]:
    if not APP_JS.is_file():
        print(f"[frontend_coupling] {APP_JS} not found", file=sys.stderr)
        raise SystemExit(2)
    return read_lines(APP_JS)


def fn_decls(lines: list[str]) -> dict[str, int]:
    """Column-0 function declarations as name -> 0-based line index."""
    out: dict[str, int] = {}
    for idx, line in enumerate(lines):
        if not line or line[0] in " \t":
            continue
        match = _FN_DECL_RE.match(line)
        if match:
            out[match.group(1)] = idx
    return out


def chunk_starts(lines: list[str]) -> list[int]:
    """Column-0 lines that begin a new top-level chunk (declaration or statement)."""
    return [i for i, line in enumerate(lines) if line and _CHUNK_START_RE.match(line)]


def fn_line_owners(lines: list[str]) -> dict[str, list[int]]:
    """Map top-level function name -> the 1-based lines it owns."""
    decls = fn_decls(lines)
    starts = chunk_starts(lines)
    owners: dict[str, list[int]] = {}
    for name, idx in decls.items():
        nxt = next((s for s in starts if s > idx), None)
        end = nxt - 1 if nxt is not None else len(lines) - 1
        owners[name] = list(range(idx + 1, end + 2))
    return owners


def dom_refs(lines: list[str], lns: list[int]) -> int:
    return sum(len(_DOM_RE.findall(lines[ln - 1])) for ln in lns if 0 < ln <= len(lines))


def module_files() -> list[Path]:
    if not MODULES_DIR.is_dir():
        return []
    return sorted(p for p in MODULES_DIR.rglob("*.js") if "node_modules" not in p.parts)


def locate_fn(name: str) -> tuple[Path, list[str], list[int]] | None:
    """Find a top-level function in app.js or, once moved, in frontend/modules/**."""
    for path in [APP_JS, *module_files()]:
        if not path.is_file():
            continue
        lines = read_lines(path)
        lns = fn_line_owners(lines).get(name)
        if lns:
            return path, lines, lns
    return None


def edge_rows(lines: list[str]) -> list[tuple[str, str, str, str, int]]:
    """Cross-domain call rows: (caller domain, caller fn, callee domain, callee fn, line)."""
    rows: list[tuple[str, str, str, str, int]] = []
    for caller_fn, lns in fn_line_owners(lines).items():
        caller_domain = NAME_TO_DOMAIN.get(caller_fn)
        if caller_domain is None:
            continue
        for ln in lns:
            raw = lines[ln - 1]
            if raw.strip().startswith(("//", "*")):
                continue
            for match in _CALL_SITE_RE.finditer(raw):
                callee = match.group(1)
                callee_domain = NAME_TO_DOMAIN.get(callee)
                if callee_domain is None or callee_domain == caller_domain or callee == caller_fn:
                    continue
                rows.append((caller_domain, caller_fn, callee_domain, callee, ln))
    return rows


def state_read_rows(lines: list[str]) -> list[tuple[str, str, str, str, int]]:
    """Cross-domain state reads: (owner domain, state, reader domain, reader fn, line)."""
    decl_line = re.compile(r"^(?:const|let|var)\s+[A-Za-z_$]")
    rows: list[tuple[str, str, str, str, int]] = []
    for reader_fn, lns in fn_line_owners(lines).items():
        reader_domain = NAME_TO_DOMAIN.get(reader_fn)
        if reader_domain is None:
            continue
        for ln in lns:
            raw = lines[ln - 1]
            stripped = raw.strip()
            if stripped.startswith(("//", "*", "/*")) or decl_line.match(stripped):
                continue
            for state, owner_domain in STATE_OWNER.items():
                if owner_domain == reader_domain:
                    continue
                if re.search(rf"(?<![.\w$]){re.escape(state)}\b(?!\s*=[^=])", raw):
                    rows.append((owner_domain, state, reader_domain, reader_fn, ln))
    return rows


def render_edges(lines: list[str]) -> str:
    """Markdown coupling report: totals + pair summary + call sites + state reads."""
    rows = edge_rows(lines)
    state_rows = state_read_rows(lines)
    counts: dict[tuple[str, str], int] = {}
    for caller, _, callee, _, _ in rows:
        counts[(caller, callee)] = counts.get((caller, callee), 0) + 1
    out = [
        f"Totals: {len(rows)} call row(s) / {len(counts)} domain pair(s), "
        f"{len(state_rows)} cross-domain state read(s).",
        "",
        "## Domain pair summary",
        "",
        "| caller domain | callee domain | call sites |",
        "|---|---|---|",
        *[f"| {a} | {c} | {n} |" for (a, c), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))],
        "",
        "## Cross-domain call sites",
        "",
        "| caller domain | caller function | callee domain | callee function | line |",
        "|---|---|---|---|---|",
        *[f"| {a} | `{fn}` | {c} | `{callee}` | {ln} |" for a, fn, c, callee, ln in sorted(rows)],
        "",
        "## Cross-domain state reads",
        "",
        "| owner domain | state | reader domain | reader function | line |",
        "|---|---|---|---|---|",
        *[f"| {o} | `{s}` | {r} | `{fn}` | {ln} |" for o, s, r, fn, ln in sorted(state_rows)],
    ]
    return "\n".join(out) + "\n"
