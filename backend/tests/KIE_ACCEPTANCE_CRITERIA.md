# KIE Acceptance Criteria Baseline

Last updated: 2026-04-10
Scope: Tracker item 1 (KIE field extraction quality)

## Sample Matrix (invoice)

Use the following baseline sample set (3 layouts):

1. test_data/testfiles/invoices/invoice_sample_01.pdf
2. test_data/testfiles/invoices/receipt-invoice-like.png
3. test_data/testfiles/invoices/sample-invoice.png

## Chosen Acceptance Rule

Rule ID: KIE-ACCEPT-001

When quality.kie_stage == "completed":
- Accept kie_fields_count == 0 as contract-valid.
- Accept kie_fields_count > 0 as hit.
- Reject only invalid numeric values (for example negative counts).

Rationale:
- Current stabilization phase focuses on contract consistency and pipeline closure first.
- Field hit rate is tracked as a quality metric and should not block completion contract.

## Reporting Convention

Per sample, record at least:
- sample_path
- kie_stage
- kie_fields_count
- accepted (true/false)
- note (hit/miss)

## Test Entry

Regression skeleton is implemented in:
- backend/tests/test_kie_acceptance_baseline.py

Quick run (contract-only unit tests):

```bash
cd backend
pytest -q tests/test_kie_acceptance_baseline.py -k "rule or matrix"
```

Optional cloud smoke run (in-process API + KIE path):

```bash
cd backend
DOCUVISION_RUN_KIE_ACCEPTANCE=1 pytest -q tests/test_kie_acceptance_baseline.py -k smoke -s
```
