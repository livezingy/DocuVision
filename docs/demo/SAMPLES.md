# Trial demo sample manifest

Pre-test these before a live 30-minute session.

> **Lite 已随 v1.8 退役**（`apps/lite/**` 已删除）。本文只覆盖 Pro 轨。

| # | Purpose | Path |
|---|---------|------|
| 1 | Invoice KIE | `test_data/testfiles/invoices/` (see [acceptance QUICK_START](../../test_data/acceptance/QUICK_START.md)) |
| 2 | Receipt KIE | `test_data/testfiles/receipts/` |
| 3 | Table mapping (bank statement) | `test_data/testfiles/GeneralFiles/bank_statement_sample.pdf` |

## Pre-flight checklist

- [ ] Pro health + KIE warm: `curl http://127.0.0.1:8000/api/v1/health`
- [ ] Run sample #1 in Pro UI → Fields tab + Export JSON downloads real result
- [ ] Run sample #3 → Processing **Table mapping** → **Mapped rows** tab populates

See [TRIAL_DEMO.md](./TRIAL_DEMO.md) for full setup.
