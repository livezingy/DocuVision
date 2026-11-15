# n8n Integration Templates

Source: R-004 / P-043 T1 + T5 (docs/R&D/runs/R-004/pack.md §1/§2/§5). Technical reference only — no claims beyond what is cited below.

## 1. Directory index (reconciliation rows)

| File | Purpose (one line) |
|------|--------------------|
| [docuvision-v1-generic.json](docuvision-v1-generic.json) | n8n workflow template, 3 flows: intake (upload/analyze) → `task.completed` callback → result fetch, plus a one-off webhook registration flow. Zero credentials, zero hardcoded URLs (all endpoints via `$env` expressions). |
| [docuvision-v1.1-outlook.json](docuvision-v1.1-outlook.json) | v1.1 Outlook watch template (T5, 定稿点 4): Outlook inbox trigger → PO-mail filter → attachment intake (upload + analyze) → `task.completed` callback → result fetch → per-field CSV written to an n8n-side watch dir. Same load discipline as v1 (see §7). |

DOC gate coverage (review P2-6): `docs/integrations/**` is outside the docs_refs_audit scan domains (measured 2026-11-15; new `*.md` = 0 error by default), so coverage is this directory index table plus the index row in `docs/README.md` → `## Integrations` → `[integrations/n8n/README.md]` (already mounted; `docs/README.md` is tombstone-scanned and token-free here).

## 2. Import

1. Open n8n → Workflows → **Import from File** → select one of the two JSON files above. A complete import needs `name` + `nodes` + `connections` (all present in both files).
2. Flow C (`Manual Trigger (one-off registration)`) is not auto-run on import; run it once per environment after §3 is done.
3. Outlook template only: create the mailbox credential in n8n **Credentials** (Outlook OAuth2 / Microsoft Graph — Azure AD app registration is a Ying prerequisite, pack.md §5.2). The template JSON carries no credential values.
4. Set the n8n-side environment variables (§4), then activate the workflow so the Webhook node gets a production URL.

Parameter shapes checked against n8n source `master` (2026-11): `httpRequest` typeVersion 4.2, `webhook` 2.2 (n8n default, `Webhook.node.ts:61-62`), `if` 2.2, `set` 3.4, `convertToFile` 1.1, `code` 2, `microsoftOutlookTrigger` 1. Import on an instance close to the current n8n release.

## 3. Closed-loop prerequisites (three items, pack.md §5.0 — all required)

1. **Backend enable**: backend `.env` gets `WEBHOOK_ENABLED=true` (default `false`, alias `DOCUVISION_WEBHOOK_ENABLED` — backend/app/core/config.py:102-105). When false, dispatch silently returns `[]` (backend/app/services/webhook_service.py:129-130) — the loop degrades to a silent no-op (P-027 precedent).
2. **Non-empty admin token**: backend `.env` gets a generated `WEBHOOK_ADMIN_TOKEN` (alias `DOCUVISION_WEBHOOK_ADMIN_TOKEN` — backend/app/core/config.py:106-109). Empty token fail-closes registration with 401 (backend/app/routers/webhooks.py:24-46, raise at :45). Generate-per-run; do not commit or log.
3. **Subscribe once** — copy-paste shape (token/URLs referenced as shell environment variables, never inline values; `Form(url, events, secret)` per backend/app/routers/webhooks.py:57-77, urlencoded accepted by FastAPI `Form`):

   ```bash
   curl -X POST "${DOCUVISION_BASE_URL}/api/v1/webhooks" \
     -H "X-DocuVision-Admin-Token: ${DOCUVISION_WEBHOOK_ADMIN_TOKEN}" \
     --data-urlencode "url=${DOCUVISION_CALLBACK_URL}" \
     --data-urlencode "events=task.completed" \
     --data-urlencode "secret=${DOCUVISION_WEBHOOK_SECRET}"
   ```

   - expect `200` → `{"subscription_id":"…","url":"…","events":["task.completed"]}` (handler return, webhooks.py:73-77)
   - `401` = token missing/wrong, or backend token empty (fail-closed, webhooks.py:24-46)
   - `400` = callback URL resolves to loopback/private network (SSRF gate, webhooks.py:71-72 → webhook_service.py:21-30, 89-90) — see Known issues: a same-host `localhost` n8n URL is rejected by the current gate

n8n docker bring-up (`docker run -it --rm -p 5678:5678 …`) stays a manual AgentE step per pack.md §5.1; the Outlook live test additionally needs the Azure AD app (§5.2).

## 4. n8n instance environment variables (set on the n8n instance, never in the file)

| Expression | Meaning |
|------------|---------|
| `$env.DOCUVISION_BASE_URL` | DocuVision backend root URL, e.g. scheme://host:port (no path) |
| `$env.DOCUVISION_SAMPLE_FILE_PATH` | Path readable by the n8n process (mounted volume); glob supported (v1 generic only) |
| `$env.DOCUVISION_PO_SUBJECT_KEYWORD` | Subject substring that qualifies a mail as PO (v1.1 outlook; falls back to literal `PO`) |
| `$env.DOCUVISION_PO_DOCUMENT_TYPE` | `document_type` Form value sent to `/api/v1/analyze` (v1.1 outlook; falls back to `auto`) |
| `$env.DOCUVISION_WATCH_DIR` | n8n-side watch directory (mounted volume) where per-task CSVs are written (v1.1 outlook) |
| `$env.DOCUVISION_CALLBACK_URL` | Full callback URL of the Flow B webhook node = `{n8n WEBHOOK_URL}/<webhook path>`; must be non-loopback from the DocuVision host (SSRF gate, §8) |
| `$env.DOCUVISION_WEBHOOK_ADMIN_TOKEN` | Same value as backend `WEBHOOK_ADMIN_TOKEN`; generate-per-run, do not commit or log (pack.md §5.0) |
| `$env.DOCUVISION_WEBHOOK_SECRET` | Optional; HMAC secret for `X-DocuVision-Signature` verification on the DocuVision side |

Self-hosted n8n allows `$env` in expressions unless `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`; on plans with the Variables feature, `$vars.*` is an equivalent substitute.

## 5. Field reconciliation tables (template field → source of truth)

### 5.1 v1 generic (T1)

| Template field | Source of truth | Evidence |
|----------------|-----------------|----------|
| `POST /api/v1/upload`, multipart `file` required | OpenAPI snapshot | backend/tests/snapshots/openapi_baseline.json → paths./api/v1/upload + components.schemas.Body_upload_file_api_v1_upload_post.required=["file"] (paths=49, measured 2026-11-15) |
| upload response `task_id`/`file_name`/`status:"uploaded"`/`message`/`page_count` | Router handler (no response_model in snapshot; 200 schema `{}`) | backend/app/routers/analyzer.py:114-120 |
| upload `task_id` is preview-only, not an analyze input | Docstring "only uploads the file without processing, allowing immediate preview"; analyze creates a new task_id from its own file | backend/app/routers/analyzer.py:88, 207-210 |
| `POST /api/v1/analyze`, multipart `file` + optional Form fields with defaults | OpenAPI snapshot + handler signature | backend/tests/snapshots/openapi_baseline.json → Body_analyze_document_api_v1_analyze_post; backend/app/routers/analyzer.py:140-174 |
| analyze response = TaskStatus (required `task_id`/`status`/`progress`/`message`/`created_at`) | OpenAPI snapshot response_model | backend/tests/snapshots/openapi_baseline.json → components.schemas.TaskStatus.required |
| Boolean Form fields accept `"1"`/`"0"`, not `"true"`/`"false"` | In-code comment | backend/app/routers/analyzer.py:181-182 |
| Callback body `{event, payload, timestamp}` | Dispatch body construction | backend/app/services/webhook_service.py:138 |
| `payload.task_id` / `file_name` / `status` / `validation_passed` | Dispatch payload | backend/app/orchestration/steps/governance.py:120-127 |
| `status` is always `"completed"` in this callback | finalize_step | backend/app/orchestration/steps/governance.py:85 |
| `validation_passed` = `(result.get("kie_validation") or {}).get("validation_passed")`; null when KIE off | finalize_step | backend/app/orchestration/steps/governance.py:126 |
| Event set is exactly `task.completed` + `batch.completed` | dataclass default + register fallback | backend/app/services/webhook_service.py:73, 94 |
| Dispatch only on the completed path; exceptions logged at debug and swallowed | finalize_step | backend/app/orchestration/steps/governance.py:117-131 |
| `X-DocuVision-Signature` = HMAC-SHA256(secret, raw body), hex | dispatch loop | backend/app/services/webhook_service.py:146-147 (body bytes serialized with `json.dumps(..., ensure_ascii=True)`, webhook_service.py:139) |
| Dispatch timeout/retries: 15s, max_retries=2, backoff 0.5*(n+1)s | dispatch loop | backend/app/services/webhook_service.py:142, 151-161 |
| Registration: Form `url` required, `events` default `"task.completed,batch.completed"`, `secret` default `""`; 200 → `{subscription_id, url, events}` | OpenAPI snapshot + handler | backend/tests/snapshots/openapi_baseline.json → Body_register_webhook_api_v1_webhooks_post; backend/app/routers/webhooks.py:57-77 (Form :60-62, return :73-77) |
| Registration gates: WEBHOOK_ENABLED + `X-DocuVision-Admin-Token` | Router guards | backend/app/routers/webhooks.py:18, 24-46 (guards), 64-65 (calls) |
| Registration rejects loopback/private URLs with 400 | SSRF gate | backend/app/services/webhook_service.py:21-30, 89-90; backend/app/routers/webhooks.py:71-72 |
| Result fetch `GET /api/v1/tasks/{task_id}/result`: 404 unknown task, 400 "Task not completed" unless status in `("succeeded","completed")`, 200 → `task["result"]` | Router | backend/app/routers/tasks_content.py:30-37 |
| Result body keys (untyped in snapshot: 200 schema `{}`): `document_info.pages`, `view` (fields/formulas/seals), `quality`, `preprocessing` merged from envelope | finalize_step assembly | backend/app/orchestration/steps/governance.py:89-109 |
| Status polling fallback `GET /api/v1/tasks/{task_id}` (TaskStatus) | Router | backend/app/routers/tasks.py:31-37 |

### 5.2 v1.1 Outlook (T5)

| Template element | Source of truth | Evidence |
|------------------|-----------------|----------|
| Trigger type `n8n-nodes-base.microsoftOutlookTrigger` typeVersion 1, event default `messageReceived` | n8n source | MicrosoftOutlookTrigger.node.ts:21 (`version: 1`), :122-129 (Trigger On / default) |
| Graph query selects `subject` (used by the PO filter) | n8n source | trigger/GenericFunctions.ts:72-73 (field list `id,conversationId,subject,bodyPreview,from,...`) |
| `options.downloadAttachments` → binary fields `attachment_0`, `attachment_1`, ... | n8n source | trigger/MessageDescription.ts:124-136 (attachmentsPrefix description: index appended, `attachment_` → `attachment_0`); poll path trigger/GenericFunctions.ts:193-203 |
| Attachment binary field name resolved by expression (first binary field) | n8n httpRequest source | HttpRequest/V3/Description.ts:603-607 (`inputDataFieldName` accepts an expression) |
| `Is PO mail?` — IF contains on `$json.subject`, keyword via `$env.DOCUVISION_PO_SUBJECT_KEYWORD` (fallback literal `PO`) | trigger output + IF node | subject per trigger/GenericFunctions.ts:72-73; operator `contains` per IF v2 conditions schema (IfV2.node.ts:55-56) |
| Intake posts the SAME attachment to `/api/v1/upload` and `/api/v1/analyze` in parallel | pack.md T1 intake chain (A4); T5 lists only "附件 POST upload" but upload never processes | backend/app/routers/analyzer.py:88 (upload docstring: no processing), :207-210 (analyze creates its own task_id); `task.completed` fires only from the analyze finalize step, backend/app/orchestration/steps/governance.py:117-128 |
| `document_type` = `$env.DOCUVISION_PO_DOCUMENT_TYPE || 'auto'` | analyze Form default | backend/app/routers/analyzer.py:150 (`document_type: str = Form("auto")`) |
| Callback payload mapping (task_id/file_name/status/validation_passed) | dispatch payload | backend/app/orchestration/steps/governance.py:120-127 |
| `view.fields` is a dict: name → scalar (empty backfilled `""`) or list (`items`/`line_items`/`findings`) | envelope assembly + kie field merge | backend/app/orchestration/steps/envelope.py:151,153 (`view["fields"] = kie_fields`), :218 (dict assumption); backend/app/services/kie/field_merge.py:60+ (`backfill_schema_keys`: scalar keys backfilled with `""`, list keys untouched) |
| CSV rows: one per field; list/object values JSON-stringified; absent `view.fields` → single `__no_kie_fields__` marker row (no invented values) | template Code node (behavior stated, not fabricated) | code in docuvision-v1.1-outlook.json node "Extract KIE Fields to Rows" |
| `Convert to CSV` — operation `csv` (node default), top-level `fileName`, output binary property `data` | n8n source | Files/ConvertToFile/ConvertToFile.node.ts:22 (`version: [1, 1.1, 1.2]`), :44-49 (csv default), actions/spreadsheet.operation.ts (params: `binaryPropertyName`, `fileName` top-level, `options.delimiter` default `,`) |
| Watch-dir write: n8n-side path `$env.DOCUVISION_WATCH_DIR/<task_id>.csv` | readWriteFile write op | Files/ReadWriteFile/actions/write.operation.ts:28 (`fileName`, resolved via helpers), :38 (`dataPropertyName`) |

## 6. Backend half-loop smoke (`scripts/integrations/n8n_loop_smoke.py`)

Scope: proves the backend half of the loop (webhook dispatch + result endpoint) without n8n — per pack.md §4 this complements, not replaces, the AgentE n8n docker test (AC1, manual).

Command shape (token read from the environment, never passed inline):

```bash
export DOCUVISION_WEBHOOK_ADMIN_TOKEN='<generated-per-run>'
python scripts/integrations/n8n_loop_smoke.py --base-url http://localhost:8000 \
  --file test_data/testfiles/invoices/invoice_sample_01.pdf
```

- Requires the backend running with §3 items 1–2 applied (`WEBHOOK_ENABLED=true`, non-empty `WEBHOOK_ADMIN_TOKEN`) — started by Ying per pack.md §4/§5.
- `--file` example above uses `test_data/testfiles/invoices/invoice_sample_01.pdf` (verified present in the repo 2026-11-15); the illustrative `sample-invoice.png` also exists in the same directory (tracked since ae3852a) — either file works with the smoke script; an earlier draft wrongly claimed it missing (corrected 2026-11-16).
- **Script status declaration**: `scripts/integrations/` did not exist at the time of this README's writing (measured `ls` 2026-11-15). The command shape above is the agreed contract; once the script lands, its actual `--help` / flags are authoritative and this section should be re-verified. Not executed in this task — no pass/fail claim is made here.
- The smoke's own callback receiver must satisfy the SSRF gate (non-loopback/private address, webhook_service.py:21-30, 89-90); on a single host with no such address the dispatch self-check cannot pass without a backend-side bypass change, which is out of scope for T1/T5 (see Known issues).

## 7. Payload & trust boundary (both templates)

**Callback payloads are narrow and fixed:**

- `task.completed` body = `{event, payload, timestamp}` (webhook_service.py:138); `payload` = exactly `task_id` / `file_name` / `status` / `validation_passed` (governance.py:120-127); `status` is always `"completed"` (governance.py:85). `validation_passed` is `(result.get("kie_validation") or {}).get("validation_passed")` — `null` when KIE is off (governance.py:126).
- `batch.completed` payload = `{batch_id, name, status, completed_tasks, failed_tasks}` (batch_runner.py:26+, payload at :43-51; dispatch batch.py:77-92).
- Only these two events are dispatched (webhook_service.py:73, 94). There is **no failure callback** — `failed`/`cancelled` statuses (document_pipeline_orchestrator.py:127, tasks.py:160/203) must be obtained by polling `GET /api/v1/tasks/{task_id}` (tasks.py:31-37).
- Templates treat any field beyond the lists above as out of contract: nothing else is read from the callback body.

**No paths cross the trust boundary in either direction:**

- Templates send no absolute path to the backend and read no path back out of the backend. The backend `task` record contains internal fields (`file_path`, `upload_dir`) that are **not** part of the callback payload or the result contract; the templates do not consume them.
- `per_order_output_dir` load discipline (R-003/P-042 hardening): the string appears in the template JSONs only inside comments; no request parameter carries it. The template JSONs never call the batch API.

**Batch trust boundary (for deployments that extend the flow to `POST /api/v1/batch`):**

| Field | Behavior at the backend | Evidence |
|-------|------------------------|----------|
| `per_order_output_dir` omitted or empty (with `options.per_order=true`) | Backend default `<settings.OUTPUT_DIR>/per_order/<batch_id>` | backend/app/services/per_order_export_service.py:53-54; opt-in gate backend/app/routers/batch.py:163; dispatch backend/app/routers/batch.py:138-174 |
| `per_order_output_dir` escapes OUTPUT_DIR (`..` traversal, other drive) | `ValueError` at batch creation → **HTTP 422** | backend/app/routers/batch.py:185-204 (raise at :204); ValueError raise backend/app/services/per_order_export_service.py:64-66; confinement docstring names the n8n watch-dir use case (per_order_export_service.py:39-42) |
| `GET /api/v1/batch/{batch_id}/export.csv` | query `mode` ∈ {kie, summary, failures} default `kie`, `validation_passed_only` bool; `text/csv` + `Content-Disposition` `batch_<id>_<mode>.csv` | backend/app/routers/batch_export.py:44-66 |

The n8n-side `$env.DOCUVISION_WATCH_DIR` written by the Outlook Flow B is a **separate output** from the backend per-order dir: they coincide only if the operator mounts the same volume and maps paths deliberately. The backend never receives nor returns the n8n watch path.

**HMAC verification:** `X-DocuVision-Signature` = HMAC-SHA256(secret, raw body) hex (webhook_service.py:146-147, body serialized `json.dumps(..., ensure_ascii=True)` :139). Byte-exact verification in n8n is possible without a fronting proxy: enable the Webhook node's `options.rawBody` (n8n source Webhook.node.ts:338-356 — the output item then carries `binary.data` = base64 of the raw request body), and a Code node can base64-decode it and compute HMAC-SHA256 over the exact bytes Python signed. The templates ship without the verify node (`rawBody` off by default); turn it on when you need strict verification.

## 8. Known issues / constraints (verified against source, not fixed by the templates)

- **SSRF gate vs same-host n8n**: the gate in webhook_service.py:21-30/89-90 rejects loopback/private targets unconditionally, so registering an n8n URL on `localhost`/`127.0.0.1` returns 400. The pack.md §5 step "localhost:5678 回调直达" does not work against the current gate; the callback URL must be a non-loopback address reachable from the DocuVision host (container name, host IP, or a reverse proxy). Changing the gate is out of scope for T1/T5.
- **Failure has no callback**: see §7; poll instead.
- **Boolean Form fields**: if you add analyze options in n8n, send `"1"`/`"0"` (analyzer.py:181-182); `"true"`/`"false"` trigger 422.
- **OpenAPI path count drift**: baseline measured at 49 paths; pack.md A3 cites the review-01 erratum "51" and itself flags re-verification on execution day. Not reconciled by these templates.

## 9. Not run / not verified here (declared, per pack.md §4 test matrix)

- n8n instance import + end-to-end closed loop (AC1): owned by AgentE (n8n docker + backend on the same host per pack.md §4); not executed by this task.
- **Outlook Trigger live test (T5)**: requires an Azure AD app registration + credentials (pack.md §5.2, Ying prerequisite) and an n8n instance; neither is available in this environment — not executed here. Template is static-reconciled against n8n source only.
- **Half-loop smoke (`n8n_loop_smoke.py`)**: script not present in the repo at writing time (measured `ls` 2026-11-15); the command shape in §6 is the documented contract, unexecuted here.
- `test_webhook_service` reconciliation (AC2, T2), REST doc reconciliation (AC3/T3), full regression (AC6): other tasks in the pack.
- The webhook node `webhookId` in the JSONs is a fixed placeholder uuid; n8n regenerates/serves callbacks per instance on activation.
