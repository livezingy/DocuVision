# scripts/cloud/ — 云测轮次一键金样例（golden sample）

> 出处：P-034 云测第 4 轮实证（2026-10-27，`feat/p034-text-first-coi` @ `c2b46e2`，tampa on/off 双向
> + 通道自证全链通过）。后续 GPU/Cloud 验证轮次**复用本脚本，只改环境变量，不改流程**；
> 流程级变更须同批更新本 README 并在 CHANGELOG 登记。

## 工具

| 文件 | 用途 |
|---|---|
| `cloud_round_test.sh` | 一键云测：版本核验 → 契约单测 → ON 跑夹具（通道自证）→ OFF ×3（分母稳定性）→ 自动判定 → 产物落脚本同目录 |

## 用法

```bash
# 上传 scripts/cloud/ 到云端（或云端 git clone 后直接用），任意临时目录执行：
bash cloud_round_test.sh
REPO_DIR=/path/to/DocuVision bash cloud_round_test.sh   # 仓库非默认位置时
```

## 可配置参数（环境变量；默认值 = P-034 worked example）

| 变量 | 默认 | 说明 |
|---|---|---|
| `REPO_DIR` | 自动探测 | 仓库根 |
| `BRANCH` | 当前分支 | 拉取目标 |
| `EXPECTED_HEAD` | 空（仅告警） | **钉版本短 hash**；保证读数可比性，正式轮次必填 |
| `PROMPT_CHECK` | `kie_configs/coi.yaml:v3.2` | `path:version` prompt 版本核验，空 = 跳过 |
| `FIXTURE` / `DOC_TYPE` | tampa / `coi` | 被测夹具与 doc-type |
| `FIELDS` / `BOILER` | 五字段 / 样板句特征 | 判定字段集与禁出值特征（逗号分隔） |
| `CHANNEL_GREP` | `KIE text-first` | 通道自证日志锚（ON ≥1 / OFF =0） |
| `UNIT_TESTS` | P-034 四文件 | 契约单测清单（旗标关）；空或 `RUN_UNIT=0` 跳过 |
| `PREFIX` | `round` | 产物文件名前缀 |

## 判定口径（与 P-034 复核记录 P1 判据一致）

1. **键存在（never-omit）**：字段键缺失一律记退化/违约——不区分「值=空」与「键省略」。
2. **样板句禁出**：`BOILER` 特征在任一字段值出现即 FAIL。
3. **不退化 = 同轮 on/off 对照 + OFF ×3 取多数为分母**：OFF 自身漂移是移动靶，单跑 OFF 不作分母
   （P-034 第 3 轮教训：OFF 轮间 `PER STATUTE` ↔ `EACH OCCURRENCE` ↔ `''` 漂移）。
4. **通道自证先行**：ON 侧服务日志必须有通道锚行、OFF 侧必须为 0——**无通道自证的 on/off 结论无效**
   （P-034 第 2 轮教训：通道未证 ⇒ prompt 失效结论不成立）。

## 纪律（与 AGENTS.md 红线一致）

- 本机无 GPU ⇒ **不宣称云端已验证**：只有本脚本产物（summary + 双侧 result JSON + 双侧日志）齐备，
  读数方可登记；产物须落 `docs/R&D/runs/<ID>/` 并同批更新 `docs/R&D/README.md` runs 索引
  （`python scripts/docs_refs_audit.py --check-rnd-index` 必须 0/0）。
- 判据不因读数难看而回改；缺口如实登记回设计复核，不硬凑通过（PENDING ③ 协议）。
- 版本不符（`EXPECTED_HEAD` 失配）= 停，不得「顺手在新 HEAD 上跑」。
