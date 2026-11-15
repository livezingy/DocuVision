# R-002 T1d verdict 回填模板（v1.4 判据复测 · bbox 坐标值直判 · Ying 14:24「A 出稿」+14:26 方式批示+14:28「定稿」）

> 执行者：Ying（Cloud Studio GPU）；判据预写死 = t1b_downstream_diff.py v1.4 文件头（|Δcx|≤1.0% 页宽 ∧ |Δcy|≤2.5% 页高 ∧ |Δw|≤5% ∧ |Δh|≤5%，检出面零容忍，100% 配对块）。
> 前置：t1_renders/ 双集仍在（T1b/T1c 产物，无需重渲染）；引擎输出直接复测。
> 读数 = 脚本 stdout + t1b_report_v14.jsonl（逐块明细 coord_blocks 全量），逐字粘贴禁止改数。**本判据全自动，无肉眼判读环节。**

## 1 执行环境

- PaddleOCR/pypdfium2 版本：____ · GPU 就位：☐ · 执行日 = ____ · 基线 = detached@8fc9345
- 命令（逐字）：

```
python scripts/cloud/t1b_downstream_diff.py --fitz-dir t1_renders/fitz --pdfium-dir t1_renders/pdfium --out t1b_report_v14.jsonl --gpu
```

## 2 汇总行（脚本 stdout 逐字）

```
VERDICT=____ pages_ok=__/_ report=t1b_report_v14.jsonl
```

## 3 逐页读数（jsonl 摘录：tag / count_equal / type_seq_equal / coord_pass / worst_block）

| tag | 块数 f/p | 序列 | coord_pass | worst_block（max(dcx,dcy)） |
|---|---|---|---|---|
| | | | | |

## 4 超容差块明细（仅 DRIFT 时填；coord_blocks 中 pass=false 的块逐条）

```
{"tag": ____, "i": __, "type": ____, "dcx": __, "dcy": __, "dw": __, "dh": __, "pass": false}
```

## 5 结论（分支预裁决，勾选其一）

- ☐ **PASS**（9/9）→ **过闸，放行 AgentE T2-T5**（R-002 主线恢复；agentD 审读确认后出放行注记）
- ☐ **DRIFT·检出面**（任一页块数/序列不一致）→ 真漂移照旧，冻结维持（回 B/C 裁决面报 Ying）
- ☐ **DRIFT·坐标差**（任一页存在超容差块）→ 附 §4 明细回报 Ying（位移超 1 字符高实证上限 = 判读幅度被低估，判据面重开）
- ☐ **UNRUN** → 附报错原文

## 6 agentD 审读（过闸判定回收，agentD 填）

- 审读人/日期：____
- 判定：____
