# Multipage receipt fixtures (Pro KIE)

| File | Pages | Sources |
|------|-------|---------|
| `receipt_multipage_2p.pdf` | 2 | `receipt-with-tips.png` + `contoso-receipt.png` |

Run `test_data/scripts/build_multipage_kie_fixtures.py` to generate PDFs.

## Cloud expectations

- `document_type=receipt`, `enable_kie=1`
- `kie_pages=all`: `kie_pages_processed >= 2`; 001/002 on merged fields.
