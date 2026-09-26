#!/usr/bin/env python3
"""E2: the unit suite cannot shrink silently (the e2e pin's counterpart).

The vitest suite runs in CI inside the required `lint` job (`.github/workflows/lint.yml`,
2026-09-20, "v1.9 S0"), so a red suite blocks a merge. What nothing caught is *shrinkage*: delete
a spec file or add `it.skip` and every remaining test still passes - the same failure shape that
`scripts/e2e_suite_pin.json` + **E1** guard on the e2e side. P-008 recorded this as its last
residual after the F6 name-level assertion was accepted by decision (2026-09-26).

Measured from the sources (mirroring vitest's `frontend/tests/unit/**/*.test.js` scope) and
compared with `scripts/unit_suite_pin.json`:

* `test_files` - collected `*.test.js` files;
* `cases` - lines declaring a case (`it(...)` / `test(...)`; modifiers such as `it.each(...)`
  allowed, since a table-driven case is one declaration);
* `skips` - `it.skip` / `it.todo` / `test.skip` / `describe.skip` / `describe.todo` anywhere: a
  skipped case removes protection, so it is an ERROR rather than a count.

Deliberately **not** measured: assertion strength (a case can be rewritten weaker without moving
any count), and vitest's runtime collection (the pin is a floor against silent deletion, not a
quality metric). Stdlib only, so `audit_agent_ops.py` evaluates it inside the already-required
`agent-ops-audit` check - **no CI configuration change**.

Standalone: ``python scripts/unit_suite_pin.py [--selftest]``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UNIT_DIR = REPO_ROOT / "frontend" / "tests" / "unit"
PIN = REPO_ROOT / "scripts" / "unit_suite_pin.json"
PIN_REL = "scripts/unit_suite_pin.json"

UNIT_SUFFIX = ".test.js"
PIN_COUNT_KEYS = ("test_files", "cases")
PIN_KEYS = (*PIN_COUNT_KEYS, "note")

_CASE_RE = re.compile(r"^\s*(?:it|test)(?:\.\w+)*\(")
_SKIP_RE = re.compile(r"^\s*(?:it|test|describe)\.(?:skip|todo)\(")


def measure_unit_suite(sources: dict[str, str]) -> dict[str, int]:
    """Count spec files, case declarations and skips from the sources (pure)."""
    files = cases = skips = 0
    for rel, text in sorted(sources.items()):
        if not rel.endswith(UNIT_SUFFIX):
            continue
        files += 1
        for line in text.splitlines():
            skipped = _SKIP_RE.match(line)
            if skipped:
                skips += 1
            if _CASE_RE.match(line) and not skipped:
                cases += 1
    return {"test_files": files, "cases": cases, "skips": skips}


def check_unit_suite(measured: object, pin: object) -> list[tuple[str, str]]:
    """Compare a measurement against the pin. Pure function (selftest-friendly)."""
    if not isinstance(measured, dict):
        return [("ERROR", f"measurement must be a dict, got {type(measured).__name__}")]
    out: list[tuple[str, str]] = []
    if not isinstance(pin, dict):
        return [("ERROR", f"{PIN_REL} must be an object, got {type(pin).__name__}")]
    unknown = sorted(set(pin) - set(PIN_KEYS))
    if unknown:
        out.append(("ERROR", f"{PIN_REL} has unknown key(s): {unknown}"))
    for key in PIN_COUNT_KEYS:
        want, got = pin.get(key), measured.get(key)
        if not isinstance(want, int) or isinstance(want, bool):
            out.append(("ERROR", f"{PIN_REL} `{key}` must be an int, got {want!r}"))
        elif want != got:
            out.append((
                "ERROR",
                f"unit suite {key}: measured {got}, pinned {want} - the suite shrank or grew. "
                f"Update {PIN_REL} in the same commit as the intended change.",
            ))
    if measured.get("skips"):
        out.append((
            "ERROR",
            f"{measured['skips']} skipped/todo case(s) in the unit suite - a skipped test removes "
            "protection silently; delete the case or keep it running",
        ))
    if not measured.get("test_files"):
        out.append(("ERROR", "no *.test.js found under frontend/tests/unit - an empty suite "
                             "protects nothing; fail-closed"))
    return out


def read_sources() -> dict[str, str]:
    out: dict[str, str] = {}
    if not UNIT_DIR.is_dir():
        return out
    for path in sorted(UNIT_DIR.rglob(f"*{UNIT_SUFFIX}")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            out[rel] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            out[rel] = ""
    return out


def check_unit_pin() -> list[dict]:
    """Repo wiring: measure the suite on disk and compare it with the pin (audit-shaped issues)."""
    issues: list[dict] = []
    try:
        pin = json.loads(PIN.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pin, issues = None, [{"check": "unit-pin", "level": "ERROR", "path": PIN_REL,
                              "msg": f"missing {PIN_REL}; the anti-shrink pin must exist (fail-closed)"}]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        pin, issues = None, [{"check": "unit-pin", "level": "ERROR", "path": PIN_REL,
                              "msg": f"{PIN_REL} is not readable JSON: {exc}"}]
    if pin is None:
        return issues
    for level, msg in check_unit_suite(measure_unit_suite(read_sources()), pin):
        issues.append({"check": "unit-pin", "level": level, "path": PIN_REL, "msg": msg})
    return issues


def selftest_cases() -> list[tuple[str, bool]]:
    """In-memory regressions for the pure predicates (no repo reads)."""
    cases: list[tuple[str, bool]] = []

    def ok(name: str, cond: object) -> None:
        cases.append((name, bool(cond)))

    def levels(measured: object, pin: object) -> list[str]:
        return [level for level, _ in check_unit_suite(measured, pin)]

    clean_pin = {"test_files": 1, "cases": 2}
    clean_measure = {"test_files": 1, "cases": 2, "skips": 0}
    ok("pin: a matching measurement is clean", check_unit_suite(clean_measure, clean_pin) == [])
    ok("pin: case count drift -> ERROR",
       levels({"test_files": 1, "cases": 1, "skips": 0}, clean_pin) == ["ERROR"])
    ok("pin: file count drift -> ERROR",
       levels({"test_files": 2, "cases": 2, "skips": 0}, clean_pin) == ["ERROR"])
    ok("pin: non-int pin value -> ERROR",
       levels(clean_measure, {"test_files": "1", "cases": 2}) == ["ERROR"])
    ok("pin: skipped case -> ERROR",
       levels({"test_files": 1, "cases": 2, "skips": 1}, clean_pin) == ["ERROR"])
    ok("pin: empty suite -> ERROR",
       levels({"test_files": 0, "cases": 0, "skips": 0}, {"test_files": 0, "cases": 0}) == ["ERROR"])
    ok("pin: non-object pin -> ERROR", levels(clean_measure, []) == ["ERROR"])
    ok("pin: unknown key -> ERROR",
       levels(clean_measure, {**clean_pin, "min_cases": 2}) == ["ERROR"])
    ok("pin: note key is allowed", check_unit_suite(clean_measure, {**clean_pin, "note": "x"}) == [])

    spec = "\n".join([
        "describe('X', () => {",
        "  it('a', () => {});",
        "  test('b', () => {});",
        "  it.each([[1], [2]])('c', () => {});",
        "});",
    ])
    ok("measure: counts it/test/it.each declarations",
       measure_unit_suite({"frontend/tests/unit/a.test.js": spec})["cases"] == 3)
    ok("measure: only *.test.js counts",
       measure_unit_suite({"frontend/tests/unit/a.test.js": "it('x', () => {});",
                           "frontend/tests/unit/helper.js": "it('y', () => {});"})["test_files"] == 1)
    ok("measure: skips counted",
       measure_unit_suite({"frontend/tests/unit/a.test.js": "it.skip('x', () => {});"})["skips"] == 1)
    ok("measure: describe.skip counted",
       measure_unit_suite({"frontend/tests/unit/a.test.js": "describe.skip('x', () => {});"})["skips"] == 1)
    ok("measure: it.todo counted",
       measure_unit_suite({"frontend/tests/unit/a.test.js": "it.todo('x');"})["skips"] == 1)
    ok("measure: prose mentioning it( does not count",
       measure_unit_suite({"frontend/tests/unit/a.test.js": "// call it( later)"})["cases"] == 0)
    return cases


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        cases = selftest_cases()
        failed = [name for name, passed in cases if not passed]
        for name, passed in cases:
            print(f"{'ok  ' if passed else 'FAIL'} {name}")
        print(f"selftest: {len(cases) - len(failed)}/{len(cases)} passed")
        return 1 if failed else 0
    issues = check_unit_pin()
    for issue in issues:
        print(f"[{issue['level']}] {issue['path']}: {issue['msg']}")
    errors = sum(1 for issue in issues if issue["level"] == "ERROR")
    print(f"unit_suite_pin: {errors} error(s), {len(issues) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
