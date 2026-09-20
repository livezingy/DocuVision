#!/usr/bin/env python3
"""Frontend structure lint (v1.8.3 B0) - stdlib only; never imports application code.

Rules (design rev2 section 6 / DEVELOPMENT.md frontend rules):

  F1  line budget     ``frontend/app.js`` + ``frontend/modules/**`` +
                      ``frontend/shared/**`` (``frontend/tests/`` exempt) over the
                      budget, or over the recorded per-file cap -> violation.
  F2  entry ratchet   top-level ``function`` / ``async function`` count of
                      ``frontend/app.js`` must not exceed ``app_js_functions``
                      (the mechanism behind "new UI functions never go back into
                      app.js").
  F3  import direction ``frontend/modules/**`` may not import ``../app.js`` and may
                      not import a sibling domain module. Allowed relative targets
                      are ``frontend/modules/utils/*``, the registered whitelist files
                      and ``frontend/shared/*`` (bare specifiers are rejected too).
                      Since the B-decision (2026-09-15) one more target is allowed:
                      a **same-directory sibling inside a domain sub-directory**
                      (``frontend/modules/<domain>/*.js`` may import its own directory
                      siblings). The ``frontend/modules`` root is excluded, or true
                      cross-domain pairs would pass too. Leaf-service L1 stays intact
                      because F5 checks registered modules independently of F3.
  F4  assembly shape  ``index.html`` keeps exactly one entry (``app.js``); no module
                      file may appear in ``index.html``; only the known legacy
                      classic scripts may stay. The entry ``type="module"``
                      conversion and the dead-code removal are gated by phase flags
                      (``app_js_module`` / ``panel_resize_removed``) so that the B0a
                      batch stays green before B0b / B1 flip them.
  F5  leaf services   every ``module_import_whitelist.files`` entry must be registered
                      in ``leaf_services`` / ``shared_state_modules`` with a date and
                      evidence, and **either** kind of registered module may reach
                      ``frontend/modules/utils/`` and ``frontend/shared/`` only (L1); so
                      the whitelist cannot grow silently nor can a registered module hub.
  F6  assembly        every ``export function initXxx`` in ``frontend/modules/**``
                      completeness  must be invoked from ``frontend/app.js`` (a forgotten init
                      call leaves the module's injected deps as stubs - runtime no-op
                      that no other static gate catches).
  F7  orphan modules  every ``frontend/modules/**`` file must be imported by ``app.js``,
                      ``index.html`` or another script (P-008: floating-progress.js was
                      unreachable since v1.8.2 and nothing noticed). An acknowledged orphan
                      is *registered* in ``known_orphans`` with a date - never auto-wired.

Line counts use ``str.splitlines()`` - same metric as ``lint_file_size.py`` (never
PowerShell ``(Get-Content x).Count``: it under-reported ``frontend/app.js`` by 6 lines,
measured 2026-09-15). Enumeration is ``git ls-files --cached --others --exclude-standard``
minus index-only entries: git still lists a path whose deletion is staged but not
committed, and no gate can read it (F6 used to crash, F7 called it an orphan).

Exit codes: 0 = pass, 1 = violations, 2 = cannot evaluate.
"""

from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ALLOWLIST = REPO_ROOT / "scripts" / "frontend_size_allowlist.json"
DOMAIN_MAP = REPO_ROOT / "scripts" / "frontend_domain_map.json"

ENTRY = "frontend/app.js"
INDEX_HTML = "frontend/index.html"
MODULES_PREFIX = "frontend/modules/"
SHARED_PREFIX = "frontend/shared/"
TESTS_PREFIX = "frontend/tests/"
DEFAULT_BUDGET = 500

# Legacy classic scripts that may stay in index.html during the strangler batches.
# B1 removes shared/notifications.js; B5a removes the inline queue_preview bridge.
ALLOWED_INDEX_SCRIPTS = {
    "app.js",
    "shared/trial-key.js",
    "shared/ui-features.js",
    "shared/demo-postprocess.js",
    "shared/export-ui.js",
}
ALLOWED_INLINE_IMPORTS = {
    "./shared/queue_preview.js",
}
# Fallback when the shared domain map is unavailable; the live values come from
# scripts/frontend_domain_map.json so a whitelist decision (e.g. promoting
# notifications / api-base to leaf-service modules in B1) is a data edit, not a code edit.
IMPORT_DIR_WHITELIST = ("frontend/modules/utils/",)
IMPORT_FILE_WHITELIST = ("frontend/modules/preview-state.js",)
IMPORT_PREFIX_WHITELIST = ("frontend/shared/",)
DEAD_CODE = "frontend/shared/panel-resize.js"


_DOMAIN_MAP_CACHE: dict | None = None


def _domain_map() -> dict:
    """Parsed ``scripts/frontend_domain_map.json`` (empty dict when unreadable)."""
    global _DOMAIN_MAP_CACHE
    if _DOMAIN_MAP_CACHE is None:
        try:
            _DOMAIN_MAP_CACHE = json.loads(DOMAIN_MAP.read_text(encoding="utf-8"))
        except Exception:
            _DOMAIN_MAP_CACHE = {}
    return _DOMAIN_MAP_CACHE


def _import_whitelist() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    entry = _domain_map().get("module_import_whitelist") or {}
    return (
        tuple(entry.get("dirs", IMPORT_DIR_WHITELIST)),
        tuple(entry.get("files", IMPORT_FILE_WHITELIST)),
        tuple(entry.get("prefixes", IMPORT_PREFIX_WHITELIST)),
    )


def _iter_imports(rel: str):
    """Yield ``(lineno, spec, repo-relative target)`` per static import in a file.

    The whole file is scanned, not line by line: a named ``import { a, b } from "..."``
    may span lines, and a line-wise scan misses those - hiding F3 violations and calling
    11 of 33 wired modules orphans (measured 2026-09-17). Comment lines are skipped.
    ``target`` is ``None`` for bare specifiers.
    """
    path = REPO_ROOT / rel
    if not path.is_file():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    text = "\n".join(lines)
    for match in _IMPORT_RE.finditer(text):
        lineno = text.count("\n", 0, match.start()) + 1
        if lines[lineno - 1].strip().startswith(("//", "*")):
            continue
        spec = match.group(1)
        if not spec.startswith("."):
            yield lineno, spec, None
            continue
        yield lineno, spec, posixpath.normpath(posixpath.join(posixpath.dirname(rel), spec))

_FN_RE = re.compile(r"^(?:async\s+)?function\s+[A-Za-z_$][\w$]*", re.MULTILINE)
_SCRIPT_RE = re.compile(r"<script\b([^>]*)>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_SRC_RE = re.compile(r"""\bsrc\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_TYPE_RE = re.compile(r"""\btype\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
# DOTALL: ``} from "..."`` (import continuation) must resolve like a one-line import.
_IMPORT_RE = re.compile(
    r"""(?:\bimport\s*(?:[^;'"]*?\bfrom\s*)?|\bfrom\s*)["']([^"']+)["']""", re.DOTALL
)


def _load_allowlist() -> dict:
    if not ALLOWLIST.is_file():
        print(f"[lint_frontend] allowlist not found: {ALLOWLIST}", file=sys.stderr)
        raise SystemExit(2)
    data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    data.setdefault("budget", DEFAULT_BUDGET)
    data.setdefault("files", {})
    data.setdefault("app_js_functions", 0)
    data.setdefault("app_js_module", False)
    data.setdefault("panel_resize_removed", False)
    return data


def _tracked_files() -> tuple[list[str], str]:
    """Return (repo-relative posix paths, mode) of frontend/** files to lint.

    ``--cached --others --exclude-standard`` = tracked files plus untracked files that
    are not ignored. A brand new module must be linted *before* it is `git add`-ed,
    otherwise F1/F3 silently skip it (that blind spot was hit while landing B0b);
    node_modules and other ignored paths stay out either way. Index-only entries (a
    staged-but-uncommitted deletion) are dropped too, with a printed count - see below.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "frontend"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [p for p in proc.stdout.split("\0") if p]
        present = [p for p in paths if (REPO_ROOT / p).is_file()]
        if len(present) != len(paths):
            print(f"[lint_frontend] skipping {len(paths) - len(present)} staged-deletion path(s) "
                  "- not committed yet, re-run after the commit")
        return present, "git"
    except Exception:
        base = REPO_ROOT / "frontend"
        files = [
            p.relative_to(REPO_ROOT).as_posix()
            for p in base.rglob("*")
            if p.is_file() and "node_modules" not in p.parts
        ]
        return sorted(files), "fs"


def _in_scope(path: str) -> bool:
    if path == ENTRY:
        return True
    if path.startswith(TESTS_PREFIX):
        return False
    if path.endswith(".js") and (path.startswith(MODULES_PREFIX) or path.startswith(SHARED_PREFIX)):
        return True
    return False


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _module_js(paths: list[str]) -> list[str]:
    """Sorted ``frontend/modules/**`` JS paths of an already-filtered file list."""
    return sorted(p for p in paths if p.startswith(MODULES_PREFIX) and p.endswith(".js"))


def check_f1(allowlist: dict, tracked: list[str]) -> list[str]:
    """Line budget + per-file ratchet for frontend sources."""
    budget = int(allowlist["budget"])
    recorded = dict(allowlist["files"])
    violations: list[str] = []
    checked = 0
    for rel in sorted(tracked):
        if not _in_scope(rel):
            continue
        path = REPO_ROOT / rel
        checked += 1
        n = _count_lines(path)
        cap = recorded.get(rel)
        if cap is None:
            if n > budget:
                violations.append(f"F1 {rel}: {n} lines > budget {budget}")
        elif n > cap:
            violations.append(f"F1 {rel}: {n} lines > allowlist {cap}")
    print(f"[lint_frontend] F1 scanned {checked} frontend file(s) (budget={budget})")
    return violations


def check_f2(allowlist: dict) -> list[str]:
    """Entry ratchet: top-level function count must not grow."""
    path = REPO_ROOT / ENTRY
    if not path.is_file():
        return [f"F2 {ENTRY} missing"]
    n = len(_FN_RE.findall(path.read_text(encoding="utf-8")))
    cap = int(allowlist["app_js_functions"])
    print(f"[lint_frontend] F2 {ENTRY}: {n} top-level function(s), cap {cap}")
    if n > cap:
        return [f"F2 {ENTRY}: {n} top-level functions > allowlist {cap}"]
    return []


def check_f3(tracked: list[str]) -> list[str]:
    """Import direction inside frontend/modules/**.

    Allowed targets: the data-driven whitelist (utils/ + registered files + shared/)
    and - since the B-decision - same-directory siblings inside a domain
    sub-directory. The ``frontend/modules`` root is deliberately excluded from the
    sibling rule so true cross-domain pairs (options-dialog <-> kie-mapping) stay
    red; leaf-service L1 is unaffected because F5 validates registered modules
    independently of this whitelist.
    """
    dirs, files, prefixes = _import_whitelist()
    violations: list[str] = []
    checked = 0
    for rel in _module_js(tracked):
        checked += 1
        for lineno, spec, target in _iter_imports(rel):
            if target is None:
                violations.append(f"F3 {rel}:{lineno} bare specifier '{spec}' not allowed")
                continue
            if target == ENTRY:
                violations.append(f"F3 {rel}:{lineno} imports the entry '{spec}'")
                continue
            if target.startswith(dirs) or target in files or target.startswith(prefixes):
                continue
            src_dir = posixpath.dirname(rel)
            if src_dir != MODULES_PREFIX.rstrip("/") and posixpath.dirname(target) == src_dir:
                # Same-domain-directory sibling: a sub-directory is the file boundary
                # of one domain, so its own files may import each other. The modules
                # root is excluded above - otherwise cross-domain pairs would pass.
                continue
            violations.append(
                f"F3 {rel}:{lineno} sibling-domain import '{spec}' -> {target} "
                "(use app.js dependency injection instead)"
            )
    print(f"[lint_frontend] F3 scanned {checked} module file(s)")
    return violations


def check_f4(allowlist: dict) -> list[str]:
    """Assembly shape of frontend/index.html + phase flags."""
    html_path = REPO_ROOT / INDEX_HTML
    if not html_path.is_file():
        return [f"F4 {INDEX_HTML} missing"]
    html = html_path.read_text(encoding="utf-8")
    violations: list[str] = []
    entries: list[str] = []
    entry_is_module = False

    for attrs, inner in _SCRIPT_RE.findall(html):
        src_match = _SRC_RE.search(attrs)
        type_match = _TYPE_RE.search(attrs)
        script_type = (type_match.group(1) if type_match else "").strip().lower()
        if not src_match:
            if script_type == "module":
                for spec in _IMPORT_RE.findall(inner):
                    if spec not in ALLOWED_INLINE_IMPORTS:
                        violations.append(
                            f"F4 {INDEX_HTML} inline module imports unlisted '{spec}'"
                        )
                    if MODULES_PREFIX in spec:
                        violations.append(
                            f"F4 {INDEX_HTML} inline module imports module file '{spec}'"
                        )
            continue
        raw = src_match.group(1).strip()
        if raw.startswith(("http://", "https://", "//")):
            # External CDN asset (katex); never a locally served module file.
            continue
        clean = raw.split("?", 1)[0].lstrip("./")
        if MODULES_PREFIX in clean:
            violations.append(f"F4 {INDEX_HTML} loads module file '{raw}' (must go through app.js)")
        if clean not in ALLOWED_INDEX_SCRIPTS:
            violations.append(f"F4 {INDEX_HTML} unexpected script src '{raw}'")
        if clean == "app.js":
            entries.append(raw)
            entry_is_module = script_type == "module"

    if len(entries) != 1:
        violations.append(f"F4 {INDEX_HTML} must load app.js exactly once (found {len(entries)})")

    flag = bool(allowlist["app_js_module"])
    if entry_is_module != flag:
        violations.append(
            f"F4 {INDEX_HTML}: entry type=\"module\" is {entry_is_module} "
            f"but allowlist app_js_module is {flag}"
        )

    removed = bool(allowlist["panel_resize_removed"])
    exists = (REPO_ROOT / DEAD_CODE).is_file()
    if removed and exists:
        violations.append(f"F4 {DEAD_CODE} still exists (panel_resize_removed=true)")
    if not removed and exists:
        print(f"[lint_frontend] F4 {DEAD_CODE} still present (phase flag false) - removal lands in B1")

    print(
        f"[lint_frontend] F4 entry type=module={entry_is_module} "
        f"(flag={flag}), dead-code removed={removed}"
    )
    return violations


def check_f5(tracked: list[str]) -> list[str]:
    """Leaf-service registry: whitelist entries must be registered *and* justified.

    Three mechanical guards, so the whitelist cannot creep and a leaf service can
    never become a hub (which is what keeps cycles impossible):

      F5a  every ``module_import_whitelist.files`` entry is registered below;
      F5b  **any** registered module (leaf service or shared-state) reaches ``utils/``
           + ``shared/`` only (L1) - closing the "register it as shared-state to skip
           L1" loophole;
      F5c  every registration carries ``added`` + ``evidence`` (+ ``criterion`` for
           leaf services), so widening the whitelist is never free.
    """
    data = _domain_map()
    whitelist = data.get("module_import_whitelist") or {}
    allowed_files = tuple(whitelist.get("files", ()))
    allowed_dirs = tuple(whitelist.get("dirs", ()))
    allowed_prefixes = tuple(whitelist.get("prefixes", ()))
    marker = str((data.get("whitelist_policy") or {}).get("criterion_marker", "L1+L2+L3"))
    registry: dict[str, tuple[str, dict]] = {}
    for kind in ("shared_state_modules", "leaf_services"):
        for rel, meta in (data.get(kind) or {}).items():
            registry[rel] = (kind, meta if isinstance(meta, dict) else {})
    violations: list[str] = []

    for rel in allowed_files:
        if rel not in registry:
            violations.append(
                f"F5 {rel}: whitelisted in module_import_whitelist.files but not registered "
                "in leaf_services / shared_state_modules"
            )

    for rel, (kind, _meta) in sorted(registry.items()):
        label = kind[:-1]  # leaf_service / shared_state_module
        if not rel.startswith(MODULES_PREFIX):
            violations.append(f"F5 {rel}: a registered {label} must live under {MODULES_PREFIX}")
            continue
        for lineno, spec, target in _iter_imports(rel):
            if target is None:
                violations.append(
                    f"F5 {rel}:{lineno} bare specifier '{spec}' not allowed in a registered module"
                )
                continue
            if target.startswith(allowed_dirs) or target.startswith(allowed_prefixes):
                continue
            violations.append(
                f"F5 {rel}:{lineno} {label} imports '{spec}' -> {target} "
                "(L1: utils/ and shared/ only - not a module, not another registered module)"
            )

    for rel, (kind, meta) in sorted(registry.items()):
        missing = [k for k in ("added", "evidence") if not str(meta.get(k, "")).strip()]
        if kind == "leaf_services" and str(meta.get("criterion", "")) != marker:
            missing.append(f"criterion {marker!r} (got {meta.get('criterion')!r})")
        if missing:
            violations.append(f"F5 {rel}: incomplete registration - {'; '.join(missing)}")

    leaves = sum(1 for kind, _ in registry.values() if kind == "leaf_services")
    print(
        f"[lint_frontend] F5 registry: {leaves} leaf service(s) / {len(registry)} registered, "
        f"{len(allowed_files)} whitelisted file(s) over {len(tracked)} scanned path(s)"
    )
    return violations


def check_f6(tracked: list[str]) -> list[str]:
    """Assembly completeness: every module-exported ``initXxx`` must be wired in app.js.

    Weak invariant (B5a): with the injection architecture, a module whose ``initXxx``
    is never called from app.js silently no-ops at runtime - its module-level deps
    stay stubs and the first user interaction that reaches them throws. This closes
    the failure mode the dependency-wiring design is most exposed to (a forgotten
    init call survives ``node --check``, lint F1-F5/F7 and C1-C8; only e2e would trip,
    late and with poor attribution). Name-based on purpose: deps completeness is a
    runtime property, but "an init exists and is never invoked" is static and the
    high-signal half of the risk.
    """
    violations: list[str] = []
    entry_text = (REPO_ROOT / ENTRY).read_text(encoding="utf-8")
    checked = 0
    for rel in _module_js(tracked):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for m in re.finditer(
            r"^export\s+(?:async\s+)?function\s+(init[A-Za-z_$][\w$]*)", text, re.MULTILINE
        ):
            checked += 1
            name = m.group(1)
            if not re.search(r"\b" + name + r"\b", entry_text):
                violations.append(
                    f"{rel}: exports {name} but {ENTRY} never calls it "
                    "(assembly completeness - wire it in the boot sequence or the wiring block)"
                )
    print(f"[lint_frontend] F6 checked {checked} init export(s)")
    return violations


def check_f7(tracked: list[str]) -> list[str]:
    """Orphan reachability: a ``modules/**`` file must be imported by a loaded script.

    Sources = ``app.js`` + ``index.html`` + every ``modules/``/``shared/`` script.
    ``known_orphans`` only *records* an acknowledged orphan; wiring it is a behaviour
    change (v1.9 decision, P-008) and never part of a structure-only lint fix.
    """
    referenced: set[str] = set()
    for rel in [ENTRY, INDEX_HTML, *tracked]:
        scannable = rel.endswith(".js") and (
            rel.startswith(MODULES_PREFIX) or rel.startswith(SHARED_PREFIX))
        if rel not in (ENTRY, INDEX_HTML) and not scannable:
            continue
        referenced.update(t for _lineno, _spec, t in _iter_imports(rel) if t)
    known = set(_domain_map().get("known_orphans") or {})
    violations = [
        f"F7 {rel}: orphan module (imported nowhere, not in known_orphans)"
        for rel in _module_js(tracked)
        if rel not in referenced and rel not in known
    ]
    print(f"[lint_frontend] F7 {len(referenced)} target(s), {len(known)} known orphan(s)")
    return violations


def main() -> int:
    allowlist = _load_allowlist()
    tracked, mode = _tracked_files()
    print(f"[lint_frontend] enumerating frontend files (mode={mode})")

    violations: list[str] = []
    violations += check_f1(allowlist, tracked)
    violations += check_f2(allowlist)
    violations += check_f3(tracked)
    violations += check_f4(allowlist)
    violations += check_f5(tracked)
    violations += check_f6(tracked)
    violations += check_f7(tracked)

    if violations:
        for v in violations:
            print(f"[FAIL] {v}")
        print(f"[lint_frontend] {len(violations)} violation(s)")
        return 1
    print(
        "[lint_frontend] OK (F1 line budget / F2 entry ratchet / F3 import direction / "
        "F4 assembly shape / F5 leaf-service registry / F6 assembly completeness / F7)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
