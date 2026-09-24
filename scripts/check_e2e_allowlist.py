#!/usr/bin/env python3
"""E2E gate for the Playwright suite: allowlist hygiene + suite pin (P-008 gap 2, step 2).

The suite joined CI on 2026-09-20 (`.github/workflows/lint.yml`, job `e2e`, main-only like the
other workflows). Two things make a runtime-error gate rot, and both are machine-checked here -
this script is stdlib-only, so it runs in the *lint* job and cannot be skipped by an e2e-job
path filter:

1. **Allowlist hygiene** (`frontend/tests/e2e/expected-errors.json`). A runtime-error assertion
   is only as strong as the list of errors it tolerates. The 2026-09-17 decision was to start
   from **zero** entries ("clean it before you wire it", the same rule ESLint was gated under),
   so every later entry needs to be visible, justified and dated:
   * `match` must be a **literal substring** - regex metacharacters are rejected, because one
     `.*` would swallow the whole gate while looking like a single line of YAML-ish config;
   * `reason` (>= 20 chars) and `added` (ISO date, not in the future) are required, and unknown
     keys are an ERROR (a typo'd field must not be silently ignored);
   * an entry older than `E2E_ALLOWLIST_STALE_DAYS` = WARN ("re-decide fix-or-keep"), the same
     mechanism as A6 for `known_orphans`;
   * the entry count is capped by `scripts/e2e_allowlist_ratchet.json` (ERROR above the cap,
     NOTE when the cap can be lowered - the ratchet only ever goes down).

2. **Suite pin** (`scripts/e2e_suite_pin.json`). A gate also rots by *shrinking*: a deleted
   spec, a `test.skip`, or a typo'd `test(...)` all remove protection without turning anything
   red. The pin asserts the collected spec-file count and top-level `test(` count measured from
   the spec sources (mirroring `playwright.config.js` `testMatch` / `testIgnore`), and treats
   `test.skip` / `test.fixme` anywhere in the counted specs as an ERROR.

Modes:
  (default)    run both checks against the repo, exit 1 on any ERROR
  --selftest   in-memory regressions for every rule above (no repo reads)
  --update     lower the recorded ratchet cap to the current entry count (never raises it);
               same convention as `lint_file_size.py --update`, and CI never passes it

Exit codes: 0 = pass, 1 = findings (ERROR present), 2 = cannot evaluate.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
E2E_DIR = REPO_ROOT / "frontend" / "tests" / "e2e"
ALLOWLIST = E2E_DIR / "expected-errors.json"
RATCHET = REPO_ROOT / "scripts" / "e2e_allowlist_ratchet.json"
PIN = REPO_ROOT / "scripts" / "e2e_suite_pin.json"

SPEC_SUFFIX = ".e2e.js"

# One quarter, same as ORPHAN_STALE_DAYS (frontend_coupling.py): short enough that a deferral
# cannot outlive the release line that made it, long enough not to nag every batch.
E2E_ALLOWLIST_STALE_DAYS = 90
MIN_MATCH_LEN = 12
MIN_REASON_LEN = 20
# A literal substring, so there is no reason for a metacharacter to appear - and every one of
# these would widen the entry beyond what its reason describes.
REGEX_META_RE = re.compile(r"[.*+?\[\](){}|^$\\]")
# Boilerplate that would match almost any failing page (and every network hiccup).
DENY_EXACT = {
    "error",
    "errors",
    "undefined",
    "null",
    "typeerror",
    "referenceerror",
    "uncaught",
    "uncaught (in promise)",
    "failed to load resource",
}
DENY_SUBSTR = ("failed to load resource", "net::err_")

ENTRY_KEYS = {"match", "reason", "added"}
ALLOWLIST_KEYS = {"note", "entries"}

_TEST_RE = re.compile(r"^\s*test\(")
_SKIP_RE = re.compile(r"^\s*test\.(?:skip|fixme)\(")
_DESCRIBE_SKIP_RE = re.compile(r"^\s*test\.describe\.(?:skip|fixme)\(")


def _issue(level: str, msg: str) -> tuple[str, str]:
    return (level, msg)


# --- 1. allowlist hygiene ---------------------------------------------------


def check_allowlist(raw: object, cap: object, today: date | None = None) -> list[tuple[str, str]]:
    """Validate the parsed allowlist plus its ratchet cap. Pure function (selftest-friendly)."""
    today = today or date.today()
    out: list[tuple[str, str]] = []

    if isinstance(raw, list):
        entries, note = raw, None
    elif isinstance(raw, dict):
        unknown = sorted(set(raw) - ALLOWLIST_KEYS)
        if unknown:
            out.append(_issue("ERROR", f"expected-errors.json has unknown top-level key(s): {unknown}"))
        note = raw.get("note")
        entries = raw.get("entries")
        if note is not None and not isinstance(note, str):
            out.append(_issue("ERROR", "expected-errors.json `note` must be a string"))
        if entries is None:
            out.append(_issue("ERROR", "expected-errors.json needs an `entries` list (may be empty)"))
            entries = []
    else:
        out.append(_issue("ERROR", f"expected-errors.json must be an object or a list, got {type(raw).__name__}"))
        entries = []

    if not isinstance(entries, list):
        out.append(_issue("ERROR", f"expected-errors.json `entries` must be a list, got {type(entries).__name__}"))
        entries = []

    for index, entry in enumerate(entries):
        where = f"entries[{index}]"
        if not isinstance(entry, dict):
            out.append(_issue("ERROR", f"{where} must be an object with match/reason/added"))
            continue
        unknown = sorted(set(entry) - ENTRY_KEYS)
        if unknown:
            out.append(_issue("ERROR", f"{where} has unknown key(s): {unknown} (allowed: {sorted(ENTRY_KEYS)})"))

        match = entry.get("match")
        if not isinstance(match, str) or not match.strip():
            out.append(_issue("ERROR", f"{where}.match must be a non-empty string"))
        else:
            stripped = match.strip()
            if len(stripped) < MIN_MATCH_LEN:
                out.append(_issue(
                    "ERROR",
                    f"{where}.match is {len(stripped)} chars; a match shorter than {MIN_MATCH_LEN} "
                    "cannot identify one error (it would tolerate a whole class)",
                ))
            if REGEX_META_RE.search(stripped):
                out.append(_issue(
                    "ERROR",
                    f"{where}.match contains a regex metacharacter ({stripped!r}); entries are "
                    "LITERAL substrings - one wildcard would silently disable the gate",
                ))
            low = stripped.lower()
            if low in DENY_EXACT or any(part in low for part in DENY_SUBSTR):
                out.append(_issue(
                    "ERROR",
                    f"{where}.match is boilerplate ({stripped!r}); it would tolerate unrelated "
                    "failures instead of naming this one",
                ))

        reason = entry.get("reason")
        if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON_LEN:
            out.append(_issue(
                "ERROR",
                f"{where}.reason must be a string of at least {MIN_REASON_LEN} chars "
                "(why this error is expected, not a restatement of the message)",
            ))

        added = entry.get("added")
        try:
            added_date = date.fromisoformat(added) if isinstance(added, str) else None
            if added_date is None:
                raise ValueError(added)
        except ValueError:
            out.append(_issue("ERROR", f"{where}.added must be an ISO date (YYYY-MM-DD), got {added!r}"))
            continue
        if added_date > today:
            out.append(_issue("ERROR", f"{where}.added ({added}) is in the future"))
            continue
        age = (today - added_date).days
        if age > E2E_ALLOWLIST_STALE_DAYS:
            out.append(_issue(
                "WARN",
                f"{where} added {added} ({age} days ago) - re-decide fix-or-keep and record the "
                "decision in PENDING (P-008 gap 2)",
            ))

    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
        out.append(_issue("ERROR", f"e2e_allowlist_ratchet.json `max_entries` must be a non-negative int, got {cap!r}"))
    elif len(entries) > cap:
        out.append(_issue(
            "ERROR",
            f"{len(entries)} allowlist entries exceed the ratchet cap of {cap}; fix the causes "
            "or get the cap raised as an explicit decision (never raise it to make CI green)",
        ))
    return out


def lowered_cap(count: int, cap: object) -> int | None:
    """The cap ``--update`` would record: lower-only, never raise (ratchet discipline).

    A hint printed on every run would just become background noise (the repo's other ratchets
    print nothing and are lowered on demand), so headroom is invisible until a maintainer runs
    ``--update`` - which is exactly when they are looking at the file anyway.
    """
    if isinstance(cap, int) and not isinstance(cap, bool) and 0 <= count < cap:
        return count
    return None


# --- 2. suite pin -----------------------------------------------------------


def measure_suite(sources: dict[str, str]) -> dict[str, int]:
    """Count collected spec files, top-level ``test(`` cases and skips from spec sources.

    ``sources`` maps a repo-relative posix path to its text; only ``*.e2e.js`` counts
    (mirrors the Playwright config's ``testMatch``).
    """
    files = 0
    tests = 0
    skips = 0
    for rel, text in sorted(sources.items()):
        if not rel.endswith(SPEC_SUFFIX):
            continue
        files += 1
        for line in text.splitlines():
            if _TEST_RE.match(line):
                tests += 1
            if _SKIP_RE.match(line) or _DESCRIBE_SKIP_RE.match(line):
                skips += 1
    return {"spec_files": files, "tests": tests, "skips": skips}


def check_suite(measured: dict[str, int], pin: object) -> list[tuple[str, str]]:
    """Compare a measurement against the pin. Pure function (selftest-friendly)."""
    out: list[tuple[str, str]] = []
    if not isinstance(pin, dict):
        return [_issue("ERROR", f"e2e_suite_pin.json must be an object, got {type(pin).__name__}")]
    for key in ("spec_files", "tests"):
        want = pin.get(key)
        got = measured.get(key)
        if not isinstance(want, int) or isinstance(want, bool):
            out.append(_issue("ERROR", f"e2e_suite_pin.json `{key}` must be an int, got {want!r}"))
        elif want != got:
            out.append(_issue(
                "ERROR",
                f"e2e suite {key}: measured {got}, pinned {want} - the gate shrank or grew. Update "
                "scripts/e2e_suite_pin.json in the same commit as the intended change.",
            ))
    if measured.get("skips"):
        out.append(_issue(
            "ERROR",
            f"{measured['skips']} test.skip / test.fixme in the counted specs - a skipped test "
            "removes protection silently; delete the test or keep it running",
        ))
    return out


# --- 3. repo wiring ---------------------------------------------------------


def read_json(path: Path) -> tuple[object | None, list[tuple[str, str]]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [_issue("ERROR", f"missing {path.relative_to(REPO_ROOT).as_posix()}")]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [_issue("ERROR", f"{path.relative_to(REPO_ROOT).as_posix()} is not readable JSON: {exc}")]


def read_specs() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(E2E_DIR.rglob(f"*{SPEC_SUFFIX}")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            out[rel] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            out[rel] = ""
    return out


def run_checks() -> int:
    issues: list[tuple[str, str]] = []
    raw, err = read_json(ALLOWLIST)
    issues += err
    cap_raw, err = read_json(RATCHET)
    issues += err
    pin, err = read_json(PIN)
    issues += err
    cap = (cap_raw or {}).get("max_entries") if isinstance(cap_raw, dict) else None
    issues += check_allowlist(raw, cap)
    issues += check_suite(measure_suite(read_specs()), pin)

    for level, msg in issues:
        print(f"[{level}] {msg}")
    errors = sum(1 for level, _ in issues if level == "ERROR")
    warns = sum(1 for level, _ in issues if level == "WARN")
    print(f"check_e2e_allowlist: {errors} error(s), {warns} warning(s)")
    return 1 if errors else 0


def run_update() -> int:
    """Lower the ratchet cap to the measured entry count (mirrors lint_file_size.py --update)."""
    raw, err = read_json(ALLOWLIST)
    if err:
        for level, msg in err:
            print(f"[{level}] {msg}")
        return 2
    cap_raw, err = read_json(RATCHET)
    if err:
        for level, msg in err:
            print(f"[{level}] {msg}")
        return 2
    if not isinstance(cap_raw, dict):
        print("[ERROR] e2e_allowlist_ratchet.json must be an object")
        return 2
    entries = (raw.get("entries") if isinstance(raw, dict) else raw) or []
    count = len(entries) if isinstance(entries, list) else 0
    new_cap = lowered_cap(count, cap_raw.get("max_entries"))
    if new_cap is None:
        print(f"[check_e2e_allowlist] ratchet cap unchanged at {cap_raw.get('max_entries')!r}")
        return 0
    print(f"[lowered] max_entries: {cap_raw['max_entries']} -> {new_cap}")
    cap_raw["max_entries"] = new_cap
    RATCHET.write_text(json.dumps(cap_raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("[check_e2e_allowlist] ratchet updated")
    return 0


# --- 4. selftest ------------------------------------------------------------


def _entry(match: str = "ReferenceError: adjustDocumentSize is not defined",
           reason: str = "masks a known preview defect tracked in PENDING P-016",
           added: str = "2026-09-20") -> dict:
    return {"match": match, "reason": reason, "added": added}


def _levels(issues: list[tuple[str, str]]) -> list[str]:
    return [level for level, _ in issues]


def selftest_cases() -> list[tuple[str, bool]]:
    today = date(2026, 9, 20)
    clean = lambda issues: issues == []  # noqa: E731 - terse in a table of cases
    cases: list[tuple[str, bool]] = []

    def ok(name: str, cond: bool) -> None:
        cases.append((name, bool(cond)))

    ok("empty baseline is clean", clean(check_allowlist({"note": "x", "entries": []}, 5, today)))
    ok("bare list form accepted", clean(check_allowlist([], 5, today)))
    ok("valid entry passes",
       clean(check_allowlist({"entries": [_entry()]}, 5, today)))
    ok("fresh entry does not warn",
       clean(check_allowlist({"entries": [_entry(added="2026-08-21")]}, 5, today)))

    missing_reason = _entry()
    missing_reason.pop("reason")
    ok("missing reason -> ERROR", _levels(check_allowlist({"entries": [missing_reason]}, 5, today)) == ["ERROR"])
    ok("short reason -> ERROR",
       _levels(check_allowlist({"entries": [_entry(reason="expected")]}, 5, today)) == ["ERROR"])
    ok("regex metacharacter -> ERROR",
       _levels(check_allowlist({"entries": [_entry(match="ReferenceError.*not defined")]}, 5, today)) == ["ERROR"])
    ok("short match -> ERROR",
       _levels(check_allowlist({"entries": [_entry(match="not defined")]}, 5, today)) == ["ERROR"])
    ok("boilerplate match -> ERROR",
       _levels(check_allowlist({"entries": [_entry(match="Failed to load resource")]}, 5, today)) == ["ERROR"])
    ok("network boilerplate -> ERROR",
       _levels(check_allowlist({"entries": [_entry(match="net::ERR_CONNECTION_REFUSED")]}, 5, today)) == ["ERROR"])
    ok("unknown entry key -> ERROR",
       _levels(check_allowlist(
           {"entries": [{**_entry(), "owner": "someone"}]}, 5, today)) == ["ERROR"])
    ok("unknown top-level key -> ERROR",
       _levels(check_allowlist({"entries": [], "cap": 1}, 5, today)) == ["ERROR"])
    ok("missing entries key -> ERROR",
       _levels(check_allowlist({"note": "x"}, 5, today)) == ["ERROR"])
    ok("entries not a list -> ERROR",
       _levels(check_allowlist({"entries": "nope"}, 5, today)) == ["ERROR"])
    ok("bad date -> ERROR",
       _levels(check_allowlist({"entries": [_entry(added="2026/09/20")]}, 5, today)) == ["ERROR"])
    ok("future date -> ERROR",
       _levels(check_allowlist({"entries": [_entry(added="2026-09-21")]}, 5, today)) == ["ERROR"])
    ok("stale entry -> WARN",
       _levels(check_allowlist({"entries": [_entry(added="2026-05-01")]}, 5, today)) == ["WARN"])
    ok("over cap -> ERROR",
       _levels(check_allowlist({"entries": [_entry() for _ in range(6)]}, 5, today)) == ["ERROR"])
    ok("at cap is not a violation", clean(check_allowlist({"entries": [_entry() for _ in range(5)]}, 5, today)))
    ok("--update lowers the cap", lowered_cap(0, 5) == 0)
    ok("--update never raises the cap", lowered_cap(6, 5) is None)
    ok("--update is a no-op at the cap", lowered_cap(5, 5) is None)
    ok("--update ignores a bad cap", lowered_cap(0, None) is None)
    ok("bad cap -> ERROR", _levels(check_allowlist({"entries": []}, None, today)) == ["ERROR"])
    ok("negative cap -> ERROR", _levels(check_allowlist({"entries": []}, -1, today)) == ["ERROR"])

    good_pin = {"spec_files": 1, "tests": 2}
    good_measure = {"spec_files": 1, "tests": 2, "skips": 0}
    ok("suite pin match is clean", clean(check_suite(good_measure, good_pin)))
    ok("suite pin test-count drift -> ERROR",
       _levels(check_suite({"spec_files": 1, "tests": 1, "skips": 0}, good_pin)) == ["ERROR"])
    ok("suite pin spec-count drift -> ERROR",
       _levels(check_suite({"spec_files": 2, "tests": 2, "skips": 0}, good_pin)) == ["ERROR"])
    ok("suite pin non-int -> ERROR",
       _levels(check_suite(good_measure, {"spec_files": "1", "tests": 2})) == ["ERROR"])
    ok("skipped test -> ERROR",
       _levels(check_suite({"spec_files": 1, "tests": 2, "skips": 1}, good_pin)) == ["ERROR"])

    spec = "\n".join([
        "test.describe('X', () => {",
        "  test('a', async () => {});",
        "  test('b', async () => {});",
        "});",
    ])
    measured = measure_suite({
        "frontend/tests/e2e/a.e2e.js": spec,
        "frontend/tests/e2e/helpers/coverage.js": "test('not a spec')",
    })
    ok("measure counts only *.e2e.js",
       measured == {"spec_files": 1, "tests": 2, "skips": 0})
    ok("measure counts skips",
       measure_suite({"frontend/tests/e2e/a.e2e.js": "  test.skip('x', () => {});"})["skips"] == 1)
    ok("measure counts test.describe.skip as a skip",
       measure_suite({"frontend/tests/e2e/a.e2e.js": "test.describe.skip('x', () => {});"})["skips"] == 1)
    return cases


def run_selftest() -> int:
    cases = selftest_cases()
    failed = [name for name, ok in cases if not ok]
    for name, ok in cases:
        print(f"{'ok  ' if ok else 'FAIL'} {name}")
    print(f"selftest: {len(cases) - len(failed)}/{len(cases)} passed")
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        return run_selftest()
    if "--update" in argv:
        return run_update()
    if argv[1:]:
        print(__doc__.split("Modes:")[0].strip())
        print(f"unknown argument(s): {argv[1:]}", file=sys.stderr)
        return 2
    return run_checks()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
