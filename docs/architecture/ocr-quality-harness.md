# OCR 质量测量 Harness — 规格与口径

> 最近对照：v1.9.0 / commit 3fd4d11（2026-09-26）
> 归属：本文件是 `scripts/measure/**` 的 owning doc（见 `../agent-ops/doc-sync-ownership.md`）；改**规格与口径**同步本文，改实现无须。
> 事实源分层：**口径与设计点**在本文件；**机器可读常量**（阈值 / 退化参数 / 列序）留在 `scripts/measure/*.py` 常量内，本文不复制取值表。
> 晋升记录：自 PENDING P-020 / P-018 晋升（2026-09-26），替代两份 local-only 过渡稿（`ocr-quality-measurement-harness.md` 提案与
> `ocr-quality-measurement-design.md` 设计稿，已删除）；原始执行包与云端读数载体仍在 `docs/R&D/`（local-only，见 §8）。

---

## 1. 要测量的两个问题

| 测量主轴 | 含义 | 本 harness 的指标 |
|---|---|---|
| **准确率（Accuracy）** | OCR 读出来的字对不对 | 字符级 CER（micro / corpus / macro 三口径）、行级 `line_exact_rate`、`matched_rate` |
| **布局保真度（Layout fidelity）** | 版面结构、阅读序、表格还原得好不好 | 区块 IoU@0.5 配对、阅读序 LCS、`cell_accuracy`（表内序列比对）、table / non-table / digit 子分 |

**它要解决的三个边界**（此前 review_list 作为测量仪器的三限）：

| # | 边界 | 现状痛点 | 本 harness 的解法 |
|---|---|---|---|
| B1 | 域限定 | review_list 只比表格内数字/符号 | 全页字符、标题、图注都进测量面 |
| B2 | 真值限定 | 真值 = PyMuPDF 文本层，扫描件无真值 | 伪扫描**已知真值**（受控退化 = 档二）；无真值共识与人工金标见 §7 |
| B3 | 口径限定 | cap-50 采样，是证据样本不是统计量 | 全量 + 失败类分层 + 曲线单调性 sanity（提示性，非门禁） |

**核心论点**：扫描件测量不是"找一个替代真值源"，而是**真值四档 + 无真值一档**的组合——档零共识分诊（无真值）／档一文本层全量对照／
档二 GT 工厂（本 harness 主力）／档三字段金标。关键杠杆：文本层不只是字符 GT，**也是几何 GT**（词 bbox 聚类出栏/行/表）。

---

## 2. 实现状态（据实，勿按设计稿推断）

| 组件 | 状态 | 说明 |
|---|---|---|
| **M1 受控退化** | **已实施**（local-only） | 单一前向仿射矩阵生成 `identity` / `rotate:{deg}+jpeg:{q}` 等退化试件；确定性（同输入同参数逐位可复现） |
| **M2 弱 GT + 全量对照 runner** | **已实施**（local-only） | born-digital 文本层产弱 GT（词级 bbox + 文本）；runner 出 per-page × per-spec 的 15 列 CSV + HTML 报告 |
| 指标核心 | **已实施**（local-only） | CER 三口径 / LCS 阅读序 / `line_exact_rate` / table 子分 / `cell_accuracy`；纯标准库 DP（见 §4 的 D2） |
| **M3 共识分诊**（档零） | **未实施** | 本包不做（§7）；原提案描述保留在 git 历史与 CHANGELOG 里，勿当现状引用 |
| **M4 字段金标**（档三） | **未实施** | 同上；业务口径指标目前由既有 review_list / Proof Pack 承担 |
| **TEDS**（表格结构树编辑距离） | **未实施** | 依赖结构真值 ⇒ 随 **P2**（表格结构 GT 对账）激活（PENDING P-018） |

**实现不入库（关键前提）**：`scripts/measure/**` 的源码、测试与产物**均不进 git**——`.gitignore` 的 `scripts/*` 是用户既定策略
（"never track these folders"，仅逐个白名单放行门禁脚本），P-020 裁决**保持 local-only**。三个直接后果：

1. CI 里**不存在**这些文件 ⇒ harness 的一切都不可机检，本文是它唯一的入库规格载体；
2. `lint_file_size.py` 以 `git ls-files` 枚举（git 模式），故 **F1 行数棘轮对 local-only 源码不生效**——实测规模 1958 行（见 §6）；
3. 换机器 = 换仪器能力；本地证据（执行包、云端读数、判读脚本）必须随机器保存（§8）。

---

## 3. 数据契约（弱 GT 与对照输出的形状）

- **输入**：born-digital PDF（文本层 = 词级 bbox + 文本）。表格结构真值不在本层，属 P2 范围。
- **弱 GT 的"弱"**：born-digital 假设下把文本层当真值、**不做人工校验**；用途限于**回归比对**（同文件两次跑分数稳定）与
  OCR/视觉输出对账，**不宣称绝对准确率**——对外只用于"我们 vs 通用工具"的相对比较。
- **被测边界（解耦）**：harness **只评不修**，且只读被测输出的 result JSON / envelope，**不 import 被测管线内部模块**；
  harness 自身改动不触发管线门禁。
- **join 语义**：GT 记录保留**源 PDF 页号**，而被测侧看到的是页内 `page=1` ⇒ 按页 join 会静默产出 0 对，故按 JSONL 序号 join。
- **未测量与失败必须可分辨**：空配对 / 空 GT 切片的指标读 `None`（未测量），GT 有行却全未配上读 `1.0`（全删除，属已测量的失败）——
  绝不允许读 `0.0`（会被读成"完美"）。

---

## 4. 钉死的设计点（改动即口径变更，须登记 PENDING）

| 点 | 内容 | 理由 |
|---|---|---|
| **D2** | 编辑距离 DP 单位唯一 = **字符**，行 = 配对单位；回溯平局写死 `sub > del > ins` | 让 `12`→`21` 稳定记 2 个替换 ⇒ 失败指纹可复现（D9 归因） |
| **D7** | 几何 GT 一律经**同一前向仿射**转成四边形，IoU 用精确 Sutherland-Hodgman 裁剪 | 退化试件与 GT 处于同一几何框架，IoU 才有意义 |
| **D8** | 行内字符级 provenance **结构性不可测**（被测只出行级框） | 已在报告头部显式声明，不假装能测 |
| **D-A** | line 级文本**按阅读顺序配对**（两侧各用尺度无关排序 + 保序 DP 对齐），**几何只留给 base A** 做区块/表/图 IoU | 把坐标帧依赖解耦：不修产品坐标也能出数；AS 多出的行免费跳过，GT 漏配的行按删除计费 |
| **归一化分层** | L1/L2 分层；归一化为空的元素剔除出 CER 串、只进 SKIPPED 列 | 避免"空 == 空"灌水准确率 |
| **曲线 sanity** | 以 **`cer_micro`** 为准的**提示性**判据（不升级为门禁） | 多指标同时单调经实测不成立（见 §6 round3），口径变更需另行登记 |

---

## 5. 坐标系与回归哨兵（读本 harness 数据前必读）

- **base A（analyze 侧）**：`view` 层含 table/figure，逆旋转对全部 kind 统一生效 ⇒ 与 GT 同系，可直视；**但 `tables[].bbox` 属
  preprocessed 系，禁入指标路径**（实测锚点-1 结论）。
- **base B（`POST /api/v1/ocr`）**：该端点的坐标帧曾与上传图像像素系相差一个**非刚性形变**（unwarping 未关闭，P-021 定位并修复）。
  修复后 8/8 标定探针 `scale 0.9992–1.0001`、残差 ≤1.13px、旋转 = 探针角。
- **回归哨兵**：`POST /api/v1/ocr` 的**空间门禁**自 2026-09-25 起为 **PASS**，其判据降级为**哨兵**——再 FAIL 即说明引擎配置漂移
  （如 `use_doc_unwarping` 被重新打开，或更换/升级 OCR 引擎改了坐标帧）。步骤与判据在执行包 §10.11/§10.12。
- 结果 JSON 的实测边界：**不含 cell 级 bbox**（`cell_bbox` 仅为重建输入、不落盘）⇒ `cell_accuracy` 收敛为
  「表级 IoU 配对 + 表内 `data` 序列比对」，`cell_word_bbox`（backfill 落盘）为可选几何来源。

---

## 6. 验收与既有证据（要点；明细在 local-only 执行包）

- **本机可判定项全绿**：G1 恒等退化与直接渲染**逐位 hash 相等**；G2 已知答案断言（`pytest scripts/measure/test_metrics.py` → **31 passed**）；
  G3 同输入跑两次 `metrics.csv` **逐位相等**；`audit_agent_ops.py` 0 error / 0 warning。
- **云端锚点（Pro GPU，据实登记、不外推）**：锚点-1 通过（15/15 落试件画布）；锚点-2 通过（结论为"无"——cell 级几何零出现，
  故 cell accuracy 走表级配对 + 表内比对）。
- **G4 smoke（15 行 × 15 列齐）**：`cer_micro` 在 5 个 fixture 上**单调不降 5/5**；`cer_macro` 4/5、`cer_corpus` 2/5（后者把 AS
  多出的表格体计为插入，**属口径性质而非脚本缺陷**）；`cell_accuracy` 随旋转单调下滑、`cer_table` 单调抬升。
- **round2 / round3 复测**：15 组合 `cer_*` 与关键串在两轮之间**逐字节一致**（确定性复现）；round3 在含 P-021 修法的构建上重采
  8/8 空间探针 → 门禁 FAIL→PASS。**单调性硬判据不成立**（`cer_micro` 3/5、`cer_macro` 4/5、`matched_rate` 0/5）⇒ 维持提示性口径。
- **规模据实登记**：实际 **1958 行** vs 预算 1205（+62.5%，超 ±20% 护栏，用户 2026-09-22 裁决接受），其中指标核心文件 **569 行**
  已越 500 行自由预算——**因 local-only 故 F1 门禁不生效**；若日后要入库，须先拆该文件。

---

## 7. 明确不做（80/20 红线）

- 不做 **M3 共识分诊**（档零）与 **M4 字段金标**（档三）——本包只交 M1+M2；要做须各自立项。
- 不做 **TEDS**（依赖结构真值）——随 P2 激活。
- 不做**端到端模型重训**、**大规模人工标注**、**GT 标注平台化建设**。
- **只测不治**：不做引擎微调/替换/超参搜索；不改 review_list 现有行为；不搬移其组件代码（import 复用）。
- 不引新依赖进主线（自实现 DP / IoU / 秩相关，不引 jiwer / rapidfuzz / scipy）。
- 不做前端 UI（报告 = CSV + 现有 HTML 胶水）。
- **金标与退化样张不进 git**（客户数据红线）。

---

## 8. 本地证据在哪（local-only，不入库）

| 载体 | 内容 |
|---|---|
| `P020-ocr-harness-M1M2-执行包.md`（`docs/R&D/`） | §3 设计细化 / §9 护栏 / **§10 runbook 与回填模板** / §10.11-§10.12 空间门禁与判读修正 |
| `P021-云端对照-执行清单与记录模板.md`（`docs/R&D/`） | P-021 的对照执行清单、OCR JSON SHA 清单、§6.6 round3 记录 |
| `test_data/TestResult/harness/` | 云端产物（`round3_20260925/` 的 `commit.txt` + `gpu.txt` + `versions.txt` + `ocr_sha256.txt`）与判读脚本 |
| `scripts/measure/**` | 仪器本体与自测（local-only，见 §2） |

## 9. 关系与后续

- **PENDING P-018**（GT 工厂立项）：P0 评测 harness + P1 弱 GT 合成 = 本 harness（已落地）；**下一待决项 = P2 表格结构 GT 对账的公开资源选型**
  （PubTabNet / FinTabNet / WTW）。
- **PENDING P-002**（表格逐格对齐）：本 harness 把 mamba p12/p29 的红率从"人工看"变成**分数**，即 P-002 立项触发条件的量化入口。
- **PENDING P-021**：`/api/v1/ocr` 坐标帧修复与哨兵（§5）。
- **PENDING P-020**：harness 落地证据与规模偏差的登记条目（本文件是其规格的 living 载体）。
