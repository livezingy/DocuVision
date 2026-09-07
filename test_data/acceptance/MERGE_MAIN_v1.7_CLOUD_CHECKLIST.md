# feature/v1.7 — Cloud Studio acceptance checklist

Last updated: 2026-09-06
Target tag: **`v1.7.0`** (pending — wait for Cloud **TASK-PERSIST-001**)
Shell: **zsh/bash** (Tencent) / bash (Baidu)

Related: [v1.7-roadmap.md](../../docs/architecture/v1.7-roadmap.md), [MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md)

**Scope delta vs v1.6**: version identity `APP_VERSION=1.7.0`; Pro single-task result persistence (`analyze_jobs` + `OUTPUT_DIR/{task_id}/result.json`). ZIP / figure contracts unchanged.

**Out of scope (v1.7)**: Lite ZIP, Batch ZIP, Searchable PDF, Recent-tasks UI, Redis, auto-resume of in-flight GPU jobs.

---

## Pass criteria (merge `feature/v1.7` → main minimum)

| # | Phase | Pass |
|---|-------|------|
| 0 | Env | Pro `:8000` health **200**; `api_version` **1.7.0** |
| 1 | Local mock | `pytest backend/tests/test_task_persistence.py tests/test_queue_persistence.py -q` **all passed** (本机或 Cloud，不触 paddle) |
| 2 | v1.6 regression | [MERGE_MAIN_v1.6](./MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md) **PACK-ZIP-001** still green if pack files are touched |
| 3 | **TASK-PERSIST-001** | analyze completes → kill `:8000` → start again → same `task_id` serves result + ZIP (`PK`) + at least one figure GET **200** |

---

## §0 Common variables

```bash
source test_data/scripts/lib/cloud_env.sh
init_cloud_env
# Sets: REPO_ROOT, CLOUD_PROVIDER, API_ROOT=http://127.0.0.1:8000

cd "$REPO_ROOT"
git fetch origin && git pull origin feature/v1.7

cd backend && source ~/docuvision_env/bin/activate
pip install -e ../packages/docuvision-core[lite] pdfplumber pymupdf -q
```

## §1 Local persist tests

```bash
cd "$REPO_ROOT/backend"
pytest tests/test_task_persistence.py tests/test_queue_persistence.py -q
```

## §3 TASK-PERSIST-001

Run a Pro analyze with `enable_layout=true` and `enable_figure_export=true` on a document that has at least one table and one figure. Record `TASK_ID`. Confirm result + ZIP + one figure **before** restart, then:

```bash
test -n "$TASK_ID" || { echo "set TASK_ID first"; exit 1; }
FIG_ID="${FIG_ID:-p1_e3}"

# Restart backend (stop the existing python run.py, then start again)
# cd "$REPO_ROOT/backend" && DEBUG=false python run.py

curl -fsS "$API_ROOT/api/v1/tasks/$TASK_ID" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status') in ('completed','succeeded'), d; print('task', d.get('status'))"
curl -fsS -o /tmp/persist_result.json "$API_ROOT/api/v1/tasks/$TASK_ID/result"
python3 -c "import json; d=json.load(open('/tmp/persist_result.json')); assert d.get('tables') or d.get('figures'); print('result ok')"
curl -fsS -o /tmp/persist_pack.zip "$API_ROOT/api/v1/tasks/$TASK_ID/export/zip"
python3 - <<'PY'
import zipfile
p = "/tmp/persist_pack.zip"
with open(p, "rb") as f:
    magic = f.read(2)
assert magic == b"PK", magic
with zipfile.ZipFile(p) as z:
    names = z.namelist()
assert "manifest.json" in names
assert any(n.startswith("tables/") for n in names)
assert any(n.startswith("figures/") for n in names)
print("zip ok")
PY
curl -fsS -o /tmp/persist_fig.png "$API_ROOT/api/v1/tasks/$TASK_ID/figures/$FIG_ID"
python3 - <<'PY'
p = open("/tmp/persist_fig.png", "rb").read()
assert p[:4] == bytes([0x89]) + b"PNG", p[:8]
print("figure ok")
PY
```

**通过**：重启后同一 `TASK_ID` HTTP **200**；result 非空；ZIP 头 `PK` 且含 `manifest.json` + `tables/` + `figures/`；至少一张 figure PNG 头合法。

If the first figure id is not `p1_e3`, set `FIG_ID` from `GET /api/v1/tasks/$TASK_ID/figures` before the crop GET.
