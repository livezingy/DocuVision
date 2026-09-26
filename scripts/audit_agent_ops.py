#!/usr/bin/env python3
"""Unified agent-ops audit: agent-rules + living-doc + retired-refs + module-map + test-registry.

check 4 = registry reconciliation; check 5 = test stub scope (P-023, no module-level
``sys.modules[...]`` write in ``backend/tests/**``); E2 = unit-suite pin (``scripts/unit_suite_pin.py``,
so deleting a vitest spec or adding ``it.todo`` cannot shrink protection silently).

1. agent-rules drift: a generated copy must match the kernel (`sync_agent_rules.py --check`) -> ERROR.
2. doc references (`scripts/docs_refs_audit.py`, own module = this file keeps its budget):
   living-doc path drift -> WARN; a retired path/port/command in outward-facing docs -> ERROR;
   decision-log entry metadata + 90-day `landed` staleness (DOC-3, P-025) -> ERROR/WARN.
3. module-map recon (P-004): module-map.md vs its fact sources - routers/*.py counts (AST, frozen 55),
   frontend_domain_map.json (domains / leaf services / shared state / boot sequence + A6 orphan staleness
   -> WARN), gate-table symbols, README/doc-sync registration, CHANGELOG freshness; fail-closed (A0).
4. test-registry recon (P-008): `scripts/test_registry_audit.py` (own module = this file keeps its budget).
Usage: python scripts/audit_agent_ops.py [--json | --selftest] - exit 1 on any ERROR.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))

import docs_refs_audit as docs_refs  # noqa: E402
import frontend_coupling as frontend_map  # noqa: E402
import sync_agent_rules as sync_mod  # noqa: E402
import test_registry_audit as test_registry  # noqa: E402
import unit_suite_pin as unit_pin  # noqa: E402

REPO_ROOT = sync_mod.REPO_ROOT

# --- module-map reconciliation (P-004, check 3) -----------------------------

MODULE_MAP_REL = "docs/architecture/module-map.md"
ANCHOR_BACKEND = "<!-- audit:backend-domains -->"
ANCHOR_FRONTEND = "<!-- audit:frontend-domains -->"
ANCHOR_GATES = "<!-- audit:gates -->"

# Same shape as docs_refs_audit.PATH_REF_RE but with the map's prefix set (packages/ in; apps/supabase out).
MODULE_MAP_PATH_RE = re.compile(
    r"\b(?:backend|frontend|scripts|docs|packages)/[A-Za-z0-9_/.\-]+"
    r"\.(?:py|js|ts|tsx|jsx|md|json|yaml|yml|sql|ps1|sh)\b"
)
# §2/§3 cells: `{a,b,c}.js` must expand to real files and match any `（N 文件）` claim.
MODULE_MAP_BRACE_RE = re.compile(
    r"\b((?:backend|frontend|scripts|docs|packages)/[A-Za-z0-9_/\-]+"
    r"\{([A-Za-z0-9_,\-]+)\}\.(?:py|js))\b"
)
BRACE_FILECOUNT_RE = re.compile(r"\{([A-Za-z0-9_,\-]+)\}\.(?:py|js)（(\d+) 文件）")

GATE_STATUSES = ("active", "retired", "时点工具")
# Gate-table 机检实现 cell grammar: `path（`symbol`）` (full-width parens) or a bare path.
GATE_IMPL_RE = re.compile(r"^(?P<path>[^（]+)（`(?P<symbol>[A-Za-z_][A-Za-z0-9_]*)`）$")


def _module_map_issue(level: str, msg: str) -> dict:
    return {"check": "module-map", "level": level, "path": MODULE_MAP_REL, "msg": msg}


def _ver_tuple(version: str) -> tuple[int, int, int]:
    """First three numeric groups as an int tuple (v1.8.3.0 -> (1, 8, 3)).
    Never use str.rstrip('.0'): it strips characters, not the suffix, and
    would turn v1.10.0 into '1.1' (false freshness WARN)."""
    nums = [int(x) for x in re.findall(r"\d+", version)[:3]]
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def _parse_anchored_table(
    text: str, anchor: str
) -> tuple[list[str], list[list[str]], str | None]:
    """Parse the markdown table after ``anchor``. Fail-closed (A0): anchor
    missing/duplicated or an empty/no-data block returns an error string."""
    count = text.count(anchor)
    if count == 0:
        return [], [], f"anchor missing: {anchor}"
    if count > 1:
        return [], [], f"anchor duplicated ({count}x): {anchor}"
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if anchor in line)
    rows: list[list[str]] = []
    for line in lines[start + 1:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    header = rows[0] if rows else []
    data = [row for row in rows[1:]
            if not all(re.fullmatch(r"[-:\s]*", cell) for cell in row)]
    if not data:
        return [], [], f"anchored block parsed empty: {anchor}"
    for row in data:
        if len(row) != len(header):
            return header, [], (f"table format drift (column count {len(row)} != "
                                f"{len(header)}): {anchor}")
    return header, data, None


def _col(header: list[str], name: str, anchor: str) -> tuple[int, str | None]:
    """Resolve a column index by header cell name (D7: never hard-code indices)."""
    if name not in header:
        return -1, f"table header lacks column '{name}': {anchor}"
    return header.index(name), None


def _expand_brace_paths(text: str) -> set[str]:
    """Expand `{a,b}.js` cells of §2/§3 into concrete paths for A1."""
    expanded: set[str] = set()
    for match in MODULE_MAP_BRACE_RE.finditer(text):
        prefix, rest = match.group(1).split("{", 1)
        names, suffix = rest.split("}", 1)
        for name in names.split(","):
            expanded.add(f"{prefix}{name}{suffix}")
    return expanded


def _symbol_in_source(source: str, symbol: str) -> bool:
    """True when ``symbol`` is defined in ``source``: ALL-CAPS -> constant
    assignment, else a top-level ``def``. Fail-closed: anything else simply
    fails the lookup."""
    if symbol.isupper():
        return re.search(rf"^\s*{re.escape(symbol)}\s*[:=]", source, re.M) is not None
    return re.search(rf"^def\s+{re.escape(symbol)}\b", source, re.M) is not None


def _gate_row_issues(impl_cell: str, status: str) -> list[str]:
    """Validate one §5 gate row (pure function; shared with --selftest)."""
    if status not in GATE_STATUSES:
        return [f"§5 unknown gate status {status!r} (expected one of "
                f"{list(GATE_STATUSES)})"]
    if status != "active":
        return []
    cell = impl_cell.strip()
    match = GATE_IMPL_RE.match(cell)
    path = match.group("path").strip() if match else cell.split("（", 1)[0].strip()
    if not path or not (REPO_ROOT / path).exists():
        return [f"§5 gate implementation path missing: {path}"]
    if match is None:
        return []
    source = (REPO_ROOT / path).read_text(encoding="utf-8")
    if not _symbol_in_source(source, match.group("symbol")):
        return [f"§5 gate symbol '{match.group('symbol')}' not found in {path}"]
    return []


def _load_route_inventory(issues: list[dict]):
    """Import the authoritative route-inventory test (stdlib-only, no paddle)."""
    tests_dir = str(REPO_ROOT / "backend" / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    try:
        import test_route_inventory as route_inv  # noqa: E402
    except Exception as exc:  # pragma: no cover - broken repo state
        issues.append(_module_map_issue("ERROR", f"cannot import test_route_inventory: {exc}"))
        return None
    return route_inv


def _count_routes_in_file(path: Path, route_inv) -> int | None:
    """Count @router.<method> decorators with the frozen test's own matcher."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               for dec in node.decorator_list
               if route_inv._route_from_decorator(dec) is not None)


def _check_infra_block(text: str, fact: dict, issues: list[dict]) -> None:
    """A3: §3 infra-block numbers/names must match frontend_domain_map.json."""

    def line(marker: str) -> str | None:
        return next((ln for ln in text.splitlines() if marker in ln), None)

    def claimed(marker: str) -> int | None:
        match = re.search(r"（(\d+)", line(marker) or "")
        if match is None:
            issues.append(_module_map_issue(
                "ERROR", f"§3 infra line missing or without （N） count: {marker}"))
        return int(match.group(1)) if match else None

    utils_dir = REPO_ROOT / "frontend/modules/utils"
    shared_dir = REPO_ROOT / "frontend/shared"
    facts = {
        "frontend/modules/utils/": len(list(utils_dir.glob("*.js"))),
        "frontend/shared/": (len([p for p in shared_dir.iterdir() if p.is_file()])
                             if shared_dir.is_dir() else -1),
        "白名单叶服务": len(fact.get("leaf_services", {})),
        "共享状态模块": len(fact.get("shared_state_modules", {})),
    }
    for marker, actual in facts.items():
        count = claimed(marker)
        if count is not None and count != actual:
            issues.append(_module_map_issue(
                "ERROR",
                f"§3 infra drift ({marker}): map says {count}, facts say {actual}"))
    for marker, key, label in (("白名单叶服务", "leaf_services", "leaf-service"),
                               ("共享状态模块", "shared_state_modules", "shared-state")):
        names = set(re.findall(r"`([a-z\-]+)`", line(marker) or ""))
        expected = {Path(k).stem for k in fact.get(key, {})}
        if names and names != expected:
            issues.append(_module_map_issue(
                "ERROR", f"§3 {label} name-list drift: "
                         f"map={sorted(names)} json={sorted(expected)}"))
    boot = re.search(r"`boot_sequence` (\d+) 项", line("boot_sequence") or "")
    boot_actual = len(fact.get("boot_sequence", []))
    if boot is None:
        issues.append(_module_map_issue("ERROR", "§3 boot_sequence count line missing"))
    elif int(boot.group(1)) != boot_actual:
        issues.append(_module_map_issue(
            "ERROR",
            f"§3 boot_sequence drift: map says {boot.group(1)}, json has {boot_actual}"))


def check_module_map() -> list[dict]:
    """Reconcile module-map.md against its fact sources (P-004, check 3)."""
    issues: list[dict] = []

    def bad(msg: str) -> None:
        issues.append(_module_map_issue("ERROR", msg))

    map_path = REPO_ROOT / MODULE_MAP_REL
    if not map_path.is_file():
        return [_module_map_issue("ERROR", "module-map.md missing")]
    text = map_path.read_text(encoding="utf-8")

    # A1: every referenced path (incl. {a,b}.js expansions) must exist.
    refs = {ref for ref in (docs_refs.norm_ref(m.group(0))
                            for m in MODULE_MAP_PATH_RE.finditer(text)) if ref}
    refs |= _expand_brace_paths(text)
    for ref in sorted(refs):
        if not (REPO_ROOT / ref).exists():
            bad(f"referenced path missing: {ref}")

    # A2: §2 per-row route conservation + three-leg total (frozen 55).
    route_inv = _load_route_inventory(issues)
    header, rows, err = _parse_anchored_table(text, ANCHOR_BACKEND)
    if err:
        bad(err)
    else:
        i_file, e1 = _col(header, "文件", ANCHOR_BACKEND)
        i_eps, e2 = _col(header, "端点数", ANCHOR_BACKEND)
        for e in (e1, e2):
            if e:
                bad(e)
        if not e1 and not e2:
            router_files = sorted(p for p in (REPO_ROOT / "backend/app/routers").glob("*.py")
                                  if p.name != "__init__.py")
            ast_counts = {p.name: _count_routes_in_file(p, route_inv)
                          for p in router_files}
            if len(rows) != len(router_files):
                bad(f"§2 row count {len(rows)} != routers/*.py count {len(router_files)}")
            total_map = 0
            for row in rows:
                try:
                    claimed = int(row[i_eps])
                except ValueError:
                    bad(f"§2 non-integer endpoint count for '{row[0]}': {row[i_eps]!r}")
                    continue
                total_map += claimed
                name = row[i_file].replace("\\", "/").rsplit("/", 1)[-1]
                actual = ast_counts.get(name)
                if actual is None:
                    bad(f"§2 file not found under routers/: {row[i_file]}")
                elif claimed != actual:
                    bad(f"§2 endpoint drift for {row[i_file]}: map says {claimed}, "
                        f"AST counts {actual}")
            if route_inv is not None:
                total_ast = sum(c for c in ast_counts.values() if c is not None)
                if total_map != total_ast or total_ast != route_inv.EXPECTED_COUNT:
                    bad(f"§2 route conservation broken: map total {total_map}, AST total "
                        f"{total_ast}, frozen EXPECTED_COUNT {route_inv.EXPECTED_COUNT}")

    # §3: domain-set conservation (exact set, not just count) + （N 文件） cells.
    try:
        fact: dict | None = json.loads(
            (REPO_ROOT / "scripts/frontend_domain_map.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        bad(f"cannot read frontend_domain_map.json: {exc}")
        fact = None
    header, rows, err = _parse_anchored_table(text, ANCHOR_FRONTEND)
    if err:
        bad(err)
    else:
        i_dom, e1 = _col(header, "域", ANCHOR_FRONTEND)
        if e1:
            bad(e1)
        elif fact is not None:
            map_domains = {row[i_dom] for row in rows}
            json_domains = set(fact.get("domains", {}))
            if map_domains != json_domains:
                bad(f"§3 domain set drift vs frontend_domain_map.json: "
                    f"missing={sorted(json_domains - map_domains)} "
                    f"unexpected={sorted(map_domains - json_domains)}")
    for m in BRACE_FILECOUNT_RE.finditer(text):
        actual = len(m.group(1).split(","))
        if int(m.group(2)) != actual:
            bad(f"§3 file-count drift: cell claims {m.group(2)} files, expansion has "
                f"{actual} ({m.group(0)})")

    # A3: §3 infra block numbers/names. Search from the §3 anchor onward so
    # §1's prose (e.g. "F5 白名单叶服务" in the diagram) cannot shadow them.
    fact_zone = text[text.find(ANCHOR_FRONTEND):]
    if fact is not None:
        _check_infra_block(fact_zone, fact, issues)

    # §5 gate table: status enum + cell grammar + symbol existence.
    header, rows, err = _parse_anchored_table(text, ANCHOR_GATES)
    if err:
        bad(err)
    else:
        i_impl, e1 = _col(header, "机检实现", ANCHOR_GATES)
        i_status, e2 = _col(header, "状态", ANCHOR_GATES)
        for e in (e1, e2):
            if e:
                bad(e)
        if not e1 and not e2:
            for row in rows:
                for msg in _gate_row_issues(row[i_impl], row[i_status]):
                    bad(msg)

    # A4: registration completeness.
    for rel, needle, label in (
        ("docs/README.md", "architecture/module-map.md",
         "module-map.md not registered in docs/README.md Architecture section"),
        ("docs/agent-ops/doc-sync-ownership.md", "module-map.md",
         "module-map.md not registered in the doc-sync owning table"),
        ("docs/README.md", "doc-sync-ownership.md",
         "doc-sync-ownership.md not registered in docs/README.md"),
    ):
        try:
            content = (REPO_ROOT / rel).read_text(encoding="utf-8")
        except OSError:
            content = ""
        if needle not in content:
            bad(label)

    # A5: freshness vs CHANGELOG (WARN only; tuple compare, never rstrip).
    doc_match = re.search(r"最近对照：v([\d.]+)", text)
    try:
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        changelog = ""
    log_match = re.search(r"^##\s*\[([\d.]+)\]", changelog, re.M)
    if doc_match is None or log_match is None:
        issues.append(_module_map_issue("WARN", "freshness skipped (no 最近对照 / CHANGELOG)"))
    else:
        doc_v, latest_v = _ver_tuple(doc_match.group(1)), _ver_tuple(log_match.group(1))
        if doc_v < latest_v:
            issues.append(_module_map_issue(
                "WARN", f"module-map 对照落后：map v{'.'.join(map(str, doc_v))} < "
                        f"CHANGELOG v{'.'.join(map(str, latest_v))}"))
    for level, msg in frontend_map.check_orphan_staleness((fact or {}).get("known_orphans")):
        issues.append(_module_map_issue(level, msg))  # A6: stale orphan registration (P-008 gap 2)
    return issues


def run_selftest() -> int:
    """In-memory parser regressions (D11) - never reads repo facts; exercises
    the same helpers as the production check (the fact-source side is covered
    by the once-per-PR bad-sample procedure)."""
    gate_hdr = "| 规则 | 断言 | 机检实现 | 状态 |\n"
    good = ("| 域 | 文件 | 端点数 |\n|---|---|---|\n"
            "| system | backend/app/routers/system.py | 4 |\n")
    cases: list[tuple[str, bool]] = list(test_registry.selftest_cases())
    cases += list(docs_refs.selftest_cases())
    cases += list(unit_pin.selftest_cases())

    def ok(name: str, cond: bool) -> None:
        cases.append((name, bool(cond)))

    def parse_err(anchor: str, text: str, needle: str) -> None:
        _, _, err = _parse_anchored_table(text, anchor)
        ok(f"parse:{needle}", err is not None and needle in err)

    def gate_msgs(cell: str) -> list[str]:
        _, rows, err = _parse_anchored_table(ANCHOR_GATES + "\n" + gate_hdr + cell,
                                             ANCHOR_GATES)
        return [] if err else _gate_row_issues(rows[0][2], rows[0][3])

    # case 1: well-formed table parses cleanly
    header, rows, err = _parse_anchored_table(ANCHOR_BACKEND + "\n" + good,
                                              ANCHOR_BACKEND)
    ok("case1-good-table",
       err is None and len(rows) == 1 and header == ["域", "文件", "端点数"])
    parse_err(ANCHOR_BACKEND, "no anchor here", "anchor missing")            # case 2
    parse_err(ANCHOR_FRONTEND, ANCHOR_FRONTEND + "\n" + good + "\ntext\n"
              + ANCHOR_FRONTEND + "\n" + good, "duplicated")                 # case 3
    parse_err(ANCHOR_GATES, ANCHOR_GATES + "\n", "parsed empty")             # case 4
    parse_err(ANCHOR_BACKEND, ANCHOR_BACKEND + "\n| 域 | 文件 | 端点数 |\n"
              "|---|---|---|\n| a | b |\n", "column count")                  # case 5
    msgs = gate_msgs("| F1 | x | scripts/lint_frontend.py | Active |\n")     # case 6
    ok("case6-status-enum", len(msgs) == 1 and "unknown gate status" in msgs[0])
    msgs = gate_msgs("| F9 | x | scripts/audit_agent_ops.py"
                     "（`check_selftest_absent_symbol`） | active |\n")       # case 7
    ok("case7-symbol-missing", len(msgs) == 1 and "not found" in msgs[0])
    ok("case8-ver", _ver_tuple("v1.8.3.0") == (1, 8, 3)                      # case 8
       and _ver_tuple("1.10") == (1, 10, 0) and _ver_tuple("v1.10.0") == (1, 10, 0))
    ok("case8-symbol", _symbol_in_source("def check_f1(x):\n    pass\n", "check_f1")
       and _symbol_in_source("DEFAULT_BUDGET = 500\n", "DEFAULT_BUDGET")
       and not _symbol_in_source("# def check_gone(x)\n", "check_gone"))

    orphan = frontend_map.check_orphan_staleness  # A6: stale -> WARN; no date -> ERROR; fresh -> quiet
    ok("case16-orphan-staleness", [lv for lv, _ in orphan({"a.js": {"added": "2026-01-01"}}, date(2026, 12, 31))] == ["WARN"]
       and orphan({"b.js": {}}, date(2026, 9, 17))[0][0] == "ERROR" and orphan({"c.js": {"added": "2026-09-01"}}, date(2026, 9, 17)) == [])

    failed = [name for name, passed in cases if not passed]
    if failed:
        print(f"[SELFTEST] {len(failed)} failure(s):")
        for name in failed:
            print(f"  [FAIL] {name}")
        return 1
    print(f"[SELFTEST] all {len(cases)} checks passed")
    return 0


def check_agent_rules() -> list[dict]:
    """Re-render each agent copy and compare to disk. Returns ERROR issues."""
    issues: list[dict] = []
    for cfg in sync_mod.AGENTS.values():
        for spec in cfg["files"]:
            out_path = cfg["dir"] / spec["out"]
            msg = None
            if not out_path.exists():
                msg = "generated copy missing; run scripts/sync_agent_rules.py"
            elif out_path.read_text(encoding="utf-8") != sync_mod.render(spec):
                msg = "copy differs from kernel; run scripts/sync_agent_rules.py"
            if msg:
                issues.append({"check": "agent-rules", "level": "ERROR",
                               "path": str(out_path.relative_to(REPO_ROOT)),
                               "msg": msg})
    return issues


def main() -> int:
    argv = sys.argv[1:]
    if "--selftest" in argv:
        return run_selftest()
    issues = (check_agent_rules() + docs_refs.check_doc_drift() + docs_refs.check_retired_refs()
              + docs_refs.check_pending_staleness()
              + check_module_map() + test_registry.check_test_registry()
              + test_registry.check_stub_scope() + unit_pin.check_unit_pin())
    errors = [i for i in issues if i["level"] == "ERROR"]
    warnings = [i for i in issues if i["level"] == "WARN"]
    if "--json" in argv:
        print(json.dumps({"checked_at": datetime.now().isoformat(),
                          "ok": not errors, "errors": errors, "warnings": warnings},
                         ensure_ascii=False, indent=2))
    else:
        print(f"[AUDIT] {datetime.now():%Y-%m-%d %H:%M} "
              f"{len(errors)} error(s), {len(warnings)} warning(s)")
        for i in errors:
            print(f"  [ERROR] {i['path']}: {i['msg']}")
        for i in warnings:
            print(f"  [WARN]  {i['path']}: {i['msg']}")
        if not issues:
            print("[AUDIT] all checks passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
