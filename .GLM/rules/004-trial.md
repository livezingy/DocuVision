# 试用资产速查（GLM trial, feat/glm-trial 分支）

1 小时免费诊断试用的全部资产与入口。剧本见 docs/demo/TRIAL_REMOTE_60MIN.md。

## 安全
- `backend/app/core/trial_auth.py`：DOCUVISION_TRIAL_API_KEY 非空即全 /api/v1 鉴权
  （HTTP X-API-Key；WS ?key=）。前端 `frontend/shared/trial-key.js` 自动携带。
- CORS 白名单：DOCUVISION_CORS_ORIGINS（逗号分隔）。
- 上传上限：MAX_FILE_SIZE（413 强制）。

## Figure 裁剪（P0-2）
- `app/services/figure_service.py`；流水线 figure_step（layout 后）。
- 契约：result.figures / envelope.figures；quality.figure_* 三指标。
- 路由：GET /api/v1/tasks/{id}/figures、.../figures/{figure_id}（PNG）。
- 开关：enable_figure_export（默认 true）。

## GT Diff（P1-4）
- `app/services/trial/gt_diff.py`（纯逻辑 + CLI + HTML 报告）。
- 路由：POST /api/v1/trial/gt-diff/{task_id}（body: fields/tables/case_sensitive）、
  GET .../gt-diff/{task_id}/report（HTML）。
- CLI：`python -m app.services.trial.gt_diff --gt gt.json --result res.json --out r.html`

## 符号基准（P1-5，云测）
- `scripts/trial/symbol_benchmark.py`：PP-OCR vs Qwen2.5-VL 符号生存率。
- 本地仅 `--render-only` 冒烟。

## 运维脚本（scripts/trial/）
- `generate_trial_samples.py`：生成 test_data/testfiles/trial/ 三份样例。
- `trial_preflight.py`：开演前 30 分钟自检（KIE ready/样例/磁盘/鉴权）。
- `trial_reset.py --yes`：试用间数据清零（uploads/outputs/debug/sqlite）。

## 已知边界（对客户要诚实）
- figure 完整性告警是几何启发式（嵌套/切分），不是语义判断。
- GT diff 的 cell 对位按 (row,col) 位置，不做模糊匹配。
- 符号基准结果依赖部署机字体/模型版本，报告须注明环境。
