"""Convert the local sciextract pilot reading into the tracked P-029 golden set.

Offline QA tool (scripts/qa/, never on a service path). Reads the handover
material from a local directory (default: docs/R&D/runs/P029) and writes the
two tracked golden files:

  backend/tests/evidence/golden/verified.jsonl        45 FindingRecord lines
  backend/tests/evidence/golden/grounding_pages.jsonl page-level grounding texts

Conversion rules are pinned in the P-029 execution record (X1 conversion
rules): join on grounding_page_key / (paper, page); fid renumbered F-001..
F-045 in file order; unreported slot spellings -> the literal NOT_REPORTED;
statement_type limitation -> limitations; quote_stage exact / trailing_token /
paraphrase -> verbatim_exact / near_match / unsupported; source.sha12 =
grounding page sha256[:12]; doi extracted from the page norm text when
present; hedge.source_hedge_terms = handover ground truth, claim_hedge_terms
and fidelity recomputed by the verifier. The run is deterministic -- two runs
must be byte-identical (scripts/measure discipline, design D6).

Usage: python scripts/qa/convert_golden.py [--source DIR] [--check]
  --check  re-run and compare against the tracked files byte-for-byte
           (non-zero exit on drift).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.evidence import verifier  # noqa: E402
from app.services.evidence.gate import canonicalize_slots  # noqa: E402

DEFAULT_SOURCE = ROOT / "docs" / "R&D" / "runs" / "P029"
GOLDEN_DIR = ROOT / "backend" / "tests" / "evidence" / "golden"

VERDICT_MAP = {"exact": "verbatim_exact", "trailing_token": "near_match", "paraphrase": "unsupported"}
DOI_RE = re.compile(r"https?://(?:dx\.)?doi\.org/([^\s\"<>]+)")


def _doi_from_text(text: str):
    match = DOI_RE.search(text)
    if not match:
        return None
    return match.group(1).rstrip(".,;)")


def convert(source_dir: Path) -> tuple:
    pages = {}
    for line in (source_dir / "grounding_pages.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            pages[record["key"]] = record
    findings = [
        json.loads(line)
        for line in (source_dir / "verified_grounding.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    out_pages = []
    for key in sorted(pages):
        page = pages[key]
        out_pages.append(
            {
                "grounding_page_key": page["key"],
                "paper": page["paper"],
                "page": page["page"],
                "sha256": page["sha256"],
                "sha12": page["sha256"][:12],
                "doi": _doi_from_text(page.get("grounding_block_norm", "")),
                "n_blocks": page.get("n_blocks"),
                "chars": page.get("chars"),
                "grounding_block_norm": page["grounding_block_norm"],
            }
        )

    out_records = []
    for idx, finding in enumerate(findings, start=1):
        page = pages[finding["grounding_page_key"]]
        hay = page["grounding_block_norm"]
        match = verifier.classify_quote(finding["quote"], hay)
        ground_hedges = finding.get("hedge_groundtruth", "none")
        source_terms = [] if ground_hedges == "none" else sorted(set(ground_hedges.split(",")))
        claim_terms = sorted(verifier.hedge_set(str(finding.get("statement", ""))))
        if set(source_terms) - set(claim_terms):
            fidelity = "overclaim"
        elif set(claim_terms) - set(source_terms):
            fidelity = "add_hedge"
        else:
            fidelity = "faithful"
        statement_type = finding.get("statement_type")
        verdict = VERDICT_MAP[finding["quote_stage"]]
        # Design L1: a rejected finding (unsupported / overclaim) must carry a
        # ledger entry; golden rejects are quote-grounding rejects (axis A).
        ledger = None
        if verdict == "unsupported":
            ledger = {
                "reject_class": "overclaim" if fidelity == "overclaim" else "unsupported",
                "axis": "B" if fidelity == "overclaim" else "A",
                "excerpt": str(finding["quote"])[:80],
            }
        out_records.append(
            {
                "finding_id": f"F-{idx:03d}",
                "source": {
                    "paper_id": str(finding["paper"]).removesuffix(".bin"),
                    "page_num": finding["page"],
                    "sha12": page["sha256"][:12],
                    "doi": _doi_from_text(hay),
                },
                "quote": finding["quote"],
                "claim": finding["statement"],
                "quote_span": list(match.span) if match.span else None,
                "pico": canonicalize_slots(finding),
                "claim_type": "limitations" if statement_type == "limitation" else statement_type,
                "verdict": verdict,
                "hedge": {
                    "source_hedge_terms": source_terms,
                    "claim_hedge_terms": claim_terms,
                    "fidelity": fidelity,
                },
                "ledger": ledger,
                "grounding_page_key": finding["grounding_page_key"],
            }
        )
    return out_records, out_pages


def _write(lines: list, path: Path) -> None:
    path.write_text(
        "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines),
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    records, pages = convert(Path(args.source))
    if args.check:
        rc = 0
        for lines, name in ((records, "verified.jsonl"), (pages, "grounding_pages.jsonl")):
            want = "".join(json.dumps(line, ensure_ascii=False) + "\n" for line in lines)
            have = (GOLDEN_DIR / name).read_text(encoding="utf-8")
            status = "ok" if want == have else "DRIFT"
            if want != have:
                rc = 1
            print(f"CHECK {name}: {status}")
        return rc

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    _write(records, GOLDEN_DIR / "verified.jsonl")
    _write(pages, GOLDEN_DIR / "grounding_pages.jsonl")
    digest = hashlib.sha256(
        (GOLDEN_DIR / "verified.jsonl").read_bytes()
    ).hexdigest()[:12]
    print(f"OK records={len(records)} pages={len(pages)} verified.jsonl sha12={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
