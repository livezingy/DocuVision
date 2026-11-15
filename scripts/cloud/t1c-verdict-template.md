# R-002 T1c verdict 回填模板（渲染参数对齐实验 + 可视化抽验 · pack v1.3 §7 · Ying 12:22 批「T1c 出包」）

> 执行者：Ying（Cloud Studio GPU 侧）；判据预写死见 t1c_render_alignment.py 文件头（判据 A 阈值 50% 降幅）。
> 读数 = 脚本 stdout + t1c_pixel_report.jsonl，逐字粘贴禁止改数；判读结论文字回填（叠加 PNG 不上仓）。
> 取证锚：基线 = detached@8fc9345 · 执行日 = ____ · 执行件 provenance（附件 blob sha）= ____

## 1 执行环境

- PaddleOCR/pypdfium2 版本：____ · GPU 就位：☐
- 命令（逐字）：

```
python scripts/cloud/t1c_render_alignment.py --pdf-dir test_data/testfiles/pdf --out t1c_renders/
python scripts/cloud/t1c_visual_overlay.py --pdf-dir test_data/testfiles/pdf --out t1c_overlays/ --gpu
```

## 2 参数矩阵汇总行（脚本 stdout 逐字）

```
=== 参数矩阵汇总（changed_px_pct 均值，越小越贴 fitz）===
P1_default: ____%
P2_annots_forms: ____%
P3_annots_nosmooth: ____%

best=____ vs P1 (____%)  降幅=____%  阈值=50%
JUDGEMENT=____
```

## 3 可视化抽验判读（逐页二值，对照 t1c_overlays/*.png 人工判读）

| tag | blocks f/p | 判读（①真漂移/②配对低估/其他） | 文字描述（框整体平移方向、哪类块漂移） |
|---|---|---|---|
| cosent-form-test-document_p001 | | | |
| sample_report_p001 | | | |
| pub_bmcpubh_PMC13595506_p8-10_p002 | | | |
| cosent-form-test-document_p002（对照） | | | |

## 4 结论（勾选其一，分支预裁决）

- ☐ **A_PASS**（P* 达标降幅 ≥50%）→ **过闸路径恢复**：以 P* 参数重产双集 → T1b 复测（t1b_downstream_diff.py v1.2.1）→ PASS 即过闸放行 AgentE；T1b 仍 DRIFT → 回报（此时漂移非参数面）
- ☐ **B_NOALIGN**（无组达标）→ 可调参数假设排除 → **引擎重评报 Ying / P-046 立项层**（替换选型回炉，T1b 冻结维持）
- ☐ **UNRUN**（环境不可执行）→ 附报错原文

## 5 agentD 审读（过闸判定回收，agentD 填）

- 审读人/日期：____
- 判定：____
