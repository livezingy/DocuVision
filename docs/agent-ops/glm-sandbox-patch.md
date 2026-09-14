# GLM 沙箱 patch 交付协议（已退役，存档）

> 存档自 `.GLM/rules/002-git.md`（2026-09 清理 `.GLM/` 时迁移）。
> 该协议为 GLM 网页沙箱环境设计：沙箱与本机是两份克隆，GLM 无法直接操作本机仓库。
> ZCode 直接运行于本机工作目录、可直接 commit，不再使用本协议。
> 若恢复 GLM 沙箱协作，按本存档执行。

## 分支
- commit 前必须 `git branch --show-current` 确认分支。
- 命名沿用仓库惯例：`feat/*`、`fix/*`、`docs/*`、`chore/*`。

## 提交
- type 枚举与格式见 `.cursor/rules/003-git.mdc`（feat/fix/docs/style/refactor/perf/test/chore/revert/build）。
- 小步提交：一个逻辑单元一个 commit，避免巨型提交。
- push 前确认工作区只含拟交付变更；密钥/.env 不进 commit。
- 日常 push 不加 `[run ci]`；PR 至 main 才自动跑 CI。

## GLM patch 交付协议（沙箱环境特有）
GLM 沙箱与用户本机（D:\3_PROJECTS\DocuVision）是**两份克隆**：
1. GLM 在沙箱分支上开发，系列 commit；
2. `git format-patch <基线>..HEAD` 导出 patch 包 + APPLY.md；
3. 用户本机：先 `git add -A && git commit` 固化本地 WIP（与 7z 内容一致），
   再 `git am *.patch` 应用；
4. 禁止 GLM 直接 push 到远端（红线）。

## 云端验证
- 合并前用腾讯 Cloud Studio GPU 拉分支跑 pytest（测试分层见 kernel `testing.md`）；
- zsh/bash 语法；PowerShell 命令不得贴进 Cloud Studio。
