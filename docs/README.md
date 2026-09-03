# DocuVision Documentation

> **Status**: living index — update when adding or renaming docs.

## Onboarding

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Product overview, Pro vs Lite, quick start |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [../test_data/acceptance/QUICK_START.md](../test_data/acceptance/QUICK_START.md) | Prepare test files and first run |

## Architecture (living)

Read in this order when onboarding to the codebase:

1. [architecture/docuvision-system-design.md](architecture/docuvision-system-design.md) — system design hub
2. [architecture/kie.md](architecture/kie.md) — KIE contract (Qwen2.5-VL)
3. [architecture/kie-custom-fields.md](architecture/kie-custom-fields.md) — custom KIE query fields
4. [architecture/lite-api.md](architecture/lite-api.md) — Lite REST API
5. [architecture/shared-ui-shell.md](architecture/shared-ui-shell.md) — Pro/Lite shared UI
6. [architecture/batch-ui-roadmap.md](architecture/batch-ui-roadmap.md) — Batch UI roadmap
7. [architecture/v1.5-roadmap.md](architecture/v1.5-roadmap.md) — post-v1.4 long-tail (searchable PDF, batch persistence)
8. [architecture/main-tracked-issues.md](architecture/main-tracked-issues.md) — lightweight backlog (code wins on conflict)
9. [architecture/pp-structurev3-official-findings.md](architecture/pp-structurev3-official-findings.md) — PP-StructureV3/Qwen2.5-VL 官方能力依据（reading order / LAYOUT_TYPES / caption / header / glyph）
10. [architecture/pp-structurev3-fix-plan.md](architecture/pp-structurev3-fix-plan.md) — 基于官方依据的 4 个问题点修复规划（F1-F4）

## Validation and QA

| Doc | Purpose |
|-----|---------|
| [architecture/CLOUD_VALIDATION.md](architecture/CLOUD_VALIDATION.md) | Cloud Studio GPU phases A–G; **§1.1 Baidu AI Studio** Pro UI via `api_serving` |
| [architecture/KIE_TEST_RUN_TRACKER.md](architecture/KIE_TEST_RUN_TRACKER.md) | KIE batch run log (append-only) |
| [../test_data/acceptance/README.md](../test_data/acceptance/README.md) | Acceptance matrix index |
| [../test_data/acceptance/UI_VERIFICATION_MATRIX.md](../test_data/acceptance/UI_VERIFICATION_MATRIX.md) | UI E2E vs manual scope; assistant manual-test reminders |
| [../test_data/AutoTest/PRO_UI_E2E_PLAN.md](../test_data/AutoTest/PRO_UI_E2E_PLAN.md) | Playwright E2E plan |
| [../backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../backend/tests/KIE_ACCEPTANCE_CRITERIA.md) | KIE acceptance criteria |

## Release (frozen per version)

| Doc | Purpose |
|-----|---------|
| [release/README.md](release/README.md) | Version index |
| [release/KNOWN_LIMITATIONS.md](release/KNOWN_LIMITATIONS.md) | Known limitations (living summary) |

## Component-local READMEs

| Path | Scope |
|------|-------|
| [../frontend/README_FRONTEND.md](../frontend/README_FRONTEND.md) | Pro SPA |
| [../apps/lite/backend/README.md](../apps/lite/backend/README.md) | Lite backend |
| [../packages/docuvision-core/README.md](../packages/docuvision-core/README.md) | Shared core library |

## Document lifecycle

| Label | Meaning |
|-------|---------|
| **living** | Update with code changes (`docs/architecture/*`, this index) |
| **frozen** | Snapshot at release (`docs/release/RELEASE_*`, `test_data/acceptance/MERGE_MAIN_v*`) |
| **append-only** | Add entries only (`KIE_TEST_RUN_TRACKER.md`) |
| **local only** | Never commit (`test_data/TestResult/`, `*Upwork*`, `docs/R&D/*` except `R&D/README.md`) |

## R&D (local notes)

Exploratory drafts: [R&D/README.md](R&D/README.md) — not authoritative; promote conclusions into `architecture/` when stable.

## Test layout (high level)

| Area | Path | CI / when to run |
|------|------|------------------|
| Pro contract (mock) | `backend/tests/test_kie_*.py`, Phase A list in `CLOUD_VALIDATION.md` | PR / Cloud Phase A |
| Pro live GPU | `backend/tests/test_live_api.py` | Cloud only, server on `:8000`; ignore in full `pytest` |
| Pro manual script | `backend/tests/test_api_contract_smoke.py`（契约快检）、`test_api_pipeline.py`（含 analyze 轮询） | Cloud REPL, optional |
| Lite | `apps/lite/backend/tests/` | GitHub `CI Lite` on PR |
| Core lib | `packages/docuvision-core/tests/` | CI Lite subset + Cloud |
| E2E UI (planned) | `frontend/tests/e2e/` | Local/Cloud with mock API |

New features: add **contract tests** first; extend `MERGE_MAIN_v*.md` only at release — do not duplicate scenarios across `test_live_api` and Phase A mocks.

**UI manual vs automated**: [UI_VERIFICATION_MATRIX.md](../test_data/acceptance/UI_VERIFICATION_MATRIX.md) — E2E green **reduces** manual scope only for mapped cases; assistants must list remaining manual checks after each UI/API change (`004-project.mdc` §手工测试提醒).

## Demo

- [demo/TRIAL_DEMO.md](demo/TRIAL_DEMO.md)
- [demo/SAMPLES.md](demo/SAMPLES.md)
- [demo/TRIAL_REMOTE_60MIN.md](demo/TRIAL_REMOTE_60MIN.md) — remote 1-hour diagnostic trial (GLM `feat/glm-trial`): bring-up, timeboxed script, cloud acceptance criteria
