#!/usr/bin/env python3
"""Test-registry reconciliation (P-008, audit check 4) - stdlib only.

Kept in its own module so ``audit_agent_ops.py`` stays inside the 500-line script
budget - the same reason ``frontend_coupling.py`` exists.

The gap this closes: a test can exist, pass and still be *dangling* - nobody registers
it and no CI list runs it. P-008 found four such files after the v1.8.2 split (they had
drifted with the implementation and were only found by accident on the cloud).

Check 5 (P-023, ``check_stub_scope``) covers a second, quieter gap: no test file may install
a stub into ``sys.modules`` at *module* level. pytest imports every test module at collection
time, so such a stub outlives the test that needs it and defeats a neighbour's
``pytest.importorskip("paddle")`` environment gate. Measured: a fake ``paddle`` made
``test_table_template_analyze.py`` stop skipping and die on the ``fastapi`` import that guard
was indirectly protecting (a wrong red, found only in CI); a gate that merely decides
*whether to run* would instead have lost coverage with no signal at all.

Fact sources:
  * ``backend/tests/test_registry.json`` - the single registration table. Kind enum:
    ``phase-a-ci`` (the Phase A CI list runs it) / ``live-gpu`` (needs a live server) /
    ``manual-script`` (REPL only) / ``full`` (local or cloud full run). There is no
    "retired" kind on purpose: deleting a test deletes its entry, so "a registered entry
    must have a file" stays contradiction-free and history lives in git.
  * the test files on disk under ``backend/tests/**``, enumerated **recursively** so the
    ``kie/`` sub-directory counts (a flat glob was part of the P-008 blind spot);
  * the Phase A pytest list in ``.github/workflows/kie-phase-a.yml``, parsed
    **read-only** - editing CI config is a red line, so this only reconciles it.

Findings: unregistered test file / registry entry with no file / CI list entry that is
unregistered or whose kind is not ``phase-a-ci`` -> ERROR; a ``phase-a-ci`` entry the CI
list no longer runs -> WARN (the ambiguous drift direction). A missing or unparsable
Phase A step is fail-closed: ERROR, never a silent pass.

Check 5 findings: a module-level ``sys.modules[...] =`` write in any test file -> ERROR
(scope 5 covers every ``backend/tests/**/test_*.py``, not only the CI list, because a
directory-wide local run is a shared session too). An unparsable test file is fail-closed:
ERROR, never a silent pass.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

TEST_REGISTRY_REL = "backend/tests/test_registry.json"
PHASE_A_WORKFLOW_REL = ".github/workflows/kie-phase-a.yml"
# The CI step whose pytest argument list is the authoritative "runs in Phase A" set.
PHASE_A_STEP = "Run Phase A pytest (Pro)"
TEST_KINDS = ("phase-a-ci", "live-gpu", "manual-script", "full")
TESTS_PREFIX = "backend/tests/"
# Non-test subtrees: helper scripts, baseline snapshots and binary fixtures.
TEST_SCAN_SKIP_DIRS = ("tools", "snapshots", "fixtures")
# ``tests/<name>.py`` tokens inside the Phase A run block (paths are backend-relative).
PHASE_A_TEST_RE = re.compile(r"tests/([A-Za-z0-9_./\-]+\.py)")


def test_files() -> set[str]:
    """Registry keys: every ``backend/tests/**/test_*.py``, as tests/-relative paths."""
    base = REPO_ROOT / TESTS_PREFIX
    found: set[str] = set()
    for path in base.rglob("test_*.py"):
        rel = path.relative_to(base)
        if not any(part in TEST_SCAN_SKIP_DIRS for part in rel.parts[:-1]):
            found.add(rel.as_posix())
    return found


def phase_a_tests() -> set[str] | None:
    """Files the Phase A (Pro) CI step runs, as tests/-relative paths.

    ``None`` means fail-closed: a step or pytest list that cannot be located must not
    silently make the reconciliation pass.
    """
    workflow = REPO_ROOT / PHASE_A_WORKFLOW_REL
    if not workflow.is_file():
        return None
    lines = workflow.read_text(encoding="utf-8").splitlines()
    start = next((i for i, ln in enumerate(lines) if PHASE_A_STEP in ln), None)
    if start is None:
        return None
    names: set[str] = set()
    for line in lines[start + 1:]:
        if line.lstrip().startswith("- name:"):
            break
        names.update(PHASE_A_TEST_RE.findall(line))
    return names or None


def registry_issues(
    registry: dict, on_disk: set[str], phase_a: set[str] | None,
    workflow_rel: str = PHASE_A_WORKFLOW_REL,
) -> list[dict]:
    """Pure reconciliation (shared with ``--selftest``): registry <-> disk <-> CI list."""

    def issue(level: str, path: str, msg: str) -> dict:
        return {"check": "test-registry", "level": level, "path": path, "msg": msg}

    issues: list[dict] = []
    for rel, meta in sorted(registry.items()):
        if not isinstance(meta, dict) or meta.get("kind") not in TEST_KINDS:
            issues.append(issue("ERROR", TEST_REGISTRY_REL,
                                f"{rel}: kind must be one of {list(TEST_KINDS)}"))
        if rel not in on_disk:
            issues.append(issue("ERROR", TESTS_PREFIX + rel,
                                "registered in test_registry.json but no such test file"))
    for rel in sorted(on_disk - set(registry)):
        issues.append(issue("ERROR", TESTS_PREFIX + rel,
                            "test file is not registered in test_registry.json"))
    if phase_a is None:
        issues.append(issue("ERROR", workflow_rel,
                            f"Phase A step '{PHASE_A_STEP}' / its pytest list not found"))
        return issues
    for name in sorted(phase_a):
        meta = registry.get(name)
        if meta is None:
            issues.append(issue("ERROR", workflow_rel,
                                f"{name} runs in Phase A CI but is not registered "
                                "in test_registry.json"))
        elif not isinstance(meta, dict) or meta.get("kind") != "phase-a-ci":
            kind = meta.get("kind") if isinstance(meta, dict) else meta
            issues.append(issue("ERROR", workflow_rel,
                                f"{name} runs in Phase A CI but registry kind is {kind!r}"))
    for rel, meta in sorted(registry.items()):
        if isinstance(meta, dict) and meta.get("kind") == "phase-a-ci" and rel not in phase_a:
            issues.append(issue("WARN", TEST_REGISTRY_REL,
                                f"{rel} is registered phase-a-ci but Phase A CI does not "
                                "run it (possible workflow drift)"))
    return issues


def check_test_registry() -> list[dict]:
    """check 4: registry <-> test files on disk <-> Phase A CI list (P-008)."""
    try:
        registry = json.loads((REPO_ROOT / TEST_REGISTRY_REL).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [{"check": "test-registry", "level": "ERROR", "path": TEST_REGISTRY_REL,
                 "msg": f"cannot read test registry: {exc}"}]
    return registry_issues(registry, test_files(), phase_a_tests())


def _module_level_sys_modules_writes(tree: ast.Module) -> list[int]:
    """Line numbers of ``sys.modules[...] = ...`` that run at *import* time.

    Deliberately does not descend into function / class / lambda bodies: a write in there
    runs only when the test (or its fixture) asks for it, which is the scoped form wanted.
    A module-level ``for`` loop over the module names *is* traversed - that is exactly the
    leaking shape (P-023), and it runs at collection time like any other top-level code.
    """

    def is_sys_modules_sub(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "modules"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "sys"
        )

    def targets(node: ast.AST) -> list[ast.expr]:
        if isinstance(node, ast.Assign):
            return list(node.targets)
        if isinstance(node, ast.AugAssign):
            return [node.target]
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            return [node.target]
        return []

    hits: list[int] = []
    stack: list[ast.AST] = [tree]
    while stack:
        node = stack.pop()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            hits.extend(t.lineno for t in targets(child) if is_sys_modules_sub(t))
            stack.append(child)
    return sorted(hits)


def check_stub_scope() -> list[dict]:
    """check 5: every ``backend/tests/**/test_*.py`` keeps its stubs scoped (P-023).

    Scope is every test file on disk, not just the Phase A list: a directory-wide local run
    is a shared session too, so the same leak reddens it (measured 2026-09-25: the two
    ``kind: full`` files' module-level stubs already do).
    """
    base = REPO_ROOT / TESTS_PREFIX
    issues: list[dict] = []
    for rel in sorted(test_files()):
        try:
            tree = ast.parse((base / rel).read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as exc:
            issues.append({"check": "stub-scope", "level": "ERROR", "path": TESTS_PREFIX + rel,
                           "msg": f"cannot parse: {exc}"})
            continue
        for lineno in _module_level_sys_modules_writes(tree):
            issues.append({
                "check": "stub-scope", "level": "ERROR", "path": TESTS_PREFIX + rel,
                "msg": (f"line {lineno}: module-level sys.modules[...] write - it runs at collection "
                        "time, so the stub leaks to every other test file and can defeat their "
                        "pytest.importorskip(...) gates; scope it with monkeypatch.setitem (fixture) "
                        "or unittest.mock.patch.dict (module load) - P-023")})
    return issues


def selftest_cases() -> list[tuple[str, bool]]:
    """In-memory regressions for checks 4-5 (never reads repo facts, D11 convention)."""
    clean = {"test_a.py": {"kind": "full"}, "test_b.py": {"kind": "phase-a-ci"}}
    ghost = registry_issues({"test_gone.py": {"kind": "full"}}, {"test_a.py"}, set())
    bad_kind = registry_issues({"test_a.py": {"kind": "retired"}}, {"test_a.py"}, set())
    ci = registry_issues({"test_a.py": {"kind": "full"}}, {"test_a.py"}, {"test_a.py"})
    drift = registry_issues({"test_a.py": {"kind": "phase-a-ci"}}, {"test_a.py"}, set())
    nolist = registry_issues({}, set(), None)
    stub_scope = [
        ("case15-stub-scope-module-level",
         "import sys, types\nsys.modules['paddle'] = types.ModuleType('paddle')\n", 1),
        ("case16-stub-scope-for-loop",
         "import sys, types\nfor m in ('paddle', 'cv2'):\n    sys.modules[m] = types.ModuleType(m)\n", 1),
        ("case17-stub-scope-in-fixture-ok",
         "import sys\n\ndef test_a(monkeypatch):\n    monkeypatch.setitem(sys.modules, 'paddle', object())\n", 0),
        ("case18-stub-scope-read-only-ok",
         "import sys\n\nif 'paddle' not in sys.modules:\n    raise SystemExit\n", 0),
        ("case19-stub-scope-patch-dict-ok",
         "import sys, types, unittest.mock\n\n_S = {'paddle': types.ModuleType('paddle')}\n"
         "with unittest.mock.patch.dict(sys.modules, _S):\n    pass\n", 0),
    ]
    return [
        ("case9-registry-clean",
         registry_issues(clean, {"test_a.py", "test_b.py"}, {"test_b.py"}) == []),
        ("case10-registry-ghost-and-unregistered",
         len(ghost) == 2 and all(i["level"] == "ERROR" for i in ghost)),
        ("case11-registry-kind-enum",
         len(bad_kind) == 1 and "kind must be one of" in bad_kind[0]["msg"]),
        ("case12-registry-ci-unregistered-kind",
         len(ci) == 1 and "registry kind" in ci[0]["msg"]),
        ("case13-registry-ci-drift-warn", len(drift) == 1 and drift[0]["level"] == "WARN"),
        ("case14-registry-phase-a-unparsable",
         len(nolist) == 1 and nolist[0]["level"] == "ERROR"),
    ] + [
        (name, len(_module_level_sys_modules_writes(ast.parse(src))) == expected)
        for name, src, expected in stub_scope
    ]
