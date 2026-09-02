# Remote 60-Minute Trial Runbook (GLM trial)

> Branch `feat/glm-trial` · Deliverables: trial hardening (P0) + diagnostic
> toolkit (P1). Local companion: `docs/demo/TRIAL_DEMO.md` (30-min, localhost).
> This runbook targets a **remote client** on a public Cloud Studio GPU server.

---

## 1. Bring-up (Cloud Studio, ~15 min before the call)

```bash
# Terminal 1 — Pro server (GPU venv, from repo root)
cd ~/DocuVision && git fetch origin && git switch feat/glm-trial
source ~/docuvision_env/bin/activate
cd backend
grep -q DOCUVISION_TRIAL_API_KEY .env || echo 'DOCUVISION_TRIAL_API_KEY=<generate-a-random-key>' >> .env
grep -q DOCUVISION_CORS_ORIGINS .env || echo 'DOCUVISION_CORS_ORIGINS=<your-frontend-origin>' >> .env
grep -q DOCUVISION_KIE_WARMUP .env || echo 'DOCUVISION_KIE_WARMUP=1' >> .env
DEBUG=false python run.py

# Terminal 2 — samples + preflight
cd ~/DocuVision
python scripts/trial/generate_trial_samples.py
cd backend && python ../scripts/trial/trial_preflight.py
```

Expose the server publicly (Cloud Studio "公网访问" / port forward :8000), then
hand the client: `https://<host>/frontend/index.html?key=<trial-key>`.

**Preflight acceptance**: `summary: 0 failure(s)` — KIE loaded, samples present,
key set, disk OK. Fix any FAIL before the call.

## 2. The 60-minute script (timeboxed)

| Slot | What happens | Assets used |
|------|--------------|-------------|
| 0–5 | Privacy promise: data stays on this server, wiped at the end (show `trial_reset.py --dry-run`) | rules/004 §运维 |
| 5–15 | Client uploads 3–5 representative PDFs; run profile pre-scan; show routing (digital vs scan) | /api/v1/document/profile |
| 15–40 | Live analysis: layout → tables (merged cells, HTML) → **figure crops + integrity warnings** → KIE fields; export JSON/Excel | figures endpoints |
| 40–55 | **Ground-truth diff**: client hand-fills 5–10 expected values; generate HTML accuracy report; symbol benchmark result walkthrough | gt-diff + symbol_bench |
| 55–60 | Verbal recommendations; wipe demo (run `trial_reset.py --yes`, restart server, show empty dirs) | trial_reset |

## 3. Acceptance criteria (Cloud Studio manual tests)

### P0-1 Trial auth
1. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/v1/engines` → **401**
2. Same with `-H "X-API-Key: <key>"` → **200**
3. Open UI with `?key=<key>` → health/tasks work; WebSocket progress events flow
4. Upload a >MAX_FILE_SIZE file → **413**
5. Wrong-key request → 401 with `{"detail": "API key required..."}`
6. (Optional) OPTIONS preflight from allowed origin → CORS headers present on 401

### P0-2 Figure crops
1. Analyze `test_data/testfiles/trial/flowchart_page.pdf` (layout on)
2. `GET /api/v1/tasks/{id}/result` → `figures.figure_count >= 1`, each item has `crop_url`
3. `GET figures.items[0].crop_url` → PNG opens, contains the diagram, not cut mid-box
4. `quality.figure_count / figure_cropped_count / figure_integrity_warning_count` present
5. Same for `architecture_diagram.pdf`; a text-only PDF → `figures` omitted or zero
6. `enable_figure_export=false` form run → no figures key
7. Path traversal: `GET .../figures/..%2F..%2Frun` → 400
8. **UI (P0-A)**: Figures tab shows cropped PNG thumbnails (not just captions);
   split-figure warnings appear as `⚠ possible split` per card + banner
9. **UI (P0-C)**: document canvas shows reading-order numbers at each region's
   top-left; tooltip includes "Reading order: N"; multi-column page numbers
   should progress column-by-column (if they jump across columns, the
   detector's reading order is wrong — state this honestly to the client)

### P0-3 Samples
1. `python scripts/trial/generate_trial_samples.py` prints 3 `[ok]` lines
2. Each PDF: 2–3 pages, ~400 KB; `multi_column_techdoc.pdf` page 1 shows two text
   columns + bordered table with merged cell + glyphs ✓ ⊗ ● ○; page 2/3 vector diagrams
3. Layout analysis detects figure regions on flowchart/architecture pages

### P1-4 GT diff
1. Complete an analysis task (any invoice sample with KIE)
2. `curl -X POST .../api/v1/trial/gt-diff/{task_id} -H 'Content-Type: application/json' -d '{"fields":{"total":"<expected>"}}'`
3. Response: `fields.summary` counts + `report_url`
4. `GET report_url` → HTML report renders; wrong values red, matches green
5. CLI path: `python -m app.services.trial.gt_diff --gt gt.json --result res.json --out r.html` prints slim JSON
6. Non-completed task → 400; unknown task → 404

### P1-5 Symbol benchmark (GPU)
1. `python scripts/trial/symbol_benchmark.py --out ../outputs/symbol_bench` (from backend/)
2. `report.json` has both engines: per-symbol hits, survival_rate, elapsed_ms
3. Expected finding: PP-OCR survival < 100% on ⊗/○ class; Qwen2.5-VL higher but slower —
   record actual numbers for the client write-up
4. `--render-only` works on CPU (grid PNG + manifest.json)

## 4. Rollback / cleanup

- Between prospects: `python ../scripts/trial/trial_reset.py --yes` (from backend/) + restart server
- Kill public exposure (Cloud Studio port forward off)
- Branch rollback: `git switch main` (feature branch untouched)

## 5. Known limits to state honestly in the trial

- Split-figure warnings are geometric heuristics (adjacency/nesting), not semantic "same figure" proofs.
- GT diff aligns cells by (row, col); merged cells or column drift need manual mapping.
- Symbol benchmark numbers are environment-specific (font, model build) — always report the env.
- KIE routes by document_type; technical drawings get layout/tables, not KIE fields.
