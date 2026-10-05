"""Evidence layer (P-029): independent verification of extraction findings.

Modules:
    findings_schema  -- FindingRecord contract, single source of truth (L1)
    verifier         -- Gate A/B/C verifier ported from the handover asset (L2)
    normalize        -- shared text normalizer for quote grounding (L2)
    gate             -- fail-closed gate, failure ledger, HITL routing (L4)

Independence discipline: this package must never import KIE extraction
modules and must not share matching/normalization code with them.
"""
