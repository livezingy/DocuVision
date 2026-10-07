"""Evidence findings schema contract (single source of truth, P-029 design L1).

Three gates verify FindingRecord values: quote grounding (A), hedge fidelity (B),
slot completeness (C). The PICO template and verifier bind to PROMPT_VERSION here;
mismatch = gate ERROR (D7). PicoSlots is the first slot template; new domains
register via register_slot_template. Fail-closed: silent nulls rejected, unreported
slots must be the literal NOT_REPORTED, rejected findings need a ledger entry.
"""
from __future__ import annotations

import re
from typing import Dict, Literal, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

SCHEMA_VERSION = "evidence-findings/1.0"
PROMPT_VERSION = "v4"
NOT_REPORTED = "NOT_REPORTED"

# Upstream spellings that MUST be canonicalized to NOT_REPORTED before validation (X1-4).
_UNREPORTED_VARIANTS = {"not_reported", "not reported", "not specified", "none"}

FINDING_ID_RE = re.compile(r"^F-[0-9]{3}$")
SHA12_RE = re.compile(r"^[0-9a-f]{12}$")

ClaimType = Literal["original_finding", "background_citation", "speculation", "limitations"]
Verdict = Literal["verbatim_exact", "near_match", "unsupported"]
FidelityKind = Literal["faithful", "overclaim", "add_hedge"]
RejectClass = Literal["unsupported", "overclaim"]
LedgerAxis = Literal["A", "B"]


class EvidenceSchemaError(ValueError):
    """Contract-level binding failure (version drift, unknown domain)."""


def check_prompt_version_binding(template_version: Optional[str]) -> None:
    """Bind the kie_configs PICO template header version to this contract (L1/D7)."""
    if template_version != PROMPT_VERSION:
        raise EvidenceSchemaError(f"prompt version binding mismatch: template={template_version!r} contract={PROMPT_VERSION!r}")


class SourceRef(BaseModel):
    """Provenance of one finding."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    page_num: int
    sha12: Optional[str] = None
    doi: Optional[str] = None

    @field_validator("paper_id")
    @classmethod
    def _paper_id_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("paper_id must be a non-empty string")
        return value

    @field_validator("sha12")
    @classmethod
    def _sha12_shape(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not SHA12_RE.match(value):
            raise ValueError("sha12 must be 12 lowercase hex chars")
        return value


class PicoSlots(BaseModel):
    """First domain slot template: PICO (scientific literature)."""

    model_config = ConfigDict(extra="forbid")

    population: str
    intervention: str
    comparator: str
    outcome: str
    follow_up: str

    @field_validator("population", "intervention", "comparator", "outcome", "follow_up")
    @classmethod
    def _slot_canonical(cls, value: str) -> str:
        if value == NOT_REPORTED:
            return value
        if not value.strip():
            raise ValueError("slot must be a non-empty string or NOT_REPORTED (silent null forbidden)")
        if value.lower() in _UNREPORTED_VARIANTS:
            raise ValueError(f"slot must use the literal {NOT_REPORTED!r}, got variant {value!r}")
        return value


SLOT_TEMPLATES: Dict[str, Type[BaseModel]] = {"pico": PicoSlots}


def register_slot_template(domain: str, slots_cls: Type[BaseModel]) -> None:
    """Register a new domain slot template; re-registering an existing domain is refused."""
    if domain in SLOT_TEMPLATES:
        raise EvidenceSchemaError(f"slot template already registered: {domain!r}")
    SLOT_TEMPLATES[domain] = slots_cls


def get_slot_template(domain: str) -> Type[BaseModel]:
    if domain not in SLOT_TEMPLATES:
        raise EvidenceSchemaError(f"unknown slot template domain: {domain!r}")
    return SLOT_TEMPLATES[domain]


class HedgeFidelity(BaseModel):
    """Gate B result: hedge-word sets of quote vs claim plus the verdict."""

    model_config = ConfigDict(extra="forbid")

    source_hedge_terms: list
    claim_hedge_terms: list
    fidelity: FidelityKind


class LedgerEntry(BaseModel):
    """Rejection record written to failure_ledger.json (fail-closed, design L4)."""

    model_config = ConfigDict(extra="forbid")

    reject_class: RejectClass
    axis: LedgerAxis
    excerpt: str


class FindingRecord(BaseModel):
    """One evidence-verified finding (design L1)."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    source: SourceRef
    quote: str
    claim: str
    quote_span: Optional[Tuple[int, int]] = None
    pico: PicoSlots
    claim_type: ClaimType
    verdict: Verdict
    hedge: HedgeFidelity
    ledger: Optional[LedgerEntry] = None

    @field_validator("finding_id")
    @classmethod
    def _finding_id_shape(cls, value: str) -> str:
        if not FINDING_ID_RE.match(value):
            raise ValueError("finding_id must match F-[0-9]{3}")
        return value

    @field_validator("quote", "claim")
    @classmethod
    def _text_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("quote/claim must be non-empty")
        return value

    @field_validator("quote_span")
    @classmethod
    def _span_shape(cls, value: Optional[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        if value is None:
            return None
        if len(value) != 2 or value[0] < 0 or value[1] < value[0]:
            raise ValueError("quote_span must be [start, end] with 0 <= start <= end")
        return value

    @model_validator(mode="after")
    def _ledger_integrity(self) -> "FindingRecord":
        rejected = self.verdict == "unsupported" or self.hedge.fidelity == "overclaim"
        if rejected and self.ledger is None:
            raise ValueError("rejected finding (unsupported/overclaim) requires a ledger entry")
        if not rejected and self.ledger is not None:
            raise ValueError("ledger is only written for rejected findings")
        if self.ledger is not None:
            expected = "overclaim" if self.hedge.fidelity == "overclaim" else "unsupported"
            if self.ledger.reject_class != expected:
                raise ValueError(f"ledger.reject_class={self.ledger.reject_class!r} contradicts {self.verdict!r}/{self.hedge.fidelity!r}")
        return self


def findings_jsonl_line(record: FindingRecord) -> dict:
    """One findings JSONL line: envelope versions + the record (design L4)."""
    line: Dict[str, object] = {"schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION}
    line.update(record.model_dump(mode="json"))
    return line


def parse_findings_jsonl_line(obj: object) -> FindingRecord:
    """Parse one findings JSONL line, enforcing envelope version binding."""
    if not isinstance(obj, dict):
        raise EvidenceSchemaError("findings line must be a JSON object")
    check_prompt_version_binding(obj.get("prompt_version"))
    if obj.get("schema_version") != SCHEMA_VERSION:
        raise EvidenceSchemaError(f"schema version mismatch: got {obj.get('schema_version')!r}, expected {SCHEMA_VERSION!r}")
    payload = {k: v for k, v in obj.items() if k not in ("schema_version", "prompt_version")}
    return FindingRecord.model_validate(payload)
