# scripts/cloud/ — 云测轮次一键金样例（golden sample）

> 出处：P-034 云测第 4 轮实证（2026-10-27，`feat/p034-text-first-coi`，tampa on/off 双向
> + 通道自证全链通过；venv 激活 / 基线包含核验 / 产物打包改进经同一轮云端实操验证）。
> 后续 GPU/Cloud 验证轮次**复用本脚本，只改环境变量，不改流程**；
> 流程级变更须同批更新本 README 并在 CHANGELOG 登记。

## 工具

| 文件 | 用途 |
|---|---|
| `cloud_round_test.sh` | 一键云测：venv 激活 → 版本核验 → 契约单测 → ON 跑夹具（通道自证）→ OFF ×3（分母稳定性）→ 自动判定 → **产物打包 tar.gz**（与本脚本同目录） |
| `t1_render_downstream_test.sh` | R-002 T1/T1b 一键：venv/版本核验 → 双引擎渲染对比集 →（`MODE=t1b`）T1b GPU 双集 diff（pack v1.2 过闸面）/（`MODE=full`）四闸 pdfium 双侧 /（`MODE=preflight`）fitz 基线 → 判定 → verdict 草稿 + 产物打包 |
| `t1_render_compare.py` | T1 附件脚本：PyMuPDF vs pypdfium2 同 scale 渲染，产出 `fitz/*.png` / `pdfium/*.png` / `t1_report.jsonl` |
| `t1b_downstream_diff.py` | T1b/T1d 附件脚本（pack v1.4 落位）：双渲染集逐页喂 `PPStructureEngine._analyze_image` 直入口；v1.4 判据 = 检出面零容忍（块数 ∧ type 序列）→ 序号一一配对 → bbox 坐标差直判（\|Δcx\|≤1.0%W ∧ \|Δcy\|≤2.5%H ∧ \|Δw\|≤5% ∧ \|Δh\|≤5%，归一化页尺寸，`coord_blocks` 全量留痕）；exit 0=PASS / 3=DRIFT / 4=UNRUN |
| `t1c_render_alignment.py` | T1c 附件脚本（pack v1.3 §7）：pdfium 渲染参数矩阵实验（P1 default / P2 annots+forms / P3 P2+no-smoothing，预写死禁增组），自动判定判据 A（P* 相对 P1 像素差降幅 ≥50% → 定对齐参数）/ B（无组达标 → 引擎重评回 Ying） |
| `t1c_visual_overlay.py` | T1c 附件脚本（pack v1.3 §7 + 本仓 local-compat-patch 2 处）：4 页预写死双引擎块框叠加图，人工二值判读；解释性证据，不改判定 |
| `t1c-verdict-template.md` | T1c verdict 回填模板（pack v1.3 §7） |
| `t1d-verdict-template.md` | T1d verdict 回填模板（pack v1.4 §8 判据面修订复测；全自动判据，无肉眼环节） |
| `r005_cloud_verify.sh` | R-005 / P-046 v2 Cloud 侧一键取证：版本核验 → 生产 pin 复核（P0-5/P0-6）→ V4 尺度 →（M1 落地后）V1/V3 schema diff + 50+ 页性能 → V6/V10/V11/G5 证据 → 判定 → verdict 草稿 + **回传数据清单** + tar 打包。自包含 Python 探针，纯 ASCII，`--self-test` 8/8 |
| `p046_textlayer_verify.sh` | P-046 文本层/端点云测一键（批次④，`feat/r005-render-swap` 起）：契约单测（含 `_page_words` 3pt 链回归）→ G3-ocr 侧（pypdfium2 渲染自证 + `_call_ocr`）→ A7 UserUnit=2 自洽闸（fitz 漂移登记）→ B1 引文归属往返 → B2/B3/B5 语料单遍（校准分布 / 判定稳定性 / coverage GAP 暴露）→ B4b 表格 bbox 几何 → C2 API 冒烟（`REAL_APP=1` 加真实 uvicorn 拉起）→ 判定 → verdict 草稿 + 回传清单 + tar。自包含探针，纯 ASCII，`--self-test` 7/7 |
| `r004_n8n_rebuild.sh` | R-004 n8n 容器一键重建（Cloud Studio）：删卷/保卷（`DEL_VOLUME=0` 幂等恢复）双模式，内置加密密钥幂等固化（/root/.n8n_enc_key）、平台代理域名 URL、/files/watch 文件白名单、5678 端口哨兵（python3 → 15678 桥接）、四验（healthz ×2 / pin 版本 / 域名透传）；删卷前自动快照至 `BACKUP_DIR`（不进 git）。真源 = `runs/R-004/attachments/2026-11-16-n8n-local/handoff-flowb-closure-2026-11-20-v3.md` §3 |
| `cloud_r003_r004_verify.sh` | R-003 (P-042) + R-004 (P-043) 云侧一键取证：版本核验 → 契约单测面（R-004 webhook 对账/文档==55/OpenAPI + R-003 batch export/同源同值 + E1 pin + docs 对账）→（`RUN_E2E=1`）R-004 AC1 闭环观察（GPU 后端 + n8n `database.sqlite` 的 `execution_entity` trigger success 计数 + watch CSV 落盘，只读）→（`RUN_SHEETS=1`）R-003 Sheets 真连接幂等（Google SA 凭据；探针走被测服务 `export_batch_to_sheets` 同 batch 两跑，断言 rows 相等 + `replaced_tasks>=1`，独立 worksheet 不碰 sheet1）→ 判定 → verdict 草稿 + 回传清单 + tar 打包。自包含 Python 探针，纯 ASCII，`--self-test` 8/8（出处 = `runs/R-004/attachments/2026-11-16-n8n-local/handoff-cloud-verify-2026-11-17.md`） |

## 用法

```bash
# 上传 scripts/cloud/ 到云端（或云端 git clone 后直接用），任意临时目录执行：
bash cloud_round_test.sh
REPO_DIR=/path/to/DocuVision bash cloud_round_test.sh   # 仓库非默认位置时
```

## 可配置参数（环境变量；默认值 = P-034 worked example）

| 变量 | 默认 | 说明 |
|---|---|---|
| `VENV_DIR` | `~/docuvision_env` | 云端虚拟环境；置空 = 跳过激活用系统 python；缺失 = 停 |
| `REPO_DIR` | 自动探测 | 仓库根（脚本目录逐级向上找 `backend/`，兜底常见安装位置） |
| `BRANCH` | 当前分支 | 拉取目标 |
| `EXPECTED_HEAD` | 空（仅告警） | **钉基线短 hash**；正式轮次必填 |
| `STRICT_HEAD` | `0` | `1` = 严格锁定 HEAD == EXPECTED_HEAD；默认「基线包含」模式（见下） |
| `PROMPT_CHECK` | `kie_configs/coi.yaml:v3.2` | `path:version` prompt 版本核验，空 = 跳过 |
| `FIXTURE` / `DOC_TYPE` | tampa / `coi` | 被测夹具与 doc-type |
| `FIELDS` / `BOILER` | 五字段 / 样板句特征 | 判定字段集与禁出值特征（逗号分隔） |
| `CHANNEL_GREP` | `KIE text-first` | 通道自证日志锚（ON ≥1 / OFF =0） |
| `UNIT_TESTS` | P-034 四文件 | 契约单测清单（旗标关）；空或 `RUN_UNIT=0` 跳过 |
| `PREFIX` | `round` | 产物文件名前缀 |

### 版本核验两模式

- **基线包含（默认）**：`EXPECTED_HEAD` 已合入当前 HEAD 即通过（`git merge-base --is-ancestor`）——
  允许分支前进到更新提交；**仅当前进提交不触被测面时读数仍可比**，判定时须核对 HEAD 与 EXPECTED_HEAD
  之间是否触及被测代码（P-034 第 4 轮实证：跑在 `dcf99a2`，被测 `c2b46e2` 已合入，且其间仅
  scripts/docs 改动、`backend/**` 逐字节一致 ⇒ 读数有效）。
- **严格锁定（`STRICT_HEAD=1`）**：HEAD 必须逐字等于 `EXPECTED_HEAD`；对被测面敏感的轮次用此模式。

## 产物契约（打包为 `<PREFIX>_artifacts_<HEAD>_<时间戳>.tar.gz`）

`run_on.log` / `run_off.log`（通道自证证据）· `<PREFIX>_on.json` / `<PREFIX>_off_{1,2,3}.json`
（result JSON）· `<PREFIX>_summary.txt`（判定读数，回传重点）。

## 判定口径（与 P-034 复核记录 P1 判据一致）

1. **键存在（never-omit）**：字段键缺失一律记退化/违约——不区分「值=空」与「键省略」。
2. **样板句禁出**：`BOILER` 特征在任一字段值出现即 FAIL。
3. **不退化 = 同轮 on/off 对照 + OFF ×3 取多数为分母**：OFF 自身漂移是移动靶，单跑 OFF 不作分母
   （P-034 第 3 轮教训：OFF 轮间 `PER STATUTE` ↔ `EACH OCCURRENCE` ↔ `''` 漂移）。
4. **通道自证先行**：ON 侧服务日志必须有通道锚行、OFF 侧必须为 0——**无通道自证的 on/off 结论无效**
   （P-034 第 2 轮教训：通道未证 ⇒ prompt 失效结论不成立）。

## 纪律（与 AGENTS.md 红线一致）

- 本机无 GPU ⇒ **不宣称云端已验证**：只有本脚本产物（tar.gz 内七件齐）解包核验后，读数方可登记；
  产物须落 `docs/R&D/runs/<ID>/` 并同批更新 `docs/R&D/README.md` runs 索引
  （`python scripts/docs_refs_audit.py --check-rnd-index` 必须 0/0）。
- 判据不因读数难看而回改；缺口如实登记回设计复核，不硬凑通过（PENDING ③ 协议）。
- 版本不符 = 停，不得「顺手在新 HEAD 上跑」；基线包含模式下放行前必须核对前进提交不触被测面。

---

## R-002 T1 渲染下游验证（`t1_render_downstream_test.sh`）

> 真源：`runs/R-002/pack.md` §3/§6（`agent-bus@7c1ee869`）+ 附件 `t1_render_compare.py` / `t1-verdict-template.md`。
> 本脚本 = pack §6 命令清单的可执行形态；骨架沿用 `cloud_round_test.sh`（版本核验 / 通道自证 / 判定 / 产物打包）。

### 用法（云端 Linux，在 `scripts/cloud/` 下）

```bash
bash t1_render_downstream_test.sh                       # preflight：基线四闸 + 渲染对比（不构成过闸）
MODE=t1b bash t1_render_downstream_test.sh              # pack v1.2 过闸面：双渲染集 → T1b GPU diff（须 GPU 栈）
P027_CMD='<仪器命令>' MODE=t1b bash t1_render_downstream_test.sh   # 指认后顺带补 P-027
MODE=full bash t1_render_downstream_test.sh             # 四闸双侧（佐证形态；须已有渲染源切换面）
bash t1_render_downstream_test.sh --self-test           # 本机判定逻辑 mock 自测（9/9，不装依赖/不跑 GPU）
REPO_DIR=/path/to/DocuVision bash t1_render_downstream_test.sh
EXPECTED_HEAD=8fc9345 STRICT_HEAD=1 bash t1_render_downstream_test.sh   # 正式轮次钉版
```

> Cloud Studio 常以 **detached HEAD** 检出：脚本用 `git symbolic-ref` 判定，此时跳过 `fetch` / `ff-only`，只以当前检出 commit 做基线核验（产物记 `branch=detached`）。**不要设 `BRANCH=HEAD`**；若需同步远端分支，显式 `BRANCH=main`（仍不自动 merge，`AUTO_FF=1` 才快进）。
>
> 若云端检出的是**旧基线**（如 tag `v1.13.0 = e8d0ee2`，2026-10-26）而非契约基线 `8fc9345`（2026-11-08），版本核验会**正确拦截**（`8fc9345 未合入 e8d0ee2`）。先补全对象并检出基线再跑：
> `git fetch --unshallow origin main && git checkout --detach 8fc9345`。
> **禁止** `EXPECTED_HEAD=` 置空硬跑；确需在旧基线执行时，须按 pack §2 重跑 A1–A7 锚点并回报 Ying 裁决。

### 执行顺序（与 pack §6 逐条对应）

1. venv 激活（`VENV_DIR`，默认 `~/docuvision_env`）
2. 仓库定位 + 版本核验（`EXPECTED_HEAD` 默认 `8fc9345`，基线包含；`STRICT_HEAD=1` 严格锁定；detached HEAD 跳过 fetch/快进，默认 `AUTO_FF=0` 不自动改工作区）
3. 依赖 `pymupdf / pypdfium2 / pillow`（**临时对比用，不进 `requirements*.txt`**）
4. `t1_render_compare.py --pdf-dir test_data/testfiles/pdf` → 双渲染集 + `t1_report.jsonl`
5. 四闸 fitz 基线：`test_golden_baseline` / `test_table_alignment` / `test_table_backfill` / `test_formula_step_pdf_roi`（在 `backend/` 下以 `PYTHONPATH=.` 跑，等价于 pack §6 的仓根 `pytest backend/tests/...`）
6. `MODE=full` 时带 `RENDER_ENGINE_VAR=pdfium` 重跑四闸
7. 通道自证（pdfium 侧日志须命中 `ENGINE_PROOF_GREP`）+ 双侧读数 diff
8. `P027_CMD` 可选复跑三指标（**只比对禁重算**；未提供即如实标注未执行）
9. 判定 → 10. 生成 `t1_verdict_draft.md` → 11. 打包 `t1_artifacts_<HEAD>_<时间戳>.tar.gz`

### 参数（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `VENV_DIR` | `~/docuvision_env` | 置空 = 用系统 python（此时自动 pip 需 `ALLOW_SYSTEM_PIP=1`） |
| `REPO_DIR` / `BRANCH` | 自动探测 / 当前分支 | `BRANCH` 仅作 fetch 目标；detached 时为空并跳过 fetch，脚本不自动切分支；与 `PACK_BRANCH` 不符只告警 |
| `EXPECTED_HEAD` / `STRICT_HEAD` | `8fc9345` / `0` | pack §2 写稿日锚；置空跳过钉版 |
| `AUTO_FF` | `0` | `1` = 显式允许 `git merge --ff-only origin/<BRANCH>`；需正常分支，detached 直接报错 |
| `MODE` | `preflight` | `t1b` = pack v1.2 过闸面（T1b GPU diff）；`full` = 四闸双侧（佐证形态） |
| `T1B_ARGS` | `--gpu` | `t1b` 模式传给 `t1b_downstream_diff.py` 的附加参数 |
| `RUN_GATES` | `0` | `t1b` 模式默认跳过四闸（佐证非过闸）；`1` = 强制跑逻辑层佐证 |
| `RENDER_ENGINE_VAR` / `RENDER_ENGINE_PDFIUM` | `DOCUVISION_PDF_RENDER_ENGINE` / `pdfium` | 仅 `full` 模式使用 |
| `ENGINE_PROOF_GREP` | `pypdfium2` | 通道自证锚（仅 `full`）；0 命中 = 无切换面，结论无效 |
| `READING_GREP` | `passed\|failed\|restamp\|sanity\|roi\|PASSED\|FAILED` | 双侧读数提取与 diff（耗时已归一） |
| `P027_CMD` | 空 | P-027 仪器命令，按 local instrument 惯例注入 |
| `RENDER_OUT` | `test_data/local/t1_renders` | 临时输出（gitignore）；`PACK_PNGS=1` 才把 PNG 入包 |
| `GATES` / `PREFIX` / `INSTALL_DEPS` | 四闸 / `t1` / `1` | 闸门清单、产物前缀、依赖安装开关 |

### 判定口径（pack v1.2 §3 T1b）

- **`MODE=t1b`（过闸面，pack v1.2 Ying 22:16 批「①A」）**：以 `t1b_downstream_diff.py` 的 exit code 直接裁决——`0=PASS`（全部页一致 → `PASS_GATE` 退出 0）/ `3=DRIFT` / `4=UNRUN`（→ `BLOCKED(7)` 退出 7）。判据预写死：块数一致 ∧ type 序列一致 ∧ 同 type 配对 IoU≥0.9 占比≥95%。
- **`MODE=full`（四闸佐证形态）**：四闸 rc 全 0 **且** 通道自证 ≥1 **且** 双侧读数无差异 → `PASS_GATE`；否则 `BLOCKED(7)`。注意 pack v1.2 注 2：四闸形态为**佐证非过闸证据**。
- **`MODE=preflight`**：仅产证据，`BLOCKED(7)`，永远不构成过闸。
- 任一模式漂移/缺证 → **停 + 回报 Ying，无自愈分支**；像素差本身**不是** fail 判据。
- 机检结论**不替代** Ying 回填 `runs/R-002/t1b-verdict.md` 与 agentD 审读的过闸令；过闸后 **AgentE 进 T2**（逐点对账），T3 全量替换在其后。

### 纪律与当前边界

- 本机无 GPU ⇒ 不宣称云端已验证；`--self-test` 只验判定逻辑（纯 bash，5 组 mock：`bash -n` + 5/5 passed）。
- 产物落 `scripts/cloud/`（与本脚本同目录）；运行后按 P-034 同口径落 `docs/R&D/runs/<ID>/` 并同批更新 `docs/R&D/README.md` 索引。
- **过闸路径（pack v1.2，Ying 22:16 批）**：`MODE=t1b` 是唯一过闸形态——双渲染集（`t1_render_compare.py`）→ `t1b_downstream_diff.py --gpu` 走 `PPStructureEngine._analyze_image`（`layout_engine_ppstructure.py:277`）图像直入口，判据预写死，exit 0/3/4 直接裁决；四闸（preflight/full）均为**佐证形态**，不构成过闸。`detached@8fc9345` 已由 agentD 追认（T1b = 验证非施工，T0 建分支留 AgentE 施工）。
- **版本核验不自动改工作区**：默认 `AUTO_FF=0`，以当前检出 commit 为实测版本，避免远端 `main` 前进后跑到已含替换的新 HEAD 上；此时 `git fetch` 失败只 WARN（本地新建分支远端无同名分支/离线仍可核验），仅 `AUTO_FF=1` 把 fetch 成功作为硬前置。detached HEAD 用 `git symbolic-ref` 判定——`git rev-parse --abbrev-ref HEAD` 会返回字面量 `HEAD`，导致 `fetch origin HEAD` 只更新 `FETCH_HEAD`、`merge origin/HEAD` 必失败（2026-11-12 云端首跑实证，已修）。

### bus 资产来源登记（引用制）

| bus 资产 @ sha | 落点 / 处置 |
|---|---|
| `runs/R-002/attachments/t1_render_compare.py` @ `agent-bus@7c1ee869` | `scripts/cloud/t1_render_compare.py`（原文 + provenance 注记）；`TEMP/bus/.../*.provenance.txt` 留证 |
| `runs/R-002/attachments/t1b_downstream_diff.py` @ `agent-bus@cb827680` | `scripts/cloud/t1b_downstream_diff.py`（原文 + provenance 注记，pack v1.2 §6 注 1 落位） |
| `runs/R-002/attachments/t1-verdict-template.md` @ `agent-bus@7c1ee869` | 结构内化进 `t1_render_downstream_test.sh`（preflight/full 草稿；v1.2 起由 t1b 模板承接） |
| `runs/R-002/attachments/t1b-verdict-template.md` @ `agent-bus@cb827680` | 结构内化进 `t1_render_downstream_test.sh` 的 `MODE=t1b` 草稿（逐页读数表 / stdout 汇总行 / 三态结论 / P-027 注记） |
| `runs/R-002/pack.md` v1.1 §3/§6 @ `agent-bus@7c1ee869`；v1.2 §2/§3/§6 @ `cb827680` | 本节 + 脚本注释（命令清单逐字对应；v1.2 = Ying 22:16 批「①A ②③照建议」） |

> 本仓尚未建 `bus-refs.md`；本节为等价的资产来源登记，后续建该文件时须同步补登。

---

## R-005 Cloud 侧一键取证（`r005_cloud_verify.sh`）

> 真源：`TEMP/bus/runs/R-005/pack.md` v1.0 §1/§8/§9 + `TEMP/bus/runs/R-005/review-01.md` v1.1 §3。
> 骨架沿用 `t1_render_downstream_test.sh`（版本核验 / 判定单一真源 / verdict 草稿 / tar 打包）；自包含 Python 探针，纯 ASCII。

### 用法（Cloud Studio GPU / Linux，在 `scripts/cloud/` 下）

```bash
bash r005_cloud_verify.sh                       # MODE=evidence：全量可自动项取证（默认）
MODE=m1 bash r005_cloud_verify.sh               # M1 直喂落地后追加 V1/V3 schema diff + 50+ 页性能
bash r005_cloud_verify.sh --self-test           # 本机判定逻辑 mock 自测（8/8，不装依赖/不跑 GPU）
REPO_DIR=/path/to/DocuVision bash r005_cloud_verify.sh
EXPECTED_HEAD=d26bfa0 STRICT_HEAD=1 bash r005_cloud_verify.sh   # 正式轮次钉版
```

### 覆盖的 Cloud 测试项

| 项 | 内容 | 归属 |
|---|---|---|
| 版本核验 | venv / HEAD（detached 安全，`AUTO_FF=0`）/ paddle 栈 + `pypdf==3.17.4` 生产 pin 漂移 | 自动 |
| 生产 pin 复核 | P0-5 hex Tr3（`literal-only=0/0` vs `hex-aware=23/19`）、P0-6 `PdfReadError` 层级；V9 加密/损坏/空文件 | 自动 |
| V4 | `fitz Matrix(2,2)` vs `pypdfium2 scale=2.0`；`PADDLE_PDX_PDF_RENDER_SCALE` 官方源码命中（paddlex 不可用**不计命中**） | 自动 |
| V1/V3 | `predict(pdf)` vs 现行 fitz 渲染喂图的字段 schema diff + 50+ 页内存/时延；入口指认留痕；样本不足 50 页时自动造合成件并标 `synthetic=true` | 仅 `MODE=m1` 且 M1 落地 |
| V6 | 预处理链 `file:line` 锚点 + 待裁清单 | 证据，Ying 裁 |
| V10 | GT 断层盘点（generator / bbox / 重建候选） | 证据，Ying 裁，**禁自行重跑 GT** |
| V11 / C0 | 存量规模 + fitz 残留复算（C0 判据范围问题如实登记） | 证据 |
| G5 | `check_e2e_allowlist.py` + `e2e_suite_pin.json`（5 specs/15 用例），两子命令真实 rc | 自动 |

### 需要回传的数据（脚本不自动 push）

产物落 `OUT_DIR`（默认 `test_data/local/r005_cloud/`，gitignore 临时区），一键打包 `r005_artifacts_<HEAD>_<时间戳>.tar.gz`，并生成 **`r005_return_manifest.md`** 逐件列出必回传文件、目标落点与本机 `bus-push.ps1` 命令模板。必回传：`r005_summary.txt`（判定读数）、`r005_verdict_draft.md`（Ying 回填）、env/pins/v4/v6/v10/v11/g5 证据、V1 两件（如有）、`r005_rc.tsv`、`r005_probe.py`。tar.gz 不上 bus（>100KB 二进制 + `.md` 白名单），读数并入 verdict `.md` 后推 bus。

### 纪律

- 本机无 GPU ⇒ 不宣称云端已验证；机检 `EVIDENCE_READY` **不是过闸**，V6/V10/V11 待 Ying 裁、M1 属 R-006。
- 判据预写死；缺证 / 生产 pin 漂移 / 无 GPU / M1 未落地一律 `BLOCKED(7)`，不自愈、不硬凑通过。
- 云端无 `bus-push.sh`（kit 为 PowerShell 本地宿主），脚本只落盘 + 打包 + 生成回传清单，**不自动 push**（红线）。
- 已验证：`bash -n` OK、`--self-test` 8/8、探针 `py_compile` + **5 个纯逻辑子命令**实跑 OK（`env`/`pins`/`v4`/`v10`/`fixture`）；**`v1` 需 GPU，本侧未跑（如实标注）**。端到端 dry-run 如实判 `BLOCKED(7)`（本机缺 3 项生产 pin）。
