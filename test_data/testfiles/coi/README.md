# COI test fixtures (P-030b, M1)

ACORD 25 Certificate of Insurance fixtures plus one purpose-built negative
case, used by the document-type classifier bidirectional regression (X6) and
the coi KIE smoke checks.

## Provenance

Extracted from the frozen COI extraction pilot corpus pack
(`SOURCE_DOCUMENTS.pdf`, local-only under `docs/R&D/runs/P030_P031/`).
The pack carries ten originals as embedded attachments with build-time
sha256 digests; all five fixtures below were hash-verified against the
pack's own digest table (10/10 attachments matched). The pack declares
"nothing from a real client": four documents are synthetic watermarked
fixtures, six are certificates published as samples on public institutional
and insurer websites.

## Deidentification record (X5)

Pattern sweep per file (SSN/EIN three-variant regex, e-mail, phone) plus a
visual page-1 inspection of the rendered page:

| fixture | source doc_id | channel | original sha256 (first 16) | committed sha256 (first 16) | redaction action |
|---|---|---|---|---|---|
| coi_acord25_synth_green.pdf | synth_green | synthetic (watermarked "NOT A REAL FILING") | e3aebf75f6028191 | e3aebf75f6028191 | none needed |
| coi_acord25_synth_yellow.pdf | synth_yellow | synthetic (watermarked) | d28a59485c8dbd11 | d28a59485c8dbd11 | none needed |
| coi_acord25_cornell_sample.pdf | cornell_2014 | public institutional sample (Cornell University) | 14c6b26b6ba65a4b | 14c6b26b6ba65a4b | none needed |
| coi_acord25_tampa_sample.pdf | tampa_2016 | public institutional sample (City of Tampa, "SAMPLE" watermarked) | 92b4319661d40305 | 92b4319661d40305 | none needed |
| coi_negative_fl_exemption.pdf | synth_fl | negative case (FL workers-comp exemption letter template, fields blank) | 7b78f3b6207f9c5f | 7b78f3b6207f9c5f | none needed |

Findings and decisions:

- Synthetic fixtures carry fabricated values only (fictional carrier "Mutual
  of Fictional County", placeholder EIN `59-1234567` in the description of
  operations, 555-prefix phone). Kept verbatim: nothing real to redact, and
  the EIN-shaped string is useful test data for the PII mask domain.
- cornell / tampa are publisher-redacted institutional samples filled with
  placeholders (SAMPLE BROKER / SAMPLE VENDOR / INSURANCE COMPANY NAME /
  policy `123456789`). No tax identifiers, no personal PII found.
- The committed set intentionally excludes the two broker-published samples
  that carry producer contact e-mail boxes and a scanned signature
  (real_pic01/07/10 family): public business data, but not needed for the
  fixture matrix, so the conservative call is to leave them out of the repo.
- `coi_negative_fl_exemption.pdf` must NOT classify as coi (it is the
  negative case: reading an exemption letter as an ACORD certificate is a
  classification failure).
