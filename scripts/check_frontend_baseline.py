#!/usr/bin/env python3
"""C0 baseline calibration gate (v1.8.3 B0) - stdlib only.

Replaces the original C0 snippet, which relied on ``sed`` / ``wc`` and therefore could
not run on the primary dev host (win32 + PowerShell). Every expectation from design
rev2 section 7 is printed as "measured vs expected"; a mismatch exits 1, so the numbers
quoted by the design cannot drift silently.

Modes:
  (default)          run every C0 check, exit 1 on mismatch
  --edges            print the cross-domain coupling tables (see frontend_coupling.py)
  --report-out=PATH  write the whole C0 snapshot (baseline table + DOM-taint evidence +
                     coupling tables) to PATH as UTF-8 - the B0a evidence trail
  --update           lower the recorded ratchets in scripts/frontend_size_allowlist.json
                     to the current measured values (never raises them; flags untouched)
  --syntax           copy every frontend/modules/**/*.js to a temp ``.mjs`` and run
                     ``node --check``; skipped (and declared) when node is unavailable

Measurement notes:
  * Lines = Python ``splitlines()`` (same metric as ``lint_file_size.py``). PowerShell
    ``(Get-Content x).Count`` under-reports frontend/app.js by 6 lines - never gate on it.
  * The boot-sequence *line number* is informational only: it drifts as soon as an
    earlier function moves, so only its length and order are asserted.
  * Preview-state writes are counted on non-declaration lines only; the design's
    "12 writes" was an under-count (see DESIGN_PREVIEW_WRITES below).
  * Coupling analysis (attribution, edge rows, state reads) lives in
    scripts/frontend_coupling.py + scripts/frontend_domain_map.json.

Exit codes: 0 = pass, 1 = mismatch, 2 = cannot evaluate.
"""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import frontend_coupling as fc

REPO_ROOT = fc.REPO_ROOT
ALLOWLIST = REPO_ROOT / "scripts" / "frontend_size_allowlist.json"
APP_JS_REL = "frontend/app.js"
APP_JS = fc.APP_JS
SHARED_DIR = REPO_ROOT / "frontend" / "shared"
PREVIEW_STATE = fc.MODULES_DIR / "preview-state.js"

DESIGN_APP_LINES = 5708
DESIGN_APP_FUNCTIONS = 145
DESIGN_BOOT_LINE = 304
# Corrected during B0a: the design said "12 writes / 6 declarations"; measured truth is
# 17 writes = 16 ``current*`` + 1 ``previewPaginationInitialized``, plus the six
# ``:895-900`` declarations. The design missed the writes inside
# renderDocumentWithAnnotations (:2947, :2957) and the pagination flag.
DESIGN_PREVIEW_WRITES = 17
DESIGN_PREVIEW_DECLS = 6

_CALL_STMT_RE = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*\(")
_CALL_KEYWORDS = {"if", "for", "while", "switch", "return", "typeof", "catch", "do", "else"}
_DECL_LINE_RE = re.compile(r"^(?:const|let|var)\s+[A-Za-z_$]")
_PREVIEW_NAMES = (
    r"current(?:TaskId|QueueItem|PreviewPage|PageImageUrl|OriginalFileUrl)"
    r"|previewPaginationInitialized"
)
_PREVIEW_WRITE_RE = re.compile(rf"\b(?:{_PREVIEW_NAMES})\s*=[^=]")
_PREVIEW_DECL_RE = re.compile(rf"^\s*(?:const|let|var)\s+(?:{_PREVIEW_NAMES})\b", re.MULTILINE)


def _load_allowlist() -> dict:
    if not ALLOWLIST.is_file():
        print(f"[baseline] missing {ALLOWLIST}", file=sys.stderr)
        raise SystemExit(2)
    return json.loads(ALLOWLIST.read_text(encoding="utf-8"))


def _count_preview_writes(text: str) -> int:
    return sum(
        1
        for line in text.splitlines()
        if not _DECL_LINE_RE.match(line.strip()) and _PREVIEW_WRITE_RE.search(line)
    )


def _boot_block(lines: list[str]) -> tuple[int | None, list[str]]:
    start = next((i for i, line in enumerate(lines) if "DOMContentLoaded" in line), None)
    if start is None:
        return None, []
    calls: list[str] = []
    for idx in range(start + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped == "});":
            break
        if not stripped or stripped.startswith("//"):
            continue
        match = _CALL_STMT_RE.match(lines[idx])
        if match and match.group(1) not in _CALL_KEYWORDS:
            calls.append(match.group(1))
    return start + 1, calls


def check_ratchet(lines: list[str], allowlist: dict) -> tuple[list[str], str]:
    failures: list[str] = []
    actual_lines = len(lines)
    fn_count = len(fc.fn_decls(lines))
    cap_lines = int(allowlist["files"].get(APP_JS_REL, 0))
    cap_fns = int(allowlist["app_js_functions"])
    print(
        f"[baseline] C1 {APP_JS_REL}: {actual_lines} lines "
        f"(ratchet cap {cap_lines}, design ref {DESIGN_APP_LINES})"
    )
    print(
        f"[baseline] C2 top-level functions: {fn_count} "
        f"(ratchet cap {cap_fns}, design ref {DESIGN_APP_FUNCTIONS})"
    )
    if actual_lines > cap_lines:
        failures.append(f"C1 {APP_JS_REL}: {actual_lines} lines > ratchet {cap_lines}")
    if fn_count > cap_fns:
        failures.append(f"C2 {APP_JS_REL}: {fn_count} functions > ratchet {cap_fns}")
    phase = "B0b+ (ESM)" if allowlist.get("app_js_module") else "B0a (pre-ESM)"
    return failures, phase


def check_boot(lines: list[str]) -> list[str]:
    start, calls = _boot_block(lines)
    if start is None:
        return ["C3 DOMContentLoaded block not found"]
    print(
        f"[baseline] C3 boot sequence at line {start} (design ref {DESIGN_BOOT_LINE}; line is "
        "informational, only length+order are asserted)"
    )
    if calls != fc.BOOT_SEQUENCE:
        missing = [n for n in fc.BOOT_SEQUENCE if n not in calls]
        extra = [n for n in calls if n not in fc.BOOT_SEQUENCE]
        return [
            f"C3 boot sequence mismatch (design={len(fc.BOOT_SEQUENCE)}, measured={len(calls)}; "
            f"missing={missing}; extra={extra})"
        ]
    defined = set(fc.fn_line_owners(lines)) | fc.imported_names(lines)
    undefined = [n for n in calls if n not in defined]
    if undefined:
        return [f"C3 boot sequence references undefined function(s): {undefined}"]
    print(f"[baseline] C3 order OK ({len(calls)} steps, all defined)")
    return []


def check_reverse_deps(lines: list[str]) -> list[str]:
    if not SHARED_DIR.is_dir():
        return []
    hits: list[tuple[str, str]] = []
    for path in sorted(SHARED_DIR.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for name in sorted(fc.fn_decls(lines)):
            if not re.search(rf"(?<![.\w$]){re.escape(name)}\b", text):
                continue
            declares = re.search(
                rf"\bfunction\s+{re.escape(name)}\b|\b(?:const|let|var)\s+{re.escape(name)}\b"
                rf"|\b{re.escape(name)}\s*[:=]",
                text,
            )
            if declares:
                continue
            hits.append((path.name, name))
    print(f"[baseline] C4 reverse dependency (app.js names x shared/*.js): {len(hits)} real hit(s)")
    if hits:
        for file_name, name in hits:
            print(f"    hit: {file_name} -> {name}")
        return [f"C4 shared/ calls app.js function(s): {hits} (a window bridge would break)"]
    return []


def check_preview_state(lines: list[str]) -> list[str]:
    text = "\n".join(lines)
    writes = _count_preview_writes(text)
    decls = len(_PREVIEW_DECL_RE.findall(text))
    if PREVIEW_STATE.is_file():
        print("[baseline] C5 preview-state module exists -> write/decl check retired")
        return []
    print(
        f"[baseline] C5 preview state sites: writes {writes} (expected {DESIGN_PREVIEW_WRITES}), "
        f"decls {decls} (expected {DESIGN_PREVIEW_DECLS})"
    )
    failures: list[str] = []
    if writes != DESIGN_PREVIEW_WRITES:
        failures.append(f"C5 preview writes {writes} != expected {DESIGN_PREVIEW_WRITES}")
    if decls != DESIGN_PREVIEW_DECLS:
        failures.append(f"C5 preview declarations {decls} != expected {DESIGN_PREVIEW_DECLS}")
    return failures


def check_utils_dom() -> list[str]:
    failures: list[str] = []
    print("[baseline] C6 DOM-taint table (utils whitelist: 0 refs except utils/dom):")
    for module, names in fc.UTILS_MODULES.items():
        for name in names:
            found = fc.locate_fn(name)
            if found is None:
                failures.append(f"C6 {name} not found in app.js or frontend/modules/**")
                print(f"    {module:<14} {name:<32} MISSING")
                continue
            path, fn_lines, lns = found
            refs = fc.dom_refs(fn_lines, lns)
            print(f"    {module:<14} {name:<32} {refs:>3} ref  {path.name}")
            if module == "utils/dom":
                if refs == 0:
                    failures.append(f"C6 utils/dom {name}: expected DOM refs > 0, got 0")
            elif refs != 0:
                failures.append(f"C6 {module} {name}: expected 0 DOM refs, got {refs}")
    return failures


def check_mime() -> list[str]:
    guessed = mimetypes.guess_type("x.js")[0] or ""
    print(f"[baseline] C7 mimetypes guess for .js: {guessed!r}")
    if "javascript" not in guessed:
        return [f"C7 static server would serve .js as {guessed!r}; ESM needs a JS type"]
    return []


def check_edges(lines: list[str]) -> list[str]:
    rows = fc.edge_rows(lines)
    pairs = {(a, c) for a, _, c, _, _ in rows}
    missing = sorted(fc.KNOWN_EDGE_PAIRS - pairs)
    extra = sorted(pairs - fc.KNOWN_EDGE_PAIRS)
    print(
        f"\n[baseline] C8 cross-domain call sites: {len(rows)} rows / {len(pairs)} domain pairs "
        "(design table: 11 sites / 9 pairs)"
    )
    for pair in sorted(pairs):
        if pair in fc.KNOWN_EDGE_PAIRS:
            tag = "known"
        elif pair[1].startswith("utils/"):
            tag = "utils (F3 whitelisted)"
        else:
            tag = "NEW  needs triage"
        print(f"    [{tag}] {pair[0]} -> {pair[1]}")
    failures: list[str] = []
    if missing:
        failures.append(f"C8 known edge pair(s) disappeared: {missing}")
    if extra:
        print(
            "    WARN: new pair(s) must be triaged into design section 5.3 + section 10 before "
            "the consuming batch closes; a domain that is only ever *called* (notifications, "
            "api-base, status-bar) is a leaf-service whitelist candidate, not an injection."
        )
    return failures


def run_report(lines: list[str], path: Path) -> int:
    allowlist = _load_allowlist()
    text = APP_JS.read_text(encoding="utf-8")
    start, calls = _boot_block(lines)
    rows = [
        ("`frontend/app.js` lines", len(lines), DESIGN_APP_LINES),
        ("top-level functions", len(fc.fn_decls(lines)), DESIGN_APP_FUNCTIONS),
        ("boot sequence line (informational)", start, DESIGN_BOOT_LINE),
        ("boot sequence steps", len(calls), len(fc.BOOT_SEQUENCE)),
        ("preview-state writes", _count_preview_writes(text), DESIGN_PREVIEW_WRITES),
        ("preview-state declarations", len(_PREVIEW_DECL_RE.findall(text)), DESIGN_PREVIEW_DECLS),
        ("`mimetypes.guess_type('x.js')`", mimetypes.guess_type("x.js")[0], "contains javascript"),
        ("app.js ratchet cap", allowlist["files"].get(APP_JS_REL), "ratchet (decreases only)"),
        ("`app_js_functions` cap", allowlist["app_js_functions"], "ratchet (decreases only)"),
        ("`app_js_module` flag", allowlist.get("app_js_module"), "B0a false -> B0b true"),
    ]
    dom_rows = []
    for module, names in fc.UTILS_MODULES.items():
        for name in names:
            found = fc.locate_fn(name)
            if found:
                p, fn_lines, lns = found
                dom_rows.append(f"| {module} | `{name}` | {fc.dom_refs(fn_lines, lns)} | {p.name} |")
    report = "\n".join(
        [
            "# v1.8.3 B0 - C0 baseline snapshot",
            "",
            "> Generated by `python scripts/check_frontend_baseline.py --report-out=<path>`.",
            "> Line metric = Python `read_text().splitlines()`; never `(Get-Content).Count`.",
            "",
            "| item | measured | expected (design rev2) |",
            "|---|---|---|",
            *[f"| {n} | {m} | {e} |" for n, m, e in rows],
            "",
            "## utils DOM-taint evidence",
            "",
            "| module | function | `document.`/`window.` refs | file |",
            "|---|---|---|---|",
            *dom_rows,
            "",
            fc.render_edges(lines),
        ]
    )
    path.write_text(report + "\n", encoding="utf-8")
    print(f"[report] wrote {path}")
    return 0


def run_update(lines: list[str]) -> int:
    allowlist = _load_allowlist()
    actual_lines = len(lines)
    fn_count = len(fc.fn_decls(lines))
    lowered = False
    if actual_lines < int(allowlist["files"].get(APP_JS_REL, 0)):
        print(f"[lowered] {APP_JS_REL}: {allowlist['files'][APP_JS_REL]} -> {actual_lines}")
        allowlist["files"][APP_JS_REL] = actual_lines
        lowered = True
    if fn_count < int(allowlist["app_js_functions"]):
        print(f"[lowered] app_js_functions: {allowlist['app_js_functions']} -> {fn_count}")
        allowlist["app_js_functions"] = fn_count
        lowered = True
    ALLOWLIST.write_text(json.dumps(allowlist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[baseline] allowlist {'updated' if lowered else 'unchanged'}")
    return 0


def run_syntax() -> int:
    files = fc.module_files()
    if not files:
        print("[syntax] no frontend/modules/**/*.js yet - nothing to check")
        return 0
    if shutil.which("node") is None:
        print("[syntax] node not available -> SKIPPED (declared, not verified)")
        return 0
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in files:
            target = Path(tmp) / (path.stem + ".mjs")
            target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            proc = subprocess.run(["node", "--check", str(target)], capture_output=True, text=True)
            rel = path.relative_to(REPO_ROOT).as_posix()
            print(f"[syntax] {rel:<48} {'ok' if proc.returncode == 0 else 'FAIL'}")
            if proc.returncode != 0:
                failures.append(f"{rel}: {proc.stderr.strip()[:400]}")
    if failures:
        for item in failures:
            print(f"[FAIL] {item}")
        print(f"[syntax] {len(failures)} file(s) failed")
        return 1
    print(f"[syntax] OK ({len(files)} module file(s))")
    return 0


def main(argv: list[str]) -> int:
    lines = fc.app_lines()
    for arg in argv:
        if arg.startswith("--report-out="):
            return run_report(lines, Path(arg.split("=", 1)[1]))
    if "--edges" in argv:
        print(fc.render_edges(lines))
        return 0
    if "--update" in argv:
        return run_update(lines)
    if "--syntax" in argv:
        return run_syntax()

    allowlist = _load_allowlist()
    failures: list[str] = []
    ratchet_failures, phase = check_ratchet(lines, allowlist)
    failures += ratchet_failures
    failures += check_boot(lines)
    failures += check_reverse_deps(lines)
    failures += check_preview_state(lines)
    failures += check_utils_dom()
    failures += check_mime()
    failures += check_edges(lines)
    print(f"\n[baseline] phase = {phase}")

    if failures:
        print()
        for item in failures:
            print(f"[FAIL] {item}")
        print(f"[baseline] {len(failures)} mismatch(es)")
        return 1
    print("[baseline] OK (C1-C8 all match the design)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
