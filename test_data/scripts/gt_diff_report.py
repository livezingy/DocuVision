#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diff a DocuVision parsing result JSON against a GT baseline JSON.

Pure stdlib (json/re/difflib/hashlib) so it runs anywhere -- the Cloud box,
a colleague laptop, or this workspace -- with zero dependencies.

Inputs:
    --gt      gt/<slug>.gt.json produced by test_data/scripts/gt_build_arxiv.py
    --result  DocuVision Pro result JSON (the response of /api/v1/tasks/{id}
              or the saved task result envelope). Expected shapes (verified
              against backend code, 2026-09-04):
                result["figures"]["items"][].caption / .page      (figure_step)
                result["tables"][].data / .html_structure / .caption / .page
                result["layout"]["elements"][].text / .page       (layout_step)
                result["layout"]["failed_pages"] = [page, ...]
    --pdf     optional sample PDF; when given, its sha256 MUST match
              provenance.pdf_sha256 (hard pin) and a text-layer token
              recall check runs (requires fitz; skipped gracefully).

Statuses (pattern reused from backend/app/services/trial/gt_diff.py):
    match      engine value == GT (normalized)
    wrong      engine produced a different value
    missing    engine produced no corresponding item/cell
    gt_empty   GT cell is empty; engine output ignored (not scored)

Scoring rules:
    - Only Tier A / A- items are HARD failures. Tier B (grids, alignments,
      bold-span sections) count only inside the human queue; they are marked
      `blocked: needs human lock` rather than failed, per gt/README.md.
    - failed_pages: every GT anchor on a failed page is scored 'unavailable'
      (not a mismatch).
    - Engine confidence is NEVER used for right/wrong; it only sorts the
      human queue (lowest confidence first).

Output:
    test_data/TestResult/gt_diff/<slug>/report.json   (NOT *.log -- the
    auto-clean script deletes *.log recursively) + console summary.

Usage:
    python gt_diff_report.py --gt <gt.json> --result <result.json> \
        [--pdf <sample.pdf>] [--out-dir <dir>]
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_ROOT = REPO_ROOT / "test_data" / "TestResult" / "gt_diff"

GLYPH_RE = re.compile(r"[\u2713\u2714\u2715\u2716\u2717\u2718\u2719\u271a\u00d7\u2217\u2014\u2013\u2212]")
WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Normalization (shared contract with backend trial gt_diff, extended for
# glyph-preserving cell comparison)
# ---------------------------------------------------------------------------

def normalize(value: str) -> str:
    """Whitespace-flattening, case-folding, hyphen/punctuation-tolerant
    normalization used for equality checks. Glyphs (✓✗×∗) are KEPT --
    glyph confusion is exactly what this benchmark must catch."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value))
    s = s.replace("\u2212", "-")        # minus sign
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s = re.sub(r"[\u2018\u2019]", "'", s)
    s = re.sub(r"[\u201c\u201d]", '"', s)
    s = WS_RE.sub(" ", s)
    return s.strip().lower()


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\W+", normalize(text)) if t]


def similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Result-side extraction (tolerant to envelope variations)
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _unwrap(result: dict) -> dict:
    """Accept either the task envelope {result: {...}} or the bare result."""
    if isinstance(result.get("result"), dict) and ("tables" in result["result"] or "layout" in result["result"]):
        return result["result"]
    return result


def collect_engine_items(result: dict) -> dict:
    r = _unwrap(result)
    layout = r.get("layout") or {}
    elements = layout.get("elements") or []
    failed_pages = set()
    for fp in layout.get("failed_pages") or []:
        try:
            failed_pages.add(int(fp))
        except (TypeError, ValueError):
            pass

    figures_block = r.get("figures") or {}
    figure_items = figures_block.get("items") if isinstance(figures_block, dict) else None
    if figure_items is None and isinstance(figures_block, dict):
        # tolerate {figures: [...]} raw-service shape
        raw = figures_block.get("figures")
        figure_items = raw if isinstance(raw, list) else []
    figure_items = figure_items or []

    captions = []  # every caption-ish string the engine bound to an element
    for el in elements:
        text = normalize(el.get("text") or "")
        if text and re.match(r"^(figure|table|algorithm)\s+\d+\s*:", text):
            captions.append(
                {
                    "text": text,
                    "page": el.get("page"),
                    "kind_hint": text.split()[0].lower(),
                    "confidence": el.get("confidence"),
                }
            )
    for it in figure_items:
        cap = normalize(it.get("caption") or "")
        if cap:
            captions.append(
                {
                    "text": cap,
                    "page": it.get("page"),
                    "kind_hint": "figure",
                    "confidence": it.get("confidence"),
                    "source": "figures.items",
                }
            )

    tables = r.get("tables") or []
    return {
        "elements": elements,
        "element_texts": [normalize(el.get("text") or "") for el in elements if el.get("text")],
        "captions": captions,
        "tables": tables,
        "figure_items": figure_items,
        "failed_pages": failed_pages,
    }


# ---------------------------------------------------------------------------
# Caption diff (GT caption vs best engine caption match, page-aware)
# ---------------------------------------------------------------------------

def diff_captions(gt_items: list[dict], engine: dict, kind: str) -> list[dict]:
    out = []
    pool = [c for c in engine["captions"] if c.get("kind_hint") in (kind, None)]
    used: set[int] = set()
    for gt in gt_items:
        gt_no = gt.get(kind + "_no") if kind == "table" else gt.get("fig_no")
        gt_caption = normalize(gt.get("caption") or "")
        best, best_score, best_idx = None, -1.0, None
        for i, c in enumerate(pool):
            if i in used:
                continue
            score = similarity(gt_caption, c["text"])
            page_bonus = 0.0
            gt_page = (gt.get("align") or {}).get("pdf_page")
            if gt_page and c.get("page"):
                page_bonus = 0.10 if int(c["page"]) == int(gt_page) else -0.05
            total = score + page_bonus
            if total > best_score:
                best, best_score, best_idx = c, total, i
        entry = {
            "kind": kind,
            "no": gt_no,
            "gt_caption": gt.get("caption") or "",
            "trust": gt.get("trust"),
        }
        align_page = (gt.get("align") or {}).get("pdf_page")
        if align_page and align_page in engine["failed_pages"]:
            entry["status"] = "unavailable"
            entry["detail"] = f"page {align_page} in failed_pages"
        elif best is None or best_score < 0.5:
            entry["status"] = "missing"
            entry["detail"] = "no engine caption matched above threshold"
        elif best_score < 0.85:
            entry["status"] = "wrong"
            entry["detail"] = f"score {best_score:.2f} (text sim + page bonus)"
            entry["engine_caption"] = best["text"]
        else:
            entry["status"] = "match"
            entry["detail"] = f"score {best_score:.2f}"
            entry["engine_caption"] = best["text"]
            if best_idx is not None:
                used.add(best_idx)
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Table cell diff (grid vs grid; glyph-preserving per-cell equality)
# ---------------------------------------------------------------------------

def _engine_grid(tbl: dict) -> list[list[str]]:
    data = tbl.get("data")
    if isinstance(data, list):
        return [[normalize(c) if c is not None else "" for c in row] if isinstance(row, list) else [] for row in data]
    hs = tbl.get("html_structure") or {}
    hdr = hs.get("header_rows", 0) if isinstance(hs, dict) else 0
    return []


def _engine_html_grid(tbl: dict) -> list[list[str]]:
    """Last-resort: parse <table> HTML with regex (stdlib only)."""
    html = tbl.get("html") or ""
    if not html:
        return []
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    grid = []
    for row_html in rows:
        cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.S | re.I)
        grid.append([normalize(re.sub(r"<[^>]+>", " ", c)) for c in cells])
    return grid


def diff_table(gt_tbl: dict, engine_tables: list[dict], failed_pages: set, used_tables: set) -> dict:
    no = gt_tbl["table_no"]
    entry = {"table_no": no, "trust": gt_tbl.get("trust")}
    gt_grid = [[normalize(c) for c in row] for row in (gt_tbl.get("cells") or [])]
    align_page = (gt_tbl.get("align") or {}).get("pdf_page")

    if not any(cell for row in gt_grid for cell in row):
        entry["status"] = "gt_empty"
        entry["detail"] = "GT grid empty (caption-only entry); not scored"
        return entry
    if align_page and align_page in failed_pages:
        entry["status"] = "unavailable"
        entry["detail"] = f"page {align_page} in failed_pages"
        return entry

    # pair GT table with an engine table: caption text first (robust --
    # grids differ in shape but captions are near-verbatim), grid text as
    # tie-break only
    candidates = [t for t in engine_tables if t.get("page") == align_page]
    if not candidates:
        entry["status"] = "missing"
        entry["detail"] = f"no engine table on page {align_page}"
        return entry
    gt_caption = normalize(gt_tbl.get("caption") or "")
    gt_text = " ".join(c for row in gt_grid for c in row)
    best_tbl, best_score = None, -1.0
    for i, t in enumerate(candidates):
        if i in used_tables:
            continue  # greedy: one engine table cannot serve two GT tables
        cand_grid = _engine_grid(t) or _engine_html_grid(t)
        cand_text = " ".join(c for row in cand_grid for c in row)
        cap_score = similarity(gt_caption[:300], normalize(t.get("caption") or "")[:300])
        grid_score = similarity(gt_text[:400], cand_text[:400])
        score = 0.8 * cap_score + 0.2 * grid_score
        if score > best_score:
            best_tbl, best_score, best_idx = t, score, i
    if best_tbl is None:
        entry["status"] = "missing"
        entry["detail"] = f"all engine tables on page {align_page} already consumed"
        return entry
    used_tables.add(best_idx)
    eng_grid = _engine_grid(best_tbl) or _engine_html_grid(best_tbl)

    if not eng_grid:
        entry["status"] = "missing"
        entry["detail"] = f"engine table on p{align_page} has no data/html"
        return entry

    cells = []
    n_match = n_wrong = n_missing = n_gt_empty = 0
    for ri, gt_row in enumerate(gt_grid):
        eng_row = eng_grid[ri] if ri < len(eng_grid) else []
        for ci, gt_cell in enumerate(gt_row):
            eng_cell = eng_row[ci] if ci < len(eng_row) else ""
            if not gt_cell:
                n_gt_empty += 1
                continue
            if not eng_cell:
                status = "missing"
                n_missing += 1
            elif eng_cell == gt_cell or similarity(gt_cell, eng_cell) >= 0.9:
                status = "match"
                n_match += 1
            else:
                status = "wrong"
                n_wrong += 1
            if status != "match":
                cells.append(
                    {
                        "r": ri,
                        "c": ci,
                        "gt": gt_cell[:80],
                        "engine": eng_cell[:80],
                        "status": status,
                    }
                )
    n_cells = n_match + n_wrong + n_missing
    entry.update(
        {
            "status": "match" if (n_wrong == 0 and n_missing == 0) else "wrong",
            "gt_shape": [len(gt_grid), len(gt_grid[0]) if gt_grid else 0],
            "engine_shape": [len(eng_grid), len(eng_grid[0]) if eng_grid else 0],
            "cell_stats": {
                "match": n_match,
                "wrong": n_wrong,
                "missing": n_missing,
                "gt_empty": n_gt_empty,
            },
            "cell_accuracy": round(n_match / n_cells, 4) if n_cells else None,
            "bad_cells": cells[:40],
        }
    )
    return entry


# ---------------------------------------------------------------------------
# Section diff + text recall
# ---------------------------------------------------------------------------

def diff_sections(gt_sections: list[dict], engine: dict) -> list[dict]:
    out = []
    have_pages = {el.get("page") for el in engine["elements"]}
    for gs in gt_sections:
        text = normalize(gs["text"])
        page = gs.get("pdf_page")
        found = None
        for et in engine["element_texts"]:
            if text and (text in et or et in text) and len(et) < len(text) * 3:
                found = et
                break
        entry = {"gt": gs["text"], "level": gs["level"], "trust": gs.get("trust")}
        if page and page in engine["failed_pages"]:
            entry["status"] = "unavailable"
        elif found:
            entry["status"] = "match"
        else:
            entry["status"] = "missing"
        out.append(entry)
    return out


def text_recall(gt: dict, pdf: Path, engine: dict) -> dict | None:
    """Tier-A-ish recall: engine text tokens must cover the sample's printed
    tokens. Uses fitz when available; None otherwise."""
    try:
        import fitz  # noqa: F401
    except ImportError:
        return None
    import fitz

    prov = gt.get("provenance", {})
    want = prov.get("pdf_sha256")
    if want and sha256_file(pdf) != want:
        raise SystemExit("ERROR: --pdf sha256 does not match provenance.pdf_sha256; refusing")
    doc = fitz.open(pdf)
    failed = set(engine["failed_pages"])
    print_tokens: set[str] = set()
    for pno in range(doc.page_count):
        if pno + 1 in failed:
            continue
        print_tokens.update(tokens(doc[pno].get_text()))
    doc.close()
    eng_tokens: set[str] = set()
    for t in engine["element_texts"]:
        eng_tokens.update(tokens(t))
    for tbl in engine["tables"]:
        for row in _engine_grid(tbl):
            eng_tokens.update(tokens(" ".join(row)))
    missing = sorted(print_tokens - eng_tokens)
    return {
        "printed_tokens": len(print_tokens),
        "engine_tokens": len(eng_tokens),
        "missing_printed_tokens": len(missing),
        "recall": round(1 - len(missing) / len(print_tokens), 4) if print_tokens else None,
        "missing_sample": missing[:60],
    }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def human_queue(gt: dict, table_entries: list[dict], caption_entries: list[dict], section_entries: list[dict], engine: dict) -> list[dict]:
    """Items routed to a human: unlocked Tier-B/C anchors, failed tables,
    low-similarity captions, missing sections. Sorted by engine confidence
    (ascending) when available -- confidence NEVER decides right/wrong."""
    queue: list[dict] = []
    for t in gt.get("tables", []):
        if t.get("trust") == "B" and any(c["status"] == "match" for c in table_entries if c.get("table_no") == t["table_no"]):
            queue.append(
                {
                    "item": f"table:{t['table_no']}",
                    "reason": "Tier-B grid matched engine output -- human lock recommended before first scored use",
                    "gt_page": (t.get("align") or {}).get("pdf_page"),
                }
            )
    for c in caption_entries:
        if c["status"] in ("wrong", "missing"):
            queue.append(
                {
                    "item": f"caption:{c['kind']}:{c['no']}",
                    "reason": f"caption {c['status']}: {c['detail']}",
                    "engine_confidence": _conf_for(engine, c),
                }
            )
    for s in section_entries:
        if s["status"] == "missing":
            queue.append({"item": f"section:{s['gt'][:40]}", "reason": "heading not found in engine element texts"})
    for fr in gt.get("figure_regions", []):
        if fr.get("trust") == "C":
            queue.append(
                {
                    "item": f"figure_region:p{fr['pdf_page']}",
                    "reason": "Tier-C drawing cluster; advisory only",
                    "bbox": fr["bbox"],
                }
            )
    queue.sort(key=lambda q: q.get("engine_confidence") if q.get("engine_confidence") is not None else 1.0)
    return queue


def _conf_for(engine: dict, caption_entry: dict) -> float | None:
    for c in engine["captions"]:
        if caption_entry.get("engine_caption") and c["text"] == caption_entry["engine_caption"]:
            return c.get("confidence")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Diff DocuVision result JSON against GT baseline")
    ap.add_argument("--gt", required=True, type=Path)
    ap.add_argument("--result", required=True, type=Path)
    ap.add_argument("--pdf", default=None, type=Path, help="sample PDF; enables sha pin + text recall (needs fitz)")
    ap.add_argument("--out-dir", default=None, type=Path)
    args = ap.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    gt = _load_json(args.gt)
    result = _load_json(args.result)
    engine = collect_engine_items(result)

    prov = gt.get("provenance", {})
    if args.pdf is not None:
        got = sha256_file(args.pdf)
        if got != prov.get("pdf_sha256"):
            raise SystemExit(
                f"ERROR: pdf sha256 mismatch: got {got}, baseline pins {prov.get('pdf_sha256')}; refusing to diff"
            )
    else:
        print("[warn] --pdf not given: sha pin and text-recall skipped")

    figure_entries = diff_captions([f for f in gt.get("figures", [])], engine, "figure")
    table_cap_entries = diff_captions([t for t in gt.get("tables", []) if t.get("caption")], engine, "table")
    table_entries = []
    used_tables: set[int] = set()
    for t in gt.get("tables", []):
        table_entries.append(diff_table(t, engine["tables"], engine["failed_pages"], used_tables))
    section_entries = diff_sections(gt.get("sections", []), engine)
    recall = text_recall(gt, args.pdf, engine) if args.pdf else None

    def counts(entries):
        c = {}
        for e in entries:
            c[e["status"]] = c.get(e["status"], 0) + 1
        return c

    hard_fail = sum(
        1
        for e in figure_entries + table_cap_entries
        if e["status"] in ("wrong", "missing") and e.get("trust") in ("A", "A-")
    )
    report = {
        "schema": "docuvision.gt_diff/1.0",
        "gt_file": str(args.gt),
        "result_file": str(args.result),
        "provenance": prov,
        "summary": {
            "figures": counts(figure_entries),
            "table_captions": counts(table_cap_entries),
            "tables": counts(table_entries),
            "sections": counts(section_entries),
            "hard_failures": hard_fail,
            "verdict": "PASS" if hard_fail == 0 else "FAIL",
        },
        "figure_captions": figure_entries,
        "table_captions": table_cap_entries,
        "tables": table_entries,
        "sections": section_entries,
        "text_recall": recall,
        "human_queue": human_queue(gt, table_entries, figure_entries + table_cap_entries, section_entries, engine),
        "notes": [
            "Only Tier A/A- mismatches are hard failures; Tier B/C route to human_queue.",
            "failed_pages anchors are scored 'unavailable', not mismatches.",
            "Glyphs (checkmarks etc.) are compared verbatim -- no normalization folding.",
        ],
    }

    slug = args.gt.stem.removesuffix(".gt")
    out_dir = args.out_dir or (DEFAULT_OUT_ROOT / slug)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "report.json"
    out_file.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    s = report["summary"]
    print(f"[ok] {out_file}")
    print(f"     verdict={s['verdict']} hard_failures={s['hard_failures']}")
    print(f"     figures={s['figures']} table_captions={s['table_captions']}")
    print(f"     tables={s['tables']} sections={s['sections']}")
    if recall:
        print(f"     text_recall={recall['recall']} (missing {recall['missing_printed_tokens']}/{recall['printed_tokens']} tokens)")
    print(f"     human_queue={len(report['human_queue'])} items")
    return 0 if s["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
