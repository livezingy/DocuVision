"""Gate B spot-check: SEMANTIC-RESIDUAL confirmation sample.

Positioning (post code-read of DocuVision's deterministic harness): verify_quotes.py
already does everything a deterministic scale can — it grounds each QUOTE to the
source PDF verbatim (Gate A) and mechanically diffs the closed hedge word-list
between QUOTE and STATEMENT. On the full auditable pool that literal diff returned
dehedge=0 / addhedge=0, i.e. the machine has ALREADY certified literal fidelity on
every row. The one thing the word-list structurally cannot see is a SEMANTIC hedge
expressed outside the list ('tends to', 'in most cases', passive framing, a
limited-sample qualifier softening a 'no difference' result).

This sheet is therefore NOT a from-scratch judgment task over the whole pool; it is
a small, seed-fixed confirmation SAMPLE whose only purpose is to estimate whether
that semantic residual is real. The human CONFIRMS or OVERTURNS the machine's
'faithful' verdict on each sampled row; a clean sample makes the machine's literal
verdict a defensible proxy for the pool.

Reads out/verified.jsonl, keeps auditable findings (verdict admit|review — a reject
quote is not verbatim, so fidelity cannot be judged), stratifies by paper x
hedge-bearing, and writes report/spotcheck_hedge.csv with empty HUMAN_JUDGE/NOTE
columns. If the pool is smaller than the sample quota it degrades to a census and
says so. Console output is ASCII; fixed SEED drives a reproducible stratified draw.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

TOPIC_DIR = Path(__file__).resolve().parent
REPORT_DIR = TOPIC_DIR / "report"
SEED = 20261003  # fixed; within-stratum random picks are reproducible across reruns
CONFIRM_N = 15   # confirmation SAMPLE, not a census of the pool

from verify_quotes import hedge_set  # single source of the closed hedge word list

RUBRIC = [
    "# Gate B - SEMANTIC-RESIDUAL confirmation sample (sciextract).",
    "# WHAT THE MACHINE ALREADY PROVED: verify_quotes.py grounds each QUOTE to the",
    "# source PDF verbatim (Gate A) and diffs the closed hedge word-list between QUOTE",
    "# and STATEMENT. On the full pool that literal diff returned dehedge=0 / addhedge=0,",
    "# so every MACHINE_VERDICT below is 'faithful'. This sheet does NOT re-derive that.",
    "# YOUR JOB: read QUOTE (the source truth) and STATEMENT (what we would publish),",
    "# then CONFIRM or OVERTURN the machine verdict. Fill HUMAN_JUDGE:",
    "#   confirm  = same certainty level; no semantic hedge hidden on either side",
    "#   dehedge  = quote is hedged IN MEANING but statement asserts flatly -> OVERCLAIM (costliest)",
    "#   addhedge = quote is plain but statement softens -> UNDERCLAIM",
    "#   other    = nuance the four buckets miss (explain in MISSED_HEDGE_NOTE)",
    "# WHAT YOU ARE CATCHING: hedges carried WITHOUT a listed word - 'tends to',",
    "# 'in most cases', 'may not', 'a trend toward', passive voice, or an overall /",
    "# limited-sample framing that already softens a 'no difference' result. Find none",
    "# on this sample and the machine's literal verdict is a safe proxy for the whole pool.",
    "# MODEL_UNC_ADVISORY = the model's self-tag: KNOWN to be confabulated on 3B",
    "# (defaults to 'may'); shown for contrast only, NEVER for the verdict.",
    "# SAMPLE (risk-aware): all hedge-WORD rows are auto-included (the known-risk cohort,",
    "# only a few), then plain rows are random-sampled by paper to reach ~15 total; the",
    "# plain cohort is where the word-list is blind, so it is the part worth auditing.",
    "# Fixed seed 20261003 -> the draw is reproducible across reruns.",
    "# Two independent passes recommended; keep this CSV as the reproducible record.",
]


def largest_remainder_alloc(sizes: list[int], total: int) -> list[int]:
    """Proportional allocation of `total` picks across strata of `sizes`,
    capped at each size; degrades to take-all when total >= sum(sizes)."""
    pool = sum(sizes)
    if total >= pool:
        return list(sizes)
    raw = [total * s / pool for s in sizes]
    base = [min(int(r), s) for r, s in zip(raw, sizes)]
    rem = total - sum(base)
    order = sorted(range(len(sizes)), key=lambda i: raw[i] - base[i], reverse=True)
    i = 0
    while rem > 0 and i < 10 * len(sizes):
        idx = order[i % len(order)]
        if base[idx] < sizes[idx]:
            base[idx] += 1
            rem -= 1
        i += 1
    return base


def machine_verdict(qh: set, sh: set) -> str:
    if qh - sh:
        return "dehedge"
    if sh - qh:
        return "addhedge"
    return "faithful"


def main() -> int:
    findings = [json.loads(l) for l in
                (TOPIC_DIR / "out" / "verified.jsonl").read_text(encoding="utf-8").splitlines()
                if l.strip()]
    pool = [f for f in findings if f.get("verdict") in ("admit", "review")]
    for f in pool:
        qh = sorted(hedge_set(str(f.get("quote", ""))))
        sh = sorted(hedge_set(str(f.get("statement", ""))))
        f["_qh"], f["_sh"] = qh, sh
        f["_shedge"] = bool(qh)
        f["_mverdict"] = machine_verdict(set(qh), set(sh))

    # Machine literal check over the WHOLE pool (the residual estimate conditions on it).
    m_faith = sum(1 for f in pool if f["_mverdict"] == "faithful")
    m_de = sum(1 for f in pool if f["_mverdict"] == "dehedge")
    m_add = sum(1 for f in pool if f["_mverdict"] == "addhedge")

    # RISK-AWARE residual draw. Two failure modes of the word-list matter:
    #   (a) rows where a hedge WORD is present in the quote -> known-risk cohort, cheap
    #       (only a few rows), so we AUTO-INCLUDE every one of them;
    #   (b) plain rows -> the real blind spot: a quote can be hedged IN MEANING
    #       ('tends to', limited-sample framing) while carrying no listed word, so the
    #       machine calls it faithful wrongly. We random-sample the plain cohort for that.
    # Strata for the plain draw = paper, largest-remainder proportional, fixed seed.
    risk = [f for f in pool if f["_shedge"]]
    plain = [f for f in pool if not f["_shedge"]]

    buckets: dict[str, list] = {}
    for f in plain:
        paper = str(f.get("paper", "?")).replace("probes/", "")
        buckets.setdefault(paper, []).append(f)
    keys = sorted(buckets)
    for k in keys:
        buckets[k].sort(key=lambda x: (x.get("page", 0), x.get("fid", "")))

    sizes = [len(buckets[k]) for k in keys]
    n_plain = max(0, CONFIRM_N - len(risk))
    picks = largest_remainder_alloc(sizes, n_plain)
    rng = random.Random(SEED)
    sampled_plain = []
    for k, take in zip(keys, picks):
        chosen = sorted(rng.sample(range(len(buckets[k])), take)) if take < len(buckets[k]) \
            else list(range(len(buckets[k])))
        sampled_plain.extend(buckets[k][j] for j in chosen)
    rows = risk + sampled_plain
    # stable display order across cohorts
    rows.sort(key=lambda x: (str(x.get("paper", "")), x.get("page", 0), x.get("fid", "")))

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = REPORT_DIR / "spotcheck_hedge.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        for line in RUBRIC:
            fh.write(line + "\n")
        w = csv.writer(fh)
        w.writerow(["sample_id", "paper", "page", "fid", "verdict",
                    "machine_quote_hedge", "machine_stmt_hedge", "MACHINE_VERDICT",
                    "model_unc_ADVISORY", "quote", "statement",
                    "HUMAN_JUDGE", "MISSED_HEDGE_NOTE"])
        for i, f in enumerate(rows, 1):
            w.writerow([i, str(f.get("paper", "")).replace("probes/", ""), f.get("page"),
                        f.get("fid"), f.get("verdict"),
                        "|".join(f["_qh"]), "|".join(f["_sh"]), f["_mverdict"],
                        f.get("uncertainty", ""),
                        str(f.get("quote", "")), str(f.get("statement", "")), "", ""])

    print(f"RESIDUAL-SAMPLE pool={len(pool)} sampled={len(rows)} "
          f"of findings={len(findings)} (rejects excluded={len(findings)-len(pool)})")
    print(f"MACHINE literal check (whole pool): faithful={m_faith} dehedge={m_de} addhedge={m_add} "
          f"-> human CONFIRMS this verdict on the {len(rows)}-row sample")
    print(f"COHORT auto-include hedge-word rows={len(risk)} (all); "
          f"random-sample plain rows={len(sampled_plain)} of {len(plain)}")
    for k, take in zip(keys, picks):
        print(f"  PLAIN-STRATUM {k}: pool={len(buckets[k])} sampled={take}")
    census = len(pool) <= CONFIRM_N
    mode = "CENSUS (pool <= CONFIRM_N)" if census else f"SAMPLE {CONFIRM_N}"
    hedged = sum(1 for f in rows if f["_shedge"])
    print(f"MODE {mode}: sampled={len(rows)} hedge_bearing={hedged} plain={len(rows)-hedged}")
    print("OUT report/spotcheck_hedge.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
