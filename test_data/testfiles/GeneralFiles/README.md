# GeneralFiles — Trial / Cloud Test Samples

| File | Purpose | Suggested track |
|------|---------|-----------------|
| `financial_report_01.pdf` | Bordered transaction table (Acme Q1) | Lite + Pro `financial_report` KIE |
| `financial_report_02.pdf` | Alternate vendor layout (GlobalFin, ASCII-safe) | Lite + Pro KIE |
| `bank_statement_sample.pdf` | Bank statement with Date/Amount/Balance | Lite table → transactions mapping |
| `transaction_ledger_unbordered.pdf` | Monospace columns, weak borders | Lite borderless / text routing |
| `financial_report_scansim.pdf` | Sparse layout | Lite scan-profile / OCR path |

Regenerate: `node test_data/scripts/generate_general_testfiles_pure.mjs`
