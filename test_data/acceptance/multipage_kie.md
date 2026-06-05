# Multipage KIE acceptance (Pro)

Rules extend [KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md).

| Rule ID | Check |
|---------|--------|
| **MP-001** | `kie_pages=1` on `invoice_sample_01.pdf`: KIE-ACCEPT-001 + 002 unchanged vs Release 1.0 |
| **MP-002** | `kie_pages=all` on `invoices/multipage/invoice_multipage_2p_header_detail.pdf`: `kie_stage=completed`, `quality.kie_pages_processed >= 2`, `quality.kie_multipage_merge=true` |
| **MP-003** | Default (no `kie_pages`): identical to MP-001 semantics (page 1 only) |

Samples: `test_data/testfiles/invoices/multipage/`. Generate PDFs with `test_data/scripts/build_multipage_kie_fixtures.py`.

Cloud: [CLOUD_VALIDATION.md](../../docs/architecture/CLOUD_VALIDATION.md) phase MP.
