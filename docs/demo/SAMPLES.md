# Trial demo sample manifest

Pre-test these before a live 30-minute session.

| # | Track | Purpose | Path |
|---|-------|---------|------|
| 1 | Lite | Bordered digital table (regression fixture) | `apps/lite/backend/tests/fixtures/sample_bordered.pdf` |
| 2 | Lite | Second vendor / statement PDF | Bring client born-digital PDF with transaction table |
| 3 | Pro | Invoice KIE | `test_data/testfiles/invoices/` (see acceptance QUICK_START) |
| 4 | Pro | Receipt KIE | `test_data/testfiles/receipts/` |

## Pre-flight checklist

- [ ] Lite health: `curl http://127.0.0.1:8001/api/v1/lite/health`
- [ ] Pro health + KIE warm: `curl http://127.0.0.1:8000/api/v1/health`
- [ ] Run sample #1 in Lite UI → Tables + Transactions + Mapped tabs populate
- [ ] Run sample #3 in Pro UI → Fields tab + Export JSON downloads real result
- [ ] Lite Save → Validation dashboard shows record

See [TRIAL_DEMO.md](./TRIAL_DEMO.md) for full setup.
