"""Evidence gate (P-029 design L4/L5): fail-closed export, failure ledger, HITL routing.

Consumes PICO-shaped finding candidates (a KIE output ``findings`` list),
verifies each against per-page grounding text via the verifier, and produces:

  * findings JSONL lines (schema envelope + FindingRecord) for candidates
    that become valid records
  * failure ledger entries for rejected findings (unsupported / overclaim)
  * HITL review items for near_match findings and for candidates that cannot
    become records (incomplete slots / schema-invalid shapes)

Fail-closed rules (design L4; interpretations registered as X1-8):
  * missing or untrusted grounding text -> unsupported (reject, axis A);
    quote grounding only runs on text-layer-trusted pages (design A7)
  * overclaim fidelity -> reject (axis B) even when grounded
  * any rejected record in the batch -> findings export blocked
  * candidates that cannot become records are routed to human review --
    never silently dropped, never silently corrected

This module is the only bridge between the evidence layer and the pipeline;
the verifier stays import-free of KIE code.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from pydantic import ValidationError

from app.services.evidence import verifier
from app.services.evidence.findings_schema import (
    NOT_REPORTED,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    FindingRecord,
    LedgerEntry,
    SourceRef,
    findings_jsonl_line,
)
from app.services.evidence.grounding import (
    attribute_candidates,
    grounding_source,
    trusted_grounding_page_set,
)
from app.services.evidence.normalize import normalize

EVIDENCE_HITL_NEAR_MATCH = "near_match_review"
EVIDENCE_HITL_SLOT = "evidence_slot_incomplete"
EVIDENCE_HITL_SCHEMA = "evidence_schema_invalid"


def _text_first_enabled() -> bool:
    """P-032 feature flag (default off): text-first extraction + grounding."""
    try:
        from app.core.config import settings

        return bool(getattr(settings, "EVIDENCE_TEXT_FIRST", False))
    except Exception:
        return False

_SLOT_KEYS = ("population", "intervention", "comparator", "outcome", "follow_up")

# Spelling variants that must be canonicalized to NOT_REPORTED (execution
# record X1-4 conversion rule; mirrors findings_schema's rejection list).
_UNREPORTED_VARIANTS = {"not_reported", "not reported", "not specified", "none"}


def closed_lists_meta() -> Dict[str, Any]:
    """Closed-list references embedded in HITL payloads (design L4)."""
    with verifier._CLOSED_LISTS_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        "closed_lists_version": data.get("schema_version"),
        "hedge_en": list(data.get("hedge", {}).get("en", [])),
        "hedge_zh": list(data.get("hedge", {}).get("zh", [])),
    }


def canonicalize_slots(raw: Dict[str, Any]) -> Dict[str, str]:
    """Map unreported spellings to the NOT_REPORTED literal; pass real values through."""
    out: Dict[str, str] = {}
    for key in _SLOT_KEYS:
        value = raw.get(key, raw.get("followup")) if key == "follow_up" else raw.get(key)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue  # left missing so Gate C flags it
            out[key] = NOT_REPORTED if stripped.lower() in _UNREPORTED_VARIANTS else value
        elif value is not None:
            out[key] = value
    return out


def _page_no_of(page: Dict[str, Any]) -> Optional[int]:
    """Resolve the 1-based page number from any fused/view page envelope key."""
    raw_no = page.get("page_num", page.get("page", page.get("page_id")))
    if raw_no is None:
        return None
    try:
        return int(raw_no)
    except (TypeError, ValueError):
        return None


def block_id_to_page(fused: Dict[str, Any]) -> Dict[str, int]:
    """Map fused ``block_id`` -> 1-based page number.

    Weak legacy hint only: the pico prompt injects just the schema (no block ids,
    no page text), so the model's ``quote_block`` is not a real fused ``block_id``
    and usually maps to nothing. Kept last in the resolution order; the reliable
    page is the one KIE actually processed (see ``enrich_candidate_pages``).
    """
    mapping: Dict[str, int] = {}
    for page in (fused or {}).get("pages", []):
        page_no = _page_no_of(page)
        if page_no is None:
            continue
        for block in page.get("blocks", []):
            bid = block.get("block_id", block.get("id"))
            if bid is None:
                continue
            mapping[str(bid)] = page_no
    return mapping


def _processed_single_page(
    kie_meta: Optional[Dict[str, Any]],
    kie_fields_by_page: Optional[Dict[str, Any]],
) -> Optional[int]:
    """The page KIE read when exactly one page was processed, else ``None``."""
    processed: List[int] = []
    if isinstance(kie_meta, dict):
        raw = kie_meta.get("kie_pages_processed")
        if isinstance(raw, (list, tuple)):
            processed = [p for p in raw if isinstance(p, int)]
    if len(processed) == 1:
        return processed[0]
    if isinstance(kie_fields_by_page, dict):
        keys = [k for k in kie_fields_by_page.keys() if str(k).isdigit()]
        if len(keys) == 1:
            return int(keys[0])
    return None


def enrich_candidate_pages(
    candidates: List[Dict[str, Any]],
    fused: Dict[str, Any],
    kie_meta: Optional[Dict[str, Any]] = None,
    kie_fields_by_page: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Inject a ``page`` into KIE finding candidates that lack one (P-029 X1-6 gap).

    P-031 E2E showed pipeline findings arrive with no ``page`` and fail closed.
    The fix (PENDING P-029 option 1) attributes them to the page KIE actually
    processed; ``quote_block`` is *not* usable for attribution because the pico
    prompt carries no block ids.

    Resolution order when ``candidate["page"]`` is absent/non-int:
      1. the single processed page (``kie_meta.kie_pages_processed`` / single-key
         ``kie_fields_by_page``) -- authoritative for the default 1-page run;
      2. fused page whose normalized text contains the normalized quote
         (multi-page findings);
      3. ``quote_block`` -> fused ``block_id`` (weak legacy hint, kept last).

    Candidates that resolve to no page stay untouched and are fail-closed by the
    gate (axis A), preserving the pinned contract.
    """
    page_texts = page_texts_from_fused(fused)
    single_page = _processed_single_page(kie_meta, kie_fields_by_page)
    block_page = block_id_to_page(fused)
    out: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            out.append(candidate)
            continue
        if isinstance(candidate.get("page"), int):
            out.append(candidate)
            continue
        resolved = single_page
        if resolved is None and page_texts:
            needle = normalize(str(candidate.get("quote") or ""))
            if needle:
                hits = [p for p, text in sorted(page_texts.items()) if needle in text]
                if hits:
                    resolved = hits[0]
        if resolved is None:
            qb = candidate.get("quote_block")
            if qb is not None:
                resolved = block_page.get(str(qb))
        if resolved is not None:
            candidate = dict(candidate)
            candidate["page"] = resolved
        out.append(candidate)
    return out


def page_texts_from_fused(fused: Dict[str, Any]) -> Dict[int, str]:
    """Per-page normalized grounding text from the fused envelope layer."""
    texts: Dict[int, str] = {}
    for page in (fused or {}).get("pages", []):
        page_no = _page_no_of(page)
        if page_no is None:
            continue
        chunks = [
            str((block.get("payload") or {}).get("text") or "")
            for block in page.get("blocks", [])
        ]
        texts[page_no] = normalize("\n".join(chunks))
    return texts


def trusted_page_set(file_path: str) -> Set[int]:
    """1-based page numbers whose text layer the E1 gatekeeper trusts (design A7)."""
    trusted: Set[int] = set()
    try:
        import fitz

        from app.services.page_text_trust import judge_page_trust

        with fitz.open(file_path) as doc:
            for index in range(doc.page_count):
                try:
                    if judge_page_trust(doc[index]).trusted:
                        trusted.add(index + 1)
                except Exception:  # single-page failure -> untrusted (fail-closed)
                    continue
    except Exception:
        return set()  # no trustable grounding at all -> all findings unsupported
    return trusted


def page_sha12(text: str) -> str:
    """Grounding-page hash prefix used as SourceRef.sha12 (X1 conversion rule)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


@dataclass
class EvidenceReport:
    """Batch outcome of one evidence gate run."""

    records: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    ledger: list = field(default_factory=list)
    hitl_payloads: list = field(default_factory=list)
    near_match: int = 0
    rejected: int = 0
    exported: int = 0
    stats: Dict[str, Any] = field(default_factory=dict)

    @property
    def export_allowed(self) -> bool:
        return self.rejected == 0


def _hitl_payload(fid: str, page: Any, detail: str, outcome: Any) -> Dict[str, Any]:
    payload = {
        "finding_id": fid,
        "page": page,
        "detail": detail,
        "matched_variant": outcome.matched_variant,
        "evidence_schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
    }
    payload.update(closed_lists_meta())
    return payload


def verify_candidates(
    candidates: List[Dict[str, Any]],
    page_texts: Dict[int, str],
    trusted_pages: Set[int],
    paper_id: str,
    doi: Optional[str] = None,
) -> EvidenceReport:
    """Run Gates A/B/C over finding candidates (pure, no I/O)."""
    report = EvidenceReport()
    variant_counts: Dict[str, int] = {}
    for idx, candidate in enumerate(candidates, start=1):
        fid = f"F-{idx:03d}"
        quote = str(candidate.get("quote", "") or "")
        claim = str(candidate.get("statement", "") or "")
        page = candidate.get("page")
        page_no = page if isinstance(page, int) else None
        slots = canonicalize_slots(candidate)
        hay = page_texts.get(page_no) if page_no is not None else None
        if hay is None or page_no not in trusted_pages:
            # Fail-closed: no trusted grounding text -> cannot admit (X1-8a).
            source_hedge = sorted(verifier.hedge_set(quote))
            claim_hedge = sorted(verifier.hedge_set(claim))
            if set(source_hedge) - set(claim_hedge):
                fidelity = verifier.OVERCLAIM
            elif set(claim_hedge) - set(source_hedge):
                fidelity = verifier.ADD_HEDGE
            else:
                fidelity = verifier.FAITHFUL
            outcome = verifier.VerifierOutcome(
                verdict=verifier.UNSUPPORTED,
                matched_variant=None,
                detail="grounding unavailable (missing or untrusted page)",
                span=None,
                source_hedge_terms=source_hedge,
                claim_hedge_terms=claim_hedge,
                fidelity=fidelity,
            )
        else:
            outcome = verifier.audit_finding(quote, claim, slots, hay)

        if outcome.matched_variant:
            variant_counts[outcome.matched_variant] = (
                variant_counts.get(outcome.matched_variant, 0) + 1
            )

        if outcome.slot_rows:
            # Incomplete slots cannot become records -> human review (X1-8b),
            # mirroring the handover's Gate C review semantics.
            report.hitl_payloads.append(
                (
                    EVIDENCE_HITL_SLOT,
                    _hitl_payload(fid, page_no, "; ".join(f"{s}: {r}" for s, r in outcome.slot_rows), outcome),
                )
            )
            report.stats["slot_incomplete"] = report.stats.get("slot_incomplete", 0) + 1
            continue

        ledger_entry = None
        if outcome.rejected:
            report.rejected += 1
            ledger_entry = LedgerEntry(
                reject_class=outcome.reject_class,
                axis="B" if outcome.reject_class == verifier.OVERCLAIM else "A",
                excerpt=quote[:80],
            )
            report.ledger.append(
                {
                    "finding_id": fid,
                    "reject_class": ledger_entry.reject_class,
                    "axis": ledger_entry.axis,
                    "excerpt": ledger_entry.excerpt,
                    "detail": outcome.detail,
                    "page": page_no,
                }
            )
        elif outcome.verdict == verifier.NEAR_MATCH:
            report.near_match += 1
            report.hitl_payloads.append(
                (EVIDENCE_HITL_NEAR_MATCH, _hitl_payload(fid, page_no, outcome.detail, outcome))
            )

        record_payload = {
            "finding_id": fid,
            "source": {
                "paper_id": paper_id,
                "page_num": page_no if page_no is not None else 0,
                "sha12": page_sha12(page_texts.get(page_no)) if page_no in (page_texts or {}) else None,
                "doi": doi,
            },
            "quote": quote,
            "claim": claim,
            "quote_span": list(outcome.span) if outcome.span else None,
            "pico": slots,
            "claim_type": "limitations" if candidate.get("statement_type") == "limitation" else candidate.get("statement_type"),
            "verdict": outcome.verdict,
            "hedge": {
                "source_hedge_terms": outcome.source_hedge_terms,
                "claim_hedge_terms": outcome.claim_hedge_terms,
                "fidelity": outcome.fidelity,
            },
            "ledger": ledger_entry,
        }
        try:
            record = FindingRecord.model_validate(record_payload)
        except ValidationError:
            # Schema-invalid candidate shape -> human review, never export (X1-8b).
            report.hitl_payloads.append(
                (
                    EVIDENCE_HITL_SCHEMA,
                    _hitl_payload(fid, page_no, "candidate does not satisfy the findings schema", outcome),
                )
            )
            report.stats["schema_invalid"] = report.stats.get("schema_invalid", 0) + 1
            if ledger_entry is not None:
                report.rejected -= 1
                report.ledger.pop()
            continue
        report.records.append(record)
        report.lines.append(findings_jsonl_line(record))
        report.exported += 1
    report.stats["matched_variants"] = variant_counts
    return report


async def run_evidence_gate(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Pipeline hook body (design L5): verify, route HITL, emit artifacts.

    Returns the ``evidence`` block stored in the task result; writes
    findings.jsonl / failure_ledger.json under the task debug artifacts
    directory when DEBUG_MODE is on.
    """
    result = ctx.get("result") or {}
    kie_fields = result.get("kie_fields") if isinstance(result.get("kie_fields"), dict) else {}
    candidates = kie_fields.get("findings") if isinstance(kie_fields, dict) else None
    raw_candidates = candidates
    text_first = _text_first_enabled()
    attribution: Dict[str, int] = {}
    page_texts: Dict[int, str] = {}
    trusted: Set[int] = set()
    if isinstance(candidates, list) and candidates:
        if text_first:
            # P-032 M4: deterministic attribution on the native text layer --
            # the same source the M1 payload fed the model; the
            # kie_pages_processed / quote_block heuristics are NOT consulted.
            source = grounding_source(str(ctx.get("file_path") or ""))
            candidates, attribution = attribute_candidates(candidates, source)
            page_texts = source.texts
            trusted = trusted_grounding_page_set(str(ctx.get("file_path") or ""))
        else:
            # P-029 page-attribution fix: pico KIE emits no page, so attribute each
            # finding to the page KIE processed before grounding (fail-closed if no
            # page can be resolved).
            candidates = enrich_candidate_pages(
                candidates,
                ctx.get("phase1_fused") or {},
                result.get("kie_meta"),
                result.get("kie_fields_by_page"),
            )
    block: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "export_allowed": True,
        "findings": [],
        "failure_ledger": [],
        "hitl_review_ids": [],
    }
    if not isinstance(candidates, list) or not candidates:
        block["note"] = "no evidence findings in kie output"
        return block

    paper_id = str(ctx.get("task", {}).get("file_name") or "unknown")
    if not text_first:
        page_texts = page_texts_from_fused(ctx.get("phase1_fused") or {})
        trusted = trusted_page_set(str(ctx.get("file_path") or ""))
    report = verify_candidates(candidates, page_texts, trusted, paper_id)

    from app.services.hitl_queue import hitl_queue

    for reason, payload in report.hitl_payloads:
        item = await hitl_queue.enqueue(
            ctx["task_id"], paper_id, reason, payload
        )
        block["hitl_review_ids"].append(item.review_id)

    block["findings"] = report.lines
    block["failure_ledger"] = report.ledger
    block["export_allowed"] = report.export_allowed
    # Self-diagnosing stats: distinguishes "page not injected" from "grounding
    # text missing/untrusted" (both otherwise surface as the same axis-A detail).
    before = sum(
        1 for c in raw_candidates
        if isinstance(c, dict) and isinstance(c.get("page"), int)
    ) if isinstance(raw_candidates, list) else 0
    after = sum(
        1 for c in candidates
        if isinstance(c, dict) and isinstance(c.get("page"), int)
    ) if isinstance(candidates, list) else 0
    block["stats"] = {
        **report.stats,
        **attribution,
        # text-first: deterministic verbatim hits (marker hint + ladder scan);
        # legacy: enrich before/after delta (P-029 semantics, unchanged)
        "page_injected": (
            attribution.get("marker_hint_hits", 0) + attribution.get("scan_hits", 0)
            if text_first
            else after - before
        ),
        "page_texts_pages": sorted(page_texts),
        "trusted_pages": sorted(trusted),
    }

    _write_artifacts(ctx, report)
    return block


def _write_artifacts(ctx: Dict[str, Any], report: EvidenceReport) -> None:
    """Persist findings JSONL + failure ledger to the task artifacts directory."""
    from app.core.config import settings

    if not getattr(settings, "DEBUG_MODE", False):
        return
    debug_dir = os.path.join(settings.DEBUG_OUTPUT_DIR, str(ctx.get("task_id") or "unknown"), "evidence")
    os.makedirs(debug_dir, exist_ok=True)
    with open(os.path.join(debug_dir, "findings.jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for line in report.lines:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    with open(os.path.join(debug_dir, "failure_ledger.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(report.ledger, fh, ensure_ascii=False, indent=1)
