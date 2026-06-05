# KIE 自定义字段（Query Fields / v1.1）

> 版本：v1.1  
> 基线：Release 1.0.1 Pro KIE  
> 关联：[kie.md](./kie.md)、[智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) §10

## 1. 目标

在 **固定 `document_type` YAML schema** 之上，允许单次分析 Job **追加** 用户命名字段（对标 Azure Document Intelligence **Query Fields** add-on），由 Qwen2.5-VL 按合并后的 schema 输出到 `view.fields`。

**不在 v1.1**：全量 `document_type=custom`、模板持久化、Custom 模型训练、字段 bbox。

## 2. 与 Azure Query Fields 对照

| 项 | Azure DI v4.0 | DocuVision v1.1 |
|----|---------------|-----------------|
| 触发 | `features=queryFields` + `queryFields=Name1,Name2` | `enable_kie=true` + `kie_query_fields` JSON 数组 |
| 与内置 schema | **仅扩展**，不替换 prebuilt 字段 | **仅追加**，不得与 YAML 顶层键同名 |
| 上限 | 20 字段 / 请求 | `KIE_QUERY_FIELDS_MAX = 20` |
| 引擎 | 云端 Layout / prebuilt | 自托管 Qwen2.5-VL + `kie_configs/*.yaml` |
| 输出 | `documents[].fields`（DocumentField） | `view.fields`（JSON dict，见 [kie.md](./kie.md)） |
| 验收 | 服务侧 SLA | **KIE-ACCEPT-002 不含 query 字段**；效果靠样例 Cloud 抽检 |

## 3. API

### 3.1 请求字段

`kie_query_fields`：JSON 数组，元素为：

- 字符串：字段名（如 `"PurchaseOrderRef"`）
- 对象：`{ "name": "PurchaseOrderRef", "description": "PO or reference on the invoice" }`

**Form 示例**（`POST /api/v1/analyze` 或 `POST /api/v1/documents:analyze`）：

```text
enable_kie=1
document_type=invoice
kie_query_fields=[{"name":"OurReference","description":"Customer reference line"},{"name":"BookingDate"}]
```

### 3.2 多页 PDF（v1.2，`kie_pages`）

- 与 query fields 正交：先按页跑 VL，再 `merge_kie_fields`；query 字段在**合并后**的 `view.fields` 上统计 `kie_query_fields_filled`。
- 默认 `kie_pages=1`（仅首页），与 v1.1 行为一致。见 [kie.md](./kie.md)、[multipage_kie.md](../../test_data/acceptance/multipage_kie.md)。

**JSON Job options 示例**（batch `options` 字符串内）：

```json
{
  "enable_kie": true,
  "document_type": "invoice",
  "kie_query_fields": ["PurchaseOrderRef", {"name": "BookingDate", "description": "Booking date if shown"}]
}
```

### 3.2 校验与错误码（HTTP 400）

| error_code | 说明 |
|------------|------|
| `invalid_json` | `kie_query_fields` 非合法 JSON |
| `invalid_type` | 非数组 |
| `invalid_field_name` | 空名或不符合 `[A-Za-z][A-Za-z0-9_]*` |
| `duplicate_query_field` | 请求内重名 |
| `duplicate_field` | 与内置 YAML 顶层键冲突 |
| `too_many_fields` | 超过 20 个 |
| `query_fields_require_kie` | 提供了 query 字段但未 `enable_kie` |
| `unsupported_document_type` | `auto` / 非 KIE 类型 |
| `unsafe_description` | description 含疑似 prompt 注入片段 |

响应体：`{"detail": {"error_code": "...", "message": "..."}}`

### 3.3 响应与 quality

- `view.fields`：内置键 + 追加键（模型未识别时可能为空字符串或缺失）
- `quality.kie_query_fields_requested`：请求中的 query 字段名列表
- `quality.kie_query_fields_filled`：在 `view.fields` 中有非空值的 query 字段名
- `kie_meta.kie_query_fields_requested` / `kie_query_fields_count`：编排层可观测

## 4. 合并规则（extend_only）

1. 加载 `kie_configs/{document_type}.yaml` 的 `schema`
2. 对每个 query 项追加 `schema[name] = description`（默认 `User-defined field: {name}`）
3. `KieManager.get_prompt` 使用合并后的 schema 注入 `{{ schema_json }}`
4. **禁止** 覆盖或删除内置键

支持的 `document_type`：`invoice`、`receipt`、`id_card`、`passport`、`bank_card`、`financial_report`。

## 5. 安全

- `description` 最长 200 字符，剥离控制字符
- 简单 denylist 拦截 instruction-like 注入短语
- 代码与日志字符串保持英文（见 `007-code-language.mdc`）

## 6. 测试与验收

- **Phase A**：`backend/tests/test_kie_query_fields.py`（合并/校验，无 GPU）
- **Cloud 阶段 F**（可选）：invoice 样例 + `OurReference`、`BookingDate` — 见 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)

## 7. 后续（v1.2+）

- `document_type=custom` 全量用户 schema
- 模板库持久化
- `ValueTyper` / `BaseField` 与 Azure 导出对齐
- 字段 bbox 与画布联动
