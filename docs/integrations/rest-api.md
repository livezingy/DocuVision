# DocuVision REST API 全量文档（生成产物）

> **generated** — 手改无效；对账用例 = `backend/tests/test_route_doc_reconciliation.py`（registry kind `full`，非写模式逐行 diff，漂移即红）。
> 生成源 = 仓内 OpenAPI 快照闸（`app.openapi()` 运行时提取），冻结口径 = `backend/tests/test_route_inventory.py` EXPECTED_ROUTES。
> 再生命令：`cd backend && DOCUVISION_REST_DOC=write python -m pytest tests/test_route_doc_reconciliation.py -q`

## 端点计数

- OpenAPI distinct paths：49
- HTTP 端点（OpenAPI operations）：54
- WebSocket 端点（OpenAPI 不表达，取自运行时路由表）：1（`/api/v1/tasks/{task_id}/ws`）
- **端点总数：55，对账锚 = test_route_inventory.EXPECTED_COUNT（冻结 55）**

## 端点全表（HTTP）

| # | Method | Path | Summary |
|---|--------|------|---------|
| 1 | GET | `/` | Root |
| 2 | POST | `/api/v1/analyze` | Analyze Document |
| 3 | GET | `/api/v1/batch` | List Batches |
| 4 | POST | `/api/v1/batch` | Create Batch |
| 5 | DELETE | `/api/v1/batch/{batch_id}` | Delete Batch |
| 6 | GET | `/api/v1/batch/{batch_id}` | Get Batch |
| 7 | POST | `/api/v1/batch/{batch_id}/cancel` | Cancel Batch |
| 8 | GET | `/api/v1/batch/{batch_id}/export.csv` | Export Batch Csv |
| 9 | GET | `/api/v1/batch/{batch_id}/export.json` | Export Batch Json |
| 10 | GET | `/api/v1/batch/{batch_id}/export.xlsx` | Export Batch Xlsx |
| 11 | POST | `/api/v1/batch/{batch_id}/pause` | Pause Batch |
| 12 | GET | `/api/v1/batch/{batch_id}/results` | Get Batch Results |
| 13 | POST | `/api/v1/batch/{batch_id}/resume` | Resume Batch |
| 14 | POST | `/api/v1/batch/{batch_id}/retry` | Retry Batch Failed |
| 15 | POST | `/api/v1/batch/{batch_id}/start` | Start Batch |
| 16 | GET | `/api/v1/batch/{batch_id}/summary` | Get Batch Summary |
| 17 | POST | `/api/v1/document/profile` | Document Profile Scan |
| 18 | POST | `/api/v1/documents:analyze` | Analyze Document V1 |
| 19 | GET | `/api/v1/engines` | List Engines |
| 20 | GET | `/api/v1/health` | Health Check V1 |
| 21 | GET | `/api/v1/hitl/reviews` | List Hitl Reviews |
| 22 | GET | `/api/v1/hitl/reviews/{review_id}` | Get Hitl Review |
| 23 | POST | `/api/v1/hitl/reviews/{review_id}/resolve` | Resolve Hitl Review |
| 24 | GET | `/api/v1/jobs/{job_id}` | Get Job Status |
| 25 | GET | `/api/v1/jobs/{job_id}/debug` | Get Job Debug |
| 26 | GET | `/api/v1/jobs/{job_id}/debug/{filename}` | Get Job Debug File |
| 27 | GET | `/api/v1/jobs/{job_id}/result` | Get Job Result |
| 28 | GET | `/api/v1/kie/templates` | List Kie Templates |
| 29 | GET | `/api/v1/kie/templates/{template_id}` | Get Kie Template |
| 30 | POST | `/api/v1/kie/templates/{template_id}` | Save Kie Template |
| 31 | POST | `/api/v1/ocr` | Ocr Recognize |
| 32 | POST | `/api/v1/pdf-tools/form-fill` | Pdf Tools Form Fill |
| 33 | POST | `/api/v1/pdf-tools/merge` | Pdf Tools Merge |
| 34 | POST | `/api/v1/pdf-tools/metadata` | Pdf Tools Metadata |
| 35 | POST | `/api/v1/pdf-tools/searchable` | Pdf Tools Searchable |
| 36 | POST | `/api/v1/pdf-tools/split` | Pdf Tools Split |
| 37 | DELETE | `/api/v1/tasks/{task_id}` | Delete Task |
| 38 | GET | `/api/v1/tasks/{task_id}` | Get Task Status |
| 39 | GET | `/api/v1/tasks/{task_id}/blocks` | Get Task Blocks |
| 40 | POST | `/api/v1/tasks/{task_id}/cancel` | Cancel Task |
| 41 | GET | `/api/v1/tasks/{task_id}/events` | Get Task Events |
| 42 | GET | `/api/v1/tasks/{task_id}/export/{format}` | Export Result |
| 43 | GET | `/api/v1/tasks/{task_id}/figures` | List Task Figures |
| 44 | GET | `/api/v1/tasks/{task_id}/figures/{figure_id}` | Get Task Figure Crop |
| 45 | PATCH | `/api/v1/tasks/{task_id}/kie-fields` | Patch Task Kie Fields |
| 46 | GET | `/api/v1/tasks/{task_id}/layout` | Get Unified Layout Analysis |
| 47 | GET | `/api/v1/tasks/{task_id}/page-image/{page_num}` | Get Page Image |
| 48 | GET | `/api/v1/tasks/{task_id}/result` | Get Task Result |
| 49 | POST | `/api/v1/trial/gt-diff/{task_id}` | Trial Gt Diff |
| 50 | GET | `/api/v1/trial/gt-diff/{task_id}/report` | Trial Gt Diff Report File |
| 51 | POST | `/api/v1/upload` | Upload File |
| 52 | GET | `/api/v1/webhooks` | List Webhooks |
| 53 | POST | `/api/v1/webhooks` | Register Webhook |
| 54 | GET | `/health` | Health Check |

## WebSocket

- `/api/v1/tasks/{task_id}/ws` — OpenAPI 规范不表达 WS，此行取自运行时路由表，计入端点总数。

## 真源注记

- 本文件为生成产物；端点真源 = 仓内 OpenAPI 快照闸（`test_openapi_snapshot_full`）+ 冻结路由清单（`test_route_inventory.EXPECTED_ROUTES`）。
- 端点/字段细节以服务运行时的 `/openapi.json` 为唯一真源。
- 漂移处置：改路由必须同步三处 —— 代码路由、`test_route_inventory.EXPECTED_ROUTES`、本文件（写模式再生）。
- 相关文档：`docs/integrations/webhook-events.md`（webhook 事件类型全表：task.completed / batch.completed 载荷与 WS 对照）。
