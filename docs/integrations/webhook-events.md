# Webhook 事件类型全表（living）

> 状态：**living** — 随派发代码变更同步更新；每条断言带仓内真源锚（`path:line`），改动派发逻辑时逐行复核本表。
> 通道：HTTP webhook（服务端 `POST` 到订阅 URL）。batch 域无 WS 流（WS 仅 task 域，见 §5）；WS 对照锚见 §6。
> REST 端点全表与订阅端点的路由细节见 [rest-api.md](rest-api.md)；字段细节以服务运行时 `/openapi.json` 为唯一真源。

## 1. 事件总表

| 事件 | 触发点（派发真源） | 载荷字段真源 | 信封真源 |
|---|---|---|---|
| `task.completed` | 单任务 finalize 末段：`backend/app/orchestration/steps/governance.py:120-128` | `governance.py:122-127` | `backend/app/services/webhook_service.py:138` |
| `batch.completed` | 批处理完成钩子：`backend/app/routers/batch.py:89`（经 `_on_batch_completed` `batch.py:176-180` 注入 `BatchService.on_complete`，`batch.py:288` start / `batch.py:308` resume） | `backend/app/services/batch_runner.py:45-50` | 同上 |

**事件非枚举**：订阅 `events` 为自由字符串（逗号分隔，`webhooks.py:68`），服务端无白名单校验。默认值三处——
dataclass 默认 `["task.completed", "batch.completed"]`（`webhook_service.py:73`）、register 兜底（`webhook_service.py:94`）、路由 Form 默认 `"task.completed,batch.completed"`（`webhooks.py:61`）。
但**实际派发仅此二事件**：全仓派发点只有 `governance.py:121` 与 `batch.py:89` 两处，订阅其它字符串永远收不到派发。

## 2. `task.completed`

触发链（同一 finalize 路径，顺序执行）：
1. `governance.py:85` 置 `task["status"] = "completed"`（注释 :84：对前端保持 `completed`；Phase 1 job 路由双收 `succeeded`/`completed`）；
2. `governance.py:113` 持久化任务；
3. `governance.py:115` 向 WS 发 `completed` 帧（§5/§6）；
4. `governance.py:120-128` 派发 webhook（异常仅降级 debug 日志 :129-130，不影响任务终态）。

载荷字段（信封 `payload` 内层）：

| 字段 | 真源 | 类型 / 说明 |
|---|---|---|
| `task_id` | `governance.py:123`（`ctx["task_id"]`） | string |
| `file_name` | `governance.py:124`（`task.get("file_name")`） | string \| null |
| `status` | `governance.py:125`（`task.get("status")`） | 该触发点恒 `"completed"`（:85 写入；`"succeeded"` 从不写入 task.status，见 §6 别名段） |
| `validation_passed` | `governance.py:126`（`(result.get("kie_validation") or {}).get("validation_passed")`） | bool \| null（无 KIE 校验结果时为 null） |

## 3. `batch.completed`

触发点两处，均走 `_notify_batch_complete`（fire-and-forget，异常降级 debug，`batch_runner.py:36-54`）：
- 正常处理收尾：`batch_runner.py:141`（终态翻转 :131-135）；
- resume 无 pending 收尾（Batch 8 asymmetry fix，注释 :198-201）：`batch_runner.py:202`。

载荷字段（信封 `payload` 内层）：

| 字段 | 真源 | 类型 / 说明 |
|---|---|---|
| `batch_id` | `batch_runner.py:46` | string |
| `name` | `batch_runner.py:47`（`batch.name`） | string |
| `status` | `batch_runner.py:48`（`batch.status.value`） | 触发时 batch 已终态（completed / failed / cancelled 之一，收尾翻转见 `batch_runner.py:131-135` 与 `:186-195`）；`BatchStatus` 全集 pending/processing/completed/failed/cancelled/paused 见 `backend/app/services/batch_models.py:22-29` |
| `completed_tasks` | `batch_runner.py:49`（`batch.completed_tasks`） | int |
| `failed_tasks` | `batch_runner.py:50`（`batch.failed_tasks`） | int |

## 4. 订阅机制（POST /api/v1/webhooks + 前置三件）

注册与查询（路由真源 `backend/app/routers/webhooks.py`）：

| 项 | 真源 | 行为 |
|---|---|---|
| `POST /api/v1/webhooks` | `webhooks.py:57-77` | `Form`：`url` / `events`（逗号分隔）/ `secret`（:60-62）；200 返回 `{subscription_id, url, events}`（:73-77） |
| `GET /api/v1/webhooks` | `webhooks.py:48-54` | 返回 `{subscriptions: [...]}`，每条 `{subscription_id, url, events, active, has_secret}`（`webhook_service.py:100-110`） |
| 闸① 实例开关 | `webhooks.py:64` → :18-21 | `WEBHOOK_ENABLED=false`（默认，`backend/app/core/config.py:102-105`，别名 `DOCUVISION_WEBHOOK_ENABLED`）时整组路由 404 |
| 闸② 管理令牌 | `webhooks.py:65` → :24-45 | 头 `X-DocuVision-Admin-Token` 必须 `== WEBHOOK_ADMIN_TOKEN`；未配置令牌时 fail-closed 401（:40-45）；`config.py:106-109` 默认空，别名 `DOCUVISION_WEBHOOK_ADMIN_TOKEN` |
| 闸③ SSRF 私网拦截 | `webhooks.py:71-72` ← `webhook_service.py:89-90` | 回环/私网目标注册即 400（网段表 `webhook_service.py:21-30`；解析后逐地址判定 :33-66） |

**启用前置三件**（缺一即静默 no-op 或 4xx）：① 置 `WEBHOOK_ENABLED=true`；② 置非空 `WEBHOOK_ADMIN_TOKEN`（生成即弃口径，不进 git 不进日志）；③ 完成注册（注册 200 且 `task.completed` 可派发）。

## 5. 派发行为（dispatch_event_async）

真源 `webhook_service.py:119-174`：

| 项 | 真源 | 说明 |
|---|---|---|
| 实例开关短路 | `webhook_service.py:129-130` | `WEBHOOK_ENABLED=false` 时直接返回 `[]`（静默 no-op） |
| 目标筛选 | `webhook_service.py:112-113` | `active` 且事件名在订阅 `events` 内 |
| 信封 | `webhook_service.py:138` | `{"event", "payload", "timestamp"}`（UTC ISO + `Z`） |
| 签名 | `webhook_service.py:145-147` | `secret` 非空时：HMAC-SHA256（对完整信封 body 字节），头 `X-DocuVision-Signature`（hex digest） |
| 超时 / 重试 | `webhook_service.py:142,124,151-161` | 单次超时 15s；`max_retries=2`（共 ≤3 次尝试）；重试退避 `0.5*(n+1)`s |
| 成功判据 | `webhook_service.py:155` | 响应 2xx |
| 返回值 | `webhook_service.py:162-169` | 每目标 `{url, subscription_id, delivered, status_code}` |

## 6. WS 流对照（task 域）与状态别名

WS 端点：`WS /api/v1/tasks/{task_id}/ws`（`backend/app/routers/tasks.py:46-47`；batch 域无 WS 通道）。
连入行为：先重放历史（`?since` 或 `?last_event_id`，过滤 `id > since`，`tasks.py:60-75`，重放发送 :79-81），再发当前帧 `{type:"status", status, progress, message, timestamp, id}`（`tasks.py:92-103`）；`ping`→`pong`（`tasks.py:120-121`）。
广播真源 `_send_event`（`backend/app/core/runtime.py:379-403`）：帧 `{type, message, timestamp, id, progress?}`（:381-387，id 单调递增 :393-397）；**无 WS 连接时事件仍入 history**（:389-401，保留最近 100 条），故迟到客户端经重放仍能看到完成帧。

WS 帧 `type` 值域（4 值，派发真源）：`log`（`backend/app/orchestration/document_pipeline_orchestrator.py:63`）、`status`（:70）、`cancelled`（:122）、`completed`（`governance.py:115`）。

`task.status` 实写值域（6 值）：`pending`（`backend/app/routers/analyzer.py:272`）/ `uploaded`（`analyzer.py:109,133`）/ `processing`（`document_pipeline_orchestrator.py:68`）/ `completed`（`governance.py:85`）/ `failed`（`document_pipeline_orchestrator.py:127`）/ `cancelled`（`document_pipeline_orchestrator.py:55,117`；`backend/app/routers/tasks.py:160,203`）。

**`succeeded` 归一别名**：`"succeeded"` 从不写入 `task.status`，只是取数别名——双 result 闸 `in ("succeeded", "completed")`（`backend/app/routers/jobs.py:52-55`、`backend/app/routers/tasks_content.py:35-36,132-133,379-380`；定义注释 `governance.py:84`）；Envelope 体 `status` 恒 `"succeeded"`（`backend/app/orchestration/steps/envelope.py:298`）。quirk：jobs debug 闸仅认 `"succeeded"`，`completed` 任务请求 debug 得 409（`jobs.py:94-99`）。

**对账锚（T2 断言形态）**：同一完成路径 `governance.py:85`（status）→ :115（WS `completed` 帧）→ :120-128（`task.completed` webhook），三者同源于 finalize；因此 webhook `task.completed` 触发 ⟺ WS 流出现 `{"type":"status","status":"completed"}` 帧（`succeeded` 仅是取数别名，WS 帧与 `task.status` 皆不写 `succeeded`；迟到订阅者经 history 重放 :75-81 可见该帧）。**对账用例** = `backend/tests/test_webhook_service.py`（同一 finalize 路径双捕获 stub orchestrator.send_event + stub webhook_registry；`succeeded` 别名双闸断言；WS 路由当前帧分支实链路钉死形态）。

## 7. 已知约束：SSRF 闸 vs 同机回调

`_is_private_target` 无条件拦截回环/私网目标（`webhook_service.py:21-30` 段表；注册入口 :89-90；解析 hostname 后逐地址判定 :51-66）。**同机 n8n 实例用 `localhost`/`127.0.0.1`/内网 IP 作回调 URL 注册会被 400 拒绝**——同机闭环需让接收端具备非回环可达地址（或由部署方在网络层提供可达性），本文件仅记录约束不改代码。

## 8. 相关文档

- [rest-api.md](rest-api.md) — REST 端点全表（生成产物；端点真源 = 仓内 OpenAPI 快照闸 + 冻结 55）。
- n8n 侧消费本表的事件名与载荷字段：见 `docs/integrations/n8n/`（模板工件，另行登记）。
