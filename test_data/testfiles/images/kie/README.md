# KIE 卡证验收样例

本目录为 **文档级 KIE** 云测固定样例（与 [doc_types.md](../../../acceptance/doc_types.md) 对齐）。

| 文件 | document_type | 说明 |
|------|----------------|------|
| `id_card_sample_01.jpg` | `id_card` | 历史样例（非标准中文身份证版式，002 仍可用） |
| `id_card_sample_02.jpg` | `id_card` | 合成中文身份证 · **清晰** |
| `id_card_sample_03.jpg` | `id_card` | 合成中文身份证 · **倾斜 + JPEG 压缩** |
| `id_card_sample_04.jpg` | `id_card` | 合成中文身份证 · **轻微模糊** |
| `passport_sample_01.png` | `passport` | 护照样例 |
| `bank_card_sample_01.png` | `bank_card` | 银行卡样例 |

## 合成身份证 ground-truth（虚构，仅供验收）

| 文件 | name | id_number |
|------|------|-----------|
| `id_card_sample_02.jpg` | 张伟 | 110101199001011234 |
| `id_card_sample_03.jpg` | 李芳 | 32010219880515231X |
| `id_card_sample_04.jpg` | 王强 | 440105199203073456 |

Cloud 阶段 D 对 `id_card` 额外适用 **KIE-ACCEPT-003**（`name` + 合法 18 位 `id_number`），见 [KIE_ACCEPTANCE_CRITERIA.md](../../../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md)。

重新生成 02～04（**生成前**会做标签/数值/照片区 bbox 自检，失败则不写入）：

```bash
# Linux / macOS / Cloud（需 Pillow）
pip install Pillow
python test_data/scripts/generate_kie_id_card_samples.py
python test_data/scripts/validate_kie_id_card_samples.py   # 仅校验，可选
```

```powershell
# Windows（需 .NET System.Drawing）
powershell -ExecutionPolicy Bypass -File test_data/scripts/generate_kie_id_card_samples.ps1
```

**版式**：标签列宽按「公民身份号码」动态计算（`value_x≈213`）；**18 位号码单独一行**，避免与标签横向重叠。旧版 02～04 若出现标签与数值压线，请用上述脚本重新生成。

无 Pillow 时请勿删除已提交的 JPG；02～04 应与脚本输出一致。
