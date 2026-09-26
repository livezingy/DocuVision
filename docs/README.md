# DocuVision Documentation

> **Status**: living index — update when adding or renaming docs.  
> 最近对照：v1.9.0 / tag v1.9.0（已切 2026-09-20）/ commit 0b01eb6（2026-09-20）

## Onboarding

| Doc | Purpose |
|-----|---------|
| [../README.md](../README.md) | Product overview, Pro vs Lite, quick start |
| [../CHANGELOG.md](../CHANGELOG.md) | Version history |
| [../test_data/acceptance/QUICK_START.md](../test_data/acceptance/QUICK_START.md) | Prepare test files and first run |

## Architecture (living)

Read in this order when onboarding to the codebase.
Start with [architecture/module-map.md](architecture/module-map.md) for the current module layout; the list below is historical reading order.

1. [architecture/docuvision-system-design.md](architecture/docuvision-system-design.md) — system design hub
2. [architecture/kie.md](architecture/kie.md) — KIE contract (Qwen2.5-VL)
3. [architecture/kie-custom-fields.md](architecture/kie-custom-fields.md) — custom KIE query fields
4. [architecture/shared-ui-shell.md](architecture/shared-ui-shell.md) — Shared UI shell (Pro; Lite retired in v1.8)
5. [architecture/batch-ui-roadmap.md](architecture/batch-ui-roadmap.md) — Batch UI roadmap
6. [architecture/v1.5-roadmap.md](architecture/v1.5-roadmap.md) — v1.5 leftovers (searchable PDF, AcroForm, mail)
7. [architecture/v1.6-roadmap.md](architecture/v1.6-roadmap.md) — v1.6.0 shipped (figure baseline + artifact pack; ZIP contract in system-design §9.1)
8. [architecture/v1.7-roadmap.md](architecture/v1.7-roadmap.md) — v1.7.0 shipped (Pro single-task result persistence; tag v1.7.0 cut 2026-09-07)
9. [architecture/main-tracked-issues.md](architecture/main-tracked-issues.md) — lightweight backlog (code wins on conflict)
10. [architecture/pp-structurev3-official-findings.md](architecture/pp-structurev3-official-findings.md) — PP-StructureV3/Qwen2.5-VL 官方能力依据（reading order / LAYOUT_TYPES / caption / header / glyph）
11. [architecture/pp-structurev3-fix-plan.md](architecture/pp-structurev3-fix-plan.md) — 基于官方依据的 4 个问题点修复规划（F1-F4）
12. [architecture/module-map.md](architecture/module-map.md) — module map: backend router domains × frontend module domains, dependency laws, gate inventory (P-004)
13. [architecture/v1.9-roadmap.md](architecture/v1.9-roadmap.md) — v1.9 **立项**（2026-09-20，前端批次：P-007 方案 B / 巨函数切分 / JSDoc+tsc 评估 / 两个孤儿 wire-or-retire）
14. [architecture/doc-governance.md](architecture/doc-governance.md) — 文档治理门禁（**DOC-1** 墓碑前缀 / **DOC-2** 路径漂移；规则文本在此，清单真源在 `scripts/docs_refs_audit.py`；晋升自 PENDING P-022，2026-09-25）
15. [architecture/ocr-quality-harness.md](architecture/ocr-quality-harness.md) — OCR 质量测量 harness 规格与口径（指标族 / 钉死设计点 D2·D7·D8·D-A / base A-B 坐标系与回归哨兵；**实现 local-only、不入库**；晋升自 PENDING P-020 + P-018，2026-09-26）

## Validation and QA

| Doc | Purpose |
|-----|---------|
| [architecture/CLOUD_VALIDATION.md](architecture/CLOUD_VALIDATION.md) | Cloud Studio GPU 回归阶段（A–F、MP、H-Batch）; **§1.1 Baidu AI Studio** `api_serving` + **§1.1.1 persist** (work / Git / PaddleX / KIE) |
| [architecture/KIE_TEST_RUN_TRACKER.md](architecture/KIE_TEST_RUN_TRACKER.md) | KIE batch run log (append-only) |
| [../test_data/acceptance/README.md](../test_data/acceptance/README.md) | Acceptance matrix index |
| [../test_data/acceptance/UI_VERIFICATION_MATRIX.md](../test_data/acceptance/UI_VERIFICATION_MATRIX.md) | UI E2E vs manual scope; assistant manual-test reminders |
| [../test_data/AutoTest/PRO_UI_E2E_PLAN.md](../test_data/AutoTest/PRO_UI_E2E_PLAN.md) | Playwright E2E plan |
| [../backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../backend/tests/KIE_ACCEPTANCE_CRITERIA.md) | KIE acceptance criteria |

## Release

| Doc | Purpose |
|-----|---------|
| [release/README.md](release/README.md) | Historical release index (v1.6 and earlier); **from v1.7 on, [`../CHANGELOG.md`](../CHANGELOG.md) is the single entry point** for release notes |
| [release/KNOWN_LIMITATIONS.md](release/KNOWN_LIMITATIONS.md) | Known limitations (living summary; applies through v1.8.3) |

## Component-local READMEs

| Path | Scope |
|------|-------|
| [../frontend/README_FRONTEND.md](../frontend/README_FRONTEND.md) | Pro SPA |
| [../packages/docuvision-core/README.md](../packages/docuvision-core/README.md) | Shared core library |

## Document lifecycle

| Label | Meaning |
|-------|---------|
| **living** | Update with code changes (`docs/architecture/*`, this index) |
| **frozen** | Snapshot at release (`docs/release/RELEASE_*`, `test_data/acceptance/MERGE_MAIN_v*`) |
| **append-only** | Add entries only (`KIE_TEST_RUN_TRACKER.md`) |
| **local only** | Never commit (`test_data/TestResult/`, `*Upwork*`, `docs/R&D/*` except `R&D/README.md`) |

## Agent-ops (multi-agent rules)

| Doc | Purpose |
|-----|---------|
| [agent-ops/core/constraints.md](agent-ops/core/constraints.md) | Shared constraints (single source of truth) |
| [agent-ops/core/environment.md](agent-ops/core/environment.md) | Environment facts |
| [agent-ops/core/testing.md](agent-ops/core/testing.md) | Testing & validation rules |
| [agent-ops/core/doc-sync.md](agent-ops/core/doc-sync.md) | Doc sync mechanisms |
| [agent-ops/doc-sync-ownership.md](agent-ops/doc-sync-ownership.md) | 归属表（`doc-sync.md` 机制 2 附表：改哪个模块 → 同步哪个文档） |
| [agent-ops/core/frontend.md](agent-ops/core/frontend.md) | Frontend architecture rules (F1-F7, module landing, whitelist registry, known orphans) |
| [agent-ops/core/agents.md](agent-ops/core/agents.md) | Agent roster (role/mapping) |
| [../AGENTS.md](../AGENTS.md) | Multi-agent rules entrypoint |

## R&D (local notes)

Exploratory drafts: [R&D/README.md](R&D/README.md) — not authoritative; promote conclusions into `architecture/` when stable.

## Test layout (high level)

| Area | Path | CI / when to run |
|------|------|------------------|
| Pro contract (mock) | `backend/tests/test_kie_*.py`, Phase A list in `CLOUD_VALIDATION.md` | PR / Cloud Phase A |
| Pro live GPU | `backend/tests/test_live_api.py` | Cloud only, server on `:8000`; ignore in full `pytest` |
| Pro manual script | `backend/tests/test_api_contract_smoke.py`（契约快检）、`test_api_pipeline.py`（含 analyze 轮询） | Cloud REPL, optional |
| Test registration | `backend/tests/test_registry.json`（每文件一条 `kind`；audit check 4 与 Phase A 列表对账，漏登记 = 红） | audit（本地 / `agent-ops-audit`） |
| Core lib | `packages/docuvision-core/tests/` | Cloud |
| E2E UI | `frontend/tests/e2e/`（4 spec / 14 用例） | CI（`lint.yml` 的 `e2e` job，main-only）+ 本地；mock API，不需后端/GPU |
| E2E gate hygiene (E1) | `scripts/check_e2e_allowlist.py`（白名单格式/时效/棘轮 + 套件用例数钉死） | CI（`lint.yml` 的 stdlib 段，与 F1-F7 同级） |

New features: add **contract tests** first; extend `MERGE_MAIN_v*.md` only at release — do not duplicate scenarios across `test_live_api` and Phase A mocks.

**UI manual vs automated**: [UI_VERIFICATION_MATRIX.md](../test_data/acceptance/UI_VERIFICATION_MATRIX.md) — E2E green **reduces** manual scope only for mapped cases; assistants must list remaining manual checks after each UI/API change (`004-project.mdc` §手工测试提醒).

## Demo

- [demo/TRIAL_DEMO.md](demo/TRIAL_DEMO.md)
- [demo/SAMPLES.md](demo/SAMPLES.md)
- [demo/TRIAL_REMOTE_60MIN.md](demo/TRIAL_REMOTE_60MIN.md) — remote 1-hour diagnostic trial (GLM `feat/glm-trial`): bring-up, timeboxed script, cloud acceptance criteria
