# 文档治理门禁（Doc governance）

> **Status**: living。**晋升自 `docs/R&D/PENDING.md` P-022**（2026-09-25 用户裁决：走「结论确认 → 晋升
> `docs/architecture/` → 从 PENDING 移除」的正规流程）。**规则文本在本文件；机器可读清单在脚本**（单一真源）。
> 机检：`python scripts/docs_refs_audit.py`（可独立跑）· `python scripts/audit_agent_ops.py`（随 `agent-ops-audit`，每 PR 必跑）。

## 1. 墓碑前缀门禁（DOC-1，ERROR）

**规则**：对外物料**不得**出现「已退役的路径 / 端口 / 命令 / 模块名」——读者会照抄一条注定失败的指令。
实现为**字面子串**匹配（大小写不敏感）：无 regex token、无 `subprocess`、无 `exec`、不写盘
（**文档是数据，不是程序**）。

| 维度 | 规定 | 真源 |
|---|---|---|
| token 清单 | 当前 **17 条**：已退役 CPU 轨的应用目录 / 端口 / 入口脚本 / UI 页面与前端 bundle / 其 API 文档与专属样式 / 其 e2e 脚本名 / core 的 pip extra；以及已删除的 core 子模块族（裸 `extractors` · `engines` · `models` 三个子模块名）与其顶层模块名；另有其 batch API 名、预览 gate 名、UI 清单名 | 脚本内 `RETIRED` 常量。**本文件刻意不逐字抄写清单**——既避免双源，也因为本目录就在扫描域内，逐字抄写会触发本门禁自身 |
| 退役标记豁免 | 同行含标记词（`RETIREMENT_MARKERS`，17 条：`退役` / `已删除` / `移除` / `不存在` / `已过期` / `不再` / `勿再执行` / `retired` / `removed` …）时视为**公告**而非指令——"…已随 v1.8 退役"是文档，不是过期命令 | 脚本内 `RETIREMENT_MARKERS` |
| 扫描白名单 | 根 `README.md`、`docs/README.md`、`docs/demo/**/*.md`、`docs/architecture/**/*.md`、`packages/**/README.md`（当前命中 **19 个文件**） | 脚本内 `SCAN_GLOBS` |
| 归档豁免（理由随报告打印，**不静默**） | `CHANGELOG.md`、`docs/release/**`、`docs/R&D/**`、`docs/agent-ops/**`、`test_data/acceptance/**`、`docs/architecture/v1.*-roadmap.md`、`docs/architecture/pp-structurev3-fix-plan.md`——引用已删之物是历史的本分 | 脚本内 `EXEMPT` |
| ALLOWLIST（**棘轮只减不增**） | **2 条**：`docs/architecture/CLOUD_VALIDATION.md` §2 冻结抬头下的 v1.2–v1.4 发版门禁行，按「文件 + 字面子串」豁免；上限 `MAX_ALLOWLIST = 2` 由 selftest 守着 | 脚本内 `ALLOWLIST` |

**口径边界（诚实登记）**：

1. 标记豁免是「同行情景词」，**挡不住**把死引用写进一句未提退役的话——而那正是本门禁要抓的对象。
2. ALLOWLIST 以「文件 + 字面子串」豁免，同文件其它位置再出现同 token 会**一并放过**（靠 `reason` 字段留痕）。
3. 只覆盖上列白名单；`docs/**` 之外的非生成物料（如 `.cursor/rules/002` / `003` / `006`）不在内。

## 2. living-doc 路径漂移（DOC-2，WARN）

`docs/architecture/*.md` 与 `docs/README.md` 中引用的文件路径（以 `backend/` · `frontend/` · `packages/` ·
应用目录 · 数据库迁移目录为前缀，且带扩展名白名单）**必须存在**：行号后缀剥离、含 `*` · `?` 的 glob 与 `...` 跳过、
运行期产物前缀不计。

级别为 **WARN**：漂移多半是重命名未同步，与 DOC-1 不同——它不会让读者执行一条注定失败的命令。

## 3. 明确不做（含理由；**不挂在任何条目的完成条件上**）

- **markdown 链接目标存在性**：实测裸上会红 4 处真死链 + 9 处误报（README 注释块内待录制 GIF、
  `media/README.md` 计划表）→ 收益/维护比明显低于墓碑规则；那 4 处真死链**已在同批修复**。
  若将来要做，**单独立项**，不要塞回本门禁的完成条件（否则本条目永远结不掉）。
- **`cd <路径>` 的 cwd 语义与机器绝对路径**：实测 `cd ../packages/docuvision-core` 从 `backend/` 出发是对的，
  从文件目录解析即误报 → 不做。

## 4. 归属与触发

- **owner**：`scripts/docs_refs_audit.py`（两条检查的实现 + 白名单/豁免/ALLOWLIST 的机器可读真源）与**本文件**
  （规则文本）。门禁经 `audit_agent_ops.py` 接线，随 `agent-ops-audit` **每 PR 必跑**（**零 CI 配置改动**）。
- **机检登记**：`docs/architecture/module-map.md` §5 的 **DOC-1** / **DOC-2** 行。
- **触发条件**：任何一次 v 级退役 / 删除 → 在 `RETIRED` 加一行；改白名单 · 豁免 · ALLOWLIST 时**同改本文件对应行**。
- **实证（2026-09-24，晋升时原样保留）**：门禁 **0 error / 0 warning**（受检 19 文件）；**正向对照**——临时注入一条
  已退役命令到 `docs/demo/_tmp_bad_sample.md` → **1 ERROR / exit 1**，样本已删；`audit_agent_ops.py --selftest`
  由 16 → 26（含本门禁的纯谓词断言）；晋升后 audit 仍 **0 error / 0 warning**。
