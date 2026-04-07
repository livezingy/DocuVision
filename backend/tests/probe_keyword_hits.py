#!/usr/bin/env python3
"""
Probe Phase1 fused text channels with two views:
1) Full-text dump by specific block_ids (default: p1_e3,p1_e9,p1_e10)
2) Optional keyword hit summary across structure_text/ocr_text/payload_text

Usage:
    python tests/probe_keyword_hits.py
    KEYWORD=fuel python tests/probe_keyword_hits.py
    BLOCK_IDS=p1_e3,p1_e9,p1_e10 KEYWORD="Fuel Saving" python tests/probe_keyword_hits.py

Defaults:
- API_BASE: http://127.0.0.1:8000
- IMAGE_PATH: /workspace/DocuVision/test_data/images/scanned/scanned_page_02.jpg (fixed)
- BLOCK_IDS: p1_e3,p1_e9,p1_e10
"""

from __future__ import annotations

import mimetypes
import os
import re
import time
from typing import Any, Dict, List, Tuple

import requests


IMAGE_PATH = "/workspace/DocuVision/test_data/images/scanned/scanned_page_02.jpg"
DEFAULT_API_BASE = "http://127.0.0.1:8000"
DEFAULT_KEYWORD = ""
DEFAULT_BLOCK_IDS = "p1_e3,p1_e9,p1_e10"

TEXT_LIKE_TYPES = {
    "doc_title",
    "paragraph_title",
    "abstract_title",
    "reference_title",
    "content_title",
    "text",
    "abstract",
    "content",
    "reference",
    "reference_content",
    "algorithm",
    "header",
    "header_image",
    "footer",
    "footer_image",
    "footnote",
    "figure_table_chart_title",
    "aside_text",
    "number",
    "formula_number",
    "title",
    "subtitle",
    "figure_caption",
    "table_caption",
    "list",
    "list_item",
    "paragraph",
    "text_block",
}


def _find_hits(text: Any, keyword: str) -> List[Tuple[int, str]]:
    value = "" if text is None else str(text)
    if not value or not keyword:
        return []

    hits: List[Tuple[int, str]] = []
    for match in re.finditer(re.escape(keyword), value, flags=re.IGNORECASE):
        start = match.start()
        end = match.end()
        left = max(0, start - 40)
        right = min(len(value), end + 40)
        context = value[left:right].replace("\n", "\\n")
        hits.append((start, context))
    return hits


def _submit_and_wait(api_base: str) -> Dict[str, Any]:
    if not os.path.exists(IMAGE_PATH):
        raise FileNotFoundError(f"image not found: {IMAGE_PATH}")

    mime = mimetypes.guess_type(IMAGE_PATH)[0] or "application/octet-stream"
    with open(IMAGE_PATH, "rb") as fh:
        submit_resp = requests.post(
            f"{api_base}/api/v1/documents:analyze",
            files={"file": (os.path.basename(IMAGE_PATH), fh, mime)},
            timeout=180,
        )
    submit_resp.raise_for_status()
    submit_data = submit_resp.json() if submit_resp.content else {}
    job_id = submit_data.get("job_id")
    if not job_id:
        raise RuntimeError("no job_id returned")

    print(f"[INFO] job_id={job_id}")
    status = ""
    for i in range(180):
        status_resp = requests.get(f"{api_base}/api/v1/jobs/{job_id}", timeout=30)
        status_resp.raise_for_status()
        status_data = status_resp.json() if status_resp.content else {}
        status = str(status_data.get("status", "")).lower()
        progress = status_data.get("progress")
        msg = str(status_data.get("message", ""))
        print(f"[POLL {i:03d}] status={status} progress={progress} msg={msg[:80]}")
        if status in ("succeeded", "completed", "failed", "cancelled"):
            break
        time.sleep(2)

    if status not in ("succeeded", "completed"):
        raise RuntimeError(f"job ended with status={status}")

    result_resp = requests.get(f"{api_base}/api/v1/jobs/{job_id}/result", timeout=120)
    result_resp.raise_for_status()
    return result_resp.json() if result_resp.content else {}


def main() -> int:
    keyword = os.environ.get("KEYWORD", DEFAULT_KEYWORD).strip()
    api_base = os.environ.get("API_BASE", DEFAULT_API_BASE).rstrip("/")
    block_ids_raw = os.environ.get("BLOCK_IDS", DEFAULT_BLOCK_IDS)
    target_block_ids = [b.strip() for b in block_ids_raw.split(",") if b.strip()]

    print(f"[INFO] api_base={api_base}")
    print(f"[INFO] keyword={keyword or '(disabled)'}")
    print(f"[INFO] image_path={IMAGE_PATH}")
    print(f"[INFO] block_ids={target_block_ids}")

    try:
        envelope = _submit_and_wait(api_base)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    pages = (((envelope or {}).get("fused") or {}).get("pages") or [])
    view_pages = (((envelope or {}).get("view") or {}).get("pages") or [])

    target_blocks: Dict[str, Dict[str, Any]] = {}
    channels: Dict[str, List[Dict[str, Any]]] = {
        "structure_text": [],
        "ocr_text": [],
        "payload_text": [],
    }

    for page in pages:
        page_num = page.get("page_num", 1)
        for block in page.get("blocks", []) or []:
            block_type = str(block.get("type", "")).lower()
            if block_type not in TEXT_LIKE_TYPES:
                continue

            block_id = str(block.get("block_id") or "")
            proc_status = block.get("processing_status")
            provenance = block.get("provenance") or {}
            payload = block.get("payload") or {}

            if block_id in target_block_ids:
                target_blocks[block_id] = {
                    "page": page_num,
                    "type": block_type,
                    "status": proc_status,
                    "structure_text": str(provenance.get("structure_text") or ""),
                    "ocr_text": str(provenance.get("ocr_text") or ""),
                    "payload_text": str(payload.get("text") or ""),
                }

            if keyword:
                for channel_name, text_value in (
                    ("structure_text", provenance.get("structure_text")),
                    ("ocr_text", provenance.get("ocr_text")),
                    ("payload_text", payload.get("text")),
                ):
                    for pos, ctx in _find_hits(text_value, keyword):
                        channels[channel_name].append(
                            {
                                "page": page_num,
                                "block_id": block_id,
                                "type": block_type,
                                "status": proc_status,
                                "pos": pos,
                                "ctx": ctx,
                            }
                        )

    print("\n" + "=" * 96)
    print("BLOCK FULL TEXT DUMP")
    print("=" * 96)
    for bid in target_block_ids:
        data = target_blocks.get(bid)
        if not data:
            print(f"\n[{bid}] not found in fused.text-like blocks")
            continue

        print(f"\n[{bid}] page={data['page']} type={data['type']} status={data['status']}")
        print("  structure_text:")
        print(repr(data["structure_text"]))
        print("  ocr_text:")
        print(repr(data["ocr_text"]))
        print("  payload_text:")
        print(repr(data["payload_text"]))

    print("\n" + "=" * 96)
    print("VIEW LAYER CHECK")
    print("=" * 96)
    if not view_pages:
        print("[WARN] envelope.view.pages is empty")
    else:
        first_page = view_pages[0] or {}
        elements = first_page.get("elements") or []
        print(
            f"[VIEW] pages={len(view_pages)} "
            f"first_page_num={first_page.get('page_num', 1)} "
            f"elements_count={len(elements)}"
        )
        if not elements:
            print("[WARN] envelope.view.pages[0].elements is empty")

    print("\n" + "=" * 96)
    print("TASK BLOCKS CHECK")
    print("=" * 96)
    try:
        blocks_resp = requests.get(f"{api_base}/api/v1/tasks/{envelope.get('job_id')}/blocks", timeout=60)
        if not blocks_resp.ok:
            print(f"[WARN] /tasks/{{id}}/blocks status={blocks_resp.status_code}")
        else:
            blocks_data = blocks_resp.json() if blocks_resp.content else {}
            flat_blocks = blocks_data.get("blocks") or []
            print(f"[BLOCKS] returned={len(flat_blocks)}")

            by_id = {str(b.get("id") or ""): b for b in flat_blocks if isinstance(b, dict)}
            for bid in target_block_ids:
                merged = target_blocks.get(bid)
                fb = by_id.get(bid)
                if not merged:
                    print(f"[{bid}] not found in fused target blocks")
                    continue
                if not fb:
                    print(f"[{bid}] not found in /tasks/{{id}}/blocks")
                    continue
                block_text = str(fb.get("text") or fb.get("content") or "")
                print(f"[{bid}] role={fb.get('role')} type={fb.get('type')} conf={fb.get('confidence')}")
                print(f"  payload_text == blocks.text ? {merged['payload_text'] == block_text}")
                print(f"  blocks_text: {repr(block_text)}")
    except Exception as exc:
        print(f"[WARN] failed to query /tasks/{{id}}/blocks: {exc}")

    if keyword:
        print("\n" + "=" * 96)
        print(f"KEYWORD HITS: {keyword}")
        print("=" * 96)
        for channel in ("structure_text", "ocr_text", "payload_text"):
            rows = channels[channel]
            print(f"\n[{channel}] hits={len(rows)}")
            if not rows:
                print("  (none)")
                continue
            for idx, row in enumerate(rows[:20], 1):
                print(
                    f"  {idx:02d}. page={row['page']} block={row['block_id']} "
                    f"type={row['type']} status={row['status']} pos={row['pos']}"
                )
                print(f"      ctx: {row['ctx']}")
            if len(rows) > 20:
                print(f"  ... {len(rows) - 20} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
