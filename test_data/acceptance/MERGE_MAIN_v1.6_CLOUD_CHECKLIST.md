# feature/v1.6-artifact-pack — Cloud Studio acceptance checklist

Last updated: 2026-09-06
Target tag: **`v1.6.0`** (cut 2026-09-06 — Cloud **PACK-ZIP-001** passed)
Shell: **zsh/bash** (Tencent) / bash (Baidu)

Related: [v1.6-roadmap.md](../../docs/architecture/v1.6-roadmap.md), [RELEASE_1.6_NOTES.md](../../docs/release/RELEASE_1.6_NOTES.md), [MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md](./MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md)

**Scope delta vs v1.5**: version identity `APP_VERSION=1.6.0`; Pro single-task **artifact pack** (`export/zip` + sidebar ZIP). Figure/layout baseline is already on the train and is a prerequisite, not re-gated here.

**Out of scope (v1.6)**: Lite ZIP, Batch ZIP, table-region screenshots, formula/seal image export.

---

## Pass criteria (merge `feature/v1.6-artifact-pack` → main minimum)

| # | Phase | Pass |
|---|-------|------|
| 0 | Env | Pro `:8000` health **200**; `api_version` **1.6.0** |
| 1 | Local mock | `pytest backend/tests/test_pack_export_service.py -q` **all passed** (本机或 Cloud，不触 paddle) |
| 2 | v1.5 regression | [MERGE_MAIN_v1.5](./MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md) §1 local mock still green if those files are touched |
| 3 | **PACK-ZIP-001** | completed analyze with layout + figures → `GET /api/v1/tasks/{id}/export/zip` HTTP **200**, file header `PK`, namelist contains `manifest.json` + `tables/` + `figures/` |
| 4 | UI (optional) | Analysis right-panel **ZIP** button triggers a browser download (`*_pack.zip`) |

Gate **passed** 2026-09-06 (operator confirmed Cloud **PACK-ZIP-001**). Local mock: `test_pack_export_service.py` 11 passed.

---

## §0 Common variables

```bash
source test_data/scripts/lib/cloud_env.sh
init_cloud_env
# Sets: REPO_ROOT, CLOUD_PROVIDER, API_ROOT=http://127.0.0.1:8000

cd "$REPO_ROOT"
git fetch origin && git pull origin feature/v1.6-artifact-pack

cd backend && source ~/docuvision_env/bin/activate
pip install -e ../packages/docuvision-core[lite] pdfplumber pymupdf -q
```

## §1 Local pack tests (after ZIP lands)

```bash
cd "$REPO_ROOT/backend"
pytest tests/test_pack_export_service.py -q
```

## §3 PACK-ZIP-001 (after ZIP lands)

Run a Pro analyze with `enable_layout=true` and `enable_figure_export=true` on a document that has at least one table and one figure. Then:

```bash
test -n "$TASK_ID" || { echo "set TASK_ID first"; exit 1; }
curl -fsS -o /tmp/pack.zip "$API_ROOT/api/v1/tasks/$TASK_ID/export/zip"
python3 - <<'PY'
import zipfile, sys
p = "/tmp/pack.zip"
with open(p, "rb") as f:
    magic = f.read(2)
assert magic == b"PK", magic
with zipfile.ZipFile(p) as z:
    names = z.namelist()
print("entries", len(names))
assert "manifest.json" in names
assert any(n.startswith("tables/") for n in names)
assert any(n.startswith("figures/") for n in names)
print("zip ok")
PY
```

**通过**：HTTP **200**；`PK`；python 打印 `zip ok`。
