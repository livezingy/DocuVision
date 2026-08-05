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
| 3 | **BATCH-PERSIST-001** | create batch → kill :8000 → restart → batch visible; `status!=processing`; path A `paused`+resume 或 path B 已 `completed`/`failed` (§3) |
| 4 | **HITL-PERSIST-001** | seed pending→load_from_db→resolve(`edited_fields`)→kill→restart→sqlite `approved` + `edited_fields`/`resolved_at` intact（§4；不依赖 KIE 入队） |
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

CREATE=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/batch" \
  -F "name=persist-test" \
  -F "files=@$SAMPLE" \
  -F 'options={"enable_kie":false,"enable_table":true}')
BATCH_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['batch_id'])" <<<"$CREATE")
echo "$BATCH_ID" > /tmp/batch_id.txt
echo "batch_id=$BATCH_ID  (saved to /tmp/batch_id.txt)"

# 2. Start processing, then kill the server mid-flight
curl -s -X POST "http://127.0.0.1:8000/api/v1/batch/$BATCH_ID/start" >/dev/null
sleep 2   # let one task flip to processing/completed
# NOTE: small PDFs may finish entirely within 2s -> path B (completed after restart).
# That still passes BATCH-PERSIST-001. Path A (paused) needs a longer job or earlier kill.

# Kill the server (simulate crash)
pkill -f "python run.py" || true
sleep 2

# 3. Restart the server
DEBUG=false python run.py &
sleep 8   # let startup load_from_db run

# 4+5. Verify recovery (self-contained; reads /tmp/batch_id.txt from step 1).
# Two valid outcomes after restart:
#   A) status=paused  -> kill mid-flight; resume must finalize
#   B) status=completed/failed/cancelled -> batch finished before kill; resume N/A
# status=processing after restart is a FAIL (load_from_db demotion broken).
python3 -c '
import json, urllib.request, time
API = "http://127.0.0.1:8000"
def get(p): return json.load(urllib.request.urlopen(API + p))
def post(p):
    req = urllib.request.Request(API + p, method="POST")
    return urllib.request.urlopen(req).status
bid = open("/tmp/batch_id.txt").read().strip()
print("batch_id =", bid)
b = get("/api/v1/batch/" + bid)
status = b["status"]
print("status after restart =", status)
assert status != "processing", "processing after restart: load_from_db demotion failed"
for t in b["tasks"]:
    ts = t["status"]
    assert ts != "processing", "stuck task " + ts
print("BATCH-PERSIST-001 recovery pass: batch visible, status=" + status)
if status == "paused":
    code = post("/api/v1/batch/" + bid + "/resume")
    print("resume HTTP", code)
    time.sleep(2)
    final = get("/api/v1/batch/" + bid)["status"]
    print("final status =", final)
    assert final in ("completed", "failed"), "expected finalized, got " + final
    print("BATCH-PERSIST-001 resume pass: finalized as", final)
elif status in ("completed", "failed", "cancelled"):
    print("BATCH-PERSIST-001 resume pass: already finalized before kill (resume N/A)")
else:
    raise AssertionError("unexpected status " + status)
'
```

**Pass** (either path A or B):
- After restart, `GET /api/v1/batch/{id}` returns the same batch (not 404)
- `status` is **not** `processing` (mid-flight batches demote to `paused`)
- Tasks have no stuck `processing` status
- Path A (`paused`): `POST /resume` → `completed`/`failed`
- Path B (`completed`/`failed`/`cancelled`): already finalized before kill — persistence still passes
- `GET /api/v1/batch` (list) shows the recovered batch

---

## §4 HITL-PERSIST-001 — HITL review survives restart with edited_fields

Self-contained: hardcoded API/DB paths, `/tmp/review_id.txt`. Do **not** `rm` the SQLite DB.

**Why not analyze→KIE?** HITL enqueue only when `validation_passed=False`. Good invoice
samples often pass date/currency checks (or extract empty fields → `failed==0` → also
"passed"), so Cloud GPU analyze is unreliable for this acceptance. Seed a pending
`hitl_reviews` row, then exercise **resolve + restart persistence** (the v1.5 contract).

### Step A0 — stop run.py (terminal 1)

```bash
# Ctrl+C  if run.py is running
```

### Step A1 — seed pending review into SQLite (terminal 2, server STOPPED)

```bash
cd /workspace/DocuVision
python3 -c '
import json, sqlite3, uuid
from datetime import datetime
from pathlib import Path

DB = Path("/workspace/DocuVision/backend/data/docuvision.sqlite")
DB.parent.mkdir(parents=True, exist_ok=True)
rid = str(uuid.uuid4())
open("/tmp/review_id.txt", "w").write(rid)
payload = json.dumps({
    "validation": {"validation_passed": False, "validation_fields_failed": 1},
    "fields": {"total": "100"},
    "hitl_profile": "full",
})
conn = sqlite3.connect(str(DB))
conn.execute(
    "CREATE TABLE IF NOT EXISTS hitl_reviews ("
    "review_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, file_name TEXT NOT NULL, "
    "reason TEXT NOT NULL, payload TEXT NOT NULL DEFAULT \"{}\", "
    "edited_fields TEXT, status TEXT NOT NULL DEFAULT \"pending\", "
    "created_at TEXT NOT NULL, resolved_at TEXT)"
)
conn.execute(
    "INSERT OR REPLACE INTO hitl_reviews "
    "(review_id, task_id, file_name, reason, payload, edited_fields, status, created_at, resolved_at) "
    "VALUES (?, ?, ?, ?, ?, NULL, \"pending\", ?, NULL)",
    (rid, "seed-task-hitl-persist", "seed-invoice.pdf", "kie_validation_failed",
     payload, datetime.now().isoformat()),
)
conn.commit()
conn.close()
print("seeded review_id =", rid)
print("HITL-PERSIST-001 Step A1 done — start run.py in terminal 1, then Step A2")
'
```

### Step A2 — start run.py then resolve (terminal 1 start, then terminal 2)

Terminal 1:

```bash
cd /workspace/DocuVision/backend
source ~/docuvision_env/bin/activate
DEBUG=false python run.py
# Wait for: HitlReviewQueue loaded N review(s) from store  (N >= 1)
```

Terminal 2 (after load log):

```bash
python3 -c '
import json, urllib.request

API = "http://127.0.0.1:8000"
rid = open("/tmp/review_id.txt").read().strip()
print("review_id =", rid)

reviews = json.load(urllib.request.urlopen(API + "/api/v1/hitl/reviews?include_payload=1", timeout=30))
ids = [r["review_id"] for r in (reviews.get("reviews") or [])]
assert rid in ids, "seeded review not in list_pending after load_from_db; ids=" + str(ids)
print("pending list contains seeded review")

payload = json.dumps({
    "status": "approved",
    "corrected_fields": {"total": "999.99", "invoice_date": "2026-07-31"},
}).encode()
req = urllib.request.Request(
    API + "/api/v1/hitl/reviews/" + rid + "/resolve",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
out = json.load(urllib.request.urlopen(req, timeout=30))
print("resolve =", out)
assert out.get("status") == "approved"
print("HITL-PERSIST-001 Step A2 done — kill run.py in terminal 1, restart, then Step C")
'
```

### Step B — kill + restart again (terminal 1)

```bash
# Ctrl+C, then:
DEBUG=false python run.py
# Wait for: HitlReviewQueue loaded N review(s) from store
```

### Step C — verify after second restart (terminal 2)

```bash
python3 -c '
import json, sqlite3
from pathlib import Path

DB = Path("/workspace/DocuVision/backend/data/docuvision.sqlite")
rid = open("/tmp/review_id.txt").read().strip()
print("review_id =", rid)
assert DB.is_file(), "sqlite missing: " + str(DB)
conn = sqlite3.connect(str(DB))
row = conn.execute(
    "SELECT review_id, status, edited_fields, resolved_at, payload FROM hitl_reviews WHERE review_id=?",
    (rid,),
).fetchone()
conn.close()
assert row, "review row missing after restart — persistence failed"
_rid, status, edited, resolved_at, payload = row
print("status =", status)
print("edited_fields =", edited)
print("resolved_at =", resolved_at)
assert status == "approved", "expected approved, got " + str(status)
edited_json = json.loads(edited) if edited else {}
assert edited_json.get("total") == "999.99", edited_json
assert edited_json.get("invoice_date") == "2026-07-31", edited_json
assert resolved_at, "resolved_at empty"
payload_json = json.loads(payload) if payload else {}
assert ("validation" in payload_json) or ("fields" in payload_json), payload_json
print("HITL-PERSIST-001 PASS: review + edited_fields survived restart, payload preserved")
'
```

**Pass**:
- After Step A2 restart/load, seeded review appears in `GET /api/v1/hitl/reviews`
- `POST .../resolve` with `corrected_fields` returns `approved`
- After Step B restart, sqlite row has `status=approved`, `edited_fields` intact, `resolved_at` set, original `payload` preserved

---

## §5 Smoke (post-restart list endpoints)

```bash
python3 -c '
import json, urllib.request
API = "http://127.0.0.1:8000"
d = json.load(urllib.request.urlopen(API + "/api/v1/batch"))
print("batches:", d.get("total"))
d = json.load(urllib.request.urlopen(API + "/api/v1/hitl/reviews"))
print("pending reviews:", len(d.get("reviews") or []))
'
```

**Pass**: recovered batches appear; pending reviews list loads (resolved items are not pending — that is expected).

---

## Notes

- **No auto GPU resume**: a `processing` batch is demoted to `paused` on restart by design (see v1.5-roadmap §Adversarial check). The user must manually `POST /resume` to continue.
- **WAL mode**: the SQLite store uses `PRAGMA journal_mode=WAL` for concurrent read/write; `-wal` and `-shm` sidecar files will appear next to `docuvision.sqlite` and are also covered by `backend/data/` in `.gitignore`.
- **`tasks` dict not persisted**: only `batch_jobs` and `hitl_reviews` rows survive restart. Single-task `/api/v1/tasks/{id}` results are lost on restart (out of scope for v1.5).
