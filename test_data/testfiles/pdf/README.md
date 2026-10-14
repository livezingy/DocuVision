# pdf — 报告 / 通用 PDF 夹具

目录语义（"纯文本/报告 PDF"）与命名规则见 [`../README.md`](../README.md)；
按文档类型的验收矩阵见 [`../../acceptance/doc_types.md`](../../acceptance/doc_types.md)。

| 文件 | 用途 | 生成方式 |
|------|------|----------|
| `pub_bmcpubh_PMC13595506_p8-10.pdf` | D8 表格几何 / 旋转帧验证：正立负对照 + 内容级 90° 旋转页 + 混合方向（表级 90/270 错帧真件） | `extract_pdf_pages.py`（见下） |
| `pub_bmcmed_PMC13613656_p6.pdf` | D8 **多表页回归对照**：同页双表且两表均正立（patch 应全程 no-op） | `extract_pdf_pages.py`（见下） |
| `sample_report.pdf` / `financial_report.pdf` / `cosent-form-test-document.pdf` / `sample-layout.pdf` | 历史入库样例（本文件只登记本次新增；用途见 `../../acceptance/` 各矩阵） | — |

---

## `pub_bmcpubh_PMC13595506_p8-10.pdf`（2026-10-12 入库）

**用途**：验证 PaddleX 表格"两套几何"的帧问题（findings §6 ISSUE-1 与新增的 N2 帧污染）——
一页正立负对照 + 一页内容级 90° 旋转（引擎 doc 级消解，作回归对照）+ 一页混合方向（**表级 90/270 错帧真件**），
覆盖既有 `GeneralFiles/bank_statement_sample.pdf`（只含 180°）未覆盖的 90/270 表级路径。

**Provenance**：派生自同源 OA 夹具 [`../pico/pub_bmcpubh_PMC13595506.pdf`](../pico/pub_bmcpubh_PMC13595506.pdf)
（DOI `10.1186/s12889-026-29388-5` · PMCID `PMC13595506` · BMC Public Health · CC BY），
取第 **8–10** 页，逐页 `insert_pdf`，零改写（内容与原页逐页等价）。许可与去标识记录见
[`../pico/README.md`](../pico/README.md)（同一篇 CC BY OA 论文）。

**每页特征**（三页 `/Rotate` 均为 `0`、MediaBox 纵向 595×794；旋转为**内容流烘焙** ⇒
`pdf-rotation-classes.md` 的 **R2 载体**，非元数据 R1）：

| 派生页 | 源页 | 内容方向（PyMuPDF line `dir`） | 表格 | 角色 |
|--------|------|-------------------------------|------|------|
| 1 | p8 | 正立（151 行全 `(1,0)`） | 1（Table 1） | **负对照**：不应触发方向校正 |
| 2 | p9 | **旋转 90°**（234 行 `(0,-1)` + 2 行页眉 `(1,0)`） | **2（Table 2 + Table 3）** | **doc 级旋转回归对照**：引擎 `doc_preprocessor_res.angle=270` 已消解 ⇒ 表级未触发，patch 应 no-op |
| 3 | p10 | 混合（129 行 `(0,-1)` + 56 行 `(1,0)`） | 1（Table 4） | **表级 90/270 错帧真件**：装前 `frame_hits={0,1,16}`、`measured=False` |

**内容指纹**（**字节 sha256 不可复现**：PyMuPDF 每次 `save` 写入随机 `/ID`，同一命令两次运行字节不同
——故按 [`verify_assets.py`](../../scripts/verify_assets.py) 的**内容级**口径登记，而非字节）：

```
pages = 3
words = 1788
text_sha256 = 2BE1B0840F8C4BADC3A79ADF54061C4AA5E081CC85A8B761362AA4DA17D38506
per_page    = p1 words=702 text_sha256=0A6CDA3FB7DC4AB333FEB64420B8BAD368FF8D79494D9D43A3E387936F4602ED
              p2 words=437 text_sha256=6AC810110A5E9E955D05299E5428E2C77158604A8AC80B7696C4174A1EA88CD5
              p3 words=649 text_sha256=AFDC5BE5AC01A17B5339D7ACA102B42CE4D3F1663D5D9BB243B420E7B89C43B8
```

**Regenerate**：

```powershell
D:\USERS\livez\Python\python.exe test_data\scripts\extract_pdf_pages.py `
  --src test_data/testfiles/pico/pub_bmcpubh_PMC13595506.pdf `
  --first 8 --last 10 `
  --out test_data/testfiles/pdf/pub_bmcpubh_PMC13595506_p8-10.pdf
```

重跑后脚本打印的 `text_sha256` 应与上表一致（内容确定；字节不同属预期）。

**引擎实测备注（2026-10-12，官方 paddlex 3.3.12 基线）**：p2 页由 **doc 前处理消解**
（`doc_preprocessor_res.angle=270`、输出横向）⇒ 表级未触发，实为 **doc 级回归对照**；
p3 页 `doc.angle=0` 但两套几何错帧（`frame_hits={raw:0,flip:1,rot180:16}`、`measured=False`）
⇒ **表级 90/270 错帧真件**，正是本夹具的核心价值。

---

## `pub_bmcmed_PMC13613656_p6.pdf`（2026-10-12 入库）

**用途**：**多表页回归对照**——单页含 **2 个表**（Table 2 + Table 3）且**两表均正立**（无非零方向），
用于验证 patch 在"真正的多表页"上**全程 no-op**（不误伤多表循环、不引入帧污染）。
注意：它**不是** T4 正对照（T4 需同页 ≥1 个表级 `angle≠0` 的表），只把多表页的回归面做扎实。

**Provenance**：派生自同源 OA 夹具 [`../pico/pub_bmcmed_PMC13613656.pdf`](../pico/pub_bmcmed_PMC13613656.pdf)
（DOI `10.1186/s12916-026-05037-x` · PMCID `PMC13613656` · BMC medicine · CC BY），
取第 **6** 页，`insert_pdf` 单页，零改写。许可与去标识记录见 [`../pico/README.md`](../pico/README.md)。

**页面特征**：`/Rotate=0`、纵向 595×794、全正立（`up_ratio=1.0`）；
2 个表（Table 2 `Biopsy information and pathological diagnoses`、Table 3 `Primary Outcomes`），
**无竖线三线表**（页内线条 h/v = 28/0）。

**内容指纹**（同前：字节 sha256 不可复现，登记内容级）：

```
pages = 1
words = 532
text_sha256 = AB1FC3F76815F36B83D1CEFA1B187A4E9F4DBEA7E32D7F399738FEFEF0998AF6
```

**Regenerate**：

```powershell
D:\USERS\livez\Python\python.exe test_data\scripts\extract_pdf_pages.py `
  --src test_data/testfiles/pico/pub_bmcmed_PMC13613656.pdf `
  --first 6 --last 6 `
  --out test_data/testfiles/pdf/pub_bmcmed_PMC13613656_p6.pdf
```

---

**相关（两个夹具通用）**：`docs/architecture/pp-structurev3-official-findings.md` §6
（表格几何与方向校正 / 180° 类）——含**合成最小复现**；含夹具读数与逐格复算的**完整实测版**为
local-only（`docs/R&D/knowledge/`，不入库）。
