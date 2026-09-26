#!/usr/bin/env python3
"""Doc-reference audit: retired-reference (tombstone) gate + living-doc path drift + PENDING log.

Split out of ``audit_agent_ops.py`` and imported by it (which must stay inside its own line
budget), following the existing ``frontend_coupling.py`` / ``test_registry_audit.py`` pattern:
the audit stays the orchestrator, the checks live here.

Three checks:

1. ``check_doc_drift()`` - *relocated unchanged* from ``audit_agent_ops.py``: every path a
   living doc references must exist (WARN). Scope, pattern and severity are untouched, so the
   audit's output is identical to before the split.

2. ``check_retired_refs()`` - **new** tombstone gate: outward-facing docs must not reference a
   path / port / command / module that has been deleted, because a reader would copy an
   instruction that can only fail. Deliberately a **literal substring** rule over an explicit
   token list: no regex for tokens, no ``subprocess``, no ``exec``, no filesystem writes - it
   reads text and tests tokens, nothing else (a doc is data, never a program).

   A hit is a violation *unless* the same line carries an explicit retirement marker
   (``已删除`` / ``retired`` / ...): "``apps/lite/**`` was deleted in v1.8" is documentation, not
   a stale instruction.

   Scope is an allow-list of outward-facing material. Archived material (release notes,
   the decision log, frozen acceptance checklists, archived roadmaps) is exempt **with a
   printed reason**, because citing deleted things is what history does.

   Design record: ``docs/architecture/doc-governance.md`` (promoted out of PENDING P-022 on
   2026-09-25). The machine-readable lists - ``RETIRED`` / ``SCAN_GLOBS`` / ``EXEMPT`` /
   ``ALLOWLIST`` - stay in this module as the single source; the living doc states the rule
   and deliberately does not copy the token list (which would create a second source and,
   since that doc is itself scanned, trip this gate).

3. ``check_pending_staleness()`` - **new** doc-lifecycle gate (DOC-3, P-025): the decision log
   ``docs/R&D/PENDING.md`` is the only part of the R&D folder CI can see (everything else is
   gitignored), so it is also the only half that can be machine-checked. Each entry must carry
   one ``> status: <open|decided|landed|retained> · since: YYYY-MM-DD`` line (single source of
   truth - the header keeps an id index and no hand-written counts, the P-019 lesson), and a
   ``landed`` entry older than ``PENDING_STALE_DAYS`` raises a WARN asking to promote it into
   ``docs/architecture/`` or to reclassify it as ``retained`` with a stated reason. Missing /
   malformed / future-dated metadata and a header index that disagrees with the ``### P-xxx``
   headings are ERRORs (fail-closed, same shape as A6 orphan staleness).

Exit code 0 = clean, 1 = violations. Standalone: ``python scripts/docs_refs_audit.py [--selftest]``.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- 1. living-doc path drift (relocated from audit_agent_ops.py, unchanged) ---------------

LIVING_DOC_GLOBS = ["docs/architecture/*.md", "docs/README.md"]

# File path references inside docs, e.g. backend/app/services/export_service.py
PATH_REF_RE = re.compile(
    r"\b(?:backend|apps|packages|frontend|supabase)/[A-Za-z0-9_/.\-]+"
    r"\.(?:py|js|ts|tsx|jsx|md|json|yaml|yml|sql|ps1|sh)\b"
)

# Strip a trailing ":<lineno>" and drop glob patterns (contain *).
GLOB_CHARS = ("*", "?")
LINE_REF_RE = re.compile(r":\d+$")

# Runtime-generated artifact prefixes (mirrors .gitignore, e.g. backend/debug/).
DOC_DRIFT_ALLOW_PREFIXES = ("backend/debug/",)


def norm_ref(ref: str) -> str | None:
    """Normalise a path reference; ``None`` when it is not checkable (glob / ellipsis)."""
    ref = LINE_REF_RE.sub("", ref)
    if any(ch in ref for ch in GLOB_CHARS) or "..." in ref:
        return None
    return ref


def check_doc_drift() -> list[dict]:
    """Report file paths referenced by living docs that do not exist."""
    issues: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for glob in LIVING_DOC_GLOBS:
        for doc in sorted(REPO_ROOT.glob(glob)):
            text = doc.read_text(encoding="utf-8")
            for m in PATH_REF_RE.finditer(text):
                ref = norm_ref(m.group(0))
                if ref is None or ref.startswith(DOC_DRIFT_ALLOW_PREFIXES):
                    continue
                key = (str(doc.relative_to(REPO_ROOT)), ref)
                if key not in seen and not (REPO_ROOT / ref).exists():
                    seen.add(key)
                    issues.append({"check": "doc-drift", "level": "WARN",
                                   "path": key[0],
                                   "msg": f"referenced path missing: {ref}"})
    return issues


# --- 2. retired references (tombstone gate) ------------------------------------------------

# (token, why it is a tombstone) - matched case-insensitively as a literal substring.
RETIRED: tuple[tuple[str, str], ...] = (
    ("apps/lite/", "Lite app deleted in v1.8 (1c9807c)"),
    ("supabase/", "trial Supabase PoC deleted in v1.8"),
    (":8001", "Lite port; Pro serves :8000"),
    ("run_lite", "Lite entrypoint deleted in v1.8"),
    ("lite.html", "Lite UI deleted in v1.8"),
    ("lite.js", "Lite bundle deleted in v1.8"),
    ("lite-api.md", "Lite API doc deleted in v1.8"),
    ("lite-overrides", "Lite-only stylesheet deleted in v1.8"),
    ("test:e2e:lite", "Lite e2e script removed in v1.8"),
    ("[lite]", "docuvision-core extras dropped in v1.8 (`dev` only remains)"),
    ("core_table_extractor", "deleted in v1.8 (zero callers)"),
    ("docuvision_core.extractors", "core family removed in v1.8"),
    ("docuvision_core.engines", "core family removed in v1.8"),
    ("docuvision_core.models", "core family removed in v1.8"),
    ("lite-batch", "Lite batch API removed in v1.3.1"),
    ("lite-preview", "Lite preview removed with the app in v1.8"),
    ("lite_ui_test_checklist", "Lite checklist deleted with the app in v1.8"),
)

# A line carrying one of these says "this was removed" - a notice, not an instruction.
RETIREMENT_MARKERS: tuple[str, ...] = (
    "退役", "已删除", "已移除", "移除", "删除", "不存在", "已过期", "已下线",
    "不再", "勿再执行", "已取消", "已作废",
    "retired", "removed", "deleted", "no longer", "gone",
)

# Outward-facing material a reader is expected to follow.
SCAN_GLOBS: tuple[str, ...] = (
    "README.md",
    "docs/README.md",
    "docs/demo/**/*.md",
    "docs/architecture/**/*.md",
    "packages/**/README.md",
)

# Archived material. Each entry carries its reason so the exclusion is visible, not silent.
EXEMPT: tuple[tuple[str, str], ...] = (
    ("CHANGELOG.md", "release history: cites every removal by design"),
    ("docs/release/**", "release notes / frozen cloud checklists"),
    ("docs/R&D/**", "decision log: records what was retired and why"),
    ("docs/agent-ops/**", "rules and operations records"),
    ("test_data/acceptance/**", "frozen acceptance checklists and the UI matrix"),
    ("docs/architecture/v1.*-roadmap.md", "archived roadmap"),
    ("docs/architecture/pp-structurev3-fix-plan.md", "pre-v1.8 fix analysis (history)"),
)

# Tolerance for historical lines that live *inside* a scanned, still-current doc.
# Literal substrings (never regex), file-scoped, and the cap may only go down - see selftest.
ALLOWLIST: tuple[tuple[str, str, str], ...] = (
    ("docs/architecture/CLOUD_VALIDATION.md", "LITE-PREVIEW",
     "v1.2-v1.4 release-gate rows under the frozen section-2 banner"),
    ("docs/architecture/CLOUD_VALIDATION.md", "LITE-BATCH",
     "v1.2-v1.4 release-gate rows under the frozen section-2 banner"),
)
MAX_ALLOWLIST = 2


def _tokens_in(line: str) -> list[str]:
    """Retired tokens present in one line (case-insensitive literal substring)."""
    low = line.lower()
    return [token for token, _ in RETIRED if token.lower() in low]


def _token_reason(token: str) -> str:
    return dict(RETIRED)[token]


def _is_notice(line: str) -> bool:
    """True when the line itself declares the removal (so it is history, not an instruction)."""
    low = line.lower()
    return any(marker.lower() in low for marker in RETIREMENT_MARKERS)


def _exempt_reason(rel: str) -> str | None:
    """Reason why a repo-relative path is archived material, or ``None`` when it is scanned."""
    for pattern, reason in EXEMPT:
        if rel == pattern or fnmatch.fnmatch(rel, pattern):
            return reason
    return None


def _allowlisted(rel: str, line: str) -> str | None:
    for file_match, needle, reason in ALLOWLIST:
        if rel == file_match and needle in line:
            return reason
    return None


def _scanned_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in SCAN_GLOBS:
        files.update(p for p in REPO_ROOT.glob(pattern) if p.is_file())
    return sorted(files)


def check_retired_refs() -> list[dict]:
    """FAIL on a retired reference in outward-facing docs unless the line is a notice."""
    issues: list[dict] = []
    for path in _scanned_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if _exempt_reason(rel):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            hits = _tokens_in(line)
            if not hits or _is_notice(line) or _allowlisted(rel, line):
                continue
            excerpt = " ".join(line.split())
            if len(excerpt) > 80:
                excerpt = excerpt[:80] + "..."
            issues.append({
                "check": "retired-refs", "level": "ERROR", "path": rel,
                "msg": (f"L{lineno} retired reference {hits[0]!r} "
                        f"({_token_reason(hits[0])}) | {excerpt}"),
            })
    return issues


# --- 3. decision-log metadata + staleness (DOC-3, P-025) ------------------------------------

PENDING_REL = "docs/R&D/PENDING.md"
# Same shape as frontend_coupling.ORPHAN_STALE_DAYS: past a quarter it is no longer "next batch".
PENDING_STALE_DAYS = 90
PENDING_STATES = ("open", "decided", "landed", "retained")
PENDING_META_SHAPE = "> status: <open|decided|landed|retained> · since: YYYY-MM-DD"

# The header is an index of ids plus a count - never a second copy of the state breakdown.
PENDING_COUNT_RE = re.compile(r"^## 待确认（本区共 \*\*(\d+)\*\* 条）", re.M)
PENDING_INDEX_RE = re.compile(r"^- \*\*机检索引（勿手改）\*\*：(.+)$", re.M)
PENDING_HEADING_RE = re.compile(r"^### (P-\d+) · ", re.M)
PENDING_META_RE = re.compile(r"^> status: ([a-z]+) · since: (\d{4}-\d{2}-\d{2})$", re.M)


def _pending_issue(level: str, msg: str) -> dict:
    return {"check": "pending", "level": level, "path": PENDING_REL, "msg": msg}


def parse_pending_entries(text: str) -> list[dict]:
    """Split the decision log into entries and read each entry's metadata line (pure)."""
    heads = [(m.start(), m.group(1)) for m in PENDING_HEADING_RE.finditer(text)]
    entries: list[dict] = []
    for idx, (pos, pid) in enumerate(heads):
        end = heads[idx + 1][0] if idx + 1 < len(heads) else len(text)
        meta = PENDING_META_RE.search(text[pos:end])
        entries.append({
            "id": pid,
            "status": meta.group(1) if meta else None,
            "since": meta.group(2) if meta else None,
            "line": text.count("\n", 0, pos) + 1,
        })
    return entries


def check_pending_staleness(text: str | None = None, today: date | None = None) -> list[dict]:
    """DOC-3: entry metadata is present/valid, and no `landed` entry is left unpromoted.

    ``docs/R&D/**`` is gitignored apart from ``README.md`` and this log, so CI can never see the
    other R&D files - the committed decision log is the checkable half. Note that PENDING is
    exempt from the DOC-1 tombstone scan *on purpose* (a decision log cites removals); that
    exemption does not apply here.
    """
    if text is None:
        try:
            text = (REPO_ROOT / PENDING_REL).read_text(encoding="utf-8")
        except OSError as exc:
            return [_pending_issue("ERROR", f"decision log unreadable ({exc}); fail-closed")]
    today = today or date.today()
    issues: list[dict] = []
    entries = parse_pending_entries(text)
    if not entries:
        return [_pending_issue("ERROR", "no `### P-xxx` entry heading found; fail-closed")]

    for entry in entries:
        where = f"{entry['id']} (L{entry['line']})"
        status, since = entry["status"], entry["since"]
        if status is None:
            issues.append(_pending_issue(
                "ERROR", f"{where} has no metadata line `{PENDING_META_SHAPE}`; fail-closed"))
            continue
        if status not in PENDING_STATES:
            issues.append(_pending_issue(
                "ERROR", f"{where} status {status!r} is not one of {list(PENDING_STATES)}"))
            continue
        try:
            decided_on = date.fromisoformat(since)
        except (TypeError, ValueError):
            issues.append(_pending_issue(
                "ERROR", f"{where} since must be an ISO date (YYYY-MM-DD), got {since!r}"))
            continue
        if decided_on > today:
            issues.append(_pending_issue("ERROR", f"{where} since {since} is in the future"))
        elif status == "landed" and (today - decided_on).days > PENDING_STALE_DAYS:
            issues.append(_pending_issue(
                "WARN", f"{where} landed {since} ({(today - decided_on).days} days ago) - promote it "
                        "into docs/architecture or reclassify as `retained` and state why it stays"))

    ids = [entry["id"] for entry in entries]
    if len(set(ids)) != len(ids):
        dupes = sorted({pid for pid in ids if ids.count(pid) > 1})
        issues.append(_pending_issue("ERROR", f"duplicate entry heading(s): {', '.join(dupes)}"))

    count_m, index_m = PENDING_COUNT_RE.search(text), PENDING_INDEX_RE.search(text)
    if not count_m or not index_m:
        issues.append(_pending_issue(
            "ERROR", "header index missing: needs `## 待确认（本区共 **N** 条）` plus a "
                     "`- **机检索引（勿手改）**：<ids>` line; fail-closed"))
        return issues
    listed = re.findall(r"P-\d+", index_m.group(1))
    if sorted(set(listed)) != sorted(set(ids)):
        missing = sorted(set(ids) - set(listed))
        extra = sorted(set(listed) - set(ids))
        parts = ([f"missing {', '.join(missing)}"] if missing else []) \
            + ([f"listed but absent {', '.join(extra)}"] if extra else [])
        issues.append(_pending_issue(
            "ERROR", f"header index does not match the `### P-xxx` headings ({'; '.join(parts)})"))
    if int(count_m.group(1)) != len(ids):
        issues.append(_pending_issue(
            "ERROR", f"header says {count_m.group(1)} entries, found {len(ids)} heading(s)"))
    return issues


def selftest_cases() -> list[tuple[str, bool]]:
    """In-memory regressions for the pure predicates (no repo reads)."""
    cases: list[tuple[str, bool]] = []

    def ok(name: str, cond: object) -> None:
        cases.append((name, bool(cond)))

    ok("tokens: case-insensitive hit", _tokens_in("see LITE-PREVIEW-001") == ["lite-preview"])
    ok("tokens: port hit", _tokens_in("curl http://127.0.0.1:8001/api/v1/lite/health") == [":8001"])
    ok("tokens: clean line has none",
       _tokens_in("cd backend && python run.py") == []
       and _tokens_in("`packages/docuvision-core` is a path dependency") == [])
    ok("notice: marker exempts the line", _is_notice("`apps/lite/**` 已删除"))
    ok("notice: instruction is not a notice",
       not _is_notice("cd apps/lite/backend && python run_lite.py"))
    ok("exempt: release notes / changelog / decision log",
       all(_exempt_reason(p) for p in (
           "docs/release/RELEASE_1.4_NOTES.md", "CHANGELOG.md", "docs/R&D/PENDING.md",
           "test_data/acceptance/UI_VERIFICATION_MATRIX.md", "docs/agent-ops/core/testing.md")))
    ok("exempt: living docs are scanned",
       all(_exempt_reason(p) is None for p in (
           "README.md", "docs/architecture/shared-ui-shell.md", "docs/demo/TRIAL_DEMO.md",
           "packages/docuvision-core/README.md", "docs/architecture/CLOUD_VALIDATION.md")))
    ok("allowlist: literal and file-scoped",
       _allowlisted("docs/architecture/CLOUD_VALIDATION.md", "x LITE-PREVIEW y") is not None
       and _allowlisted("docs/demo/TRIAL_DEMO.md", "x LITE-PREVIEW y") is None)
    ok("allowlist: cap can only go down", len(ALLOWLIST) <= MAX_ALLOWLIST)
    ok("norm_ref: drops line suffix, rejects globs",
       norm_ref("backend/app/x.py:12") == "backend/app/x.py"
       and norm_ref("frontend/**/*.js") is None
       and norm_ref("a/...") is None)

    # --- DOC-3: PENDING entry metadata / staleness / header index -----------------------------
    today = date(2026, 9, 26)

    def pend_entry(pid: str, status: str | None, since: str = "2026-09-01") -> str:
        meta = "" if status is None else f"> status: {status} · since: {since}\n"
        return f"### {pid} · title {pid}\n{meta}- body\n\n"

    def pend_log(count: int, ids: list[str], body: str) -> str:
        listed = " ".join(f"`{pid}`" for pid in ids)
        return (f"## 待确认（本区共 **{count}** 条）\n\n"
                f"- **机检索引（勿手改）**：{listed}\n\n{body}")

    def pend_issues(text: str) -> list[dict]:
        return check_pending_staleness(text=text, today=today)

    def pend_levels(text: str) -> list[str]:
        return [i["level"] for i in pend_issues(text)]

    healthy = pend_log(2, ["P-001", "P-002"],
                       pend_entry("P-001", "landed", "2026-09-24")
                       + pend_entry("P-002", "open", "2026-09-13"))
    ok("pending: an in-shape log is clean", pend_issues(healthy) == [])
    ok("pending: missing metadata fails closed",
       pend_levels(pend_log(1, ["P-001"], pend_entry("P-001", None))) == ["ERROR"])
    ok("pending: unknown status is an ERROR",
       pend_levels(pend_log(1, ["P-001"], pend_entry("P-001", "wip"))) == ["ERROR"])
    ok("pending: non-ISO date is an ERROR",
       pend_levels(pend_log(1, ["P-001"], pend_entry("P-001", "landed", "2026/09/01"))) == ["ERROR"])
    ok("pending: future date is an ERROR",
       pend_levels(pend_log(1, ["P-001"], pend_entry("P-001", "landed", "2026-10-01"))) == ["ERROR"])
    ok("pending: landed > 90 days is a WARN (no ERROR)",
       pend_levels(pend_log(1, ["P-001"], pend_entry("P-001", "landed", "2026-06-01"))) == ["WARN"])
    ok("pending: landed inside the window is clean",
       pend_issues(pend_log(1, ["P-001"], pend_entry("P-001", "landed", "2026-06-29"))) == [])
    ok("pending: retained is exempt from the clock",
       pend_issues(pend_log(1, ["P-001"], pend_entry("P-001", "retained", "2025-01-01"))) == [])
    ok("pending: open is exempt from the clock",
       pend_issues(pend_log(1, ["P-001"], pend_entry("P-001", "open", "2025-01-01"))) == [])
    ok("pending: header index must list every heading",
       any("header index" in i["msg"] for i in
           pend_issues(pend_log(1, ["P-001"], pend_entry("P-001", "open") + pend_entry("P-002", "open")))))
    ok("pending: header count must match the headings",
       any("header says" in i["msg"] for i in
           pend_issues(pend_log(9, ["P-001"], pend_entry("P-001", "open")))))
    ok("pending: duplicate heading is an ERROR",
       any("duplicate" in i["msg"] for i in
           pend_issues(pend_log(1, ["P-001"], pend_entry("P-001", "open") + pend_entry("P-001", "open")))))
    ok("pending: a missing header index fails closed",
       pend_levels(pend_entry("P-001", "open")) == ["ERROR"])
    return cases


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        cases = selftest_cases()
        failed = [name for name, passed in cases if not passed]
        for name, passed in cases:
            print(f"{'ok  ' if passed else 'FAIL'} {name}")
        print(f"selftest: {len(cases) - len(failed)}/{len(cases)} passed")
        return 1 if failed else 0
    issues = check_doc_drift() + check_retired_refs() + check_pending_staleness()
    for issue in issues:
        print(f"[{issue['level']}] {issue['path']}: {issue['msg']}")
    errors = sum(1 for issue in issues if issue["level"] == "ERROR")
    print(f"docs_refs_audit: {errors} error(s), {len(issues) - errors} warning(s)")
    scanned = len([p for p in _scanned_files() if _exempt_reason(
        p.relative_to(REPO_ROOT).as_posix()) is None])
    print(f"docs_refs_audit: scanned {scanned} outward-facing file(s); "
          f"{len(RETIRED)} tombstone token(s); {len(ALLOWLIST)} allowlist entry/entries")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
