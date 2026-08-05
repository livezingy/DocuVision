# Release 1.5.0 notes

**Tag**: `v1.5.0`
**Date**: 2026-08-05
**Train**: Queue persistence (Batch + HITL) — first minor with SQLite-backed restart recovery

## Summary

v1.5.0 adds single-file SQLite persistence for Pro Batch jobs and HITL review items so queue state survives `:8000` process restarts. Runtime memory remains the live cache; DB is crash-recovery only. No Redis / Alembic / multi-replica.

## Added

- `backend/app/services/persistence/queue_store.py`: `QueueStore` Protocol + `SqliteQueueStore` (WAL, `threading.Lock`, column registry for `batch_jobs` / `hitl_reviews`).
- `BatchService.attach_store` / `load_from_db` / `_persist` / `_persist_async`: upsert on create and status flips; `processing→paused` (task `processing→pending`) on load; no auto GPU resume.
- `HitlReviewQueue.attach_store` / `load_from_db` / async `enqueue` / `resolve(..., edited_fields=)`: persist human corrections in `edited_fields` + `resolved_at`; original `payload` unchanged.
- Config `SQLITE_DB_PATH` (default `data/docuvision.sqlite`, relative to `backend/` cwd); `.gitignore` `backend/data/`.
- Tests: `backend/tests/test_queue_persistence.py` (local-runnable, no paddle).
- Cloud gate: [MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md) (**BATCH-PERSIST-001**, **HITL-PERSIST-001**).

## Fixed

- `resume_batch`: when no pending tasks remain after restart demotion, finalize to `completed`/`failed`/`cancelled` instead of sticking in `PROCESSING`.

## Changed

- `APP_VERSION` default **1.5.0**.
- `hitl_queue.enqueue` / `resolve` are async (orchestrator + resolve route await them).
- Living doc: [v1.5-roadmap.md](../architecture/v1.5-roadmap.md) Schema + Adversarial check (`edited_fields` column).

## Out of scope

- `tasks` dict in `main.py` (single-task results) still in-memory.
- Webhook subscription persistence, Redis, task-level SQL query, HITL edit history/diff.

## Verification (hard gate passed 2026-08-05)

| Layer | Result |
|-------|--------|
| Local mock | `pytest backend/tests/test_queue_persistence.py` — **7 passed** |
| BATCH-PERSIST-001 | Cloud path B: batch `completed` survives restart |
| HITL-PERSIST-001 | Cloud: seed → resolve(`edited_fields`) → restart → sqlite intact |
| CI | PR #12 — KIE Phase A `kie-contract` **SUCCESS** |

## Upgrade / migration

- First start creates tables via `CREATE TABLE IF NOT EXISTS` (no Alembic).
- Ensure process cwd is `backend/` (or set `DOCUVISION_SQLITE_DB_PATH` to an absolute path).
- After unexpected kill of a mid-flight batch, UI/API may show `paused`; call `POST /api/v1/batch/{id}/resume` to continue or finalize.
