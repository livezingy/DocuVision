# KIE Test Run Tracker

Last updated: 2026-06-12  
Scope: Cloud verification for invoice + card + receipt KIE (contract + production + id_card precision); **v1.1 `kie_query_fields`** (Phase F)

验证步骤见 [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（**长期保留**：发版/改 KIE 后按同流程回归）。  
Phase C/D/E 原始 JSON 可放在 `test_data/TestResult/PhaseCDE/`（`.gitignore`，不提交 Git）。

Release 1.0：[RELEASE_1.0_CHECKLIST.md](../release/RELEASE_1.0_CHECKLIST.md) · **Release 1.1**：[RELEASE_1.1_CHECKLIST.md](../release/RELEASE_1.1_CHECKLIST.md) · Known limitations：[KNOWN_LIMITATIONS.md](../release/KNOWN_LIMITATIONS.md)

## Tracking Rules

| Rule ID | 用途 | 判定 |
|---------|------|------|
| **KIE-ACCEPT-001** | 流水线契约 | `kie_stage == completed` 且 `kie_fields_count >= 0` |
| **KIE-ACCEPT-002** | 生产质量 | `kie_production_hit == true` |
| **KIE-ACCEPT-003** | id_card 字段精度 | `kie_id_card_precision_hit == true`（`name` + 18 位 `id_number`） |

`kie_fields_count` 为有意义字段计数（排除仅 `raw_output`、空值不计）。

**Query fields（v1.1）**：KIE-ACCEPT-002 **不**因 query 字段未填而失败；抽检看 `quality.kie_query_fields_requested` / `kie_query_fields_filled`。

---

## Release 1.1 baseline — 2026-06-04

- **tag**: `v1.1.0`（2026-06-04，已推送 `origin`）
- **branch**: `main`
- **commit**: `e79db9a`（含 `7eb3f3a` feat、`555f10f` UI、`9d78b03` 发版文档）
- **base_url**: `http://127.0.0.1:8000`
- **Phase A / B**: passed（契约 + `kie_query_fields` 400）
- **阶段 F**: **1/1** — 见下「阶段 F — Query fields」
- **阻塞项**: 无
- **阶段 C + E 回归**（发版后）: ☑ 2026-06-04 已复跑，001/002 无回归（与 Release 1.0 矩阵一致）

### Release 1.1 KIE 总览

| 维度 | 结果 |
|------|------|
| 固定矩阵（继承 1.0 C+D+E） | 10 样例；001/002 基线见 Release 1.0 |
| **阶段 F**（query fields） | **1/1** `sample-invoice.png`；001/002 pass |
| 可选待补 F | `invoice_sample_01.pdf` + query（非阻塞） |
| 下一产品优先级 | v1.2 MP + H-Batch Cloud 已通过（见 [Release 1.2](#release-12--multipage-kie--batch)）；字段校验见 [RELEASE_1.1_CHECKLIST.md](../release/RELEASE_1.1_CHECKLIST.md) §6 |

---

## Release 1.2 — multipage KIE + batch

- **branch**: `feature/batch-ui`（待合入 `main`）
- **commits**: `116ac47`（feat: multipage KIE + batch v1.2）、`e64b335`（fix: kie_step raster fallback + Phase A contract tests）
- **tag target**: `v1.2.0`
- **features**: `kie_pages`, `kie_fields_by_page`, batch orchestrator + `export.csv` / `export.json`, Pro Batch UI tab
- **fixtures**: `test_data/scripts/build_multipage_kie_fixtures.py` → `invoices/multipage/*.pdf`
- **Cloud**: 阶段 MP + H-Batch — [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)

### Release 1.2 baseline — 2026-06-05（Cloud Studio GPU）

- **base_url**: `http://127.0.0.1:8000`
- **env**: `docuvision_env`（Python 3.11）；终端 1 `python run.py`，终端 2 手动 API
- **Phase A**: **33/33 passed**（`test_kie_pages_parse.py`、`test_kie_field_merge.py`、`test_batch_export_service.py`、`test_kie_field_metrics.py`、`test_kie_service.py`、`test_kie_return_raw_contract.py`、`test_orchestrator_order.py`）
- **Layout 回归**（单页 PDF）: `invoice_sample_01.pdf` + `enable_layout=1` — pass（UI / API）
- **阶段 MP**: **1/1** — 见下表
- **阶段 H-Batch**: **6/6** — 见下「阶段 Batch-KIE」
- **阻塞项**: 无（发版前建议合 PR + tag）
- **已知非阻塞**: 轮询 `GET /tasks/{id}` / `GET /batch/{id}` 含 KIE `raw_output` 控制字符时 `json.load(strict=True)` 可能失败；验收用 `/summary` + `/export.csv` 或 `strict=False`

### 阶段 MP — 多页 PDF KIE（2026-06-05 Cloud）

| sample_path | kie_pages | task_id (ref) | 001 | 002 | pages_processed | merge | fields | note |
|---|---|---|---:|---:|---|---|---|---|
| testfiles/invoices/invoice_sample_01.pdf | `1` | — | — | — | `[1]` | — | — | 单页 layout 回归已确认；KIE 矩阵继承阶段 C |
| testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf | `all` | `d2844524-7f2a-4565-9c2c-eeb858079ed6` | pass | hit | `[1, 2]` | true | 14 | `enable_layout=0` `enable_table=0` `enable_kie=1` |

**MP-002 结果摘要**（`GET /api/v1/tasks/{task_id}/result`）：

- `kie_stage`: `completed`
- `kie_production_hit`: `true`（`kie_production_reason`: `production_hit`）
- `kie_pages_requested`: `all`
- `kie_pages_processed`: `[1, 2]`
- `kie_multipage_merge`: `true`
- `kie_fields_by_page`: keys `1`, `2`
- merged `kie_fields` 含 `invoice_number`, `invoice_date`, `total`, `items` 等

**MP 汇总（2026-06-05）**：**1/1** 多页样例；001 + 002 通过；双页 VL + 文档级合并可观测。

#### 阶段 MP — 待补（可选）

| sample_path | kie_pages | 001 | 002 | pages_processed | note |
|---|---|---:|---:|---|---|
| testfiles/invoices/multipage/invoice_multipage_3p_items.pdf | `all` | — | — | `[1,2,3]` | batch 内已覆盖；独立 MP 用例可选 |
| testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf | `1` | — | — | `[1]` | 默认仅第 1 页向后兼容 |

### 阶段 Batch-KIE — `kie_invoice_6`（2026-06-05 Cloud）

| metric | target | actual | note |
|---|---|---|---|
| batch_id | — | `52ce6aed-0635-4a0a-a72b-4743f9199bf8` | name: `Cloud kie_invoice_6` |
| completed | 6/6 | **6/6** | `success_rate=100%`，~108s |
| kie_production_hit | 6/6 true | **6/6** | 含 2 个多页 PDF |
| export.csv | `file_name`, `kie_production_hit` | pass | `GET .../export.csv?mode=kie` |
| options | KIE only | `enable_layout=false` `enable_table=false` `enable_kie=true` `kie_pages=1` | 避免合成多页 PDF layout 与 PP-Structure 冲突 |

**Batch 文件清单**（6）：

1. `testfiles/invoices/sample-invoice.png`
2. `testfiles/invoices/receipt-invoice-like.png`
3. `testfiles/invoices/invoice_sample_01.pdf`
4. `testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf`
5. `testfiles/invoices/multipage/invoice_multipage_3p_items.pdf`
6. `testfiles/invoices/sample-invoice.png`（重复项，与 manifest 一致）

**H-Batch 汇总（2026-06-05）**：BATCH-001 ~ BATCH-003 pass；脚本等价 `test_data/scripts/run_batch_kie_acceptance.ps1`（本次为 zsh/curl 手动）。

### 阶段 Batch-KIE — `kie_invoice_6` 复测（2026-06-06 Cloud）— **FAIL → 已修脚本**

| metric | target | actual | note |
|---|---|---|---|
| batch_id | — | `6397b4ef-31e5-44da-992a-5e1bedd0db14` | `pwsh run_batch_kie_acceptance.ps1` |
| completed | 6/6 | **6/6** | BATCH-001 pass |
| kie_production_hit | 6/6 true | **0/6** | BATCH-002 **fail** |
| kie_stage | `completed` | **`skipped_doc_type` ×6** | `document_type` 实际为 `auto` |
| export.csv | 表头 + hit | 表头 pass，hit 全 False | BATCH-003 pass，BATCH-002 fail |
| layout JPG `kie_pages=all` | HTTP 200 | **pass** | `enable_kie=0` 回归 |
| §3 控制流 | pause/resume | **未测** | `$BATCH_ID` 未 export；批次已 completed |

**根因**：`manifest.json` 的 `document_type` 在 set 顶层，脚本仅提交 `set.options`（无 `document_type`）→ API 默认 `auto` → KIE 跳过。  
**修复**（2026-06-06）：脚本合并 set 级 `document_type` 入 options；manifest `options` 内补 `document_type`；脚本末尾校验 `kie_production_hit` 并 non-zero 退出。

**复测（2026-06-12 Cloud）**：脚本修复后 **6/6** `kie_production_hit` — 见下「合 main 门禁」。

### 合 main 门禁 — 2026-06-12（Cloud Studio GPU）

清单：[MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md)

| 阶段 | 状态 | 通过判据 / 备注 |
|------|:----:|-----------------|
| §0 健康检查 | pass | HTTP 200（`api_version` 需重启 T1 后应为 `1.2.0`） |
| §1 Phase A | pass | **37/37**（2026-06-12 复测，`edac3a5` `pdf_page_count` 修复后） |
| §1 Vitest | pass | `queue.test.js` **11/11** |
| §2 MP-002 | pass | `TASK_ID=3826fbf2-...`，轮询 → `completed` |
| §3 H-Batch | pass | `BATCH_ID=2a74ad5c-...`，`kie_production_hit` **6/6**（方式 A 脚本） |
| §4 Layout batch | pass | `1f70fb58-...`，2/2 `completed`，`export.json` 合法 |
| §5 控制流 | pass | `CTRL_BATCH_ID=96bdfbfd-...`：pause → `paused` → resume → `completed`（`resume` 后 `start` 返回 already processing 为预期） |
| §6 Layout 回归 | pass | JPG + `kie_pages=all` → HTTP 200 |
| §7 UI 冒烟 | pass | BATCH-U-01～07 + FIX-Q 队列回归，与预期相符（2026-06-12 手工） |

**合 main 门禁**：**全部通过**（2026-06-12）。下一项：开 PR `feature/batch-ui` → `main` → tag `v1.2.0`。

### Release 1.2 KIE 总览

| 维度 | 结果 |
|------|------|
| Phase A（契约单测） | **37/37**（2026-06-12 复测） |
| 阶段 MP（多页 KIE） | **1/1**（2p `all`；2026-06-12 复测 `3826fbf2-...`） |
| 阶段 H-Batch（2026-06-05） | **6/6** completed，`kie_hit=6/6` |
| 阶段 H-Batch（2026-06-12 复测） | **6/6** completed，`kie_hit=6/6`（`2a74ad5c-...`） |
| Batch 控制流（§5） | **pass**（`96bdfbfd-...` pause/resume） |
| UI 冒烟（§7） | **pass**（2026-06-12） |
| 合 main 门禁 | **全部通过** |
| 下一项 | PR `feature/batch-ui` → `main` → tag `v1.2.0` |

---

## Release 1.0 baseline — 2026-05-21

- **tag target**: `v1.0.0`
- **branch**: `main`
- **commits**: `e7dc4ab`（PDF KIE）→ `2c9c58b`（id_card 02–04、ACCEPT-003、Phase A CI）
- **base_url**: `http://127.0.0.1:8000`（UI）
- **Phase A CI**: green on `main`

### 阶段 C — 发票（2026-05-20 批次，commit `e7dc4ab+`）

| sample_path | document_type | kie_stage | kie_fields_count | 001 | 002 |
|---|---|---|---:|---|---|
| testfiles/invoices/invoice_sample_01.pdf | invoice | completed | >0 | pass | hit |
| testfiles/invoices/receipt-invoice-like.png | invoice | completed | 11 | pass | hit |
| testfiles/invoices/sample-invoice.png | invoice | completed | 14 | pass | hit |

**C 汇总**：3/3

### 阶段 D — 卡证 `images/kie/`（2026-05-21 UI 批次，commit `2c9c58b+`）

| sample_path | document_type | kie_stage | fields | 001 | 002 | 003 | note |
|---|---|---|---:|---|---|---|---|
| testfiles/images/kie/bank_card_sample_01.png | bank_card | completed | 5 | pass | hit | n/a | JSON `…5023578` |
| testfiles/images/kie/passport_sample_01.png | passport | completed | 11 | pass | hit | n/a | JSON `…5009993` |
| testfiles/images/kie/id_card_sample_01.jpg | id_card | completed | 5 | pass | hit | **ref miss** | 美国驾照风格；003 预期失败 |
| testfiles/images/kie/id_card_sample_02.jpg | id_card | completed | 6 | pass | hit | **hit** | JSON `…5018388` |
| testfiles/images/kie/id_card_sample_03.jpg | id_card | completed | 6 | pass | hit | **hit** | JSON `…5015901` |
| testfiles/images/kie/id_card_sample_04.jpg | id_card | completed | 6 | pass | hit | **hit** | JSON `…5013366` |

**D 汇总**：

- 001 + 002：**6/6**
- 003（id_card 02~04）：**3/3**；01 为 **ref**（见 Known limitations）

### 阶段 E — 收据（2026-05-20 批次）

| sample_path | document_type | kie_stage | kie_fields_count | 001 | 002 |
|---|---|---|---:|---|---|
| testfiles/receipts/receipt-with-tips.png | receipt | completed | 10 | pass | hit |

**E 汇总**：1/1

### 阶段 F — Query fields（v1.1 Cloud 验收）

在 **阶段 C 任一样例** 上追加 `kie_query_fields`，确认 001/002 仍通过且 `quality.kie_query_fields_*` 可观测。设计见 [kie-custom-fields.md](./kie-custom-fields.md)。

#### F baseline — 2026-06-04（Cloud Studio GPU）

- **release**: [Release 1.1 baseline](#release-11-baseline--2026-06-04) · **commit**: `555f10f`（+ `7eb3f3a`）
- **base_url**: `http://127.0.0.1:8000`
- **Phase A**: passed（`test_kie_query_fields.py` 等）
- **Phase B**: passed（`kie_query_fields` 校验 400 用例）
- **note**: 端到端需在**同一** `python run.py` 进程内 analyze 后立即轮询；重启/reload 会导致 `Task not found`（内存 `tasks` 字典清空）

| sample_path | document_type | kie_query_fields | task_id (ref) | 001 | 002 | query requested | query filled | note |
|---|---|---|---:|---|---|---|---|
| testfiles/invoices/sample-invoice.png | invoice | `CustomerName`, `OurReference` | `aec6e250-46ed-4422-b632-61586ce880b0` | pass | hit | `CustomerName`, `OurReference` | `CustomerName` | `CustomerName` → `MICROSOFT CORPORATION`; `OurReference` → `""` |

**请求**（`POST /api/v1/analyze`，zsh/curl）：

```text
enable_kie=1
document_type=invoice
kie_query_fields=[{"name":"CustomerName"},{"name":"OurReference"}]
```

**结果摘要**（`GET /api/v1/tasks/{task_id}/result`）：

- `status`: `completed`
- `kie_production_hit`: `true`
- `kie_query_fields_requested`: `["CustomerName", "OurReference"]`
- `kie_query_fields_filled`: `["CustomerName"]`
- `view.fields` 含内置键（如 `invoice_number`, `total`, `items`）及 query 键

**F 汇总（2026-06-04）**：**1/1** 样例；001 + 002 通过；query extend-only 可观测；**002 不因 query 未填失败**。`OurReference` 空值为模型未抽到，可换字段名/description 复测，非契约失败。

#### 阶段 F — 待补（可选）

| sample_path | document_type | kie_query_fields | 001 | 002 | query filled |
|---|---|---|---|---|---|
| testfiles/invoices/invoice_sample_01.pdf | invoice | `OurReference`, `BookingDate` | — | — | 待 Cloud 复测 |

**请求示例**（PDF 发票 + 带 description）：

```text
enable_kie=1
document_type=invoice
kie_query_fields=[{"name":"OurReference","description":"Customer or PO reference"},{"name":"BookingDate"}]
```

### Release 1.0 KIE 总览（历史）

| 维度 | 结果 |
|------|------|
| 固定矩阵（C+D 卡证+E） | **10** 样例路径；001 **10/10**；002 **10/10** |
| id_card 003（02~04） | **3/3** |
| 阻塞项（1.0 时） | 无 |

> v1.1 阶段 F 见 [Release 1.1 baseline](#release-11-baseline--2026-06-04)。发 **v1.1.0** tag 前建议在同环境重跑 **阶段 C + E**。

---

## Historical — 2026-05-20 Cloud Studio（commit `e7dc4ab`）

首批 **7 样例** 001/002 全过；`id_card_sample_02~04` 尚未入库。PDF 发票修复见 `e7dc4ab`。

| sample_path | note |
|---|---|
| invoice_sample_01.pdf | 修复前曾 `runtime_error`（PIL 无法打开 PDF） |
| 其余 6 样例 | completed + production_hit |

---

## Historical — pre-fix batch（commit `61dc578`）

| sample_path | kie_stage | note |
|---|---|---|
| invoice_sample_01.pdf | runtime_error | `preprocessed_image_path` 误为 PDF 路径 |

---

## Related Artifacts

- Acceptance criteria: [backend/tests/KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)
- Summarize script: `backend/tests/tools/summarize_kie_results.py`
- 验收矩阵: [test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
- Changelog: [CHANGELOG.md](../../CHANGELOG.md)
