# Codebuddy 会话启动与回顾

> Codebuddy 低频角色专属。共享约束见 `001-general.md`（kernel 生成，勿手改）。

## 启动检查
1. 读 `.codebuddy/rules/001-general.md`（通用约束，kernel 生成）。
2. 读 `docs/R&D/PENDING.md`（待决决策；看"有 N 条结论待确认"）。
3. 按任务读 `004-project.md`（环境/测试）、`009-doc-sync.md`（文档同步）或 `011-frontend.md`（前端架构 F1-F7）。

## 执行能力（默认：本机终端已加载）
- **默认前提**：本会话**默认加载本机终端**（`execute_command`，跑在用户本机的 Windows/PowerShell 上）。
  因此 `git` / `gh` / 本机 Python 与各门禁脚本**由会话直接执行**，**不要**只给脚本让用户手动跑。
  但 kernel `constraints.md` §自主边界 的红线（`git push`、改 CI 配置、删除文件/分支、force push…）
  **仍然先问**——"默认有终端"≠"可以直接 push"。
- **不确定就先自检**：跑一条只读命令 `git status --porcelain`；有输出 = 本机终端可用。
- **两条通道互不替代**（独立挂载，是加法不是替换）：

  | 通道 | 工具 | 能做什么 | 边界 |
  |------|------|----------|------|
  | **本机终端** | `execute_command` | `git` / `gh` / 本机 pytest / 门禁脚本 | 用用户本机的仓库与凭证 |
  | **远程沙箱** | `cloud_studio_execute_command` / `cloud_studio_deploy_sandbox` / `cloud_studio_fetch_log` | 在 Cloud Studio `/workspace` 跑命令、部署 Web 预览、取日志 | **没有**本仓库与 git 凭证；资源属**用户的** Cloud Studio 账号；沙箱是**持久环境**，用完须 `cloud_studio_delete_deployment` 销毁；接口**无 GPU / 规格参数**，算力与型号选择在平台控制台人工完成 |

- IDE「配置集成 → 已部署 Cloud Studio」**只表示该集成连通**：既不表示本会话只有云端能力，也**不能**据此推断本机终端的有无（两个独立开关）。
- **本机终端缺失属异常情形**（实测诱因：会话处于 Ask / 只读模式，或该会话未挂载本机终端这一项）。此时：
  只产出**文件改动 + runbook**，并**明确告知用户**——"这是会话工具挂载所致，**不是**仓库红线，授权也无法解除"。
- **禁止**：把"我做不到"归因于仓库规则或本次改动；也**禁止**在缺终端时反复索要授权来"解"一个解不了的问题。

## 结论回流
- 会话产生新结论 / 约定时：稳定结论晋升 `docs/architecture/`，待确认结论登记到 `docs/R&D/PENDING.md`。
- 一次性任务无新约定则跳过。
