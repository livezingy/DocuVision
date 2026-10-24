#!/usr/bin/env python3
"""Negative probes for lint_services (runs/split 05 §3 + shared-leaf P11-P13).

Synthetic input only — no repo facts, no files written; same predicates as the
production check (test_registry_audit.check_stub_scope 范式). Kept as a sibling
module so lint_services.py stays inside the 500-line budget (Placement D,
runs/split batch 1); aggregated by audit_agent_ops.run_selftest and by
`python scripts/lint_services.py --selftest` via a deferred import.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lint_services import (  # noqa: E402
    ANCHOR_SERVICES,
    allowlist_issues,
    check_service_table,
    classify_edges,
    cycle_issues,
    iter_imports,
    shared_leaf_issues,
)

FIG = "app.services.figure_service"
TS = "backend/app/services/table_service.py"
X = "backend/app/services/x.py"


def _alw(src, dst, pair, kind, added="2026-10-16"):
    return {"edges": [{"src_file": src, "dst_module": dst, "domain_pair": pair,
                       "kind": kind, "added": added}], "stale_days": 90}


def selftest_cases():
    domap = {"backend/app/services/table_service.py": "table",
             "backend/app/services/table_html.py": "table",
             "backend/app/services/x.py": "table",
             "backend/app/services/figure_service.py": "figure"}
    no_exemption = {"edges": [], "stale_days": 90}
    alw_ok = _alw(TS, FIG, "table->figure", "cross-domain")
    cases: list = []

    def ok(name: str, cond: bool) -> None:
        cases.append((name, bool(cond)))

    fig_edge = [(TS, FIG, 1)]
    # P1: S1b cross-domain without exemption = ERROR; exempted edge stays quiet (P1b).
    v, _ = classify_edges(fig_edge, domap, no_exemption)
    ok("P1-s1b-cross-domain", len(v) == 1 and v[0]["level"] == "ERROR"
       and "S1b" in v[0]["msg"] and "table -> figure" in v[0]["msg"])
    v, pairs = classify_edges(fig_edge, domap, alw_ok)
    ok("P1b-exempt-quiet", not v and pairs.get("table->figure") is True)

    # P2: S1a reverse dependency without a layer-kind entry; a wrong-kind
    # entry must not exempt it (P2c).
    ORCH = "app.orchestration.document_pipeline_orchestrator"
    rev = [(X, ORCH, 1)]
    v, _ = classify_edges(rev, domap, no_exemption)
    ok("P2-s1a-reverse", len(v) == 1 and "S1a" in v[0]["msg"])
    v, _ = classify_edges(rev, domap, _alw(X, ORCH, "pipeline->L2", "layer"))
    ok("P2b-layer-exempt", not v)
    v, _ = classify_edges(rev, domap, _alw(X, ORCH, "pipeline->L2", "cross-domain"))
    ok("P2c-kind-mismatch", len(v) == 1 and "S1a" in v[0]["msg"])

    # P3: non-exempt cycle = ERROR; fully-exempt cycle quiet while fresh (P10), WARN after clock (P10b).
    v = cycle_issues({"a->b": False, "b->a": False}, {"a->b": date(2026, 10, 16)}, date(2026, 10, 24))
    ok("P3-cycle-error", len(v) == 1 and v[0]["level"] == "ERROR" and "non-exempt" in v[0]["msg"])
    v = cycle_issues({"a->b": True, "b->a": True}, {"a->b": date(2026, 10, 16)}, date(2026, 10, 24))
    ok("P10-fresh-cycle-quiet", not v)
    v = cycle_issues({"a->b": True, "b->a": True}, {"a->b": date(2026, 10, 16)}, date(2027, 1, 20))
    ok("P10b-stale-cycle-warn", len(v) == 1 and v[0]["level"] == "WARN")

    # P4/P7: §2b three-way — unmapped disk file and ghost map entry = ERROR.
    dmap = {"domains": {"table": "t", "figure": "f"}, "file_domains": {
        "backend/app/services/table_service.py": "table",
        "backend/app/services/table_html.py": "table",
        "backend/app/services/figure_service.py": "figure"}}
    tbl = (ANCHOR_SERVICES + "\n| 域 | 文件 | 职责 | owning doc | 出向跨域边 |\n|---|---|---|---|---|\n"
           "| table | backend/app/services/{table_service,table_html}.py（2 文件） | t | — | table->figure |\n"
           "| figure | backend/app/services/figure_service.py | f | — | — |\n")
    disk3 = {"backend/app/services/table_service.py", "backend/app/services/table_html.py",
             "backend/app/services/figure_service.py"}
    v = check_service_table(tbl, dmap, disk3 | {"backend/app/services/zz_new.py"}, alw_ok)
    ok("P4-unmapped-file", any(i["level"] == "ERROR" and "unmapped services file" in i["msg"] for i in v))
    ghost = {"domains": dmap["domains"],
             "file_domains": dict(dmap["file_domains"], **{"backend/app/services/ghost.py": "table"})}
    v = check_service_table(tbl, ghost, disk3, alw_ok)
    ok("P7-ghost-entry", any(i["level"] == "ERROR" and "ghost entry" in i["msg"] for i in v))
    v = check_service_table(tbl, dmap, disk3, alw_ok)
    ok("P7b-clean-table-quiet", not v)

    # P5: relative-import penetration (A-4).
    out = list(iter_imports("from ..figure_service import X\n", "app.services.kie.text_first",
                            {"app.services.figure_service"}))
    ok("P5-relative-import", out == [("app.services.figure_service", 1)])

    # P6: R0 import from services is legal (P6a); app.* inside the package is a violation (P6b).
    v, _ = classify_edges([(X, "docuvision_core.utils.pdf_text_utils", 1)], domap, no_exemption)
    ok("P6a-r0-legal", not v)
    v, _ = classify_edges([("packages/docuvision-core/utils/pdf_text_utils.py", FIG, 1)],
                          domap, no_exemption)
    ok("P6b-pkg-no-app", len(v) == 1 and "S1a" in v[0]["msg"])

    # P8: zero false positives — in-domain sibling, services->core.config, router->runtime.
    v, _ = classify_edges([(TS, "app.services.table_html", 1), (TS, "app.core.config", 2),
                           ("backend/app/routers/system.py", "app.core.runtime", 3)], domap, no_exemption)
    ok("P8-no-false-positives", not v)

    # P9: resolved entry asks for removal (WARN, free); stale entry fires clock WARN (P9b).
    v = allowlist_issues(set(), alw_ok, today=date(2026, 10, 24))
    ok("P9-resolved-remove", len(v) == 1 and v[0]["level"] == "WARN" and "ratchet" in v[0]["msg"])
    v = allowlist_issues({(TS, FIG)}, alw_ok, today=date(2027, 1, 20))
    ok("P9b-stale-clock", len(v) == 1 and v[0]["level"] == "WARN" and "clock" in v[0]["msg"])

    # P11: shared-leaf channel — a cross-domain import of a registered shared
    # leaf is a legal channel (no S1b violation, and the edge feeds no domain
    # pair, so it cannot create a cycle in S1c).
    leaves = {"backend/app/services/pdf_raster.py": {"added": "2026-10-24"}}
    v, pairs = classify_edges([("backend/app/services/kie_qwen_service.py",
                                "app.services.pdf_raster", 1)],
                              {**domap, "backend/app/services/kie_qwen_service.py": "kie",
                               "backend/app/services/pdf_raster.py": "infra"},
                              no_exemption, shared_leaves=leaves)
    ok("P11-shared-leaf-legal", not v and not pairs)

    # P12: L1 predicate — a registered shared leaf with an app.*/docuvision_core
    # outbound import = ERROR; a zero-outbound leaf stays quiet; ghost
    # registration (file not on disk) = ERROR (P12b).
    leaf_src = {X: "import os\nfrom app.services.figure_service import Y\n"}
    v = shared_leaf_issues({X: {"added": "2026-10-24"}}, leaf_src, domap)
    ok("P12-leaf-outbound", any(i["level"] == "ERROR" and "outbound" in i["msg"] for i in v))
    v = shared_leaf_issues({X: {"added": "2026-10-24"}}, {X: "import os\n"}, domap)
    ok("P12b-leaf-clean-quiet", not v)
    v = shared_leaf_issues({"backend/app/services/nope.py": {}}, {}, domap)
    ok("P12c-leaf-ghost", any(i["level"] == "ERROR" and "ghost" in i["msg"] for i in v))

    # P13: §2b shared-leaf roster reconciliation — the prose line's count and
    # backtick name list must match shared_leaf_modules exactly.
    tbl_leaf = tbl.replace("| figure | backend/app/services/figure_service.py | f | — | — |\n",
                           "| figure | backend/app/services/figure_service.py | f | — | — |\n"
                           "共享叶（1）：`pdf_raster`。\n")
    domap_leaf = {"domains": dmap["domains"], "file_domains": dmap["file_domains"],
                  "shared_leaf_modules": {"backend/app/services/pdf_raster.py": {"added": "2026-10-24"}}}
    v = check_service_table(tbl_leaf, domap_leaf, disk3, alw_ok)
    ok("P13-roster-ok", not [i for i in v if "共享叶" in i["msg"]])
    tbl_bad = tbl_leaf.replace("共享叶（1）：`pdf_raster`。", "共享叶（2）：`pdf_raster`、`ghost_leaf`。")
    v = check_service_table(tbl_bad, domap_leaf, disk3, alw_ok)
    ok("P13b-roster-drift", any(i["level"] == "ERROR" and "共享叶" in i["msg"] for i in v))
    v = check_service_table(tbl, domap_leaf, disk3, alw_ok)
    ok("P13c-roster-missing", any(i["level"] == "ERROR" and "共享叶" in i["msg"] for i in v))
    return cases
