# feat/v1.5-queue-persistence — Cloud Studio acceptance checklist

Last updated: 2026-07-31
Target tag: **`v1.5.0`** (pending — merge first, tag later)
Shell: **zsh/bash** (Tencent) / bash (Baidu)

Related: [v1.5-roadmap.md](../../docs/architecture/v1.5-roadmap.md), [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md)

**Scope delta vs v1.4**: **Queue persistence** for Batch + HITL via single-file SQLite (`backend/data/docuvision.sqlite`, two tables `batch_jobs` / `hitl_reviews`). New: `backend/app/services/persistence/queue_store.py`, `BatchService.attach_store/load_from_db/_persist`, `HitlReviewQueue.attach_store/load_from_db/_persist`, `ReviewItem.edited_fields` + `resolved_at`, `SQLITE_DB_PATH` config, `backend/data/` in `.gitignore`.

**Out of scope (v1.5)**: `tasks` dict in `main.py` is still in-memory — task *result* persistence is NOT covered. HITL-PERSIST-001 only asserts the **review item** (with `edited_fields`) survives restart; the task it refers to is gone after restart by design.

---

## Pass criteria (merge `feat/v1.5-queue-persistence` → main minimum)

| # | Phase | Pass |
|---|-------|------|
| 0 | Env | Pro `:8000` health **200** |
| 1 | Local mock tests | `pytest backend/tests/test_queue_persistence.py -q` **6 passed** (本机或 Cloud 均可，不触 paddle) |
| 2 | v1.4 regression | [MERGE_MAIN_v1.4](./MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md) §1 (Phase A v1.4 contract tests) green |
| 3 | **BATCH-PERSIST-001** | create batch → flip task → kill :8000 → restart → batch visible, `status=paused`, task `pending`, manual resume 续跑 (§3) |
| 4 | **HITL-PERSIST-001** | enqueue review → resolve with `edited_fields` → kill :8000 → restart → review visible, `status=approved`, `edited_fields` intact (§4) |
| 5 | Smoke | `GET /api/v1/batch` returns recovered batches; `GET /api/v1/hitl/reviews` returns recovered pending reviews |

---

## §0 Common variables

```bash
source test_data/scripts/lib/cloud_env.sh
init_cloud_env
# Sets: REPO_ROOT, CLOUD_PROVIDER, API_ROOT=http://127.0.0.1:8000

cd "$REPO_ROOT"
git fetch origin && git pull origin feat/v1.5-queue-persistence

cd backend && source ~/docuvision_env/bin/activate
pip install -e ../packages/docuvision-core[lite] pdfplumber pymupdf -q
```

**T1 Pro**: `DEBUG=false python run.py` (`:8000`)

Health:

```bash
curl -s -o /dev/null -w "Pro HTTP %{http_code}\n" "$API_ROOT/api/v1/health"
```

---

## §1 Local mock tests (no GPU)

```bash
cd "$REPO_ROOT/backend"
pytest tests/test_queue_persistence.py -q
```

**Pass**: **6 passed**. Covers:
- `SqliteQueueStore` round-trip (save/load/load_all/delete + upsert)
- `BatchService` restart recovery (processing→paused, task processing→pending)
- `BatchService` delete removes row from store
- `HitlReviewQueue` restart recovery (edited_fields + resolved_at intact, payload preserved)
- `HitlReviewQueue` pending preserved on restart

These do NOT import `app.main` and do NOT trigger paddle/torch.

---

## §2 v1.4 regression (Phase A contract tests)

```bash
cd "$REPO_ROOT/backend"
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py tests/test_hitl_policy.py \
  tests/test_webhook_service.py tests/test_phase1_analyze_form.py -q
```

**Pass**: all green (no regression from the `enqueue` async signature change or `resolve` signature change).

---

## §3 BATCH-PERSIST-001 — Batch survives restart

Requires Pro `:8000` running.

```bash
# 1. Create a batch (use a small PDF from testfiles)
SAMPLE="$REPO_ROOT/test_data/testfiles/GeneralFiles/bank_statement_sample.pdf"
test -f "$SAMPLE" || { echo "missing $SAMPLE"; exit 1; }

# Clean any prior DB so the test starts fresh
rm -f "$REPO_ROOT/backend/data/docuvision.sqlite"*

# (restart :8000 to start with empty store)

CREATE=$(curl -s -X POST "$API_ROOT/api/v1/batch" \
  -F "name=persist-test" \
  -F "files=@$SAMPLE" \
  -F 'options={"enable_kie":false,"enable_table":true}')
BATCH_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['batch_id'])" <<<"$CREATE")
echo "batch_id=$BATCH_ID"

# 2. Start processing, then kill the server mid-flight
curl -s -X POST "$API_ROOT/api/v1/batch/$BATCH_ID/start" >/dev/null
sleep 2   # let one task flip to processing/completed

# Kill the server (simulate crash)
pkill -f "python run.py" || true
sleep 2

# 3. Restart the server
DEBUG=false python run.py &
sleep 8   # let startup load_from_db run

# 4. Verify recovery
# NOTE: use `python3 -c` (not `python3 - <<PY`) so the pipe feeds stdin to
# json.load; heredoc would shadow the pipe and break parsing.
curl -s "$API_ROOT/api/v1/batch/$BATCH_ID" | python3 -c '
import json, sys
b = json.load(sys.stdin)
status = b["status"]
print("status =", status)
assert status == "paused", f"expected paused, got {status}"
tasks = b.get("tasks", [])
assert len(tasks) >= 1, "tasks missing"
for t in tasks:
    ts = t["status"]
    assert ts in ("pending", "completed", "skipped"), f"stuck task status {ts}"
print("BATCH-PERSIST-001 recovery pass: batch paused, tasks recoverable")
'

# 5. Manual resume should continue processing (no auto GPU resume by design).
# If all tasks already finished before the crash, resume finalizes the batch
# to completed/failed immediately (no pending tasks to run).
curl -s -X POST "$API_ROOT/api/v1/batch/$BATCH_ID/resume" >/dev/null
sleep 10
FINAL=$(curl -s "$API_ROOT/api/v1/batch/$BATCH_ID" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
echo "final status=$FINAL"
```

**Pass**:
- After restart, `GET /api/v1/batch/{id}` returns the batch with `status=paused`
- Tasks recoverable (no `processing` task stuck)
- `POST /resume` returns 200 and batch reaches `completed`/`failed`:
  - If tasks were still pending → `_process_batch` runs them and finalizes
  - If all tasks already finished before the crash → resume finalizes
    immediately (no pending tasks to run)
- `GET /api/v1/batch` (list) shows the recovered batch

**Re-verify after a fix (self-contained, no shell env vars needed)** — use this
when re-running step 4-5 in a fresh shell where `$API_ROOT`/`$BATCH_ID` are not
set; it picks the batch_id from the list endpoint:

```bash
python3 -c '
import json, urllib.request, time
API = "http://127.0.0.1:8000"
def get(p): return json.load(urllib.request.urlopen(API + p))
def post(p):
    req = urllib.request.Request(API + p, method="POST")
    return urllib.request.urlopen(req).status
batches = get("/api/v1/batch")["batches"]
assert batches, "no batches in store — run section 3 from scratch first"
bid = batches[0]["batch_id"]
print("batch_id =", bid)
b = get("/api/v1/batch/" + bid)
status = b["status"]
print("status before resume =", status)
assert status == "paused", "expected paused, got " + status
for t in b["tasks"]:
    ts = t["status"]
    assert ts in ("pending", "completed", "skipped"), "stuck task " + ts
print("BATCH-PERSIST-001 recovery pass: batch paused, tasks recoverable")
code = post("/api/v1/batch/" + bid + "/resume")
print("resume HTTP", code)
time.sleep(2)
final = get("/api/v1/batch/" + bid)["status"]
print("final status =", final)
assert final in ("completed", "failed"), "expected finalized, got " + final
print("BATCH-PERSIST-001 resume pass: finalized as", final)
'
```

---

## §4 HITL-PERSIST-001 — HITL review survives restart with edited_fields

Requires Pro `:8000` running and a document that triggers low-confidence KIE (e.g. an invoice with missing fields).

```bash
# 1. Trigger a low-confidence KIE run that enqueues a review
SAMPLE="$REPO_ROOT/test_data/testfiles/GeneralFiles/invoice_sample.pdf"
# (substitute any invoice/receipt sample that fails KIE validation)
test -f "$SAMPLE" || { echo "missing $SAMPLE; pick an invoice sample"; exit 1; }

rm -f "$REPO_ROOT/backend/data/docuvision.sqlite"*
# (restart :8000)

# Submit analyze with KIE enabled + HITL enabled
ANALYZE=$(curl -s -X POST "$API_ROOT/api/v1/analyze" \
  -F "file=@$SAMPLE" \
  -F "document_type=invoice" \
  -F "enable_kie=1" \
  -F "enable_hitl=1")
TASK_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['task_id'])" <<<"$ANALYZE")
echo "task_id=$TASK_ID"

# Poll to completion
for i in $(seq 1 60); do
  ST=$(curl -s "$API_ROOT/api/v1/tasks/$TASK_ID" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))")
  [ "$ST" = "completed" ] && break
  sleep 2
done

# 2. List pending reviews; pick the first
REVIEWS=$(curl -s "$API_ROOT/api/v1/hitl/reviews?include_payload=1")
REVIEW_ID=$(python3 -c "import json,sys; r=json.load(sys.stdin)['reviews']; print(r[0]['review_id'] if r else '')" <<<"$REVIEWS")
test -n "$REVIEW_ID" || { echo "no review enqueued — sample did not trigger HITL"; exit 1; }
echo "review_id=$REVIEW_ID"

# 3. Resolve with edited_fields (human correction)
curl -s -X POST "$API_ROOT/api/v1/hitl/reviews/$REVIEW_ID/resolve" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved","corrected_fields":{"total":"999.99","invoice_date":"2026-07-31"}}' >/dev/null

# 4. Kill and restart
pkill -f "python run.py" || true
sleep 2
DEBUG=false python run.py &
sleep 8

# 5. Verify the resolved review survived with edited_fields intact
# (resolved reviews are NOT in list_pending; query the store directly).
# Write sqlite output to a temp file, then parse with python (avoids
# heredoc-vs-pipe stdin conflict).
ROW=$(sqlite3 "$REPO_ROOT/backend/data/docuvision.sqlite" \
  "SELECT review_id, status, edited_fields, resolved_at FROM hitl_reviews WHERE review_id='$REVIEW_ID';")
echo "sqlite row: $ROW"
export ROW
python3 -c '
import json, os
line = os.environ["ROW"].strip()
assert line, "review row missing after restart — persistence failed"
parts = line.split("|")
status, edited, resolved_at = parts[1].strip(), parts[2].strip(), parts[3].strip()
assert status == "approved", f"expected approved, got {status}"
edited_json = json.loads(edited)
assert edited_json.get("total") == "999.99", edited_json
assert edited_json.get("invoice_date") == "2026-07-31", edited_json
assert resolved_at != "", "resolved_at empty"
print("HITL-PERSIST-001 pass: review + edited_fields survived restart")
'
```

**Pass**:
- After restart, the `hitl_reviews` row exists with `status=approved`
- `edited_fields` JSON contains the human-corrected values
- `resolved_at` is non-empty
- Original `payload` (validation context) is preserved separately from `edited_fields`

---

## §5 Smoke (post-restart list endpoints)

```bash
curl -s "$API_ROOT/api/v1/batch" | python3 -c "import json,sys; d=json.load(sys.stdin); print('batches:', d['total'])"
curl -s "$API_ROOT/api/v1/hitl/reviews" | python3 -c "import json,sys; d=json.load(sys.stdin); print('pending reviews:', len(d['reviews']))"
```

**Pass**: recovered batches and pending reviews appear after restart (loaded from SQLite via `load_from_db`).

---

## Notes

- **No auto GPU resume**: a `processing` batch is demoted to `paused` on restart by design (see v1.5-roadmap §Adversarial check). The user must manually `POST /resume` to continue.
- **WAL mode**: the SQLite store uses `PRAGMA journal_mode=WAL` for concurrent read/write; `-wal` and `-shm` sidecar files will appear next to `docuvision.sqlite` and are also covered by `backend/data/` in `.gitignore`.
- **`tasks` dict not persisted**: only `batch_jobs` and `hitl_reviews` rows survive restart. Single-task `/api/v1/tasks/{id}` results are lost on restart (out of scope for v1.5).
