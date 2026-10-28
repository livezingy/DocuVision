# 验证例程（Verification routine）

> kernel 真源。验证角色（agents.md 运行时三角色）的例程分层、verdict 规范与工具准入。

## 例程分层
- L0 恒定例程（每 run 必跑，读数进 verdict）：`python scripts/audit_agent_ops.py`（0 error）、`--selftest`（全绿）、`scripts/lint_file_size.py` / `lint_routes.py` / `lint_frontend.py` / `check_frontend_baseline.py` / `check_e2e_allowlist.py`（均 OK）、`scripts/lint_commit_msgs.py`（PR 时随 CI）。
- L1 契约绑定：按执行包 §0 断言与 DoD 逐条执行；AC 绑定机器闸的以读数回填，绑不上的显式标 `人工验收` 转交用户。
- L2 专项（暂断开）：GPU 金样 = Cloud Studio 手动，verdict 以 `cloud: pending` 占位，回填由用户完成。

## verdict 规范（bus 仓 runs/R-xxx/verdict.md frontmatter）
- 必填：`verdict: pass|fail|blocked`、`readings:`（每门禁一行 `工具: 读数`）、`coverage:`（机器闸覆盖 AC 数 / AC 总数）、`cloud: pending`。
- 失败诊断字段（照 Multica 实践 4.5）：`step` / `tool` / `failure_type` / `stderr_tail`（≤5 行）/ `final_state`。

## 工具准入（裁判也要被 pin）
- 新增验证脚本入例程前必须带最小自检（构造违规样本全检出的证明），且 ≤500 行预算。
- 现有工具正确性由 audit selftest（93 探针，运行读数口径）与 E2 suite pin 固定；两者红灯 = 例程红灯，禁止降级继续。

## 缺陷注入自检（能力确认，每季度或大改后）
- 在牺牲分支埋 5 类违规：超预算文件 / 白名单外路由 / 薄壳手改 / 文档死链 / type 枚举外 commit。验证角色必须全检出并写入 verdict；漏检项 = 覆盖缺口清单，按需补闸。
