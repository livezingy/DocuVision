# KIE 卡证验收样例

本目录为 **文档级 KIE** 云测固定样例（与 [doc_types.md](../../../acceptance/doc_types.md) 对齐）。

| 文件 | document_type | 说明 |
|------|----------------|------|
| `id_card_sample_01.jpg` | `id_card` | 合成/测试用证件图（源自仓库 `testfiles/IDCard`，仅供验收） |
| `passport_sample_01.png` | `passport` | 护照样例 |
| `bank_card_sample_01.png` | `bank_card` | 银行卡样例 |

重新生成（需 Python + Pillow）：

```bash
python test_data/scripts/generate_kie_card_samples.py
```

无 Pillow 时可用仓库内既有图复制到本目录（与当前文件等价）。
