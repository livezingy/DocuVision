"""End-to-end tests for the Proof Pack packager + CLI shell (v1.8.1 E4)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import fitz
import pytest

from app.services.proof_pack import ProofPackError, ProofRenderError, build_proof_pack

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "trial" / "proof_pack.py"

AMBER = (0.85, 0.55, 0.0)


def _pdf(tmp_path: Path, name: str = "src.pdf", pages: int = 1) -> str:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=595, height=842)
    path = tmp_path / name
    doc.save(str(path))
    doc.close()
    return str(path)


def _result():
    return {
        "preprocessing": {"coordinate_space": "original", "angle_deg": 0.0, "use_doc_unwarping": False},
        "tables": [
            {
                "page": 1,
                "bbox": {"x": 200, "y": 300, "width": 600, "height": 200},
                "data": [["5678"]],
                "cell_provenance": [["text_backfilled"]],
                "cell_ocr_text": [["1234"]],
            }
        ],
        "quality": {
            "table_backfill": {
                "enabled": True,
                "pages_judged": 1,
                "pages_text_layer_trusted": 1,
                "pages_skipped_preprocessed": 0,
                "cells_candidates": 1,
                "cells_confirmed": 0,
                "cells_backfilled": 1,
                "cells_mismatch": 0,
                "backfill_rate": 1.0,
                "mismatch_rate": 0.0,
                "mismatch_details": [],
                "mismatch_details_truncated": 0,
                "page_verdicts": ["text_layer"],
            },
            "engines_used": ["doc_preprocessor"],
        },
        "view": {"pages": [{"page_num": 1, "width": 1190.0, "height": 1684.0, "elements": []}]},
    }


def _write_result(tmp_path: Path, result) -> str:
    path = tmp_path / "task-1_result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    return str(path)


def test_build_proof_pack_end_to_end(tmp_path) -> None:
    pdf = _pdf(tmp_path)
    result_path = _write_result(tmp_path, _result())
    out_dir = str(tmp_path / "proof")
    before = hashlib.sha256(Path(pdf).read_bytes()).hexdigest()

    outcome = build_proof_pack(result_path, pdf, out_dir, app_version="1.8.1-test")

    assert outcome["summary"]["cells_backfilled"] == 1
    with zipfile.ZipFile(outcome["zip_path"]) as zf:
        assert zf.namelist() == ["annotated.pdf", "report.html", "report.json"]

    annotated = fitz.open(outcome["annotated_pdf"])
    colors = {tuple(round(c, 3) for c in d.get("color") or ()) for d in annotated[0].get_drawings()}
    annotated.close()
    assert AMBER in colors

    assert json.loads(Path(outcome["report_json"]).read_text(encoding="utf-8")) == outcome["report_data"]
    html = Path(outcome["report_html"]).read_text(encoding="utf-8")
    assert "Sample of corrected values" in html
    assert "v1.8.1-test" in html
    assert "task-1" in outcome["report_data"]["header"]["task_id"]

    assert hashlib.sha256(Path(pdf).read_bytes()).hexdigest() == before  # original untouched


def test_pack_zip_tables_and_figures_merged(tmp_path) -> None:
    pdf = _pdf(tmp_path)
    result_path = _write_result(tmp_path, _result())
    pack_path = tmp_path / "task-1_pack.zip"
    with zipfile.ZipFile(pack_path, "w") as zf:
        zf.writestr("tables/tables.csv", "a,b\n1,2\n")
        zf.writestr("tables/table_01_p1.csv", "x\n")
        zf.writestr("figures/fig1.png", b"\x89PNG fake")
        zf.writestr("manifest.json", "{}")
        zf.writestr("result.json", "{}")

    outcome = build_proof_pack(result_path, pdf, str(tmp_path / "proof"), pack_zip=str(pack_path))

    with zipfile.ZipFile(outcome["zip_path"]) as zf:
        names = zf.namelist()
    assert "annotated.pdf" in names and "tables/tables.csv" in names and "figures/fig1.png" in names
    assert "manifest.json" not in names and "result.json" not in names


def test_missing_contract_raises_exit_code_2(tmp_path) -> None:
    pdf = _pdf(tmp_path)
    no_quality = {"tables": []}
    with pytest.raises(ProofPackError) as exc:
        build_proof_pack(_write_result(tmp_path, no_quality), pdf, str(tmp_path / "proof"))
    assert exc.value.exit_code == 2

    no_tables = {"quality": {"table_backfill": {"enabled": False}}}
    with pytest.raises(ProofPackError) as exc:
        build_proof_pack(_write_result(tmp_path, no_tables), pdf, str(tmp_path / "proof2"))
    assert exc.value.exit_code == 2

    with pytest.raises(ProofPackError) as exc:
        build_proof_pack(str(tmp_path / "missing.json"), pdf, str(tmp_path / "proof3"))
    assert exc.value.exit_code == 2


def test_corrupt_pdf_raises_exit_code_3(tmp_path) -> None:
    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"not a pdf at all")
    with pytest.raises(ProofRenderError) as exc:
        build_proof_pack(_write_result(tmp_path, _result()), str(bad_pdf), str(tmp_path / "proof"))
    assert exc.value.exit_code == 3


def test_cli_subprocess_exit_codes(tmp_path) -> None:
    pdf = _pdf(tmp_path)
    result_path = _write_result(tmp_path, _result())
    out_dir = str(tmp_path / "proof")

    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--result", result_path, "--pdf", pdf, "--out", out_dir],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert "[OK]" in done.stdout
    assert (Path(out_dir) / "proof_pack.zip").exists()

    bad_result = _write_result(tmp_path, {"tables": []})  # no quality -> exit 2
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--result", bad_result, "--pdf", pdf, "--out", str(tmp_path / "proof2")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 2
    assert "[FAIL]" in done.stdout
