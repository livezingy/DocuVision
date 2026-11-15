#!/usr/bin/env bash
# =============================================================================
# p046_textlayer_verify.sh - P-046 text-layer / evidence / endpoints one-shot
#                            cloud verification (batch 4 of the R-005+P-046
#                            cloud-test checklist)
#
# Source of truth:
#   docs/R&D/runs/R-005/attachments/fitz_abc_p046_closure.md sec.7/8/9
#   (cloud checklist items: G3-ocr side, A7 UserUnit, B1 attribution round-trip,
#    B2 page_type_probe re-calibration, B3 E1 gatekeeper stability, B4 table
#    backfill geometry + 3pt-chain regression, B5 image_coverage registered gap,
#    C2 app/endpoint smoke)
# Skeleton: scripts/cloud/r005_cloud_verify.sh (rc.tsv + judge_verdict + tar)
# Discipline: scripts/cloud/README.md + kernel testing.md / constraints.md
#
# Covers (checklist mapping):
#   G3-ocr side : ocrsmoke   (pypdfium2-rendered PNG -> OCRService._call_ocr)
#   A7          : userunit   (UserUnit=2 fixture, pdfium self-consistency + fitz drift)
#   B1          : grounding  (quote round-trip attribution on the new block engine)
#   B2/B3/B5    : corpus     (page_type_probe distribution + stability + coverage gap)
#   B4a/B4b     : unit + backfill (3pt-chain regression via pytest; table bbox geometry)
#   C2          : appsmoke   (API contract pytest; REAL_APP=1 adds a real uvicorn boot)
#
# Usage (Cloud Studio GPU / Linux, from scripts/cloud/):
#   bash p046_textlayer_verify.sh                 # default: contract pytest + all probes
#   REAL_APP=1 bash p046_textlayer_verify.sh      # + real uvicorn boot + HTTP smoke
#   bash p046_textlayer_verify.sh --self-test     # local bash-only logic mock, no GPU/deps
#   EXPECTED_HEAD=0db4036 STRICT_HEAD=1 bash p046_textlayer_verify.sh
#
# Hard boundaries (no forced-pass):
#   - Criteria are fixed in advance below; missing evidence = BLOCKED(7), never
#     a forced pass. No retry loops around judgment.
#   - Registered/soft items (fitz drift on UserUnit, corpus verdict distribution,
#     image_coverage gap, backfill rates) are RECORDED, never silently dropped
#     and never turned into a pass by re-wording.
#   - Local/CI has no GPU: never claim "cloud verified". Readings register only
#     after the tarball is unpacked and reviewed (agentD review + Ying sign-off).
#   - No auto-push: git push is a red line. This script only packs artifacts and
#     writes a carry-back manifest; the push-back is manual on the local host.
#
# Exit codes: 0 = EVIDENCE_READY, 7 = BLOCKED(7), 2 = fatal setup error,
#             self-test: 0 = all mock cases pass, 1 = self-test failed.
#
# Artifacts in OUT_DIR (carry-back payload, prefix p046tl_):
#   p046tl_env.txt / p046tl_unit.log / p046tl_ocrsmoke.txt / p046tl_userunit.txt
#   p046tl_grounding.txt / p046tl_calib.jsonl / p046tl_stability.txt
#   p046tl_coverage.jsonl / p046tl_backfill.txt / p046tl_app_real.txt (opt)
#   p046tl_rc.tsv / p046tl_probe.py / p046tl_summary.txt / p046tl_verdict_draft.md
#   p046tl_return_manifest.md / p046tl_artifacts_<HEAD>_<timestamp>.tar.gz
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-p046tl}"
VENV_DIR="${VENV_DIR-$HOME/docuvision_env}"    # set VENV_DIR= (empty) to skip activation
REPO_DIR="${REPO_DIR:-}"
OUT_DIR="${OUT_DIR:-}"                          # empty = $REPO_DIR/test_data/local/p046tl_cloud
BRANCH="${BRANCH:-}"
EXPECTED_HEAD="${EXPECTED_HEAD:-0db4036}"       # feat/r005-render-swap HEAD at writing date; ancestor mode by default
STRICT_HEAD="${STRICT_HEAD:-0}"
AUTO_FF="${AUTO_FF:-0}"
GPU_REQUIRED="${GPU_REQUIRED:-1}"
PDF_DIR="${PDF_DIR:-test_data/testfiles/pdf}"
FIXTURE_GLOB="${FIXTURE_GLOB:-tampa}"           # born-digital KIE fixture name substring
FORM_GLOB="${FORM_GLOB:-cosent}"                # table/form fixture name substring
FIXDIR="${FIXDIR:-docs/R&D/runs/R-005/attachments/r005_feas_fixtures}"
DOCS_LIMIT="${DOCS_LIMIT:-12}"                  # corpus docs cap (one probe pass)
PAGES_PER_DOC="${PAGES_PER_DOC:-8}"             # corpus pages cap per doc
REAL_APP="${REAL_APP:-0}"                       # 1 = boot real uvicorn + HTTP smoke
APP_PORT="${APP_PORT:-8901}"
APP_BOOT_TIMEOUT="${APP_BOOT_TIMEOUT:-240}"     # seconds; model init on GPU can be slow

log() { echo "[p046tl] $*"; }
die() { echo "[p046tl][FATAL] $*" >&2; exit 2; }

# ---- Verdict: single bash-only source of truth (shared with --self-test) -----
# Args: rc_file gpu_ok pin_drift missing
# Criteria fixed in advance (closure doc sec.7/8 + this header):
#   EVIDENCE_READY = every recorded step rc==0 AND GPU up AND production pins in
#     range AND all REQUIRED evidence files present. Everything else = BLOCKED(7).
#   Registered soft items (drift/distribution/rates) never gate: they are recorded
#     artifacts for agentD review / Ying sign-off.
judge_verdict() {
  local rc_file="$1" gpu_ok="$2" pin_drift="$3" missing="$4"
  local fails=0 reason="" verdict="EVIDENCE_READY" step side rc
  while IFS=$'\t' read -r step side rc; do
    [ -z "${step:-}" ] && continue
    if [ "${rc:-}" != "0" ]; then
      fails=$((fails + 1)); reason="${reason} ${step}/${side}=rc${rc}"
    fi
  done < "$rc_file"
  [ "$fails" -eq 0 ] || verdict="BLOCKED(7)"
  if [ "$gpu_ok" != "1" ]; then
    verdict="BLOCKED(7)"; reason="${reason} NO_GPU(cloud GPU unavailable, no evidence claim)"
  fi
  if [ "$pin_drift" != "0" ]; then
    verdict="BLOCKED(7)"; reason="${reason} PIN_DRIFT(${pin_drift} production pins off, readings not comparable)"
  fi
  if [ "$missing" -gt 0 ]; then
    verdict="BLOCKED(7)"; reason="${reason} MISSING_EVIDENCE(${missing} required artifacts absent)"
  fi
  printf 'VERDICT=%s\nREASON=%s\n' "$verdict" "${reason:-criteria pre-written, all hard gates green}"
}

# ---- --self-test: local mock, no venv/GPU/pytest ------------------------------
SELF_TEST=0
for arg in "$@"; do
  case "$arg" in
    --self-test) SELF_TEST=1 ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) die "unknown arg: $arg (only --self-test / --help)" ;;
  esac
done
if [ "$SELF_TEST" = "1" ]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  ok=0; total=0
  assert_verdict() {
    total=$((total + 1))
    printf '%b' "$3" > "$TMP/rc.tsv"
    out="$(judge_verdict "$TMP/rc.tsv" "$4" "$5" "$6")"
    if printf '%s' "$out" | grep -qF "$1" && printf '%s' "$out" | grep -qF "$2"; then
      ok=$((ok + 1))
    else
      echo "[p046tl][SELFTEST-FAIL] expect VERDICT~$1 REASON~$2, got: $out" >&2
    fi
  }
  assert_verdict "EVIDENCE_READY" "all hard gates green" "" 1 0 0
  assert_verdict "BLOCKED(7)" "ocrsmoke/main=rc3" "ocrsmoke\tmain\t3\n" 1 0 0
  assert_verdict "BLOCKED(7)" "grounding/roundtrip=rc3" "grounding\troundtrip\t3\n" 1 0 0
  assert_verdict "BLOCKED(7)" "NO_GPU" "" 0 0 0
  assert_verdict "BLOCKED(7)" "PIN_DRIFT(2" "" 1 2 0
  assert_verdict "BLOCKED(7)" "MISSING_EVIDENCE(3" "" 1 0 3
  assert_verdict "BLOCKED(7)" "userunit/selfconsistency=rc3" "userunit\tselfconsistency\t3\nunit\tcontract\t1\n" 1 0 0
  echo "[p046tl][SELFTEST] ${ok}/${total} passed"
  [ "$ok" -eq "$total" ] || exit 1
  exit 0
fi

record() { printf '%s\t%s\t%s\n' "$1" "$2" "$3" >> "$RC_FILE"; log "  $1/$2 rc=$3"; }

# ---- 0) venv -----------------------------------------------------------------
if [ -n "$VENV_DIR" ]; then
  [ -f "$VENV_DIR/bin/activate" ] || die "venv not found: $VENV_DIR/bin/activate (set VENV_DIR= to skip)"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  log "venv activated: $VENV_DIR"
fi
PY="$(command -v python3 || command -v python)" || die "python not found"
log "PY=$PY ($("$PY" -V 2>&1))"

# ---- 1) repo locate ----------------------------------------------------------
if [ -z "$REPO_DIR" ]; then
  d="$SCRIPT_DIR"
  while [ "$d" != "/" ]; do
    [ -f "$d/backend/app/services/pdf_raster.py" ] && REPO_DIR="$d" && break
    d="$(dirname "$d")"
  done
fi
[ -n "$REPO_DIR" ] || die "repo not found; set REPO_DIR=/path/to/DocuVision"
[ -f "$REPO_DIR/backend/requirements.txt" ] || die "REPO_DIR does not look like DocuVision: $REPO_DIR"
log "REPO_DIR=$REPO_DIR"
[ -n "$OUT_DIR" ] || OUT_DIR="$REPO_DIR/test_data/local/p046tl_cloud"
mkdir -p "$OUT_DIR" || die "cannot create OUT_DIR=$OUT_DIR"
log "OUT_DIR=$OUT_DIR"
RC_FILE="$OUT_DIR/${PREFIX}_rc.tsv"; : > "$RC_FILE"
PROBE="$OUT_DIR/${PREFIX}_probe.py"

# ---- 2) version check (detached-HEAD safe, no auto-ff) -----------------------
cd "$REPO_DIR" || die "cannot cd $REPO_DIR"
CUR_BRANCH="$(git symbolic-ref -q --short HEAD 2>/dev/null || true)"
[ "$BRANCH" = "HEAD" ] && BRANCH=""
[ -n "$BRANCH" ] || BRANCH="$CUR_BRANCH"
RUN_REF="${CUR_BRANCH:-detached}"
if [ -n "$BRANCH" ]; then
  if git fetch origin "$BRANCH"; then
    log "synced origin/$BRANCH (refs only)"
  else
    log "WARN: git fetch failed (offline / no remote branch); local checkout is the measured version"
  fi
else
  log "WARN: detached HEAD - skip fetch/ff"
fi
HEAD_NOW="$(git rev-parse --short HEAD)"
if [ -n "$EXPECTED_HEAD" ]; then
  git cat-file -e "${EXPECTED_HEAD}^{commit}" 2>/dev/null \
    || die "EXPECTED_HEAD=$EXPECTED_HEAD missing locally (shallow clone?). Fix: git fetch --unshallow origin main"
  if [ "$STRICT_HEAD" = "1" ]; then
    [ "$HEAD_NOW" = "$EXPECTED_HEAD" ] || die "version mismatch (strict): expected $EXPECTED_HEAD got $HEAD_NOW"
  elif git merge-base --is-ancestor "$EXPECTED_HEAD" HEAD; then
    log "version OK (ancestor): $EXPECTED_HEAD merged into $HEAD_NOW"
  else
    die "version mismatch: $EXPECTED_HEAD not ancestor of $HEAD_NOW
  diag: git merge-base $EXPECTED_HEAD HEAD ; git log --oneline $EXPECTED_HEAD..HEAD -5
  fix: git fetch --unshallow origin main && git checkout --detach $EXPECTED_HEAD
  Do NOT set EXPECTED_HEAD= to force-run (kernel: version mismatch = stop)"
  fi
else
  log "WARN: EXPECTED_HEAD not pinned - comparability at your own risk"
fi
log "HEAD=$HEAD_NOW ref=$RUN_REF"

# ---- 3) self-contained Python probe (also an artifact: reproducible) ---------
cat > "$PROBE" <<'PYEOF'
#!/usr/bin/env python3
"""P-046 text-layer/evidence cloud probe (batch 4). Self-contained, ASCII-only.

Subcommands (each prints STATUS lines the bash wrapper records into rc.tsv):
  env        versions + GPU + production-pin drift
  ocrsmoke   G3-ocr side: pypdfium2-rendered PNG -> OCRService._call_ocr
  userunit   A7: UserUnit=2 fixture, pdfium self-consistency (+ fitz drift, INFO)
  grounding  B1: quote round-trip attribution via grounding_source (new blocks)
  corpus     B2/B3/B5: page_type_probe distribution + stability + coverage gap
  backfill   B4b: GPU layout on form fixture -> table bbox geometry round-trip
"""
import argparse
import glob
import io
import json
import os
import sys
import tempfile

REPO_DIR = os.environ.get("P046TL_REPO_DIR", "")
OUT_DIR = os.environ.get("P046TL_OUT_DIR", "")
PDF_DIR = os.environ.get("P046TL_PDF_DIR", "test_data/testfiles/pdf")
FIXTURE_GLOB = os.environ.get("P046TL_FIXTURE_GLOB", "tampa")
FORM_GLOB = os.environ.get("P046TL_FORM_GLOB", "cosent")
FIXDIR = os.environ.get("P046TL_FIXDIR", "")
DOCS_LIMIT = int(os.environ.get("P046TL_DOCS_LIMIT", "12"))
PAGES_PER_DOC = int(os.environ.get("P046TL_PAGES_PER_DOC", "8"))

if REPO_DIR:
    BACKEND = os.path.join(REPO_DIR, "backend")
    for p in (BACKEND, os.path.join(REPO_DIR, "packages", "docuvision-core")):
        if p not in sys.path:
            sys.path.insert(0, p)
os.environ.setdefault("DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLEX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")


def emit(name, content, jsonl=False):
    """Write one artifact file into OUT_DIR; also print the first lines."""
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        if jsonl:
            for row in content:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            fh.write(content)
    print("EMIT=%s" % name)
    return path


def versions():
    import importlib.metadata as md
    names = ["pypdfium2", "reportlab", "pypdf", "pdfplumber", "paddleocr",
             "paddlex", "paddlepaddle-gpu", "paddlepaddle", "Pillow", "PyMuPDF"]
    out = {}
    for n in names:
        try:
            out[n] = md.version(n)
        except Exception:
            out[n] = "MISSING"
    return out


def _in_range(v, lo, hi):
    try:
        parts = str(v).split(".")
        major = int(parts[0])
        return lo <= major < hi
    except Exception:
        return False


def cmd_env():
    import subprocess
    v = versions()
    g = {"nvidia_smi": "MISSING", "paddle_gpu": "UNKNOWN"}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        g["nvidia_smi"] = r.stdout.strip() if r.returncode == 0 else "ERR:" + r.stderr.strip()[:120]
    except Exception as e:
        g["nvidia_smi"] = "ERR:" + str(e)[:120]
    try:
        import paddle
        g["paddle_gpu"] = str(paddle.device.is_compiled_with_cuda())
        g["paddle_version"] = paddle.__version__
    except Exception as e:
        g["paddle_gpu"] = "UNAVAILABLE:" + type(e).__name__

    lines = ["P-046 text-layer cloud env (closure doc sec.7/8; batch 4)",
             "python=%s" % sys.version.split()[0], ""]
    lines += ["%s=%s" % (k, val) for k, val in v.items()]
    lines += [""] + ["%s=%s" % (k, val) for k, val in g.items()]

    drifts = []
    if not _in_range(v.get("pypdfium2"), 5, 6):
        drifts.append({"package": "pypdfium2", "expected": ">=5,<6", "actual": v.get("pypdfium2")})
    if not _in_range(v.get("reportlab"), 5, 6):
        drifts.append({"package": "reportlab", "expected": ">=5,<6", "actual": v.get("reportlab")})
    for pkg, want in (("paddleocr", "3.3.2"), ("paddlex", "3.3.12"), ("pypdf", "3.17.4")):
        if v.get(pkg, "MISSING") != want:
            drifts.append({"package": pkg, "expected": want, "actual": v.get(pkg, "MISSING")})
    # PyMuPDF: test-only since P-046; presence is INFO, absence is INFO too.
    lines += ["", "PYMUPDF_INFO=test-only dependency, presence is informational (P-046)",
              "PIN_DRIFT_COUNT=%d" % len(drifts),
              "PIN_DRIFTS=" + json.dumps(drifts),
              "GPU_OK=%s" % ("1" if (g["paddle_gpu"] == "True" and not str(g["nvidia_smi"]).startswith(("ERR", "MISSING"))) else "0")]
    emit("p046tl_env.txt", "\n".join(lines) + "\n")
    print("PIN_DRIFT_COUNT=%d" % len(drifts))
    print("GPU_OK=%s" % ("1" if (g["paddle_gpu"] == "True" and not str(g["nvidia_smi"]).startswith(("ERR", "MISSING"))) else "0"))
    return 0


def _pdfium_render_png(pdf_path, scale=2.0):
    """Render page 1 with the RUNTIME stack (pypdfium2) and save a PNG.

    Self-proof line: RENDER_ENGINE=pypdfium2 (channel self-evidence for G3-ocr).
    Returns (png_path, width, height).
    """
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_path)
    try:
        doc.init_forms()  # pack v2.1 sec.4: forms env BEFORE page retrieval
        page = doc[0]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        png = os.path.join(tempfile.mkdtemp(prefix="p046tl_ocr_"), "page1.png")
        img.save(png, format="PNG")
        print("RENDER_ENGINE=pypdfium2")
        print("RENDER_PX=%dx%d" % (img.width, img.height))
        return png, img.width, img.height
    finally:
        doc.close()


def cmd_ocrsmoke():
    """G3-ocr side: OCRService._call_ocr on a pypdfium2-rendered fixture page.

    Fixture resolution: gitignored local fixture dir first (f1_normal.pdf),
    then fall back to the first tracked corpus PDF (cloud clones have
    test_data/testfiles/pdf but NOT docs/R&D/**)."""
    fixture = os.path.join(FIXDIR, "f1_normal.pdf")
    if not os.path.isfile(fixture):
        corpus = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
        if not corpus:
            print("OCRSMOKE_FIXTURE_MISSING=no local fixture and empty %s" % PDF_DIR)
            return 4
        fixture = corpus[0]
        print("OCRSMOKE_FIXTURE_FALLBACK=%s" % fixture)
    png, w, h = _pdfium_render_png(fixture)
    from app.services.ocr_service import PaddleOCREngine
    # The feeding chain (ocr_service._process_pdf -> _call_ocr) runs on
    # PaddleOCREngine; OCRService is the multi-engine facade above it.
    # Cloud round 1 hit AttributeError on OCRService._init_engine (facade
    # exposes _init_engines registry only), round 2 hit OCR_READY=False on the
    # facade (its _ready lives on the inner engine) - use the engine directly.
    eng = PaddleOCREngine(use_gpu=True)
    if not eng.is_ready():
        eng._init_engine()
    if not eng.is_ready():
        print("OCR_READY=False")
        return 3
    print("OCR_READY=True")
    result = eng._call_ocr(png)
    blocks = []
    for item in result or []:
        if isinstance(item, dict) and str(item.get("text", "")).strip():
            blocks.append(item["text"])
        elif isinstance(item, (list, tuple)):
            for sub in item:
                if isinstance(sub, (list, tuple)) and sub and str(sub[0]).strip():
                    blocks.append(str(sub[0]))
    lines = ["G3-ocr side smoke (closure doc sec.7 item 1)",
             "fixture=%s" % fixture,
             "render_engine=pypdfium2 scale=2.0 px=%dx%d" % (w, h),
             "ocr_text_blocks=%d" % len(blocks),
             ""]
    lines += [b[:80] for b in blocks[:10]]
    emit("p046tl_ocrsmoke.txt", "\n".join(lines) + "\n")
    print("OCR_BLOCKS=%d" % len(blocks))
    return 0 if len(blocks) > 0 else 3


def cmd_userunit():
    """A7: UserUnit=2 fixture; pdfium self-consistency is the hard gate,
    fitz-era dims comparison is RECORDED drift (registered engine difference)."""
    lines = ["A7 UserUnit=2 probe (closure doc sec.7 / review finding 2)"]
    try:
        from reportlab.pdfgen import canvas as rl_canvas
        base_pdf = os.path.join(tempfile.mkdtemp(prefix="p046tl_uu_"), "base.pdf")
        c = rl_canvas.Canvas(base_pdf, pagesize=(595, 842))
        c.setFont("Helvetica", 12)
        c.drawString(72, 700, "DocuVision UserUnit probe page")
        c.save()
    except Exception as e:
        lines.append("reportlab_base_pdf_ERR=%r" % (e,))
        emit("p046tl_userunit.txt", "\n".join(lines) + "\n")
        print("U1_BASE_PDF=ERR")
        return 4

    import pypdf
    from pypdf.generic import NameObject, NumberObject
    reader = pypdf.PdfReader(base_pdf, strict=False)
    writer = pypdf.PdfWriter()
    page = reader.pages[0]
    page[NameObject("/UserUnit")] = NumberObject(2)
    writer.add_page(page)
    uu_pdf = os.path.join(tempfile.mkdtemp(prefix="p046tl_uu_"), "userunit2.pdf")
    with open(uu_pdf, "wb") as fh:
        writer.write(fh)

    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(uu_pdf)
    try:
        size_w, size_h = doc[0].get_size()
        bitmap = doc[0].render(scale=2.0)
        px_w, px_h = bitmap.width, bitmap.height
    finally:
        doc.close()
    scale_x = px_w / size_w if size_w else 0.0
    scale_y = px_h / size_h if size_h else 0.0
    consistent = (px_w == int(round(size_w * 2.0))) and (px_h == int(round(size_h * 2.0)))
    lines += ["pdfium get_size_pt=%.1fx%.1f" % (size_w, size_h),
              "pdfium render_px=%dx%d" % (px_w, px_h),
              "pdf_to_img_scale=%.4f,%.4f (runtime.py semantics)" % (scale_x, scale_y),
              "U1_SELFCONSISTENT=%s" % consistent]

    # fitz-era comparison: RECORDED drift, never a gate (registered difference).
    try:
        import fitz
        fdoc = fitz.open(uu_pdf)
        rect = fdoc[0].rect
        pix = fdoc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
        lines += ["fitz_rect_pt=%.1fx%.1f (UserUnit applied by MuPDF)" % (rect.width, rect.height),
                  "fitz_render_px=%dx%d" % (pix.width, pix.height),
                  "REGISTERED_DRIFT=fitz-era px were %dx%d; pypdfium2 px are %dx%d"
                  % (pix.width, pix.height, px_w, px_h)]
        fdoc.close()
    except Exception as e:
        lines.append("fitz_compare_UNAVAILABLE=%r (test-only dep may be absent)" % (e,))

    lines += ["NOTE: width_px/height_px halve vs fitz era for UserUnit!=1 pages; "
              "pdf_to_img_scale stays self-consistent on both engines."]
    emit("p046tl_userunit.txt", "\n".join(lines) + "\n")
    print("U1_SELFCONSISTENT=%s" % consistent)
    print("U1_PX=%dx%d" % (px_w, px_h))
    return 0 if consistent else 3


def cmd_grounding():
    """B1: quote round-trip attribution with the NEW block engine.

    For every corpus page with text blocks, take the first block's head as a
    quote; the only acceptable attribution target is the page it came from.
    Pre-written criterion: hits == samples, samples >= 1.
    """
    from app.services.evidence.grounding import grounding_source
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))[:DOCS_LIMIT]
    if not pdfs:
        print("GROUNDING_CORPUS_MISSING=%s" % PDF_DIR)
        return 4
    try:
        from app.services.evidence.normalize import normalize
    except Exception:
        normalize = None
    lines = ["B1 grounding quote round-trip (closure doc sec.7; registered granularity change)",
             "engine=pdfminer LTTextBox via grounding_source", ""]
    samples = hits = 0
    rows = []
    for pdf_path in pdfs:
        try:
            src = grounding_source(pdf_path)
        except Exception as e:
            rows.append({"file": os.path.basename(pdf_path), "error": repr(e)[:160]})
            continue
        for page_str, blocks in sorted(src.blocks.items()):
            page_no = int(page_str)
            if page_no > PAGES_PER_DOC or not blocks:
                continue
            quote = str(blocks[0]).strip()[:60]
            if not quote:
                continue
            hay = src.texts.get(page_str, "")
            if normalize is not None:
                hay = normalize(hay)
                quote_n = normalize(quote)
            else:
                quote_n = quote.lower()
            matched = [q for q, txt in src.texts.items()
                       if (normalize(txt) if normalize is not None else txt.lower()).find(quote_n) >= 0]
            ok = page_no in matched
            samples += 1
            hits += 1 if ok else 0
            rows.append({"file": os.path.basename(pdf_path), "page": page_no,
                         "quote": quote[:40], "matched_pages": matched, "ok": ok})
    emit("p046tl_grounding.txt",
         "\n".join(lines) + "\nsamples=%d\nhits=%d\nroundtrip=%s\n"
         % (samples, hits, "PASS" if samples > 0 and hits == samples else "FAIL"))
    emit("p046tl_grounding.jsonl", rows, jsonl=True)
    print("GROUNDING_SAMPLES=%d" % samples)
    print("GROUNDING_HITS=%d" % hits)
    if samples == 0:
        print("GROUNDING=NO_SAMPLES(born-digital corpus empty?)")
        return 4
    return 0 if hits == samples else 3


def cmd_corpus():
    """B2/B3/B5 in one pass: page_type_probe distribution (B2), judge stability
    (B3: zero exceptions across the corpus), image_coverage vs annots gap (B5)."""
    import pypdfium2 as pdfium
    from app.services.page_text_trust import judge_page_trust
    pdfs = sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))[:DOCS_LIMIT]
    if not pdfs:
        print("CORPUS_MISSING=%s" % PDF_DIR)
        return 4
    dist = {}
    rows = []
    exceptions = 0
    pages_total = 0
    for pdf_path in pdfs:
        try:
            reader = __import__("pypdf").PdfReader(pdf_path, strict=False)
            annot_counts = []
            for pg in reader.pages[:PAGES_PER_DOC]:
                try:
                    annots = pg.get("/Annots")
                    annot_counts.append(len(annots) if annots else 0)
                except Exception:
                    annot_counts.append(0)
        except Exception as e:
            rows.append({"file": os.path.basename(pdf_path), "error": repr(e)[:160]})
            continue
        try:
            doc = pdfium.PdfDocument(pdf_path)
        except Exception as e:
            rows.append({"file": os.path.basename(pdf_path), "error": repr(e)[:160]})
            continue
        try:
            for idx in range(min(len(doc), PAGES_PER_DOC)):
                pages_total += 1
                try:
                    res = judge_page_trust(doc[idx])
                    v = res.verdict
                    dist[v] = dist.get(v, 0) + 1
                    annots = annot_counts[idx] if idx < len(annot_counts) else 0
                    gap_exposed = bool(annots) and res.signals.get("image_coverage", 0.0) < 0.1
                    rows.append({"file": os.path.basename(pdf_path), "page": idx + 1,
                                 "verdict": v, "trusted": res.trusted,
                                 "confidence": res.confidence,
                                 "invisible_ratio": res.signals.get("invisible_ratio"),
                                 "image_coverage": res.signals.get("image_coverage"),
                                 "annots": annots, "coverage_gap_exposed": gap_exposed})
                except Exception as e:
                    exceptions += 1
                    rows.append({"file": os.path.basename(pdf_path), "page": idx + 1,
                                 "error": repr(e)[:200]})
        finally:
            doc.close()

    # B2 hard sanity: born-digital KIE fixture page 1 must be text_layer.
    fixture_check = "NOT_FOUND"
    fixture_fail = False
    for pdf_path in pdfs:
        if FIXTURE_GLOB.lower() in os.path.basename(pdf_path).lower():
            try:
                doc = pdfium.PdfDocument(pdf_path)
                v1 = judge_page_trust(doc[0]).verdict
                doc.close()
                fixture_check = "%s p1=%s" % (os.path.basename(pdf_path), v1)
                fixture_fail = v1 != "text_layer"
            except Exception as e:
                fixture_check = "ERR:%r" % (e,)
                fixture_fail = True
            break

    emit("p046tl_calib.jsonl", rows, jsonl=True)
    stability = ["B3 judge stability (closure doc sec.7)",
                 "pages_total=%d" % pages_total,
                 "exceptions=%d" % exceptions,
                 "stability=%s" % ("PASS" if exceptions == 0 and pages_total > 0 else "FAIL"),
                 "verdict_distribution=%s" % json.dumps(dist, sort_keys=True)]
    emit("p046tl_stability.txt", "\n".join(stability) + "\n")
    gap_rows = [r for r in rows if r.get("coverage_gap_exposed")]
    coverage = ["B5 image_coverage vs /Annots (REGISTERED GAP: pdfium object walk misses",
                "annotation appearance-stream images; pages with annots and coverage<0.1",
                "are expected and RECORDED, never a gate)",
                "gap_exposed_pages=%d" % len(gap_rows)]
    emit("p046tl_coverage.txt", "\n".join(coverage) + "\n")
    emit("p046tl_coverage.jsonl", gap_rows, jsonl=True)
    print("PAGES_TOTAL=%d" % pages_total)
    print("JUDGE_EXCEPTIONS=%d" % exceptions)
    print("VERDICT_DIST=%s" % json.dumps(dist, sort_keys=True))
    print("FIXTURE_CHECK=%s" % fixture_check)
    print("GAP_EXPOSED=%d" % len(gap_rows))
    if pages_total == 0:
        return 4
    if exceptions > 0 or fixture_fail:
        return 3
    return 0


def cmd_backfill():
    """B4b: GPU layout on the table/form fixture -> table bbox geometry
    round-trip via table_backfill.derive_cell_bbox. The full OCR-text-matching
    funnel rate stays a registered item; this proves the bbox pipeline on GPU."""
    matches = [p for p in sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf")))
               if FORM_GLOB.lower() in os.path.basename(p).lower()]
    if not matches:
        print("BACKFILL_FIXTURE_MISSING=%s in %s" % (FORM_GLOB, PDF_DIR))
        return 4
    fixture = matches[0]
    from app.services.layout_engine_ppstructure import PPStructureEngine
    engine = PPStructureEngine(use_gpu=True)
    if not engine.is_ready():
        print("LAYOUT_READY=False")
        return 3
    import asyncio
    result = asyncio.run(engine._analyze_pdf(fixture))
    elements = result.get("elements", []) or []
    tables = [e for e in elements
              if isinstance(e, dict)
              and "table" in str(e.get("type", "")).lower()
              and isinstance(e.get("bbox"), dict)]
    lines = ["B4b table bbox geometry (closure doc sec.7; full-funnel rate stays registered)",
             "fixture=%s" % os.path.basename(fixture),
             "layout_elements=%d tables=%d" % (len(elements), len(tables))]
    derive_ok = None
    if tables:
        try:
            from app.services.table_backfill import derive_cell_bbox
            bbox = tables[0]["bbox"]

            def _num(v):
                try:
                    return float(v)
                except Exception:
                    return None

            def _cell_bounds(cell):
                """Accept dict {x,y,width,height} or 4-tuple (x0,y0,x1,y1)."""
                if isinstance(cell, dict):
                    vals = tuple(_num(cell.get(k)) for k in ("x", "y", "width", "height"))
                    if all(v is not None for v in vals):
                        x, y, w, h = vals
                        return (x, y, x + w, y + h)
                    return None
                if isinstance(cell, (list, tuple)) and len(cell) == 4:
                    vals = tuple(_num(v) for v in cell)
                    if all(v is not None for v in vals):
                        return vals
                    return None
                return None

            tb_x, tb_y = _num(bbox.get("x")), _num(bbox.get("y"))
            tb_w, tb_h = _num(bbox.get("width")), _num(bbox.get("height"))
            cells = [derive_cell_bbox(bbox, 2, 2, r, c) for r in range(2) for c in range(2)]
            bounds = [_cell_bounds(cell) for cell in cells]
            # derive_cell_bbox returns PT-space rects (raster px / 2): cloud
            # round 2 evidence - cell (36.0, 47.5, ...) vs px-space table
            # x=72/y=95 -> exactly half. Compare in pt space.
            pt = ((tb_x / 2.0, tb_y / 2.0, (tb_x + tb_w) / 2.0, (tb_y + tb_h) / 2.0)
                  if None not in (tb_x, tb_y, tb_w, tb_h) else None)
            inside = True
            if pt is None or None in bounds:
                inside = False
            else:
                for (x0, y0, x1, y1) in bounds:
                    if x0 < pt[0] - 1 or y0 < pt[1] - 1 or x1 > pt[2] + 1 or y1 > pt[3] + 1:
                        inside = False
                        break
            derive_ok = bool(inside)
            lines.append("derive_cell_bbox_2x2=%s first=%r table_px=%r table_pt=%r"
                         % (derive_ok, cells[0],
                            {k: bbox.get(k) for k in ("x", "y", "width", "height")}, pt))
        except Exception as e:
            lines.append("derive_cell_bbox_ERR=%r" % (e,))
            derive_ok = False
    else:
        lines.append("NO_TABLES_DETECTED (first element keys=%r)"
                     % (sorted(elements[0].keys()) if elements and isinstance(elements[0], dict) else None))
    emit("p046tl_backfill.txt", "\n".join(lines) + "\n")
    print("BACKFILL_TABLES=%d" % len(tables))
    print("DERIVE_OK=%s" % derive_ok)
    if not tables:
        return 3
    return 0 if derive_ok else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["env", "ocrsmoke", "userunit", "grounding",
                                        "corpus", "backfill"])
    args = ap.parse_args()
    return {"env": cmd_env, "ocrsmoke": cmd_ocrsmoke, "userunit": cmd_userunit,
            "grounding": cmd_grounding, "corpus": cmd_corpus,
            "backfill": cmd_backfill}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
PYEOF

# ---- 4) env + GPU + pins -----------------------------------------------------
log "=== env/GPU/pins ==="
P046TL_REPO_DIR="$REPO_DIR" P046TL_OUT_DIR="$OUT_DIR" P046TL_PDF_DIR="$PDF_DIR" \
  P046TL_FIXDIR="$FIXDIR" P046TL_DOCS_LIMIT="$DOCS_LIMIT" P046TL_PAGES_PER_DOC="$PAGES_PER_DOC" \
  P046TL_FIXTURE_GLOB="$FIXTURE_GLOB" P046TL_FORM_GLOB="$FORM_GLOB" \
  "$PY" "$PROBE" env > "$OUT_DIR/${PREFIX}_env.log" 2>&1
record env stdout $?
grep -E "^(GPU_OK|PIN_DRIFT_COUNT)=" "$OUT_DIR/${PREFIX}_env.log" > "$OUT_DIR/${PREFIX}_env_keys.txt" || true
GPU_OK="$(sed -n 's/^GPU_OK=//p' "$OUT_DIR/${PREFIX}_env_keys.txt" | tail -1)"
GPU_OK="${GPU_OK:-0}"
PIN_DRIFT="$(sed -n 's/^PIN_DRIFT_COUNT=//p' "$OUT_DIR/${PREFIX}_env_keys.txt" | tail -1)"
PIN_DRIFT="${PIN_DRIFT:-9}"
log "gpu_ok=$GPU_OK pin_drift=$PIN_DRIFT"
if [ "$GPU_REQUIRED" = "1" ] && [ "$GPU_OK" = "0" ]; then
  log "WARN: GPU unavailable -> BLOCKED(7), not a self-heal path"
fi

# ---- 5) contract/unit pytest (B4a included: 3pt-chain fix regression) --------
log "=== contract/unit pytest (B4a + B1/B3/B5 unit layer) ==="
( cd "$REPO_DIR/backend" && PYTHONPATH=. "$PY" -m pytest \
    tests/test_table_backfill.py tests/test_page_text_trust.py \
    tests/evidence/test_gate.py tests/evidence/test_evidence_text_first.py \
    tests/test_pdf_tools_service.py -q --tb=short ) \
  > "$OUT_DIR/${PREFIX}_unit.log" 2>&1
record unit contract_pytest $?

# ---- 6) G3-ocr side smoke ----------------------------------------------------
log "=== G3-ocr side smoke ==="
P046TL_REPO_DIR="$REPO_DIR" P046TL_OUT_DIR="$OUT_DIR" P046TL_FIXDIR="$FIXDIR" \
  "$PY" "$PROBE" ocrsmoke > "$OUT_DIR/${PREFIX}_ocrsmoke.log" 2>&1
record ocrsmoke main $?

# ---- 7) UserUnit=2 (A7) ------------------------------------------------------
log "=== A7 UserUnit probe ==="
P046TL_REPO_DIR="$REPO_DIR" P046TL_OUT_DIR="$OUT_DIR" \
  "$PY" "$PROBE" userunit > "$OUT_DIR/${PREFIX}_userunit.log" 2>&1
record userunit selfconsistency $?

# ---- 8) grounding round-trip (B1) -------------------------------------------
log "=== B1 grounding quote round-trip ==="
P046TL_REPO_DIR="$REPO_DIR" P046TL_OUT_DIR="$OUT_DIR" P046TL_PDF_DIR="$PDF_DIR" \
  P046TL_DOCS_LIMIT="$DOCS_LIMIT" P046TL_PAGES_PER_DOC="$PAGES_PER_DOC" \
  "$PY" "$PROBE" grounding > "$OUT_DIR/${PREFIX}_grounding.log" 2>&1
record grounding roundtrip $?

# ---- 9) corpus: B2 distribution + B3 stability + B5 coverage gap -------------
log "=== B2/B3/B5 corpus pass ==="
P046TL_REPO_DIR="$REPO_DIR" P046TL_OUT_DIR="$OUT_DIR" P046TL_PDF_DIR="$PDF_DIR" \
  P046TL_DOCS_LIMIT="$DOCS_LIMIT" P046TL_PAGES_PER_DOC="$PAGES_PER_DOC" \
  P046TL_FIXTURE_GLOB="$FIXTURE_GLOB" \
  "$PY" "$PROBE" corpus > "$OUT_DIR/${PREFIX}_corpus.log" 2>&1
record corpus stability_calibration $?

# ---- 10) table bbox geometry on GPU (B4b) ------------------------------------
log "=== B4b table bbox geometry ==="
P046TL_REPO_DIR="$REPO_DIR" P046TL_OUT_DIR="$OUT_DIR" P046TL_PDF_DIR="$PDF_DIR" \
  P046TL_FORM_GLOB="$FORM_GLOB" \
  "$PY" "$PROBE" backfill > "$OUT_DIR/${PREFIX}_backfill.log" 2>&1
record backfill geometry $?

# ---- 11) app smoke (C2): pytest API contract; REAL_APP=1 adds a real boot ----
log "=== C2 app smoke ==="
# C2 carriers: real TestClient pytest files (23 cases). The two files named in
# the closure doc draft (test_api_contract_smoke/test_api_pipeline) are
# run-scripts, not pytest files -> exit 5 "no tests collected" (cloud round 1).
( cd "$REPO_DIR/backend" && PYTHONPATH=. "$PY" -m pytest \
    tests/test_analyze_kie_options.py tests/test_blocks_reading_order.py \
    tests/test_phase1_analyze_form.py tests/test_table_template_analyze.py \
    tests/test_trial_auth.py -q --tb=short ) \
  > "$OUT_DIR/${PREFIX}_appsmoke.log" 2>&1
record appsmoke contract_pytest $?
if [ "$REAL_APP" = "1" ]; then
  ( cd "$REPO_DIR/backend" && PYTHONPATH=. nohup "$PY" -m uvicorn app.main:app \
      --host 127.0.0.1 --port "$APP_PORT" > "$OUT_DIR/${PREFIX}_app_real.log" 2>&1 & echo $! > "$OUT_DIR/${PREFIX}_app.pid" )
  up="0"
  i=0
  while [ "$i" -lt "$APP_BOOT_TIMEOUT" ]; do
    code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$APP_PORT/docs" 2>/dev/null || echo 000)"
    if [ "$code" = "200" ]; then up="1"; break; fi
    sleep 5; i=$((i + 5))
  done
  openapi="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$APP_PORT/openapi.json" 2>/dev/null || echo 000)"
  {
    echo "C2 REAL_APP boot smoke (closure doc sec.7)"
    echo "port=$APP_PORT boot_timeout_s=$APP_BOOT_TIMEOUT"
    echo "docs_http=$code openapi_http=$openapi up=$up"
    echo "NOTE: full /pdftools + /page-image endpoint exercise needs an uploaded task; register manually if exercised."
  } > "$OUT_DIR/${PREFIX}_app_real.txt"
  if [ -f "$OUT_DIR/${PREFIX}_app.pid" ]; then
    kill "$(cat "$OUT_DIR/${PREFIX}_app.pid")" 2>/dev/null || true
  fi
  if [ "$up" = "1" ] && [ "$openapi" = "200" ]; then record appsmoke real_boot 0; else record appsmoke real_boot 3; fi
else
  echo "# REAL_APP=0 - real uvicorn boot skipped (set REAL_APP=1)" > "$OUT_DIR/${PREFIX}_app_real.txt"
  record appsmoke real_boot_skipped 0
fi

# ---- 12) judge + summary + verdict draft + return manifest + tar -------------
log "=== judge + artifacts ==="
REQUIRED=(
  "${PREFIX}_env.txt" "${PREFIX}_unit.log" "${PREFIX}_ocrsmoke.txt"
  "${PREFIX}_userunit.txt" "${PREFIX}_grounding.txt" "${PREFIX}_grounding.jsonl"
  "${PREFIX}_calib.jsonl" "${PREFIX}_stability.txt" "${PREFIX}_coverage.txt"
  "${PREFIX}_coverage.jsonl" "${PREFIX}_backfill.txt" "${PREFIX}_app_real.txt"
  "${PREFIX}_rc.tsv"
)
MISSING=0
for f in "${REQUIRED[@]}"; do
  if [ ! -s "$OUT_DIR/$f" ]; then MISSING=$((MISSING + 1)); log "WARN: missing evidence $f"; fi
done

JUDGE_OUT="$(judge_verdict "$RC_FILE" "$GPU_OK" "$PIN_DRIFT" "$MISSING")"
VERDICT="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^VERDICT=//p')"
REASON="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^REASON=//p')"

SUMMARY="$OUT_DIR/${PREFIX}_summary.txt"
{
  echo "P-046 text-layer cloud verification - machine summary (primary carry-back item)"
  echo "HEAD=$HEAD_NOW ref=$RUN_REF date=$(date -Iseconds)"
  echo "EXPECTED_HEAD=$EXPECTED_HEAD STRICT_HEAD=$STRICT_HEAD REAL_APP=$REAL_APP"
  echo "PY=$PY VENV_DIR=${VENV_DIR:-<none>}"
  echo "--- env pins ---"; grep -E '^(pypdfium2|reportlab|pypdf|pdfplumber|paddleocr|paddlex|PyMuPDF|GPU_OK|PIN_DRIFT_COUNT|nvidia_smi|paddle_gpu)=' \
    "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null || echo "(env missing)"
  echo "--- contract/unit pytest (B4a) ---"; tail -3 "$OUT_DIR/${PREFIX}_unit.log" 2>/dev/null || echo "(missing)"
  echo "--- G3-ocr ---"; grep -E '^(OCR_READY|OCR_BLOCKS|RENDER_ENGINE|RENDER_PX)=' "$OUT_DIR/${PREFIX}_ocrsmoke.log" 2>/dev/null || echo "(missing)"
  echo "--- A7 UserUnit ---"; grep -E '^(U1_SELFCONSISTENT|U1_PX)=' "$OUT_DIR/${PREFIX}_userunit.log" 2>/dev/null || echo "(missing)"
  echo "--- B1 grounding ---"; grep -E '^(GROUNDING_SAMPLES|GROUNDING_HITS|GROUNDING)=' "$OUT_DIR/${PREFIX}_grounding.log" 2>/dev/null || echo "(missing)"
  echo "--- B2/B3/B5 corpus ---"; grep -E '^(PAGES_TOTAL|JUDGE_EXCEPTIONS|VERDICT_DIST|FIXTURE_CHECK|GAP_EXPOSED)=' "$OUT_DIR/${PREFIX}_corpus.log" 2>/dev/null || echo "(missing)"
  echo "--- B4b backfill ---"; grep -E '^(BACKFILL_TABLES|DERIVE_OK|LAYOUT_READY)=' "$OUT_DIR/${PREFIX}_backfill.log" 2>/dev/null || echo "(missing)"
  echo "--- app smoke ---"; tail -3 "$OUT_DIR/${PREFIX}_appsmoke.log" 2>/dev/null || echo "(missing)"; cat "$OUT_DIR/${PREFIX}_app_real.txt" 2>/dev/null
  echo "--- rc (step/side/rc) ---"; cat "$RC_FILE"
  echo "--- judge (does NOT replace agentD review / Ying verdict) ---"
  printf '%s\n' "$JUDGE_OUT"
} > "$SUMMARY"

DRAFT="$OUT_DIR/${PREFIX}_verdict_draft.md"
{
  echo "# P-046 text-layer cloud verdict DRAFT (generated; paste readings verbatim)"
  echo
  echo "> Sign-off: Ying (Cloud Studio GPU) -> agentD review. Machine verdict is NOT a gate."
  echo "> Anchor: base=$EXPECTED_HEAD measured HEAD=$HEAD_NOW ref=$RUN_REF date=$(date -I)"
  echo "> Machine verdict: **$VERDICT** ($REASON)"
  echo
  echo "## 0 env / pins"
  echo '```'; grep -E '^(pypdfium2|reportlab|pypdf|pdfplumber|paddleocr|paddlex|PyMuPDF|GPU_OK|PIN_DRIFT_COUNT)=' \
    "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 1 B4a contract/unit pytest (incl. 3pt-chain fix regression)"
  echo '```'; tail -5 "$OUT_DIR/${PREFIX}_unit.log" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 2 G3-ocr side (RENDER_ENGINE self-proof + block count)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_ocrsmoke.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 3 A7 UserUnit (hard: pdfium self-consistency; RECORDED: fitz drift)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_userunit.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 4 B1 grounding round-trip"
  echo '```'; cat "$OUT_DIR/${PREFIX}_grounding.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 5 B2 calibration distribution (registered; human review)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_calib.jsonl" 2>/dev/null | head -40 || echo "(missing)"; echo '```'
  echo
  echo "## 6 B3 stability"
  echo '```'; cat "$OUT_DIR/${PREFIX}_stability.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 7 B5 image_coverage gap exposure (registered)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_coverage.txt" 2>/dev/null; head -20 "$OUT_DIR/${PREFIX}_coverage.jsonl" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 8 B4b table bbox geometry"
  echo '```'; cat "$OUT_DIR/${PREFIX}_backfill.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 9 C2 app smoke"
  echo '```'; tail -5 "$OUT_DIR/${PREFIX}_appsmoke.log" 2>/dev/null || echo "(missing)"; cat "$OUT_DIR/${PREFIX}_app_real.txt" 2>/dev/null; echo '```'
  echo
  echo "## 10 gate decision (agentD fills after review)"
  echo "- [ ] EVIDENCE_READY -> register readings into the closure doc sec.10"
  echo "- [ ] BLOCKED(7) -> stop + report to Ying, no self-heal branch"
  echo "- reviewer / date: ____"
} > "$DRAFT"

MANIFEST="$OUT_DIR/${PREFIX}_return_manifest.md"
TARBALL="${PREFIX}_artifacts_${HEAD_NOW}_$(date +%Y%m%d_%H%M%S).tar.gz"
{
  echo "# P-046 text-layer cloud - data to carry back (manual push-back; script never auto-pushes)"
  echo
  echo "> git push is a red line. This script only lands artifacts + packs + writes this list;"
  echo "> the push-back action is performed by Ying on the local host after download."
  echo "> Machine verdict: **$VERDICT** ($REASON) HEAD=$HEAD_NOW $(date -Iseconds)"
  echo
  echo "## 1 one-shot commands (Cloud Studio)"
  echo '```bash'
  echo "bash p046_textlayer_verify.sh                 # default (contract pytest + all probes)"
  echo "REAL_APP=1 bash p046_textlayer_verify.sh      # + real uvicorn boot + HTTP smoke"
  echo "bash p046_textlayer_verify.sh --self-test     # local logic self-test, no GPU"
  echo '```'
  echo
  echo "## 2 required carry-back data (all inside the tarball)"
  echo "| File | Purpose | Priority |"
  echo "|---|---|---|"
  echo "| \`$TARBALL\` | full artifact bundle | REQUIRED |"
  echo "| \`${PREFIX}_summary.txt\` | machine summary | REQUIRED (primary) |"
  echo "| \`${PREFIX}_verdict_draft.md\` | Ying sign-off template | REQUIRED |"
  echo "| \`${PREFIX}_env.txt\` | pins / GPU readings (pypdfium2>=5,<6 + reportlab>=5,<6) | REQUIRED |"
  echo "| \`${PREFIX}_ocrsmoke.txt\` | G3-ocr side (RENDER_ENGINE self-proof) | REQUIRED |"
  echo "| \`${PREFIX}_userunit.txt\` | A7 hard gate + registered fitz drift | REQUIRED |"
  echo "| \`${PREFIX}_grounding.txt\` / \`.jsonl\` | B1 round-trip | REQUIRED |"
  echo "| \`${PREFIX}_calib.jsonl\` | B2 distribution (registered) | REQUIRED |"
  echo "| \`${PREFIX}_stability.txt\` | B3 zero-exception stability | REQUIRED |"
  echo "| \`${PREFIX}_coverage.txt\` / \`.jsonl\` | B5 registered gap exposure | REQUIRED |"
  echo "| \`${PREFIX}_backfill.txt\` | B4b bbox geometry | REQUIRED |"
  echo "| \`${PREFIX}_unit.log\` / \`${PREFIX}_appsmoke.log\` / \`${PREFIX}_app_real.txt\` | contract + C2 | REQUIRED |"
  echo "| \`${PREFIX}_rc.tsv\` / \`${PREFIX}_probe.py\` / \`${PREFIX}_*.log\` | reproducible evidence | recommended |"
  echo
  echo "## 3 push-back target and commands (local PowerShell, NOT on Cloud)"
  echo '```powershell'
  echo "# (a) merge readings into the verdict .md, then push that .md to bus (local host):"
  echo "& 'D:\\3_PROJECTS\\eWorkers\\agent-bus\\tools\\bus-transfer\\bus-push.ps1' \"
  echo "  -File '<local>/p046tl-cloud-verdict.md' -Path 'runs/R-005/steps/p046tl-cloud-verdict.md' \"
  echo "  -Prefix zcode -Msg 'P-046 text-layer cloud verdict'"
  echo "# (b) land the bundle under docs/R&D/runs/R-005/, update docs/R&D/README.md runs index"
  echo "python scripts/docs_refs_audit.py --check-rnd-index   # expect 0/0"
  echo '```'
  echo
  echo "## 4 discipline"
  echo "- Criteria are fixed in advance; missing evidence = BLOCKED(7), never a forced pass."
  echo "- Local has no GPU: never claim cloud verified; only register readings after unpacking."
  echo "- Registered soft items (UserUnit drift, verdict distribution, coverage gap, backfill"
  echo "  rates) go to agentD review, not to the bash verdict."
} > "$MANIFEST"

PACK_FILES=("${PREFIX}_summary.txt" "${PREFIX}_verdict_draft.md" "${PREFIX}_return_manifest.md"
            "${PREFIX}_rc.tsv" "${PREFIX}_env.txt" "${PREFIX}_probe.py")
for f in "${PREFIX}_env.log" "${PREFIX}_unit.log" "${PREFIX}_ocrsmoke.log" "${PREFIX}_ocrsmoke.txt" \
         "${PREFIX}_userunit.log" "${PREFIX}_userunit.txt" "${PREFIX}_grounding.log" \
         "${PREFIX}_grounding.txt" "${PREFIX}_grounding.jsonl" "${PREFIX}_corpus.log" \
         "${PREFIX}_calib.jsonl" "${PREFIX}_stability.txt" "${PREFIX}_coverage.txt" \
         "${PREFIX}_coverage.jsonl" "${PREFIX}_backfill.log" "${PREFIX}_backfill.txt" \
         "${PREFIX}_appsmoke.log" "${PREFIX}_app_real.txt" "${PREFIX}_app_real.log"; do
  [ -f "$OUT_DIR/$f" ] && PACK_FILES+=("$f")
done
( cd "$OUT_DIR" && tar -czf "$TARBALL" "${PACK_FILES[@]}" ) || die "tar failed"
log "artifacts packed: $OUT_DIR/$TARBALL"

log "=== done; carry back per ${PREFIX}_return_manifest.md ==="
printf '%s\n' "$JUDGE_OUT"
if [ "$VERDICT" = "EVIDENCE_READY" ]; then
  log "evidence ready (NOT a gate: agentD review + Ying sign-off still required)"
  exit 0
fi
log "=== STOP: BLOCKED(7) - report to Ying, no self-heal ==="
exit 7
