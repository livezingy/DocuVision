# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **P-008 — docs-and-tests governance gates** (2026-09-17, governance batch):
  - `scripts/lint_frontend.py`: new **F7** orphan-reachability rule — every
    `frontend/modules/**` file must be imported by `app.js`, `index.html` or another script;
    an acknowledged orphan is *registered* in `scripts/frontend_domain_map.json`
    (`known_orphans`, with date + evidence) — registration is data, not a permission. The first
    full scan found exactly one orphan (`floating-progress.js`, D11), matching P-008.
    Also fixed `_iter_imports` to scan the whole file: a line-wise scan silently missed every
    multi-line `import { ... } from "..."` (measured: it reported 11 of 33 wired modules as
    orphans, and F3/F5 were blind to those same lines).
  - `scripts/test_registry_audit.py` (**audit check 4**) + `backend/tests/test_registry.json`:
    three-way reconciliation between the registration table, the `test_*.py` files on disk
    (recursive, so `tests/kie/` counts) and the Phase A list in `.github/workflows/kie-phase-a.yml`
    (parsed **read-only** — editing CI config is a red line). Unregistered test file / ghost entry /
    a CI test that is unregistered or whose kind is not `phase-a-ci` = ERROR; a `phase-a-ci` entry
    CI no longer runs = WARN. Six `--selftest` regressions added (9 → 15).
  - `backend/pytest.ini`: `addopts = --continue-on-collection-errors` — P-008 measured that one
    collection error left 430 tests unrun; errors are still reported and the exit code stays non-zero.
  - `frontend/eslint.config.mjs` + `"lint": "eslint ."` (**P-010 stage 1**, CI not wired): flat
    config with only `no-unused-vars` (`args:"none"`) + `no-undef`, scoped to `app.js` +
    `modules/**` + `shared/**`   (`tests/**` is the second batch). First pass: 76 findings.
  - **P-010 stage 3 — ESLint is a CI gate** (2026-09-17, authorized): `.github/workflows/lint.yml` gained
    `actions/setup-node` (Node 22; eslint 10.10.0 needs `^20.19.0 || ^22.13.0 || >=24`), `npm ci`
    (`working-directory: frontend`, lockfile already tracked) and `npm run lint`, placed **after** the four
    stdlib gates so a stdlib failure never pays for `npm ci`. `frontend/**` was already in the workflow's
    `paths`, so the trigger filter is untouched. ESLint is the only gate that can see dead code / unused
    bindings — F1-F7 and C1-C8 are structural. Scope is still batch 1 (`frontend/tests/**` pending).
  - **P-008 gap 1 closed (option B) — injected-dependency fidelity as C9**: `frontend_coupling.py`
    `check_injection_keys()`, run by `check_frontend_baseline.py`, asserts that the key set `app.js` passes to
    each `initXxx` **equals** the set of `deps.*` keys that module's body reads. F6 only checks that an init is
    *called*: a missing key leaves the module's stub standing silently (`no-undef` cannot see it — the
    identifier is declared; that is the v1.8.3 B5a failure mode), and a surplus key is a dead injection
    (`no-unused-vars` cannot see an object property passed as an argument). An init whose parameter is neither
    empty nor `deps` fails closed. Two landing choices, both toward "CI-enforceable": it went into the C-series
    instead of a vitest test because vitest/e2e do **not** run in CI (a local-only test would not close the
    gap), and the contract is derived from the module source rather than recorded in
    `frontend_domain_map.json`, because a hand-kept copy goes stale exactly when a module grows a dependency —
    the case it is meant to catch. Evidence: 25 init exports / 24 compared (one is injected rather than called)
    plus five negative probes — missing key, surplus key, injection into a no-deps init, non-`deps` parameter,
    and a clean baseline — all fired as designed. The intermediate scope-analysis answer (JSDoc +
    `tsc --allowJs --checkJs --noEmit`) is recorded for the v1.9 frontend batch.
  - **P-015 closed — big-binary policy**: LFS migration is declined (an environment without `git-lfs` yields
    pointer files that e2e/C1-C8 would silently consume — a worse failure than a larger repository — and it
    adds a toolchain prerequisite this repo deliberately avoids). Instead kernel `constraints.md` now requires
    a new >5 MB binary to be justified in the PR description ("reason + is it a test fixture"), derived into
    both rule copies by `sync_agent_rules.py`.
  - **P-011 (the part that was authorized) — `backend/tests/**` added to the audit workflow's
    `pull_request.paths`**: check 4's truth sources are the registry and the test files themselves, so a PR
    that adds / renames / deletes a test must re-run the audit. Measured before changing it: `backend/tests/`
    holds no untracked files at all (only ignored `__pycache__/*.pyc`), and a `paths` filter only ever sees
    committed diffs — so the extra trigger costs nothing (the `push` trigger has no filter and always ran).
    `docs/agent-ops/operations.md` mirrors the list.
  - **P-008 gap 2, the half that can be machine-checked — audit A6 orphan staleness**:
    `frontend_coupling.py` `check_orphan_staleness()` requires every `known_orphans` entry to carry an ISO
    `added` date (missing or malformed = ERROR, fail closed) and WARNs once an entry is older than
    `ORPHAN_STALE_DAYS = 90`, turning "remember to re-read the registry" into a line of audit output instead
    of a human habit. Registered as A6 in module-map §6; `--selftest` case16 covers stale / missing-date /
    fresh. The runtime-coverage report (option B proper) stays open.
  - **P-013 closed (option C) — service-layer ownership split into two buckets**: a double scan (module
    filename *and* derived class name) of the living doc set shows 2 of the 25 modules have a carrier
    (`batch_service.py` / `hitl_queue.py` -> `v1.5-roadmap.md`, now rows of the owning table) and 23 have no
    standing living contract — listed explicitly in footnote 2, so the empty cell becomes a stated conclusion
    instead of a question. The judge rule ("a carrier describes this module's own contract; a passing mention
    does not count") and the five near-miss mentions are recorded for the next reviewer.
- **P-004 — current-state module map + fail-closed recon** (PR #21, merge `a88fdb4`):
  - `docs/architecture/module-map.md`: backend `routers/` 13 domains × frontend
    `modules/` 15 domains, dependency laws L1-L5, the cross-end consumer table, the
    invariant gate table (R1-R3 / INV-1 / INV-2 / S-a/b/c / F1-F6 / C1-C8, incl. the
    retired rows) and its own recon protocol A0-A5. Registered in `docs/README.md`;
    owning rows added to `docs/agent-ops/core/doc-sync.md`.
  - `scripts/audit_agent_ops.py` **check 3 (module-map recon)**, fail-closed:
    ERROR on a missing/duplicated anchor, an empty or column-broken anchored table,
    referenced-path drift, router-count / endpoint-count drift, frontend domain-set or
    infra-count drift, gate-symbol drift and missing registration; WARN on 最近对照
    freshness vs CHANGELOG. New `--selftest` (9 in-memory parser regressions).
  - `docs/architecture/shared-ui-shell.md`: two stale references to files removed in
    v1.8.3 B0b/B1 fixed — the last standing living-doc drift WARN; the audit is now
    0 error / 0 warning.
- **P-004 PR-B — frontend rules promoted into the kernel** (PR #23, merge `1853610`):
  - `docs/agent-ops/core/frontend.md` (new, kernel file 7): frontend hard rules F1-F6,
    dependency laws L1-L5, the mandatory actions for new or modified frontend code
    (landing point / fact sources to sync / whitelist registration / ratchet), the local
    lint commands and the known gaps (F6 is a name-level weak assertion; the orphan
    module has no reachability check).
  - `docs/agent-ops/core/constraints.md`: three self-protection red lines — raising a
    ratchet cap (`*_size_allowlist.json` counts only decrease), widening the frontend
    whitelist (`module_import_whitelist` / `leaf_services` / `shared_state_modules`) and
    changing the `frontend/index.html` entry script or load order.
  - `scripts/sync_agent_rules.py` maps `frontend.md` to `.cursor/rules/011-frontend.mdc`
    and `.codebuddy/rules/011-frontend.md` (kernel and copies in one commit);
    `AGENTS.md`'s frontend task-routing row now points at `frontend.md` +
    `python scripts/lint_frontend.py` (previously `node --check` only).

### Changed
- **P-008/P-010 governance batch** (2026-09-17):
  - Repo governance: the 6 committed `test_data/testfiles/GeneralFiles_staging/` files are untracked
    (`git rm --cached`, worktree kept) and the directory is re-ignored **after** the
    `!test_data/testfiles/**` negations — the earlier ignore line alone did not hold, because those
    negations re-include every PDF (verified with `git check-ignore`).
  - `docs/architecture/v1.8-cloud-validation.md` → `docs/release/v1.8-cloud-validation.md`
    (v1.8 pre-release validation manual; v1.8.0–v1.8.3 all shipped), internal link fixed and indexed
    in `docs/release/README.md`. It had **no inbound references**: both `README.md` and
    `docs/README.md` point at `docs/architecture/CLOUD_VALIDATION.md`, a different, still-living file.
  - Kernel: `doc-sync.md` mechanism 2 ownership table extracted to the new appendix
    `docs/agent-ops/doc-sync-ownership.md` (so the table can grow without pushing the kernel past its
    ~60-line soft limit; 78 → 56 lines) and mechanism 1 now names the footer check as a PR-review gate;
    `testing.md` gained the test-registration rule; `frontend.md` gained F7 and the "orphan module has
    no reachability check" gap is closed. Copies re-derived with `scripts/sync_agent_rules.py`
    (kernel + copies in one commit).
  - `scripts/frontend_domain_map.json`: `known_orphans` added (2 entries); two write-only state entries
    removed (`lastStatusUpdateTime`, `forcePureLayoutBboxOverlay`) with the status-bar leaf-service
    evidence updated to match.
  - ESLint cleanup (delete-only, no behaviour change): 49 dead imports in `frontend/app.js`
    (211 → 173 lines; ratchet lowered with `--update`), 24 unused variables / catch bindings across 11
    modules, `catch (e)` → `catch` where the binding was unused. `modules/utils/geometry.js` became a
    registered orphan as a direct result — its only production importer was one of those dead imports
    (its 5 functions are now covered only by `tests/unit/geometry.test.js`).
  - 3 unit tests re-pointed: their assertion was "app.js imports X", i.e. it pinned exactly the dead
    imports; it is now "X is imported by a consumer" (shared helper `frontend/tests/unit/_sources.js`),
    which also mirrors F7's `known_orphans` exemption.
  - `docs/architecture/module-map.md`: F7 and T1 (test registry) rows added to §5, D11 row updated,
    §6 A4 widened to the owning-table appendix + new A6 row; `docs/agent-ops/operations.md` inspection
    routine and `DEVELOPMENT.md` / `frontend/README_FRONTEND.md` updated for F1-F7 and `npm run lint`.
  - `docs/R&D/PENDING.md`: P-008/P-010/P-011 status written back, P-012 recorded as
    "registered, awaiting cloud verification" (**not** marked done), new P-013 (service-layer owning
    docs unverified — TODO instead of guesswork), P-014 (`shell/tools.js` `startProcessing` unbound)
    and P-015 (Git LFS assessment: 4 tracked files > 5MB, measured and listed; migration not done).
  - **P-014 resolved in its own follow-up commit** (user decision: retire outright, option 2-prime):
    `npm run lint` now reports **0 errors**. The dead `initAnalysisView` boot step was removed end to
    end — its only body wired a `#startProcessBtn` listener for an id that does not exist in
    `index.html`, and `startProcessing` was never bound in `modules/shell/tools.js` (the D4 sibling
    `shell/ui.js` receives it via `initShellUi`, and Run Analysis is wired there). `boot_sequence` and
    `domains["D4 shell-init"]` went 17 -> 16 **in the same commit as the code** (C3 fails closed
    otherwise), together with module-map section 3, the `README_FRONTEND.md` boot snippet, the ratchet
    (173 -> 172) and two stale `options-dialog.js` comments that attributed the D6 hook to
    `initAnalysisView` instead of `shell/ui.js::initResultTabs`. Evidence: F6 26 -> 25 init exports all
    wired, C3 "16 steps, all defined", vitest 80/80, e2e 14/14.
  - ESLint resolved to **10.10.0** (the plan said 9; flat config and both rules behave identically).
  - Gate evidence: `lint_file_size` / `lint_routes` / `lint_frontend` (F1-F7) /
    `check_frontend_baseline` (C1-C8) / `audit_agent_ops` (+`--selftest`, 15 cases) all green;
    vitest **80/80**; Playwright **14/14**.
- `.github/workflows/agent-ops-audit.yml`: also runs on push to `main` and when
  `backend/app/routers/**`, `frontend/modules/**`, `scripts/frontend_domain_map.json`,
  `docs/architecture/**` or `docs/README.md` change; new `--selftest` step.
- `docs/agent-ops/operations.md` / `docs/agent-ops/review.md` / `docs/README.md`:
  module-map recon and `--selftest` added to the inspection routine, the review
  checklist and the kernel index.
- `docs/architecture/module-map.md`: 最近对照 refreshed to `v1.8.3.0 / commit 1853610`
  (doc-sync mechanism 4 — refresh when merging to `main`).
- `docs/release/**` cleanup batch: the release index is now explicitly **historical**
  (v1.6 and earlier), release notes are documented as living in this file **from v1.7
  on** (no new `RELEASE_*_NOTES.md`), the known-limitations scope is bumped to v1.8.3,
  and the `MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md` orphan link is restored.
- `CHANGELOG.md`: the v1.7.0 release notes were moved out of a stale
  `## [Unreleased] — v1.7.0 train (tag pending)` heading into a proper
  `## [1.7.0] — 2026-09-07` section, and five places claiming "tag pending" /
  "tag not cut" were corrected (`tag v1.7.0` was cut 2026-09-07, commit `a72ec1d`).

### Fixed
- **`TASK-PERSIST-001` verified on cloud — `v1.7-roadmap.md` no longer says `pending`** (2026-09-17):
  a completed Pro analyze task survives an `:8000` restart. Run on `main` `a73468b`
  (`git describe` = `v1.8.3.0-23-ga73468b`), Tencent Cloud Studio A10, `backend/install_pro_gpu.sh`;
  `task_id = 0691cc4a-5366-4259-9a83-c5d2842bfc07`, `/health` `api_version = 1.8.3` (operator-confirmed, matched
  expectation), document `test_data/testfiles/PDF_Parsing/03_page11.pdf` (1 page / 408,464 B; uploaded to the
  cloud instance manually for the run, then **committed in the same batch** so a clone reproduces with the same
  fixture).
  Pre- and post-restart both 4/4: task **200 `completed`**; result **200** (`tables=1`,
  `figures.figure_count=2`); ZIP **200** with magic `PK`, `manifest.json`, `tables/`x3, `figures/`x3;
  figure `p1_e3` **200** with `\x89PNG` header. Evidence table lives in the roadmap's Acceptance section.
  **Baseline caveat (recorded on purpose)**: this ran on `main`, not on the `v1.7.0` tag —
  `backend/app/services/persistence/**` is unchanged since the tag (zero diff), but the route and
  orchestration layers were refactored by v1.8.2 SPLIT-U (`routers/tasks.py` +219,
  `routers/tasks_content.py` +425, `document_pipeline_orchestrator.py` +47, `core/config.py` 11 lines;
  106 commits since the tag). The conclusion is "persistence works across restart on the main
  baseline", **not** a byte-for-byte replay of the tag-time gate. Not collected: `SQLITE_DB_PATH` / `OUTPUT_DIR`
  resolved values (not gate criteria).
- `docs/architecture/v1.7-roadmap.md`: Train identity row `Tag \`v1.7.0\` = not cut` corrected to
  `shipped (2026-09-07, commit a72ec1d)` — a sixth residual of the P-009 release-docs batch, which had
  fixed five other "tag pending" / "tag not cut" claims but missed this one, and it contradicted the
  same file's own header plus `git tag -l v1.7*`. The `APP_VERSION 1.7.0` line is now explicitly scoped
  to the train-open commit so it cannot be read as the current version (`main` reports `1.8.3`).
- `docs/R&D/PENDING.md`: **P-012 closed and removed** — its conclusion was promoted into
  `docs/architecture/v1.7-roadmap.md` per the file's own rule (pending: 10 -> 9 groups).
- `docs/release/MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md` (**moved** from `test_data/acceptance/`): the v1.7 merge-gate
  checklist is archived and frozen now that its gate is verified. Internal links were re-pointed for the new depth,
  the header no longer says the tag is pending, and an archive note warns that section 0 is stale (`feature/v1.7` no
  longer exists; the `docuvision-core[lite]` extra was dropped in v1.8). The three inbound references
  (`docs/architecture/v1.7-roadmap.md`, `docs/release/README.md`, `docs/release/KNOWN_LIMITATIONS.md`) were updated,
  and the release index now lists this file under the archived validation material.
- `03_page11.pdf` provenance is recorded instead of left open: it is page 11 extracted from
  `test_data/testfiles/PDF_Parsing/03_paper_arxiv-mamba_multicolumn_glyph-tables.pdf` (operator-confirmed). The roadmap
  also records why neither ① nor ② is filled in for the historical question — there is no in-repo evidence either way
  (`git grep TASK-PERSIST` hits documents only, the KIE run tracker has no v1.7 row, and the tag shares the feature
  commit's date) — so what gets written down is the absence of a record, not a guess.
- `docs/R&D/PENDING.md` P-011 wording corrected: the audit workflow's `paths` filter applies to `pull_request` only
  (`push` to main has no filter, so the audit always runs there). The gap is narrower but real: in a PR, editing
  `backend/tests/**`, `backend/pytest.ini`, `scripts/test_registry_audit.py` or the Phase A workflow does not trigger
  the audit, so a check-4 regression would only surface after merging.

## [1.8.3] — 2026-09-16

Tag: **v1.8.3.0**. Branch: `feature/v1.8.3`. Front-end split: `frontend/app.js`
5708 → **211 lines / 1 function** (assembly + mediator only), 33 modules under
`frontend/modules/**` (15 domains). Acceptance: local gates (lint F1-F6, C1-C8,
`--syntax` 34/34 incl. app.js, vitest 80/80, e2e 14/14) plus **FRONT-C1** on
Cloud Studio (38/38 assets 200 + JS MIME; walkthrough 9/9; cache revalidation
green on a plain F5 via the gateway's content-MD5 ETag; SPLIT-C1 re-check green;
SPLIT-U4 **430 passed / 0 failed**). See
[docs/architecture/CLOUD_VALIDATION.md](docs/architecture/CLOUD_VALIDATION.md)
§ 阶段 FRONT-C1.

### Added
- **v1.8.3 B0a — frontend governance & measurement baseline** (structure-only, no
  frontend behaviour change):
  - `scripts/lint_frontend.py`: four machine-checkable rules — F1 line budget
    (500 lines, `splitlines()` metric), F2 `frontend/app.js` top-level function
    ratchet, F3 import direction inside `frontend/modules/**` (no `../app.js`, no
    sibling-domain imports), F4 assembly shape (one `app.js` entry, no module file
    loaded directly by `index.html`, phase flags for the `type="module"` conversion
    and the `panel-resize.js` removal).
  - `scripts/check_frontend_baseline.py` + `scripts/frontend_coupling.py` +
    `scripts/frontend_domain_map.json`: the C0 calibration gate (measured vs design
    expectation, exits non-zero on drift), the cross-domain coupling scan
    (`--edges`), the C0 snapshot writer (`--report-out=PATH`) and a `--syntax`
    `node --check` pass over the module files. Replaces the original C0 snippet,
    which used `sed`/`wc` and could not run on win32 + PowerShell.
  - `scripts/frontend_size_allowlist.json`: frontend-only ratchet record
    (`frontend/app.js` 5708 lines, `app_js_functions` 145; both only decrease).
- CI: `lint.yml` gains a third step (`python scripts/lint_frontend.py`) and watches
  `frontend/**`; `kie-phase-a.yml` now also runs
  `tests/test_route_contract_freeze.py` and `tests/test_route_inventory.py`, so
  route-contract drift fails at PR time instead of only locally (PENDING P-003).

### Changed
- **v1.8.3 B5b — docs and version close-out**: `DEVELOPMENT.md` grows from "three hard
  rules" to **six** - the three front-end invariants the gates already enforce (module
  ≤500 lines + import only downward; `app.js` assembly-only with ratchets; every
  `initXxx` must be wired and cross-domain deps injected, no `window.*` bridges) are now
  stated where contributors will look for them. `frontend/README_FRONTEND.md` gets its
  **file structure / initialisation / main modules** sections rewritten against the
  split reality (33 modules, the three-stage boot, the injection assembly, the 17-step
  boot sequence) - the stale v1.1.0 section is gone, remaining sections are labelled
  functional-only. `APP_VERSION` **1.8.2 → 1.8.3** (`backend/app/core/config.py`;
  `info.version` is excluded from the OpenAPI baseline, so the route-contract snapshot is
  unaffected). Entry cache-bust token **`?v=20260915-b0b` → `?v=20260915-v183`** (D9:
  the token tracks assembly/dependency-structure changes - this is the terminal one).
- **v1.8.3 B5a — shell extracted, entry at terminal state**: `frontend/modules/shell/`
  (`ui.js` + `tools.js`, D4's 12 functions plus the `globalTooltip` state; no cross-half
  calls, so no extra injection). The shell's cross-domain calls are **injected - 10
  deps / 15 call points**, five times the design's estimate of 2, because D6-D10 are all
  extracted by now and F3 forbids importing sibling domain modules (the design assumed
  the callees would still live in app.js): D8 `startProcessing` ×2, D6
  `openAnalysisOptionsDialog` + `setSyncProcessingModeUI`, D7 ×4, D9
  `updateEnhancementTabs` ×4, D15 `refreshHitlReviews`, D1 `refreshActiveEngineFooterLine`,
  D10 `highlightResultItem`. The `:744` `window.DocuVisionPreview` bridge (R1's last
  standing window bridge) is **removed** - verified it had no consumer besides
  `previewHelpers`, which now imports `shared/queue_preview.js` directly (whitelisted
  `shared/*`). The window-resize listener left behind by B4 moved into
  `preview-paging/core.js`. `app.js` is at its **terminal state: 211 lines / 1 function**
  (the `updateResultsDisplay` mediator) - imports, dependency wiring, boot sequence,
  mediator; **5708 → 211 lines (-96%)**, far inside the ≤600 acceptance.
  New gate **F6 assembly completeness**: every `export function initXxx` must be called
  from app.js. Its first run caught 3 over-exported inits (module-private now); a known
  gap is recorded - F6's name-based weak assertion cannot catch "referenced but not
  imported" (that bit us once this batch; e2e + a pageerror probe caught it).
  Gate evidence: lint F1-F6, C1-C8, `--syntax` 34/34 (incl. app.js), vitest 80/80,
  e2e 14/14.
- **v1.8.3 B-decision — same-domain splits switch from injection to sibling imports**:
  `preview-nav.js` / `preview-render.js` move into `frontend/modules/preview-paging/`
  (`core.js` + `nav.js` + `render.js`) and `pipeline-run.js` / `pipeline-result.js`
  into `frontend/modules/pipeline/` (`run.js` + `result.js`). F3 gains one allowed
  target - a same-directory sibling inside a domain sub-directory (the `modules/` root
  is excluded, so true cross-domain pairs stay red; leaf-service L1 is unaffected
  because F5 validates registered modules independently of F3) - and the 8
  same-domain injection points from B4 are retired: D5's hub functions
  (`previewHelpers` / `resolveResultPageCount` / `syncPreviewPaginationControls` /
  `revokeCurrentPageImageUrl` / `getPdfPageImage` / `adjustDocumentSize`) moved to
  `preview-paging/core.js`, which turns the split into a one-way DAG
  (`nav -> render -> core`) with **no circular import and no ESM TDZ hazard**
  (D8's run -> result was already one-way). The 36 cross-domain injections, the
  domain-to-function map and the edge table are unchanged; every function body stays
  byte-identical. `app.js` 806 → 805 lines (13 functions, ratchet lowered).
  Gate evidence: lint F1-F5, C1-C8, `--syntax` 32/32 (now including `app.js`),
  vitest 80/80, e2e 14/14.
- **v1.8.3 B4 — orchestration chain extracted (D3 upload-queue + D5 preview-paging + D8
  pipeline)**: new `frontend/modules/preview-nav.js` + `preview-render.js` (D5, 14
  functions split by the design's line cut), `pipeline-run.js` + `pipeline-result.js` (D8,
  6 functions - `updateResultsDisplay` stays in app.js as the result mediator), and
  `upload-queue.js` (D3, 10 functions). `app.js` **2320 → 806 lines**, **43 → 13**
  top-level functions (the entry is now imports + dependency wiring + the mediator +
  the boot sequence).
  The D3 ↔ D5 ↔ D8 cycles are closed by injection: 36 cross-domain call points (D1
  api-base, D3, D5, D6, D7) plus 8 same-domain-split points. The split of D5 and D8
  **exposed a new problem** the design's line cuts had not accounted for - the two halves
  of each domain call each other (D5 nav ↔ render 6 points; D8 run → result 2 points) -
  and those same-domain calls are injected from app.js as well, so F3's "no
  module-to-module imports" rule is kept unchanged (no new exemption, no path change).
  The B3 leftovers are re-pointed: `initOverlayRender`'s 7 D5/D8 deps now pass the
  preview-nav.js / preview-render.js / pipeline-result.js exports, and
  `initResultPanelsFigures` passes preview-render's `fetchAuthedImage` (call sites
  untouched). `known_edge_pairs` drops D5 → D8 / D5 → D7 / D5 → D10 (all resolved by
  injection). Gate evidence: lint F1-F5, C1-C8, `--syntax` 30/30, app.js `node --check`,
  vitest 80/80, e2e 14/14.
- **v1.8.3 B3 — result-panels + overlay extracted**: `frontend/modules/result-panels/`
  (D9 as seven sub-modules per design §3.1 - quality / demo-transaction / tables / text /
  figures / enhance / json; 16 functions, plus `TABLE_TEMPLATE_COLUMNS` and the 46-line
  top-level style block now owned by figures.js) and `frontend/modules/overlay-render.js`
  (D10 rendering half, 9 functions + its 3 overlay state values; the geometry half has
  been in utils/geometry.js since B0b). `app.js` **3798 → 2320 lines**, **68 → 43**
  top-level functions.
  Injections (11 deps / 12 call sites, all via the same-name module-scope binding trick
  so every call site stays byte-identical): `overlay-render.js` 9 (D5 previewHelpers /
  resolveResultPageCount / syncPreviewPaginationControls / revokeCurrentPageImageUrl /
  getPdfPageImage / adjustDocumentSize, D8 fetchTaskBlocks, D9 updateContentText, D4
  initAnnotationInteractions), `result-panels/tables.js` 1 (D12 bindTableCardCsvExport),
  `result-panels/figures.js` 1 (D5 fetchAuthedImage). The D5/D8 wirings are re-pointed
  to the module exports in B4 (call sites untouched).
  The seven sub-modules import nothing from each other (verified: every D9 internal call
  lands in the same sub-module). `known_edge_pairs` drops D10 → D4 and D10 → D9 (both
  resolved by injection). `envelope_display.test.js` is re-pointed to the real modules -
  the inline copies of updateEnhancementTabs / updateContentFormulas /
  updateContentSeals / escapeHtml are deleted, so production drift can no longer hide
  there (R9). Gate evidence: lint F1-F5, C1-C8, `--syntax` 25/25, vitest 80/80, e2e 14/14.
- **v1.8.3 B2 — options-dialog + kie-mapping extracted**: `frontend/modules/options-dialog.js`
  (D6: the analysis-options dialog - 6 functions plus the `syncProcessingModeUI` hook, now
  assigned through `setSyncProcessingModeUI`) and `frontend/modules/kie-mapping.js` (D7: 12
  functions - table-mapping eligibility, document-profile pre-scan, KIE field payload and
  Fields rendering). `app.js` **4318 → 3798 lines**, **86 → 68** top-level functions.
  The D6 ↔ D7 cycle is broken by app.js assembly injection (D6 needs D7's
  `clearTableMappingEligibility` / `updateKieQueryFieldsAvailability` /
  `buildKieQueryFieldsPayload`; D7 needs D6's `getSelectedProcessingMode`), and D6 → D9
  `updateEnhancementTabs` (result-panels, not yet extracted) is injected from app.js too -
  the same-name module-scope binding trick keeps every call site byte-identical. The
  `syncProcessingModeUI` hook moved with D6; D4's `initAnalysisView` now assigns it through
  `setSyncProcessingModeUI`. `known_edge_pairs` drops D7 → D6 (the cycle is no longer a
  static edge). Gate evidence: lint F1-F5, C1-C8, `--syntax` 17/17, vitest 80/80, e2e 14/14.
- **v1.8.3 B1b (part 3) — batch / hitl-review + the single injection (B1b complete)**:
  `frontend/modules/batch.js` (11 functions; `getProcessingOptions` is injected into
  `initBatchProcessing` through a module-scope binding so `createBatch`'s call site stays
  byte-identical) and `frontend/modules/hitl-review.js` (7 functions + its selection state).
  `app.js` **4816 → 4318 lines**, **104 → 86** functions. `getBatchResults` moves as
  exported-but-unused (no call site; flagged for v1.9).
  B1b is now complete: **9 module files**, `app.js` **5708 → 4318 lines**, **145 → 86**
  top-level functions.
- **v1.8.3 B1b (part 2) — api-base / floating-progress / export-csv**:
  `frontend/modules/api-base.js` (5 functions; a normal domain module — it calls status-bar
  and owns a refresh timer, so it is not a leaf service), `frontend/modules/floating-progress.js`
  (3 functions) and `frontend/modules/export-csv.js` (4 functions). `app.js` **5136 → 4816
  lines**, **116 → 104** functions.
  Dead-code note (no cleanup performed, per the structure-only rule): `showFloatingProgressCard`
  / `updateFloatingProgress` and the app.js `exportResults` have no call sites — the
  processing flow uses the status bar and the export UI uses `shared/export-ui.js` — so they
  move as exported-but-unused and are flagged for v1.9 review.
- **v1.8.3 B1b (part 1) — base services + notifications fold-in**:
  - new `frontend/modules/status-bar.js` (5 functions + its presentation-only throttle
    state; a leaf service with no imports), `frontend/modules/api-state.js`
    (`lastHealthPayload` + setter — the shared-state module from design §4.1, needed because
    the value is re-written after boot so a "pass it once" injection would go stale), and
    `frontend/modules/notifications.js` (fold-in of `frontend/shared/notifications.js` plus
    the app.js facade).
  - `frontend/shared/notifications.js` (classic IIFE `window.DocuVisionNotify`) and
    `frontend/shared/panel-resize.js` (Lite dead code) are removed, and `index.html` no
    longer loads the notifications script. The two `notify: (m, t) => DocuVisionNotify.show(m, t)`
    sites in app.js now use the imported `showNotification`.
  - The boot-sequence gate (C3) and the bootstrap test now accept *imported* functions too,
    not just declared ones, since `updateStatusBar` (boot step 2) is now imported.
  - `frontend/app.js` **5357 → 5136 lines**, **124 → 116** top-level functions.
- **v1.8.3 B2 prep — `modules/kie-config.js`**: the five KIE / table-mapping constants
  (`KIE_DOC_TYPES`, `KIE_FIELD_NAME_RE`, `TABLE_MAPPING_MODE`, `TABLE_MAPPING_ELIGIBLE`,
  `TABLE_MAPPING_IMAGE_EXTENSIONS`; `const` in app.js `:1462-1466`, never reassigned)
  moved verbatim into a read-only leaf service that imports nothing, so no setter channel is
  needed. Required before B2 because the options dialog (D6) and kie-mapping (D7) both read
  them and F3 forbids domain-to-domain imports — without it, moving the options dialog would
  hit an unavoidable D6 → D7 import. The dependency only became visible once the state-read
  scan stopped skipping declaration lines (previous commit). `frontend/app.js` 5358 → 5357
  lines; the export surface is pinned in `tests/unit/kie-config.test.js`.
- **v1.8.3 B1a follow-up — `lastFetchedBlocks` shared, state-read scan blind spot fixed**:
  `frontend/modules/preview-state.js` now also owns `lastFetchedBlocks` (pipeline state
  read by `updateContentText` in the result panels), so all four of its write sites are
  behind a setter and `app.js` keeps only reads — without this, the batch that moves the
  result panels could not compile. It was found by fixing `scripts/frontend_coupling.py`:
  `state_read_rows` skipped *every* `const`/`let`/`var` line (the intent was to skip the
  state's own declaration), so reads on declaration lines such as
  `const blocksData = lastFetchedBlocks;` were invisible. Now only lines that declare a
  tracked state are skipped, whereupon the cross-domain state-read count went **29 → 61**,
  also exposing `TABLE_MAPPING_MODE` (read by the options dialog — the next batch) and
  `lastHealthPayload` (read by the pipeline, B4) as real dependencies.
  `frontend/app.js` **5368 → 5358 lines**; 23 assignments became 21 setter call sites.
- **v1.8.3 B1a — shared base extracted**: `frontend/modules/preview-state.js`
  (7 live-binding states: the 6 preview slots plus `lastRenderedAnalysisResult`, which
  the overlay domain reads at `:2936-2937`; 8 setters/reset) and
  `frontend/modules/api-config.js` (the four immutable `API_BASE_URL` / `API_ROOT_URL` /
  `HEALTH_URL` / `ENGINES_URL` constants plus the two URL helpers that build them).
  `app.js` **5386 → 5368 lines**, top-level functions **126 → 124**: 19 assignment sites
  became setter calls, every read expression stayed byte-identical, and all three
  `URL.revokeObjectURL` call sites stayed exactly where they were (absorbing the revoke
  into the setters is not byte-equivalent: it would evaluate `createObjectURL` before the
  revoke, and would move the page-image revoke across an `await`).
  The URL helpers deliberately did **not** go to `frontend/modules/utils/`: the C6 gate
  asserts zero `document`/`window.` references there and `resolveApiBaseUrl` has 7, so
  they live inside `api-config.js`, which now imports nothing at all.
  New: `frontend/tests/unit/preview-state.test.js` (export surface pinned by the domain
  map, setter/live-binding and reset semantics).
- **v1.8.3 B0a follow-up — leaf-service whitelist + lint rule F5**: `notifications`
  (65 call sites / 8 domains) and `status-bar` (12 / 3) are now whitelisted import
  targets for `frontend/modules/**`, each registered in
  `scripts/frontend_domain_map.json` with its qualification evidence (L1 no
  reverse dependency / L2 no domain semantics / L3 no domain-owned state).
  `api-base` is deliberately not registered yet (it calls `status-bar`, which
  conflicts with L1) - B4 decides the trade-off. New rule **F5** keeps this
  mechanical: a whitelisted file must be registered, a registered leaf service may
  reach `utils/` and `shared/` only (so it can never become a hub or close a
  cycle), and every registration needs a date plus evidence - the whitelist cannot
  grow silently.
- **v1.8.3 B0b — frontend entry converted to native ESM + pure helpers extracted**
  (structure-only, no behaviour change):
  - `frontend/index.html`: the app entry is now
    `<script type="module" src="app.js?v=20260915-b0b">` (module scripts are deferred
    by default, so load order is unchanged; the classic shared scripts and the inline
    `queue_preview` bridge stay as-is until B1/B5a).
  - `frontend/app.js` **5708 → 5386 lines**, top-level functions **145 → 126**.
  - new `frontend/modules/utils/`: `geometry.js` (5 functions, bbox / coordinate-space
    math), `csv.js` (8, CSV & Markdown formatting), `text.js` (5, text / role-label
    normalisation), `dom.js` (1, `escapeHtml`). All 19 bodies were moved verbatim
    (only the declaration line gained `export `); `app.js` keeps calling them through
    an explicit import block.
  - new unit tests: `tests/unit/geometry.test.js` (17 cases incl. the v1.8
    coordinate-space regression), `tests/unit/csv.test.js` (14 cases),
    `tests/unit/bootstrap.test.js` (7 static boot-order + extraction guards).
  - frontend ratchets lowered to the measured values (`frontend/app.js` 5386,
    `app_js_functions` 126); `app_js_module` phase flag flipped to `true`.

### Fixed
- **UI e2e determinism (FRONT-U1)** — two test-infrastructure fixes, no application code
  touched:
  1. new `scripts/e2e_static_server.py` (stdlib `ThreadingHTTPServer`, 256-deep accept
     backlog) replaces `python -m http.server` as the Playwright `webServer`. The stdlib
     default backlog is **5**, Playwright defaults to cores/2 workers (10 on this host) and
     each page loads ~12 files, so connections were refused and `app.js` *itself* failed to
     load in some pages — `#documentPage` still held the raw index.html placeholder, i.e.
     the app had never booted, which is why affected tests looked like "the click did
     nothing". Serial runs were always 14/14 while parallel runs failed 2-6 of 14 with a
     different set each time (the B0b baseline failed too, so this was pre-existing).
  2. new `frontend/tests/e2e/helpers/app-boot.js` (`gotoApp` / `waitForAppBoot`), used by
     every spec so no test can click before the boot sequence has finished. It waits for
     the last boot step's DOM side effect (`#documentPage .empty-skeleton`) — a test-only
     signal, no new global — and turns any future load failure into an explicit "boot never
     finished" error instead of a misleading assertion failure.
  Verified: three consecutive full runs at the default worker count — 14/14, 14/14, 14/14.
- `frontend/package-lock.json` now actually contains **jsdom 25.0.1**. It was
  declared in `frontend/package.json` but absent from the lock (no
  `packages["node_modules/jsdom"]` entry; the only "jsdom" strings in the lock
  were vitest's optional peer declaration), so any lock-driven install —
  `npm ci` on a fresh clone or in CI — could never produce it and
  `npm run test:unit` failed with `Cannot find dependency 'jsdom'`. CI was
  unaffected so far only because no workflow runs vitest yet.
- `scripts/lint_frontend.py` now enumerates with
  `git ls-files --cached --others --exclude-standard`, so a newly created module is
  linted *before* it is `git add`-ed. Previously F1/F3 silently skipped it.
- Baseline recalibration against `frontend/app.js` (mechanical scan, not grep):
  - preview-state **writes are 17, not 12** as the design stated (16 `current*`
    plus `previewPaginationInitialized`; the design missed `:2947`, `:2957` and
    `:1018`).
  - the cross-domain coupling surface is **219 call sites / 49 domain pairs**
    plus **29 cross-domain state reads**, versus the 11 / 9 hand-built table in
    the design. Evidence: `docs/R&D/PLAN/v1.8.3-frontend-split/cross-domain-edges.md`
    (local only), which also lists the F3-whitelist decision that blocks B1.
  - `convertToMarkdown` is a pure function (0 DOM references): the earlier
    "DOM-tainted, 3 hits" note came from a bare `document` grep matching
    `data.document.name`.

## [1.8.2] — 2026-09-15

### Changed
- **Backend architecture**: `backend/app/main.py` split from 2644 lines into a
  268-line assembly layer (app factory + middleware chain + startup hooks +
  pinned `include_router` table), 13 domain routers under
  `backend/app/routers/`, and shared singletons/state in
  `backend/app/core/runtime.py`. All 55 routes moved verbatim; a pre-split
  OpenAPI snapshot baseline locks the contract (zero-diff gate).
- Agent-ops: retire `.GLM` rules dir (generated copies); ZCode reads `AGENTS.md`
  + `docs/agent-ops/core/` directly; sandbox patch protocol archived
  (`docs/agent-ops/glm-sandbox-patch.md`); `.GLM/` added to `.gitignore`.
  Adds kernel spec `docs/agent-ops/core/routing.md` + Cursor rule `010-routing`.

### Added
- `DEVELOPMENT.md`: three hard rules (500-line budget, routes only in domain
  routers, leaf modules must not import `app.main`).
- `scripts/lint_routes.py` and `scripts/lint_file_size.py`
  (+ `scripts/file_size_allowlist.json`): route-architecture lint and the
  500-line ratchet gate.
- `.github/workflows/lint.yml`: runs both gates on push/PR touching
  `backend/**` or `scripts/**`.

## [1.8.1] — 2026-09-14

Tag: **v1.8.1.0**. Branch: `feature/v1.8.1` (base f2ad595 = v1.8.0 content).
Release gates: PROOF-001/002/003 all green (2026-09-13/14, Cloud Studio GPU) —
BACKFILL-001 numbers identical to v1.8.0 baseline; pure-scan zero-hallucination
form verified; OpenAPI snapshot + pipeline regression green.

### Added
- Proof Pack (customer-facing trust evidence, pure post-processing — pipeline untouched):
  `proof_render.py` burns three-state provenance boxes into the original PDF's content
  stream (green=verified / amber=corrected / red=review; color + line-style double
  encoding for color-blind readers; cell bboxes re-derived from the raster-px table bbox
  via uniform grid, parity-pinned against `table_backfill.derive_cell_bbox`);
  `proof_report.py` one-page self-contained HTML report (en/zh literal tables, inline CSS,
  zero JS) + full machine-readable JSON; `proof_pack.py` packager + thin
  `scripts/trial/proof_pack.py` CLI (exit 0 / 2 contract-missing / 3 render-failure).
- `text_mismatch` provenance value: funnel-stage-4 failures are labeled instead of
  staying `vision`, so a review list ("cells we recommend you check") is finally
  possible; `quality.table_backfill.mismatch_details` (cap 50 + `mismatch_details_truncated`).
- Task result (GET `/api/v1/tasks/{id}/result`) now carries `preprocessing` metadata
  (coordinate_space / angle_deg / use_doc_unwarping) merged from the envelope.

### Changed
- `backfill_tables` gains an optional `angle_deg`/`use_doc_unwarping` gate: pages whose
  table bboxes live in preprocessed raster space are skipped and counted in
  `pages_skipped_preprocessed` instead of being aligned against the original PDF text
  layer (which fabricated mismatches). Defaults keep v1.8 behavior — upright fixtures
  (BACKFILL-001) produce identical numbers.
- `APP_VERSION` default **1.8.1**.
- TRIAL runbook: new P1-6 proof pack manual checks, including the real result-export
  command (`/tasks/{id}/result` — the envelope endpoint has no `tables`) and the honest
  deskew-skip limitation note.

## [1.8.0] — 2026-09-10

Tag: **v1.8.0** (f2ad595). Branch: `feature/v1.8`.

### Added
- Page-level text-layer trust gatekeeper (`page_text_trust.py`): invisible-rendered character ratio (Tr3) + full-page image coverage, per-page verdict `text_layer`/`overlay`/`mixed`/`no_text`.
- Selective cell backfill (`table_backfill.py`, four-layer funnel): amount/code/date/symbol cells are char-verified or backfilled from the text layer; `cell_provenance` / `cell_ocr_text` parallel grids + `quality.table_backfill` summary. Kill switch `TABLE_TEXT_BACKFILL=off`.
- Unified `AnalyzeOptions` (`models/analyze_options.py`) for both analyze routes; `table_text_backfill: off|auto` request switch.
- OpenAPI contract snapshot test (cloud-only), page-type calibration CLI (`page_type_probe.py`).
- `normalize_for_compare` in `docuvision_core.utils.pdf_text_utils` (NFKC + whitespace strip + punctuation fold).

### Changed
- `file_type_detector` from "first 3 pages accumulate 30 chars" to per-page gatekeeper judgement (mixed PDFs handled naturally).
- `APP_VERSION` default **1.8.0**.

### Removed
- `apps/lite/` (Lite app retired), `supabase/` (trial PoC with `to anon` RLS hole), `.github/workflows/ci-lite.yml`.
- core retirement: `processing/` adaptive family / evaluator / stitch / processor / result_mapper, `extractors/`, `engines/`, `models/`, `export/`, `demo/`, and utils config family. `pyproject.toml` drops camelot-py/pdfplumber/pandas/Pillow/numpy/scipy.
- `backend/app/services/core_table_extractor.py` (zero callers).

### Fixed
- `GET/POST /kie/templates/{template_id}` template id whitelist (`[A-Za-z0-9_-]+` path validation).
- `.gitignore`: ignore `backend/debug/` and `frontend/test-results/`.
- `QualityLayer` 缺失 `table_backfill` 字段：`GET /api/v1/jobs/{id}/result` 的 `quality.table_backfill` 被 Pydantic (`extra=ignore`) 静默丢弃，BACKFILL-001 验收误判为未启用；补字段后可正常回传。

## [1.7.0] — 2026-09-07

Tag: **v1.7.0** (commit `a72ec1d`). Branch: `feature/v1.7`.
See [v1.7-roadmap.md](docs/architecture/v1.7-roadmap.md).

### Added
- Pro single-task result persistence: `analyze_jobs` on the existing `QueueStore` SQLite plus `OUTPUT_DIR/{task_id}/result.json`. Startup hydrates the in-memory `tasks` dict. In-flight jobs become `interrupted` (no auto GPU resume). FIFO `TASK_KEEP_LAST_N` (default 50) deletes the DB row and output directory together. Builder: `analyze_job_store.py`. Tests: `backend/tests/test_task_persistence.py`. Cloud gate **TASK-PERSIST-001**.

### Changed
- `APP_VERSION` default **1.7.0** (`/health` `api_version`). Tag `v1.7.0` was cut on 2026-09-07 (commit `a72ec1d`), not in this commit.

## [1.6.0] — 2026-09-06

See [RELEASE_1.6_NOTES.md](docs/release/RELEASE_1.6_NOTES.md) and [v1.6-roadmap.md](docs/architecture/v1.6-roadmap.md).

### Added
- Pro single-task artifact pack: `GET /api/v1/tasks/{id}/export/zip` (`include=tables,figures,json`) and sidebar **ZIP** button. Layout: `manifest.json` + `tables/` + `figures/` (`is_merged` under `figures/merged/`). Builder: `pack_export_service.py`. Tests: `backend/tests/test_pack_export_service.py`.
- Trial hardening: API-key middleware (`DOCUVISION_TRIAL_API_KEY`, HTTP `X-API-Key` / WS `?key=`), configurable CORS allowlist (`DOCUVISION_CORS_ORIGINS`), enforced `MAX_FILE_SIZE` (413) on all four upload endpoints, frontend key bridge (`shared/trial-key.js`). See [TRIAL_REMOTE_60MIN.md](docs/demo/TRIAL_REMOTE_60MIN.md) §3 P0-1.
- Figure crop export + integrity checks: `figure_service.py`, pipeline `figure_step`, `result.figures` / `envelope.figures` + `quality.figure_*`, routes `GET /tasks/{id}/figures[/{figure_id}]`, option `enable_figure_export`. Split-figure merge veto, caption binding (F3), crop-to-detection-box (no pad).
- Layout-first tables via PP-StructureV3; reading order from `block_order`; `LAYOUT_TYPES` expanded to 23 classes; multi-level table headers (F1/F2/F4). Per-page layout timeout with bad-page skip.
- Trial sample generator (`scripts/trial/generate_trial_samples.py`): multi-column techdoc with merged-cell symbol table, flowchart and architecture diagram PDFs into `test_data/testfiles/trial/`.
- Ground-truth diff: `app/services/trial/gt_diff.py` (CLI + HTML report), routes `POST /api/v1/trial/gt-diff/{task_id}` + `GET .../report`. §3 P1-4.
- Symbol survival benchmark (`scripts/trial/symbol_benchmark.py`, GPU): PP-OCR vs Qwen2.5-VL. §3 P1-5.
- Trial ops scripts: `trial_preflight.py` (readiness gate), `trial_reset.py` (data wipe between prospects); `.GLM/` assistant rules.

### Changed
- `APP_VERSION` default **1.6.0** (`/health` `api_version`).

### Fixed
- `MAX_FILE_SIZE` was configured but never enforced; now wired into `/ocr`, `/upload`, `/analyze`, `/documents:analyze`.
- pytest collection interrupted on `test_api_contract_smoke.py` / `test_api_pipeline.py`: those legacy manual scripts use top-level `from _sample_paths import ...` while package-mode collection (tests/__init__.py) only puts `backend/` on sys.path. `tests/conftest.py` now inserts the tests dir into sys.path; the scripts collect 0 items harmlessly and stay runnable via `python tests/test_api_pipeline.py`.
- Table CSV/Excel cells starting with `=`/`+`/`@` or non-numeric `-` are prefixed so Excel does not treat them as formulas.
- PaddleX #17446 empty-detection crash: drop predict kwargs that trigger it; uniquify figure crop ids.

## [1.5.0] — 2026-08-05

### Added
- Pro Queue persistence (Batch + HITL): single-file SQLite (`backend/data/docuvision.sqlite`), `queue_store.py`, `BatchService` / `HitlReviewQueue` `load_from_db` + `_persist`, HITL `edited_fields` / `resolved_at`. See [RELEASE_1.5_NOTES.md](docs/release/RELEASE_1.5_NOTES.md) and [MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md).

### Fixed
- `resume_batch` finalizes when no pending tasks remain after restart demotion (avoids stuck `PROCESSING`).

### Changed
- `APP_VERSION` default **1.5.0**; `hitl_queue.enqueue` / `resolve` are async.

## [1.4.1] — 2026-07-31

### Added
- Lite `POST /api/v1/lite/extract/tables` now accepts `table_template` (`bank_statement` / `invoice_line_items`), forwarding it to `extract_tables_from_pdf`; results return in `mapped_table_rows` + `table_template`. Parity with `POST /extract/auto` (non-breaking, optional param). See [lite-api.md §7.4](docs/architecture/lite-api.md).

### Fixed
- `apps/lite/backend/tests/test_lite_health.py`: `LITE_RESULT_TOP_KEYS` constant drifted from `LiteResult` schema (missing `mapped_table_rows`, `table_template` added in v1.4.0); `test_lite_result_schema_keys` now passes. Test-only contract alignment.

## [1.4.0] — 2026-06-30

Table mapping productization, HITL editable review, PDF Tools nav tab, batch mapped-row Excel export, and backend hardening (webhook auth/SSRF, Phase1 form parity, dead-config cleanup). See [RELEASE_1.4_NOTES.md](docs/release/RELEASE_1.4_NOTES.md) and [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md).

### Added

- Pro **Table mapping** processing mode: `processingMode=table_mapping` + `table_template` (`bank_statement`, `invoice_line_items`) → `mapped_table_rows` UI tab.
- Document profile **eligibility** hint on upload (`Ready for table mapping` for `pdf_digital`).
- Pro **Reviews** tab: editable KIE fields, Save (`PATCH /tasks/{id}/kie-fields`), Approve/Reject; **`hitl_policy`** profiles (`full` / `lite` / `off`).
- Pro **PDF Tools** tab: merge, split, metadata (UI); API stubs remain for searchable / form-fill.
- Batch manifest set **`mapped_bank_statement_3`**; XLSX **MappedRows** sheet; script `run_batch_mapped_acceptance.ps1` (**MAPPED-BATCH-001**).
- `POST /api/v1/documents:analyze` (Phase1 Job endpoint) now accepts the full Form parameter set previously only on legacy `POST /api/v1/analyze`: `enable_layout`/`enable_table`/`enable_formula`/`enable_seal`/`enable_kie`, `language`, `ocr_engine`/`layout_engine`/`table_engine`, `table_allow_fullpage_fallback`, formula thresholds (`formula_disable_layout`/`formula_disable_preprocess`/`formula_two_stage_threshold_retry`/`formula_primary_layout_threshold`/`formula_fallback_layout_threshold`/`formula_layout_threshold`/`pipeline_formula_batch_size`), `table_template`, `enable_hitl`. Defaults mirror legacy; `document_type=invoice/receipt/id_card` auto-enables KIE. Non-breaking (all new params optional with legacy-matching defaults).
- Contract tests: `test_table_template_analyze.py`, `test_hitl_policy.py`, `test_task_kie_fields_patch.py`, `test_pdf_tools_service.py`, `test_phase1_analyze_form.py`, `test_webhook_service.py`; core `test_table_column_mapping.py`, `test_table_result_mapper.py`.
- `accelerate` dependency for KIE `device_map=auto`; multi-cloud KIE model path discovery; `GET /api/v1/health` for AI Studio `api_serving`.

### Changed

- `APP_VERSION` default **1.4.0**; Phase A CI extended with v1.4 contract files.
- Table mapping routes born-digital PDF via `enable_layout=false` + docuvision-core TableProcessor (no KIE / no HITL enqueue on this path).
- `batch_export_service._task_kie_fields`: removed dead `quality` branch (`if isinstance(quality, dict): pass` had no effect).
- Debug artifact download endpoint (`GET /api/v1/jobs/{job_id}/debug/{filename}`): replaced `os.path.abspath(...).startswith(...)` with `Path.is_relative_to` to block sibling-directory traversal (e.g. `./debug2/...`).

### Security

- Webhook registration hardened (breaking). Two-layer gating:
  - `DOCUVISION_WEBHOOK_ENABLED` (default `false`): when disabled, `GET/POST /api/v1/webhooks` return `404` and `dispatch_event_async` returns `[]` (no outbound POST even for previously registered subscriptions).
  - `DOCUVISION_WEBHOOK_ADMIN_TOKEN`: when enabled, `GET/POST /api/v1/webhooks` require `X-DocuVision-Admin-Token` header to match. Fail-closed: empty configured token rejects registration with `401` (no open registration when enabled without a token).
- SSRF guard on webhook registration: URLs whose host resolves to private/loopback ranges (`127.0.0.0/8`, `10.0.0.0/8`, `169.254.0.0/16`, `192.168.0.0/16`, `172.16.0.0/12`, `::1`, `fc00::/7`, `fe80::/10`) are rejected with `400`. Does not defend against DNS rebinding (v1.5+ roadmap).

### Removed

- `enable_ocr` per-block OCR dead config removed from `ProcessingOptions`, `/api/v1/analyze` Form, frontend payload, and tests. Standalone `/api/v1/ocr` endpoint and `OCRService` are unchanged.
- `chart_step` and `enable_chart` removed from orchestrator pipeline and Pro UI. `ChartService` deleted (no remaining callers).
- `financial_report` document type removed from KIE registry, orchestrator allow-list, frontend `KIE_DOC_TYPES`, and docs. API callers passing `document_type=financial_report` now hit `unsupported_document_type` (breaking).
- `table_areas` ROI removed across Pro/Lite/core: orchestrator, `table_service`, `core_table_extractor`, Lite `/extract/auto` Form field, Lite `table_pipeline`, core `TableProcessor`/`CamelotExtractor` params, and dead methods `extract_camelot_lattice`/`extract_camelot_stream`. Lite `/extract/auto` no longer accepts `table_areas` (breaking API change).
- `POST /api/v1/pdf-tools/searchable` now returns `501 Not Implemented`. The previous `make_searchable_pdf` was a placeholder that inserted the supplied text into a fixed rectangle (not a real OCR text layer) and has been deleted. Searchable PDF remains on the v1.5+ roadmap (breaking).

### Fixed

- PDF Tools split page list coercion and file-selection hints.
- Pro tab typography; Quality panel gated on KIE-enabled runs.
- Queue reprocess prefers selected completed item; API probe fallback to `/engines` on AI Studio.

## [1.3.1] — 2026-06-23

Maintenance release: remove unused Lite/Pro UI scope, add Lite server-side PDF preview. See [RELEASE_1.3.1_NOTES.md](docs/release/RELEASE_1.3.1_NOTES.md) and [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md).

### Added

- Lite **server-side preview** API (`POST /preview`, `GET .../page-image/{n}`) with PyMuPDF rasterization.
- Lite contract tests `test_lite_preview.py`; Playwright **LITE-PREVIEW-01** (`npm run test:e2e:lite`).

### Removed

- Pro **Auto-detect** UI and analyze classify shortcut.
- Lite **Batch API/UI** (`/api/v1/lite/batch`).
- Lite **Table ROI** UI; client-side **pdf.js** in Lite frontend.

### Changed

- `APP_VERSION` default **1.3.1**; Pro E2E mock routes extended for queue/options regression.
- Cloud merge gate v1.3.1 replaces **LITE-BATCH-001** with **LITE-PREVIEW-001**.

## [1.3.0] — 2026-06-17

Roadmap **P0** (PDF core routing + IDP validation + Lite batch). See [RELEASE_1.3.0_NOTES.md](docs/release/RELEASE_1.3.0_NOTES.md) and [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md).

### Added

- Pro **pdf_digital** → `docuvision-core` TableProcessor; **table stitch** MVP; PyMuPDF `find_tables` fallback.
- **KIE field validation** (`kie_validation`); batch CSV validation columns; custom templates API.
- Lite **Batch API** (`/api/v1/lite/batch`) with CSV/XLSX export.
- Pro MVP APIs: classify, document profile, HITL, webhooks, PDF tools.
- Cloud checklist [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md).

### Changed

- `APP_VERSION` default `1.3.0`; Pro `requirements.txt` adds `docuvision-core[lite]`, `pdfplumber`, `pymupdf`.

## [1.2.1] — 2026-06-17

Maintenance patch (deferred from v1.2.0). See [RELEASE_1.2.1_NOTES.md](docs/release/RELEASE_1.2.1_NOTES.md).

### Added

- Batch **Excel** export: `GET /batch/{id}/export.xlsx` + UI **Download Excel**.
- Playwright E2E P0 (UI-S + UI-Q); Shared UI Shell PR2 (`shared/components.css`, `pro-only.css`).

### Changed

- [KNOWN_LIMITATIONS.md](docs/release/KNOWN_LIMITATIONS.md): Batch Excel delivered; Playwright P0 spec added.

## [1.2.0] — 2026-06-12

Pro **multipage PDF KIE** (`kie_pages`) and **Batch Processing** productization (API export + UI tab). Cloud merge gate passed; see [RELEASE_1.2_NOTES.md](docs/release/RELEASE_1.2_NOTES.md) and [KIE_TEST_RUN_TRACKER.md](docs/architecture/KIE_TEST_RUN_TRACKER.md).

### Added

- **Multipage PDF KIE**: `kie_pages` on analyze / jobs (`1`, `1-3`, `all`; max 5 pages). Per-page VL + document-level field merge; `kie_fields_by_page` + `quality.kie_pages_*`.
- **Batch productization**: batch jobs use full document orchestrator (KIE + envelope); `GET /batch/{id}/export.csv` (kie/summary/failures) and `export.json`; Pro UI Batch tab wired.
- Test fixtures script `test_data/scripts/build_multipage_kie_fixtures.py`; batch manifest `test_data/testfiles/batch/manifest.json`; acceptance `multipage_kie.md`, `batch_kie.md`.
- Merge gate checklist `test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md` (Cloud Studio zsh/bash).

### Changed

- `APP_VERSION` default `1.2.0`; batch KIE concurrency defaults to 1 (`BATCH_MAX_CONCURRENT_KIE`).
- Batch `resume` re-schedules pending tasks when `process_func` is provided.

### Fixed

- Batch KIE acceptance script: merge manifest set-level `document_type` into `options` before `POST /batch` (fixes `skipped_doc_type` / 0/6 `kie_production_hit`).
- Batch manifest: duplicate `document_type` inside each set `options` for API clarity.
- Acceptance script: print `export BATCH_ID=...`, validate CSV `kie_production_hit`, exit non-zero on BATCH-002 failure.
- `pdf_page_count`: return `0` when PDF cannot be opened so `resolve_document_page_count` can fall back to `view.pages` / layout (fixes Phase A `test_document_page_count_from_view_pages`).
- Pro UI: queue processes selected item only (no auto-run of other pending); multipage preview page count; batch JSON download as file.

## [1.1.0] — 2026-06-04

Pro **KIE query fields** (extend-only runtime schema). Cloud Phase F accepted; see [RELEASE_1.1_NOTES.md](docs/release/RELEASE_1.1_NOTES.md) and [KIE_TEST_RUN_TRACKER.md](docs/architecture/KIE_TEST_RUN_TRACKER.md).

### Added

- **Pro KIE query fields** (`kie_query_fields`): extend built-in YAML schema at runtime (Azure Query Fields aligned, max 20 fields). API: `POST /api/v1/analyze`, `POST /api/v1/documents:analyze`, batch `options`. See [kie-custom-fields.md](docs/architecture/kie-custom-fields.md).
- Pro UI: Analysis Options → Advanced → Additional KIE fields (comma-separated or JSON).
- `quality.kie_query_fields_requested` / `kie_query_fields_filled`.

### Changed

- `KieManager` / `QwenDocumentKIEService` accept merged schema for VL prompts.
- `APP_VERSION` default `1.1.0`.

## [1.0.1] — 2026-06-02

Maintenance release: **DocuVision Lite** on `main`, dead-code cleanup, CI/docs alignment. Pro KIE scope unchanged from 1.0.

### Added

- **DocuVision Lite** (CPU): [`apps/lite/`](apps/lite/), [`packages/docuvision-core/`](packages/docuvision-core/), [`docs/architecture/lite-api.md`](docs/architecture/lite-api.md).
- Lite: digital PDF tables (Camelot / pdfplumber), Document Profile, scan/image Text OCR (EasyOCR / Tesseract), JSON / CSV / Markdown / Word export.
- Shared UI shell [`frontend/shared/`](frontend/shared/); GitHub Actions **CI Lite**.
- Pro: `install_pro_gpu.sh`, `gpu_lib_path`, live API tests skip when `:8000` is down.

### Fixed

- Lite EasyOCR Reader process cache and multi-page reuse.
- Lite Analysis Options: hide Tables for raster documents.
- Phase A CI: lazy-import `requests` in `conftest.py`.

### Removed

- Dead code: `page_processor`, `base_processor`, broken `file_utils`, `paddleocr_model_preloader`, core `paddleocr_engine`, `generate_kie_card_samples.py`, `test-canvas-display.html`.

### Pro vs Lite (summary)

| Area | Pro (`:8000`) | Lite (`:8001`) |
|------|---------------|----------------|
| Engines | PP-StructureV3 + Qwen KIE | pdfplumber / Camelot + EasyOCR / Tesseract |
| KIE | 5 fixed document types | None |
| GPU | Recommended | CPU |
| Tables | Layout + complex PDF | Born-digital PDF; raster tables frozen by default |
| Batch | Backend API | Not available |

See [Known limitations](docs/release/KNOWN_LIMITATIONS.md) and [RELEASE_1.0.1_NOTES.md](docs/release/RELEASE_1.0.1_NOTES.md).

## [1.0.0] — 2026-05-21

First self-hosted release: Azure Layout–style analysis (PP-StructureV3) plus optional Qwen2.5-VL KIE for five fixed document types.

### Added

- FastAPI pipeline: layout, table, optional formula/seal, envelope (`raw` / `fused` / `view` / `quality`).
- **Qwen KIE** via `QwenDocumentKIEService` + `kie_configs/*.yaml` for `invoice`, `receipt`, `id_card`, `passport`, `bank_card`.
- KIE acceptance rules **KIE-ACCEPT-001/002/003** and `quality.kie_*` / `kie_id_card_precision_*` metrics.
- Synthetic Chinese ID card samples `id_card_sample_02~04.jpg` with layout self-check scripts under `test_data/scripts/`.
- GitHub Actions workflow **KIE Phase A** (CPU contract tests, no Paddle / no Qwen weights).
- Root **MIT License**; release notes and [Known limitations](docs/release/KNOWN_LIMITATIONS.md).

### Fixed

- PDF invoice KIE: rasterize page 1 instead of passing `.pdf` to PIL (`e7dc4ab`).
- Phase A CI: remove eager Paddle imports from `app/services/__init__.py`; slim CI dependencies.

### Changed

- Strengthened `id_card.yaml` prompt and **KIE-ACCEPT-003** (18-digit `id_number` + `name` for Chinese ID regression).
- Cloud validation docs, Tracker, and architecture doc **Release 1.0** / **v1.1 custom fields** roadmap (v1.12).

### Verified (Cloud Studio GPU, see [KIE_TEST_RUN_TRACKER.md](docs/architecture/KIE_TEST_RUN_TRACKER.md))

- **Phase C** (invoices): 3/3 — 001 + 002.
- **Phase D** (`images/kie/`): 6/6 — 001 + 002; id_card **02~04** — 003.
- **Phase E** (receipt): 1/1 — 001 + 002.
- **Phase A** (GitHub Actions): contract pytest green on `main`.

### Known limitations (1.0)

See [docs/release/KNOWN_LIMITATIONS.md](docs/release/KNOWN_LIMITATIONS.md). Summary:

- `id_card_sample_01.jpg` is a legacy non–Chinese-ID layout; **003 may fail** while 002 still passes.
- No user-defined KIE schema, Batch UI productization, multi-page PDF KIE, or field bbox overlay.
- Full `pytest tests/` green not required; live `:8000` integration tests remain manual.

### Out of scope for 1.0

- Custom fields MVP (planned v1.1).
- `PP-DocTranslation`, PaddleOCR-VL long-document QA.

---

## Pre-1.0 history (high level)

| Period | Highlights |
|--------|------------|
| Phase 1–2 | PP-StructureV3 layout, envelope layers, formula/seal, table layout-first. |
| KIE migration | Qwen2.5-VL replaces PaddleNLP UIE; `kie_step` + `view.fields`. |
| 2026-05-20 | Cloud 7-sample KIE baseline; PDF KIE fix (`e7dc4ab`). |
| 2026-05-21 | id_card samples 02–04, ACCEPT-003, Phase A CI, Release 1.0 prep (`2c9c58b`). |

[Unreleased]: https://github.com/livezingy/DocuVision/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/livezingy/DocuVision/releases/tag/v1.1.0
[1.0.1]: https://github.com/livezingy/DocuVision/releases/tag/v1.0.1
[1.0.0]: https://github.com/livezingy/DocuVision/releases/tag/v1.0.0
