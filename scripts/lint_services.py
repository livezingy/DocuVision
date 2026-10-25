#!/usr/bin/env python3
"""Services-layer structure lint — stdlib AST only (no imports, no paddle).

S1 rules (kernel routing.md; baseline docs/R&D/runs/split 01-05, 2026-10-16
snapshot, re-verified at landing 2026-10-24):
  S1a  layer direction (02 table-1 forbidden cells + fix A-2): services must
      not import orchestration/routers/core.runtime; orchestration not
      routers/runtime; routers not routers; core(except runtime)/models not
      upper layers; packages/docuvision-core not app.* (app.main is R3's
      job in lint_routes.py — not duplicated, fix A-5).
  S1b  domain placement: every backend/app/services/**/*.py must be mapped in
      scripts/service_domain_map.json (fail-closed, B-2); importing a services
      module of another domain needs an exemption in
      scripts/service_dependency_allowlist.json (ruling 2: frozen, only-shrink,
      adding an entry is a red line).
  S1c  acyclicity (fix A-9): cycle over non-exempt edges = ERROR; fully-exempt
      cycle WARNs once the 90-day clock expires (A6 paradigm).
Relative imports (level>0) resolve via the file's package (A-4); scan covers
app.* AND docuvision_core.* (04 §0); deferred imports included (ast.walk);
blind spot: dynamic importlib/__import__. Also reconciles module-map.md §2b
three ways (table vs map vs disk, fail-closed) + the §2b edge column vs
allowlist domain pairs bidirectionally (I-3).
Usage: python scripts/lint_services.py [--selftest] — exit 1 on any ERROR.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "backend" / "app"
PKG_DIR = REPO_ROOT / "packages" / "docuvision-core"
DOMAIN_MAP_REL = "scripts/service_domain_map.json"
ALLOWLIST_REL = "scripts/service_dependency_allowlist.json"
MODULE_MAP_REL = "docs/architecture/module-map.md"
ANCHOR_SERVICES = "<!-- audit:backend-service-domains -->"
SHARED_DOMAIN = "shared"
STALE_DAYS = 90
L0A, L0B, L1, L2, L3, L4, PKG, EXT = ("L0a", "L0b", "L1", "L2", "L3", "L4", "pkg", "ext")

# 02 表 1 forbidden cells (+A-2); L0a (app.main) targets belong to R3.
S1A_FORBIDDEN = {
    (L3, L1), (L3, L2), (L3, L0B), (L2, L1), (L2, L0B), (L1, L1),
    (L4, L0B), (L4, L1), (L4, L2), (L4, L3),
    (PKG, L0A), (PKG, L0B), (PKG, L1), (PKG, L2), (PKG, L3), (PKG, L4),
}

# §2b cells: the brace may sit directly after any directory level (audit A1 shape).
CELL_BRACE_RE = re.compile(r"(backend/app/services(?:/[A-Za-z0-9_\-]+)*/)\{([A-Za-z0-9_,\-]+)\}\.py")
CELL_BARE_RE = re.compile(r"\bbackend/app/services/[A-Za-z0-9_/]+\.py\b")
PAIR_RE = re.compile(r"\b([a-z][a-z0-9]*->[A-Za-z0-9]+)")


def _issue(level: str, path: str, msg: str) -> dict:
    return {"check": "services-lint", "level": level, "path": path, "msg": msg}


def _is_or_under(module: str, base: str) -> bool:
    return module == base or module.startswith(base + ".")


def layer_of(module: str) -> str:
    for base, layer in (("app.main", L0A), ("app.core.runtime", L0B), ("app.routers", L1),
                        ("app.orchestration", L2), ("app.services", L3), ("app.core", L4),
                        ("app.models", L4), ("docuvision_core", PKG)):
        if _is_or_under(module, base):
            return layer
    return EXT


def module_of(rel_path: str) -> str:
    p = rel_path.replace("\\", "/")
    for prefix, root in (("backend/app/", "app"), ("packages/docuvision-core/", "docuvision_core")):
        if p.startswith(prefix):
            return ".".join([root] + p[len(prefix):-len(".py")].split("/"))
    return ""


def iter_imports(source: str, src_module: str, known_modules: set, is_package: bool = False):
    """Yield (dst_module, lineno) for app.*/docuvision_core.* imports, incl.
    function-body deferred imports; level>0 resolves via the file's package
    (A-4); `from pkg import submodule` resolves to the submodule when known."""
    tree = ast.parse(source)
    pkg_parts = src_module.split(".") if is_package else src_module.split(".")[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(("app.", "docuvision_core")):
                    yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                base_parts = pkg_parts[: len(pkg_parts) - (node.level - 1)]
            elif node.module and node.module.startswith(("app.", "docuvision_core")):
                base_parts = []
            else:
                continue
            if node.module:
                base_parts = base_parts + node.module.split(".")
            base = ".".join(base_parts)
            for alias in node.names:
                cand = f"{base}.{alias.name}" if base else alias.name
                yield (cand if cand in known_modules else base), node.lineno


def classify_edges(edges, file_domains, allowlist, shared_leaves=None):
    """S1a/S1b over edges [(src_rel, dst_module, lineno)]. Pure function.
    Returns (issues, domain_pairs); domain_pairs maps 'src->dst' to True only
    when every physical edge of the pair is exempt. A services module listed
    in shared_leaves is a legal channel for any domain (I-1): the edge feeds
    no domain pair and thus no S1c cycle."""
    issues: list[dict] = []
    shared_leaves = shared_leaves or set()
    exempt = {(e.get("src_file"), e.get("dst_module")): e for e in allowlist.get("edges", [])}
    mod_to_rel = {module_of(r): r for r in file_domains}
    pair_flags: dict = {}
    seen = set()
    for src_rel, dst, lineno in edges:
        key = (src_rel, dst, lineno)
        if key in seen:
            continue
        seen.add(key)
        src_layer, dst_layer = layer_of(module_of(src_rel)), layer_of(dst)
        if (src_layer, dst_layer) in S1A_FORBIDDEN:
            entry = exempt.get((src_rel, dst))
            if entry is None or entry.get("kind") != "layer":
                issues.append(_issue(
                    "ERROR", f"{src_rel}:{lineno}",
                    f"S1a layer violation {src_layer} -> {dst_layer}: import {dst} "
                    "(kernel routing.md S-rules; a reverse dependency needs a "
                    "layer-kind allowlist entry - adding one is a red line, ask first)"))
        if src_layer != L3 or dst_layer != L3:
            continue
        if mod_to_rel.get(dst, "") in shared_leaves:
            continue  # registered shared leaf: legal channel for every domain
        d_src = file_domains.get(src_rel)
        if d_src is None:
            issues.append(_issue(
                "ERROR", src_rel, "S1b unmapped services file (fail-closed): register it in "
                f"{DOMAIN_MAP_REL} + module-map §2b (Placement N/D decision)"))
            continue
        d_dst = file_domains.get(mod_to_rel.get(dst, ""))
        if d_dst in (None, SHARED_DOMAIN) or d_dst == d_src:
            continue  # dst unmapped gets reported from its own file; shared shell is free
        pair = f"{d_src}->{d_dst}"
        entry = exempt.get((src_rel, dst))
        ok = entry is not None and entry.get("kind") == "cross-domain"
        if not ok:
            issues.append(_issue(
                "ERROR", f"{src_rel}:{lineno}",
                f"S1b cross-domain import {d_src} -> {d_dst} ({dst}): give it an in-domain "
                "home, or register the edge in the allowlist (red line - ask first) and "
                "declare Placement X in the footer"))
        pair_flags.setdefault(pair, []).append(ok)
    return issues, {p: all(flags) for p, flags in pair_flags.items()}


def allowlist_issues(actual_keys: set, allowlist: dict, today: date | None = None) -> list[dict]:
    """Ratchet: resolved entries ask for removal (WARN, free); still-present
    entries older than stale_days WARN on the A6 clock."""
    issues: list[dict] = []
    today = today or date.today()
    stale_days = allowlist.get("stale_days", STALE_DAYS)
    for i, e in enumerate(allowlist.get("edges", [])):
        where = f"{ALLOWLIST_REL} edges[{i}] ({e.get('domain_pair', '?')})"
        try:
            added = date.fromisoformat(e.get("added", ""))
        except (TypeError, ValueError):
            issues.append(_issue("ERROR", where, "'added' must be an ISO date (fail-closed)"))
            continue
        if (e.get("src_file"), e.get("dst_module")) not in actual_keys:
            issues.append(_issue("WARN", where, "frozen edge no longer present in code; remove "
                             "the entry to ratchet down (removal is free)"))
        elif (today - added).days > stale_days:
            issues.append(_issue("WARN", where, f"frozen since {added} ({(today - added).days} days) "
                             f"past the {stale_days}-day clock: fix the edge or re-rule it "
                             f"explicitly (target: {e.get('target', 'n/a')})"))
    return issues


def _sccs(graph: dict) -> list:
    """Tarjan SCC over {node: {successors}} (iterative; sorted for determinism)."""
    index, low = {}, {}
    stack, on_stack, comps, counter = [], set(), [], [0]
    for start in sorted(graph):
        if start in index:
            continue
        index[start] = low[start] = counter[0]
        counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        work = [(start, iter(sorted(graph.get(start, ()))))]
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(sorted(graph.get(nxt, ())))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                comps.append(comp)
    return comps


def cycle_issues(domain_pairs: dict, pair_dates: dict, today: date | None = None) -> list[dict]:
    """S1c (A-9): non-exempt cycle = ERROR; fully-exempt cycle stays quiet
    until the oldest member edge passes the 90-day clock, then WARNs once."""
    issues: list[dict] = []
    today = today or date.today()
    graph: dict = {}
    for pair in domain_pairs:
        a, b = pair.split("->")
        graph.setdefault(a, set()).add(b)
    for comp in _sccs(graph):
        if len(comp) < 2:
            continue
        members = set(comp)
        inner = {f"{a}->{b}" for a in comp for b in graph[a] if b in members}
        bad = sorted(p for p in inner if not domain_pairs.get(p, False))
        msg = "S1c domain cycle " + " -> ".join(comp) + f" ({', '.join(sorted(inner))})"
        if bad:
            issues.append(_issue("ERROR", MODULE_MAP_REL, msg + f"; non-exempt edges: {', '.join(bad)}"))
            continue
        oldest = max((d for p, d in pair_dates.items() if p in inner), default=None)
        if oldest is not None and (today - oldest).days > STALE_DAYS:
            issues.append(_issue("WARN", MODULE_MAP_REL, msg + "; all edges frozen but past the "
                             "90-day clock - promote the shared predicate or invert the edge"))
    return issues


def check_service_table(module_map_text: str, domain_map: dict, disk_files: set, allowlist: dict) -> list[dict]:
    """§2b three-way reconciliation (B-2 fail-closed) + edge column vs
    allowlist domain pairs (I-3). Pure function."""
    issues: list[dict] = []
    count = module_map_text.count(ANCHOR_SERVICES)
    if count == 0:
        return [_issue("ERROR", MODULE_MAP_REL, f"anchor missing: {ANCHOR_SERVICES}")]
    if count > 1:
        return [_issue("ERROR", MODULE_MAP_REL, f"anchor duplicated ({count}x): {ANCHOR_SERVICES}")]
    lines = module_map_text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ANCHOR_SERVICES in ln)
    rows: list = []
    for ln in lines[start + 1:]:
        if not ln.startswith("|"):
            break
        rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
    header = rows[0] if rows else []
    data = [r for r in rows[1:] if not all(re.fullmatch(r"[-:\s]*", c) for c in r)]
    if not data:
        return [_issue("ERROR", MODULE_MAP_REL, f"anchored block parsed empty: {ANCHOR_SERVICES}")]
    for name in ("域", "文件"):
        if name not in header:
            issues.append(_issue("ERROR", MODULE_MAP_REL, f"§2b header lacks column {name!r}"))
            return issues
    i_dom, i_file = header.index("域"), header.index("文件")
    table_domains: dict = {}
    for row in data:
        if len(row) != len(header):
            issues.append(_issue("ERROR", MODULE_MAP_REL, f"§2b column count {len(row)} != {len(header)}"))
            continue
        files = set(CELL_BARE_RE.findall(row[i_file]))
        for m in CELL_BRACE_RE.finditer(row[i_file]):
            files.update(f"{m.group(1)}{name}.py" for name in m.group(2).split(","))
        table_domains[row[i_dom]] = files
    table_files = set().union(*table_domains.values()) if table_domains else set()

    file_domains: dict = domain_map.get("file_domains", {})
    shared_files = {f for f, d in file_domains.items() if d == SHARED_DOMAIN}
    map_domain_files = set(file_domains) - shared_files
    for f in sorted(table_files ^ map_domain_files):
        side = "§2b lists file not in domain map" if f in table_files else "§2b missing mapped file"
        issues.append(_issue("ERROR", MODULE_MAP_REL, f"{side}: {f}"))
    for f in sorted(set(file_domains) - disk_files):
        issues.append(_issue("ERROR", DOMAIN_MAP_REL, f"ghost entry (no such file on disk): {f}"))
    for f in sorted(disk_files - set(file_domains)):
        issues.append(_issue("ERROR", DOMAIN_MAP_REL, f"unmapped services file (fail-closed): {f}"))
    for dom, files in table_domains.items():
        expect = {f for f, d in file_domains.items() if d == dom}
        if files != expect:
            issues.append(_issue("ERROR", MODULE_MAP_REL, f"§2b row '{dom}' file set != map: "
                                 f"table-only={sorted(files - expect)} map-only={sorted(expect - files)}"))
    map_domains = {d for d in file_domains.values() if d != SHARED_DOMAIN}
    if set(table_domains) != map_domains:
        issues.append(_issue("ERROR", MODULE_MAP_REL, "§2b domain set drift: "
                             f"table-only={sorted(set(table_domains) - map_domains)} "
                             f"map-only={sorted(map_domains - set(table_domains))}"))
    declared = set(domain_map.get("domains", {}))
    if declared != map_domains:
        issues.append(_issue("ERROR", DOMAIN_MAP_REL, "domains dict != files actually mapped: "
                             f"declared-only={sorted(declared - map_domains)} "
                             f"used-only={sorted(map_domains - declared)}"))
    section = "\n".join(lines[start:])
    for f in sorted(shared_files):
        if f not in section:
            issues.append(_issue("ERROR", MODULE_MAP_REL,
                                 f"§2b must mention the shared shell in its prose row: {f}"))
    # shared-leaf roster (A3-style): the §2b prose line's count + backtick
    # name list must equal shared_leaf_modules exactly — no hand-copy drift.
    leaves = domain_map.get("shared_leaf_modules", {})
    m = re.search(r"共享叶（(\d+)）：([^（\n]*)", section)
    if leaves and m is None:
        issues.append(_issue("ERROR", MODULE_MAP_REL,
                             "§2b lacks the 共享叶 roster line but shared_leaf_modules is non-empty"))
    elif m is not None:
        names = set(re.findall(r"`([a-z_][a-z0-9_]*)`", m.group(2)))
        expected = {Path(k).stem for k in leaves}
        if int(m.group(1)) != len(leaves) or names != expected:
            issues.append(_issue("ERROR", MODULE_MAP_REL, "§2b 共享叶 roster drift: "
                                 f"line={sorted(names)} ({m.group(1)}), map={sorted(expected)} ({len(leaves)})"))
    if "出向跨域边" in header:
        i_edge = header.index("出向跨域边")
        table_pairs = {p for row in data for p in PAIR_RE.findall(row[i_edge])}
        allow_pairs = {e.get("domain_pair") for e in allowlist.get("edges", [])}
        for p in sorted(table_pairs - allow_pairs):
            issues.append(_issue("ERROR", MODULE_MAP_REL,
                                 f"§2b edge column names unregistered pair {p} (not in allowlist)"))
        for p in sorted(allow_pairs - table_pairs):
            issues.append(_issue("ERROR", MODULE_MAP_REL,
                                 f"allowlist pair {p} missing from §2b edge column"))
    return issues


def shared_leaf_issues(shared_leaves: dict, leaf_sources: dict, file_domains: dict) -> list[dict]:
    """Shared-leaf registration integrity (I-1, L1 = strength A): a registered
    module must exist on disk (ghost = ERROR), stay mapped in file_domains
    (ERROR), and be zero-outbound — no app.*/docuvision_core.* import at all
    (ERROR). Pure function; leaf_sources maps rel path -> source text."""
    issues: list[dict] = []
    for rel in shared_leaves:
        where = f"{DOMAIN_MAP_REL} shared_leaf_modules[{Path(rel).name}]"
        if rel not in leaf_sources:
            issues.append(_issue("ERROR", where, "ghost shared-leaf registration (no such file)"))
            continue
        if rel not in file_domains:
            issues.append(_issue("ERROR", where,
                                 "shared leaf must keep its file_domains entry (dual registration)"))
        try:
            out = list(iter_imports(leaf_sources[rel], module_of(rel), set(),
                                    rel.endswith("__init__.py")))
        except SyntaxError:
            issues.append(_issue("ERROR", rel, "unparsable (fail-closed)"))
            continue
        for dst, lineno in out:
            issues.append(_issue("ERROR", f"{rel}:{lineno}",
                                 f"registered shared leaf has outbound import {dst}; "
                                 "L1 zero-outbound is strength A - unregister it or invert"))
    return issues


def check_services() -> list[dict]:
    """Full run: scan backend/app + packages, classify, reconcile, check §2b."""
    issues: list[dict] = []

    def read_json(rel: str):
        try:
            return json.loads((REPO_ROOT / rel).read_text(encoding="utf-8")), None
        except (OSError, json.JSONDecodeError) as exc:
            return None, _issue("ERROR", rel, f"unreadable/invalid JSON (fail-closed): {exc}")

    domain_map, err = read_json(DOMAIN_MAP_REL)
    allowlist, err2 = read_json(ALLOWLIST_REL)
    if err or err2:
        return [i for i in (err, err2) if i]
    file_domains: dict = domain_map.get("file_domains", {})
    shared_leaves: dict = domain_map.get("shared_leaf_modules", {})
    sources: dict = {}
    for root in (d for d in (APP_DIR, PKG_DIR) if d.is_dir()):
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" not in p.parts:
                sources[p.relative_to(REPO_ROOT).as_posix()] = p.read_text(encoding="utf-8")
    known = {m for m in (module_of(r) for r in sources) if m}
    disk_services = {r for r in sources if r.startswith("backend/app/services/")}

    edges: list = []
    for rel, source in sources.items():
        try:
            edges.extend((rel, dst, lineno) for dst, lineno
                         in iter_imports(source, module_of(rel), known, rel.endswith("__init__.py")))
        except SyntaxError as exc:
            issues.append(_issue("ERROR", rel, f"unparsable (fail-closed): {exc}"))

    edge_issues, domain_pairs = classify_edges(edges, file_domains, allowlist, shared_leaves)
    issues += edge_issues
    issues += shared_leaf_issues(shared_leaves, sources, file_domains)
    actual_keys = {(s, d) for s, d, _ in edges}
    issues += allowlist_issues(actual_keys, allowlist)
    pair_dates: dict = {}
    for e in allowlist.get("edges", []):
        try:
            pair_dates[e["domain_pair"]] = max(pair_dates.get(e["domain_pair"], date.min),
                                               date.fromisoformat(e["added"]))
        except (KeyError, TypeError, ValueError):
            pair_dates.setdefault(e.get("domain_pair", "?"), date.min)
    issues += cycle_issues(domain_pairs, pair_dates)

    try:
        text = (REPO_ROOT / MODULE_MAP_REL).read_text(encoding="utf-8")
    except OSError:
        return issues + [_issue("ERROR", MODULE_MAP_REL, "unreadable (fail-closed)")]
    issues += check_service_table(text, domain_map, disk_services, allowlist)
    return issues


def main() -> int:
    if "--selftest" in sys.argv[1:]:
        from lint_services_selftest import selftest_cases  # deferred: sibling module
        cases = list(selftest_cases())
        failed = [name for name, passed in cases if not passed]
        if failed:
            print(f"[SELFTEST] {len(failed)} failure(s): " + ", ".join(failed))
            return 1
        print(f"[SELFTEST] all {len(cases)} checks passed")
        return 0
    issues = check_services()
    errors = [i for i in issues if i["level"] == "ERROR"]
    warns = [i for i in issues if i["level"] == "WARN"]
    print(f"[lint_services] {len(errors)} error(s), {len(warns)} warning(s)")
    for i in errors:
        print(f"  [ERROR] {i['path']}: {i['msg']}")
    for i in warns:
        print(f"  [WARN]  {i['path']}: {i['msg']}")
    if not issues:
        print("[lint_services] OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
