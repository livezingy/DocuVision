# PICO test fixtures (P-031, M1/C1)

Open-access randomized-controlled-trial articles used as the calibration
corpus (C1) for the pico document-type keywords (P-031 X1) and as file-level
positive fixtures for the classifier bidirectional regression. The classifier
reads page 1 only.

## Provenance

Downloaded 2026-10-06 from publisher OA endpoints (BMC/Springer
counter|content PDF, PLOS printable file) after Europe PMC confirmed
isOpenAccess=y. Metadata (DOI/PMCID/license) from the Europe PMC REST API.
`pub_bmc_PMC10685505.pdf` and `pub_springer_PMC10719124.pdf` are the source
papers behind the evidence golden n-set (backend/tests/evidence/golden,
paper_ids pub_bmc / pub_springer),
so the keyword calibration is anchored to the same corpus as the evidence
layer, per the P-031 execution-package recommendation.

## Deidentification record

All five fixtures are published OA research articles (CC BY): aggregate trial
data, no subject-level identifiers; author names are published bibliographic
facts. Pattern sweep not applicable beyond that; no redaction performed
(committed sha256 == downloaded sha256).

| fixture | DOI | PMCID | journal | license | sha256 |
|---|---|---|---|---|---|
| pub_bmc_PMC10685505.pdf | 10.1186/s12871-023-02341-4 | PMC10685505 | BMC anesthesiology | cc by | ec273bd83a47c3ca6dbf9a86b80aff723b15e3bb8ae1deed742f6f9282a62a29 |
| pub_springer_PMC10719124.pdf | 10.1007/s00167-023-07634-2 | PMC10719124 | Knee surgery, sports traumatology, arthroscopy : official journal of the ESSKA | cc by | bad5ef1a3cdaaadcd5fdf439f17ba94d0d886c58171dc79808780e773503e2c6 |
| pub_bmcmed_PMC13613656.pdf | 10.1186/s12916-026-05037-x | PMC13613656 | BMC medicine | cc by | ce719de5bc158fc9e6cb6dab9c35e1ac8c10c5ce05ad42512a46447e40e6260e |
| pub_bmcpubh_PMC13595506.pdf | 10.1186/s12889-026-29388-5 | PMC13595506 | BMC public health | cc by | 26e0b51153c50157a4cb1f105a46958c49b4110613a7837eadfb33f8090b70d7 |
| pub_plosone_PMC13618946.pdf | 10.1371/journal.pone.0359282 | PMC13618946 | PloS one | cc by | bbcf4c7af4f9e9059cb6efb75348c17efa991906a7c030c687461ff7423ca821 |

## Calibration note

Keyword set ('randomized', 'controlled trial', 'placebo', 'double-blind',
'primary outcome') was selected from the measured hit matrix on these five
papers plus the business/COI negative set; words hitting any negative doc
('consent', 'informed consent' on the cosent form) were rejected per the
P-031 guardrail. Matrix and pre/post outputs live in the P-031 PR record.
