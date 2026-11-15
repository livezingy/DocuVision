#!/usr/bin/env bash
# =============================================================================
# r005_cloud_verify.sh - R-005 / P-046 v2 Cloud-side one-shot evidence runner
#
# Source of truth:
#   TEMP/bus/runs/R-005/pack.md v1.0 sec.1/8/9 (V1/V3/V4/V6/V10/V11 + G1-G5/C0)
#   TEMP/bus/runs/R-005/review-01.md v1.1 sec.3 (Cloud scope + P0-5/P0-6 pin recheck)
# Skeleton: scripts/cloud/t1_render_downstream_test.sh
# Discipline: scripts/cloud/README.md + kernel testing.md / constraints.md
#
# Usage (Cloud Studio GPU / Linux, from scripts/cloud/):
#   bash r005_cloud_verify.sh                     # MODE=evidence, default
#   MODE=m1 bash r005_cloud_verify.sh             # after M1 direct-feed lands (R-006)
#   bash r005_cloud_verify.sh --self-test         # local bash-only logic mock, no GPU/deps
#   EXPECTED_HEAD=d26bfa0 STRICT_HEAD=1 bash r005_cloud_verify.sh
#
# Hard boundaries (no forced-pass):
#   - M1 direct-feed is NOT in R-005 (pack sec.0, belongs to R-006). MODE=m1 with
#     M1 absent = UNRUN, never a fake run on the old fitz-rendered chain.
#   - V6/V10/V11 belong to Ying (GPU/business): this script emits evidence and
#     pending-decision lists only; it never decides or rebuilds GT.
#   - Local has no GPU: never claim "cloud verified". Verdict comes from artifacts
#     + agentD review + Ying sign-off.
#   - No bus-push.sh on Linux (the kit is PowerShell, local host only). This script
#     only packs artifacts + writes a return manifest; it never pushes (red line).
#
# Artifacts in OUT_DIR (carry-back payload):
#   r005_env.txt / r005_env_drift.json / r005_pins_recheck.txt / r005_v4_scale.txt
#   r005_v1_schema_diff.jsonl / r005_v1_perf.jsonl / r005_v6_chain.md
#   r005_v10_gt_inventory.jsonl / r005_v11_inventory.txt / r005_g5_pin.txt
#   r005_rc.tsv / r005_summary.txt / r005_verdict_draft.md
#   r005_return_manifest.md / r005_probe.py / r005_*.log
#   r005_artifacts_<HEAD>_<timestamp>.tar.gz
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-r005}"
VENV_DIR="${VENV_DIR-$HOME/docuvision_env}"    # set VENV_DIR= (empty) to skip activation; no-colon keeps the empty value
REPO_DIR="${REPO_DIR:-}"
OUT_DIR="${OUT_DIR:-}"                          # empty = $REPO_DIR/test_data/local/r005_cloud
BRANCH="${BRANCH:-}"
EXPECTED_HEAD="${EXPECTED_HEAD:-d26bfa0}"       # pack sec.9 writing-date anchor; empty falls back to it (kernel forbids un-pinned runs)
STRICT_HEAD="${STRICT_HEAD:-0}"
AUTO_FF="${AUTO_FF:-0}"                         # 1 = explicitly allow git merge --ff-only
MODE="${MODE:-evidence}"                        # evidence | m1
GPU_REQUIRED="${GPU_REQUIRED:-1}"
RUN_PINS="${RUN_PINS:-1}"
RUN_V4="${RUN_V4:-1}"
RUN_V6="${RUN_V6:-1}"
RUN_V10="${RUN_V10:-1}"
RUN_V11="${RUN_V11:-1}"
RUN_G5="${RUN_G5:-1}"
V1_PDF="${V1_PDF:-test_data/testfiles/pdf/sample_report.pdf}"
V1_PAGES="${V1_PAGES:-50}"
V1_TIMEOUT="${V1_TIMEOUT:-1800}"                # seconds; timeout is reported, never retried
GT_DIR="${GT_DIR:-test_data/testfiles/PDF_Parsing/gt}"
PDF_DIR="${PDF_DIR:-test_data/testfiles/pdf}"

log() { echo "[r005] $*"; }
die() { echo "[r005][FATAL] $*" >&2; exit 2; }

# ---- Verdict: single bash-only source of truth (shared with --self-test) -----
# Args: rc.tsv mode m1_ready gpu_ok pin_drift evidence_missing v1_state
# Criteria are fixed in advance (pack sec.8 + review v1.1 sec.3):
#   EVIDENCE_READY = all required evidence present AND no rc!=0 AND GPU up
#     AND no production-pin drift AND (evidence mode skips V1 / m1 mode has V1 data)
#   Everything else = BLOCKED(7). MODE=m1 with M1 absent = UNRUN, not self-heal.
judge_verdict() {
  local rc_file="$1" mode="$2" m1_ready="$3" gpu_ok="$4" pin_drift="$5" missing="$6" v1_state="$7"
  local fails=0 reason="" verdict="EVIDENCE_READY" step side rc
  while IFS=$'\t' read -r step side rc; do
    [ -z "${step:-}" ] && continue
    if [ "${rc:-}" != "0" ]; then
      fails=$((fails + 1)); reason="${reason} ${step}/${side}=rc${rc}"
    fi
  done < "$rc_file"
  [ "$fails" -eq 0 ] || verdict="BLOCKED(7)"
  if [ "$gpu_ok" != "1" ] && [ "$GPU_REQUIRED" = "1" ]; then
    verdict="BLOCKED(7)"; reason="${reason} NO_GPU(cloud GPU unavailable, no evidence claim)"
  fi
  if [ "$pin_drift" != "0" ]; then
    verdict="BLOCKED(7)"; reason="${reason} PIN_DRIFT(${pin_drift} production pins off, readings not comparable)"
  fi
  if [ "$missing" -gt 0 ]; then
    verdict="BLOCKED(7)"; reason="${reason} MISSING_EVIDENCE(${missing} required artifacts absent)"
  fi
  if [ "$mode" = "m1" ]; then
    if [ "$m1_ready" != "1" ]; then
      verdict="BLOCKED(7)"; reason="${reason} M1_UNRUN(M1 not landed, belongs to R-006; no fake run)"
    elif [ "$v1_state" != "OK" ]; then
      verdict="BLOCKED(7)"; reason="${reason} V1_${v1_state}(schema diff / perf readings missing)"
    fi
  fi
  if [ -z "$reason" ]; then
    if [ "$mode" = "m1" ]; then
      reason="M1 landed: V1/V3 schema diff + 50p perf present; V6/V10/V11 pending Ying"
    else
      reason="evidence round: pins/V4/V6/V10/V11/G5 present; M1 belongs to R-006, not run (reported as such)"
    fi
  fi
  echo "VERDICT=${verdict}"
  echo "REASON=${reason# }"
}

# ---- --self-test: local mock, no venv/GPU/pytest ------------------------------
SELF_TEST=0
for arg in "$@"; do
  case "$arg" in
    --self-test) SELF_TEST=1 ;;
    -h|--help) sed -n '2,32p' "$0"; exit 0 ;;
    *) die "unknown arg: $arg (only --self-test / --help)" ;;
  esac
done
if [ "$SELF_TEST" = "1" ]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  ok=0; total=0
  assert_verdict() {
    total=$((total + 1))
    printf '%b' "$3" > "$TMP/rc.tsv"
    out="$(judge_verdict "$TMP/rc.tsv" "$4" "$5" "$6" "$7" "$8" "$9")"
    if printf '%s' "$out" | grep -qF "$1" && printf '%s' "$out" | grep -qF "$2"; then
      ok=$((ok + 1))
    else
      echo "[r005][SELFTEST-FAIL] expect VERDICT~$1 REASON~$2, got: $out" >&2
    fi
  }
  assert_verdict "EVIDENCE_READY" "evidence round" "" evidence 0 1 0 0 UNRUN
  assert_verdict "EVIDENCE_READY" "M1 landed" "" m1 1 1 0 0 OK
  assert_verdict "BLOCKED(7)" "M1_UNRUN" "" m1 0 1 0 0 UNRUN
  assert_verdict "BLOCKED(7)" "V1_TIMEOUT" "" m1 1 1 0 0 TIMEOUT
  assert_verdict "BLOCKED(7)" "NO_GPU" "" evidence 0 0 0 0 UNRUN
  assert_verdict "BLOCKED(7)" "PIN_DRIFT" "" evidence 0 1 2 0 UNRUN
  assert_verdict "BLOCKED(7)" "MISSING_EVIDENCE" "" evidence 0 1 0 3 UNRUN
  assert_verdict "BLOCKED(7)" "rc1" "g1\ts1\t1\n" evidence 0 1 0 0 UNRUN
  echo "[r005][SELFTEST] ${ok}/${total} passed"
  [ "$ok" -eq "$total" ] || exit 1
  exit 0
fi

case "$MODE" in evidence|m1) ;; *) die "MODE must be evidence|m1, got=$MODE" ;; esac
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
[ -n "$OUT_DIR" ] || OUT_DIR="$REPO_DIR/test_data/local/r005_cloud"
mkdir -p "$OUT_DIR" || die "cannot create OUT_DIR=$OUT_DIR"
log "OUT_DIR=$OUT_DIR"
RC_FILE="$OUT_DIR/${PREFIX}_rc.tsv"; : > "$RC_FILE"
PROBE="$OUT_DIR/${PREFIX}_probe.py"

# ---- 2) version check (detached-HEAD safe, no auto-ff) ----------------------
cd "$REPO_DIR" || die "cannot cd $REPO_DIR"
CUR_BRANCH="$(git symbolic-ref -q --short HEAD 2>/dev/null || true)"
[ "$BRANCH" = "HEAD" ] && BRANCH=""
[ -n "$BRANCH" ] || BRANCH="$CUR_BRANCH"
RUN_REF="${CUR_BRANCH:-detached}"
if [ -n "$BRANCH" ]; then
  if git fetch origin "$BRANCH"; then
    log "synced origin/$BRANCH (refs only)"
  elif [ "$AUTO_FF" = "1" ]; then
    die "git fetch failed with AUTO_FF=1"
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
fi
if [ "$AUTO_FF" = "1" ]; then
  [ -n "$CUR_BRANCH" ] || die "AUTO_FF=1 needs a normal branch (detached unsupported)"
  git merge --ff-only "origin/$BRANCH" || die "ff-only failed"
  HEAD_NOW="$(git rev-parse --short HEAD)"
fi
if [ -n "$EXPECTED_HEAD" ]; then
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
log "HEAD=$HEAD_NOW ref=$RUN_REF MODE=$MODE"

# ---- 3) self-contained Python probe (also an artifact: reproducible) ---------
cat > "$PROBE" <<'PYEOF'
#!/usr/bin/env python3
"""R-005 Cloud probe. Self-contained; generated by r005_cloud_verify.sh.

Subcommands: env | pins | v4 | v1 | v10. All output is ASCII JSON/plain text.
Failures are reported as data, never swallowed. Readings are evidence; the
verdict belongs to agentD / Ying, not to this probe.
"""
import json
import os
import re
import sys
import tempfile
import time

CMD = sys.argv[1] if len(sys.argv) > 1 else ""
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
REPO = sys.argv[3] if len(sys.argv) > 3 else "."


def emit(name, obj, jsonl=True):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        elif jsonl:
            for row in obj:
                f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        else:
            json.dump(obj, f, ensure_ascii=False)
            f.write("\n")


def versions():
    import importlib.metadata as md
    names = ["PyMuPDF", "pypdf", "pdfplumber", "pypdfium2", "paddleocr",
             "paddlex", "paddlepaddle-gpu", "paddlepaddle", "Pillow", "reportlab"]
    out = {}
    for n in names:
        try:
            out[n] = md.version(n)
        except Exception:
            out[n] = "MISSING"
    return out


def gpu_info():
    info = {"nvidia_smi": "MISSING", "paddle_gpu": "UNKNOWN"}
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        info["nvidia_smi"] = r.stdout.strip() if r.returncode == 0 else "ERR:" + r.stderr.strip()[:120]
    except Exception as e:
        info["nvidia_smi"] = "ERR:" + str(e)[:120]
    try:
        import paddle
        info["paddle_gpu"] = str(paddle.device.is_compiled_with_cuda())
        info["paddle_version"] = paddle.__version__
    except Exception as e:
        info["paddle_gpu"] = "UNAVAILABLE:" + type(e).__name__
    return info


def cmd_env():
    v = versions()
    g = gpu_info()
    lines = ["R-005 Cloud env / version evidence (pack sec.9 + kernel official-source-first)",
             "python=%s" % sys.version.split()[0], ""]
    lines += ["%s=%s" % (k, val) for k, val in v.items()]
    lines += [""] + ["%s=%s" % (k, val) for k, val in g.items()]
    expected = {"paddleocr": "3.3.2", "paddlex": "3.3.12",
                "paddlepaddle-gpu": "3.3.0", "pypdf": "3.17.4"}
    drifts = [{"package": k, "expected": want, "actual": v.get(k, "MISSING")}
              for k, want in expected.items() if v.get(k, "MISSING") != want]
    lines += ["", "EXPECTED_PINS=" + json.dumps(expected),
              "PIN_DRIFT_COUNT=%d" % len(drifts),
              "PIN_DRIFTS=" + json.dumps(drifts),
              "NOTE: pypdf!=3.17.4 makes V7/V9 readings non-comparable (review v1.1 P0-5/P0-6).",
              "NOTE: paddle stack pins from environment.md; local without GPU reports MISSING here."]
    emit("r005_env.txt", "\n".join(lines) + "\n")
    emit("r005_env_drift.json", drifts, jsonl=False)
    print("PIN_DRIFT_COUNT=%d" % len(drifts))
    print("NVIDIA_SMI=%s" % g["nvidia_smi"][:60])
    return 0


def make_tr3_fixture():
    """Same fixture as attachments/v7_tr3_pypdf_v4_scale.py (pack sec.1 V7)."""
    import fitz
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.insert_text((72, 100), "Hello visible world", fontsize=12, fontname="helv")
    pg.insert_text((72, 100), "INVISIBLE OVERLAY LAYER", fontsize=12,
                   fontname="helv", render_mode=3)
    path = os.path.join(tempfile.mkdtemp(prefix="r005_tr3_"), "tr3.pdf")
    doc.save(path)
    doc.close()
    return path


def cmd_pins():
    """Production-pin recheck of review v1.1 P0-5 (hex Tr3) and P0-6 (exception class)."""
    import fitz
    import pypdf
    lines = ["R-005 production-pin recheck (review-01.md v1.1 sec.1.1 A/B/C/G)",
             "pypdf=%s PyMuPDF=%s" % (versions()["pypdf"], versions()["PyMuPDF"]), ""]
    path = make_tr3_fixture()

    d = fitz.open(path)
    spans = []
    for it in d[0].get_texttrace():
        if isinstance(it, dict):
            if "spans" in it:
                spans.extend(it["spans"])
            elif "lines" in it:
                for ln in it["lines"]:
                    if isinstance(ln, dict):
                        spans.extend(ln.get("spans", []))
            else:
                spans.append(it)
    total = sum(len(s.get("chars", [])) if isinstance(s.get("chars"), (list, tuple))
                else len(s.get("text", "")) for s in spans)
    inv = sum(len(s.get("chars", [])) if isinstance(s.get("chars"), (list, tuple))
              else len(s.get("text", "")) for s in spans if s.get("type") == 3)
    d.close()
    lines.append("A1 fitz get_texttrace: total=%d invisible=%d visible=%d" % (total, inv, total - inv))

    c = pypdf.PdfReader(path).pages[0].get_contents().get_data().decode("latin-1")
    lits = re.findall(r"\((?:[^()\\]|\\.)*\)", c)
    hexes = re.findall(r"<[0-9A-Fa-f]+>", c)
    lines.append("A2 content stream: len=%d Tr_hits=%s literals=%d hex=%d"
                 % (len(c), re.findall(r"(\d+)\s+Tr\b", c), len(lits), len(hexes)))

    segs = re.split(r"(BT|ET)", c)
    state, tr3, vis = "vis", 0, 0
    for seg in segs:
        if seg in ("BT", "ET"):
            if seg == "ET":
                state = "vis"
            continue
        m = re.search(r"(\d+)\s+Tr\b", seg)
        if m:
            state = "tr3" if m.group(1) == "3" else "vis"
        for s in re.findall(r"\((?:[^()\\]|\\.)*\)", seg):
            n = len(s) - 2
            if state == "tr3":
                tr3 += n
            else:
                vis += n
    lines.append("A3 ATTACHMENT parser (literal-only): tr3=%d vis=%d" % (tr3, vis))

    state, h3, hv = "vis", 0, 0
    for seg in segs:
        if seg in ("BT", "ET"):
            if seg == "ET":
                state = "vis"
            continue
        m = re.search(r"(\d+)\s+Tr\b", seg)
        if m:
            state = "tr3" if m.group(1) == "3" else "vis"
        for h in re.findall(r"<([0-9A-Fa-f\s]+)>", seg):
            n = len(re.sub(r"\s", "", h)) // 2
            if state == "tr3":
                h3 += n
            else:
                hv += n
        for s in re.findall(r"\((?:[^()\\]|\\.)*\)", seg):
            n = len(s) - 2
            if state == "tr3":
                h3 += n
            else:
                hv += n
    lines.append("A4 HEX-AWARE parser: tr3=%d vis=%d" % (h3, hv))
    lines.append("A5 attachment reproduces pack 23/19: %s" % ((tr3, vis) == (23, 19)))
    lines.append("A6 hex-aware matches fitz invisible: %s" % (h3 == inv))
    lines.append("P0-5 REPRODUCED=%s (literal-only misses hex stream)" % (tr3 == 0 and h3 == inv))

    import pypdf.errors as pe
    tmp = tempfile.mkdtemp(prefix="r005_v9_")
    normal = os.path.join(tmp, "normal.pdf")
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), "hello")
    doc.save(normal)
    doc.close()
    enc = os.path.join(tmp, "enc.pdf")
    doc = fitz.open(normal)
    doc.save(enc, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="ownerpw", user_pw="")
    doc.close()
    corrupt = os.path.join(tmp, "corrupt.pdf")
    with open(corrupt, "wb") as f:
        f.write(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")
    empty = os.path.join(tmp, "empty.pdf")
    with open(empty, "wb") as f:
        f.write(b"")
    for label, p in [("normal", normal), ("encrypted", enc), ("corrupt", corrupt), ("empty", empty)]:
        try:
            z = fitz.open(p)
            t = z[0].get_text("text") if z.page_count else ""
            fz = "OPEN pages=%d enc=%s text=%r" % (z.page_count, z.is_encrypted, (t or "")[:20])
            z.close()
        except Exception as e:
            fz = "RAISE %s: %s" % (type(e).__name__, str(e)[:70])
        try:
            r = pypdf.PdfReader(p)
            dec = ""
            if r.is_encrypted:
                dec = " decrypt='%s'" % r.decrypt("")
            txt = r.pages[0].extract_text() if len(r.pages) else ""
            pp = "OPEN pages=%d enc=%s%s text=%r" % (len(r.pages), r.is_encrypted, dec, (txt or "")[:20])
        except Exception as e:
            pp = "RAISE %s.%s: %s" % (type(e).__module__, type(e).__name__, str(e)[:70])
        lines.append("C/%s fitz: %s" % (label, fz))
        lines.append("C/%s pypdf: %s" % (label, pp))
    lines.append("G1 PdfStreamError MRO: %s" % [x.__name__ for x in pe.PdfStreamError.__mro__])
    lines.append("G2 except PdfStreamError catches PdfReadError: %s"
                 % issubclass(pe.PdfReadError, pe.PdfStreamError))
    lines.append("G3 fitz.EmptyFileError is pypdf EmptyFileError: %s"
                 % (getattr(fitz, "EmptyFileError", None) is pe.EmptyFileError))
    lines.append("P0-6 REPRODUCED=%s" % (not issubclass(pe.PdfReadError, pe.PdfStreamError)))
    emit("r005_pins_recheck.txt", "\n".join(lines) + "\n")
    print("PINS_OK p0_5=%s p0_6=%s" % (tr3 == 0 and h3 == inv,
                                       not issubclass(pe.PdfReadError, pe.PdfStreamError)))
    return 0


def cmd_v4():
    """V4: fitz Matrix(2,2) vs pypdfium2 scale=2.0; resolve RENDER_SCALE in paddlex source."""
    import fitz
    import pypdfium2
    path = make_tr3_fixture()
    d = fitz.open(path)
    pix = d[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    d.close()
    pdf = pypdfium2.PdfDocument(path)
    bmp = pdf[0].render(scale=2.0)
    size_pdfium = (bmp.width, bmp.height)  # get_size() does not exist in pypdfium2 5.x
    pdf.close()
    lines = ["R-005 V4 scale equivalence (pack sec.1 V4 + attachment :45 GPU-side pending item)",
             "fitz Matrix(2,2)=%dx%d" % (pix.width, pix.height),
             "pypdfium2 scale=2.0=%dx%d" % size_pdfium,
             "equal=%s" % ((pix.width, pix.height) == size_pdfium),
             "PdfBitmap.get_size exists=%s (attachment bug, review P1-3)" % hasattr(bmp, "get_size"),
             ""]
    # Official-source-first. An unavailable paddlex is NOT a source hit (no false positive).
    hits = []
    paddlex_status = "NOT_CHECKED"
    try:
        import paddlex
        root = os.path.dirname(paddlex.__file__)
        paddlex_status = "AVAILABLE:" + root
        for base, _dirs, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                fp = os.path.join(base, fn)
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                        for i, line in enumerate(f, 1):
                            if "PADDLE_PDX_PDF_RENDER_SCALE" in line:
                                hits.append("%s:%d: %s" % (fp, i, line.strip()))
                except OSError:
                    pass
                if len(hits) >= 20:
                    break
    except Exception as e:
        paddlex_status = "UNAVAILABLE:%s:%s" % (type(e).__name__, str(e)[:120])
    if paddlex_status.startswith("AVAILABLE") and hits:
        verify = "VERIFIED"
    elif paddlex_status.startswith("AVAILABLE"):
        verify = "NOT_VERIFIED_NO_SOURCE_HIT (pack sec.0 claim unverified on this build)"
    else:
        verify = "NOT_VERIFIED_PADDLEX_UNAVAILABLE (local/no-GPU side; Cloud build must recheck)"
    lines.append("paddlex_status=%s" % paddlex_status)
    lines.append("RENDER_SCALE_VERIFY=%s" % verify)
    lines.append("source_hits=%d (real source matches only; availability failures NOT counted)" % len(hits))
    lines += hits
    lines.append("env PADDLE_PDX_PDF_RENDER_SCALE=%r" % os.environ.get("PADDLE_PDX_PDF_RENDER_SCALE"))
    emit("r005_v4_scale.txt", "\n".join(lines) + "\n")
    print("V4_OK equal=%s verify=%s hits=%d" % ((pix.width, pix.height) == size_pdfium,
                                                 verify.split()[0], len(hits)))
    return 0


def _result_signature(res):
    """Structural signature of one PaddleX predict result (schema-first, no pixel compare)."""
    out = {}
    for r in res:
        d = dict(r) if hasattr(r, "keys") else {"_type": type(r).__name__}
        page = d.get("page_index", d.get("page", len(out)))
        sig = {}
        for k in sorted(d.keys()):
            v = d[k]
            if isinstance(v, dict):
                sig[k] = {"dict_keys": sorted(v.keys())}
            elif isinstance(v, (list, tuple)):
                sig[k] = {"len": len(v),
                          "item_keys": sorted(v[0].keys()) if v and hasattr(v[0], "keys") else []}
            else:
                sig[k] = {"type": type(v).__name__}
        out[str(page)] = sig
    return out


def _rss_mb():
    try:
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 1)
    except Exception:
        try:
            with open("/proc/self/status", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("VmHWM:"):
                        return round(int(line.split()[1]) / 1024.0, 1)
        except Exception:
            pass
    return -1


def cmd_v1():
    """V1/V3: predict(pdf) direct feed vs current fitz-render path; schema diff + 50p perf.

    Only invoked in MODE=m1 after the caller confirmed M1 landed. Emits UNRUN /
    TIMEOUT truthfully instead of guessing (kernel adversarial-review discipline).
    """
    src_pdf = os.environ.get("R005_V1_PDF", "")
    fixture_path_file = os.path.join(OUT, "r005_v1_fixture_path.txt")
    pdf_path = src_pdf
    if os.path.isfile(fixture_path_file):
        with open(fixture_path_file, encoding="utf-8") as f:
            pdf_path = f.read().strip() or src_pdf
    pages = int(os.environ.get("R005_V1_PAGES", "50"))
    timeout = float(os.environ.get("R005_V1_TIMEOUT", "1800"))
    t0 = time.time()
    rows = []
    perf = []
    # Entry identification: pack sec.0 asserts PaddleX "pipeline.predict('x.pdf')",
    # while this repo instantiates paddleocr.PPStructureV3. They are NOT the same
    # object; record which one is actually callable before drawing conclusions.
    entry = {"repo_entry": "paddleocr.PPStructureV3.predict",
             "pack_entry": "paddlex pipeline.predict('x.pdf')",
             "note": "if predict(pdf) is unsupported on PPStructureV3, report as "
                     "UNSUPPORTED - do NOT silently substitute a PaddleX pipeline"}
    try:
        import paddleocr
        entry["paddleocr_version"] = getattr(paddleocr, "__version__", "UNKNOWN")
    except Exception as e:
        entry["paddleocr_import_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    try:
        import paddlex
        entry["paddlex_version"] = getattr(paddlex, "__version__", "UNKNOWN")
    except Exception as e:
        entry["paddlex_import_error"] = "%s: %s" % (type(e).__name__, str(e)[:200])
    rows.append({"status": "ENTRY", **entry})
    try:
        from paddleocr import PPStructureV3
        import fitz
        eng = PPStructureV3(device="gpu", lang="en", use_doc_unwarping=False)
        doc = fitz.open(pdf_path)
        n = min(len(doc), pages) if pages > 0 else len(doc)
        doc.close()
        rows.append({"status": "FIXTURE", "path": pdf_path, "pages": n,
                     "synthetic_hint": pdf_path != src_pdf,
                     "note": "see r005_v1_fixture.json for synthetic/source provenance"})
        ta = time.time()
        try:
            a = list(eng.predict(pdf_path))
            sig_a = _result_signature(a)
            perf.append({"path": "predict(pdf)", "pages": len(a), "sec": round(time.time() - ta, 3),
                         "rss_mb": _rss_mb(), "status": "OK"})
        except Exception as e:
            sig_a = {}
            perf.append({"path": "predict(pdf)", "sec": round(time.time() - ta, 3),
                         "status": "UNSUPPORTED", "error": "%s: %s" % (type(e).__name__, str(e)[:300])})
            rows.append({"status": "V1_DIRECT_FEED_UNSUPPORTED", "error": str(e)[:300]})
        tb = time.time()
        tmp = tempfile.mkdtemp(prefix="r005_v1_img_")
        sig_b = {}
        try:
            d = fitz.open(pdf_path)
            for i in range(min(len(d), n)):
                if time.time() - t0 > timeout:
                    rows.append({"status": "TIMEOUT", "elapsed_sec": round(time.time() - t0, 1)})
                    break
                pix = d[i].get_pixmap(matrix=fitz.Matrix(2, 2))
                p = os.path.join(tmp, "p%d.png" % i)
                pix.save(p)
                s = _result_signature(list(eng.predict(p)))
                if s:
                    sig_b[str(i)] = next(iter(s.values()))
            d.close()
            perf.append({"path": "fitz_render->predict(image)", "pages": len(sig_b),
                         "sec": round(time.time() - tb, 3), "rss_mb": _rss_mb(), "status": "OK"})
        except Exception as e:
            perf.append({"path": "fitz_render->predict(image)", "sec": round(time.time() - tb, 3),
                         "status": "ERROR", "error": "%s: %s" % (type(e).__name__, str(e)[:300])})
            rows.append({"status": "V1_RENDER_PATH_ERROR", "error": str(e)[:300]})

        # Compare FIELD SCHEMA, not per-page pairing: predict(pdf) may not carry
        # page_index while the render path numbers pages 0..n-1. Pairing by page
        # key would manufacture false drifts. pack sec.1 V1 asserts schema identity.
        def fold_schema(sig_by_page):
            folded = {}
            for _page, fields in (sig_by_page or {}).items():
                for k, v in fields.items():
                    folded.setdefault(k, set()).add(json.dumps(v, sort_keys=True, default=str))
            return {k: sorted(v) for k, v in folded.items()}

        fa, fb = fold_schema(sig_a), fold_schema(sig_b)
        rows.append({"status": "PAGE_KEYS", "predict_pdf_pages": len(sig_a),
                     "render_path_pages": len(sig_b), "note": "page keys are NOT paired"})
        drifts = 0
        for f in sorted(set(fa) | set(fb)):
            if fa.get(f) != fb.get(f):
                drifts += 1
                rows.append({"field": f, "equal": False, "a": fa.get(f), "b": fb.get(f)})
        rows.append({"status": "SUMMARY", "pages_a": len(sig_a), "pages_b": len(sig_b),
                     "fields_compared": len(set(fa) | set(fb)), "schema_drifts": drifts,
                     "elapsed_sec": round(time.time() - t0, 2),
                     "note": "numeric/pixel/bbox drift is NOT a fail criterion (pack sec.1 V1)"})
    except Exception as e:
        rows.append({"status": "UNRUN", "error": "%s: %s" % (type(e).__name__, str(e)[:400])})
        perf.append({"status": "UNRUN", "error": str(e)[:400]})
    emit("r005_v1_schema_diff.jsonl", rows)
    emit("r005_v1_perf.jsonl", perf)
    print("V1_ROWS=%d PERF_ROWS=%d" % (len(rows), len(perf)))
    return 0


def cmd_fixture():
    """Ensure a 50+ page PDF for V1 perf (pack sec.1 V1 item 2).

    Repo samples are <=3 pages. If the supplied PDF is shorter than the target,
    build a SYNTHETIC one by repeating its pages with pypdf (already pinned), and
    record that it is synthetic: a synthetic file validates engine behaviour and
    relative magnitude, NOT the real 50+ page production acceptance. That limit
    is stated in the fixture note and in the verdict draft.
    """
    src = os.environ.get("R005_V1_PDF", "")
    target = int(os.environ.get("R005_V1_PAGES", "50"))
    import hashlib
    import pypdf
    row = {"source": src, "target_pages": target, "synthetic": False}
    if not os.path.isfile(src):
        row.update({"status": "SRC_MISSING"})
        emit("r005_v1_fixture.json", [row])
        print("FIXTURE=SRC_MISSING")
        return 0
    n = len(pypdf.PdfReader(src).pages)
    row["source_pages"] = n
    if n >= target:
        out_path = src
    else:
        out_path = os.path.join(OUT, "r005_v1_50p_synthetic.pdf")
        w = pypdf.PdfWriter()
        r = pypdf.PdfReader(src)
        for i in range(target):
            w.add_page(r.pages[i % n])
        with open(out_path, "wb") as f:
            w.write(f)
        row["synthetic"] = True
        row["note"] = ("Synthetic repeat of the source page(s); NOT a real 50+ page "
                       "production doc. Use V1_PDF to point at a real long document "
                       "for the acceptance-grade memory/latency comparison.")
    with open(out_path, "rb") as f:
        row["sha256"] = hashlib.sha256(f.read()).hexdigest()
    row["pages"] = len(pypdf.PdfReader(out_path).pages)
    row["path"] = out_path
    row["status"] = "OK"
    emit("r005_v1_fixture.json", [row])
    with open(os.path.join(OUT, "r005_v1_fixture_path.txt"), "w", encoding="utf-8") as f:
        f.write(out_path + "\n")
    print("FIXTURE=OK pages=%d synthetic=%s" % (row["pages"], row["synthetic"]))
    return 0


def cmd_v10():
    """V10 GT fault inventory: text-layer GT immune? which bitmap baselines need rebuild?"""
    gt_dir = os.environ.get("R005_GT_DIR", os.path.join(REPO, "test_data/testfiles/PDF_Parsing/gt"))
    rows = []
    if not os.path.isdir(gt_dir):
        rows.append({"status": "GT_DIR_MISSING", "path": gt_dir})
    else:
        for fn in sorted(os.listdir(gt_dir)):
            if not fn.endswith(".gt.json"):
                continue
            try:
                with open(os.path.join(gt_dir, fn), "r", encoding="utf-8") as f:
                    d = json.load(f)
                prov = d.get("provenance", {})
                raw = json.dumps(d)
                rows.append({
                    "file": fn, "schema": d.get("schema"),
                    "generator": prov.get("generator"), "pdf_pages": prov.get("pdf_pages"),
                    "pdf_sha256": prov.get("pdf_sha256"),
                    "tables": len(d.get("tables", [])), "figures": len(d.get("figures", [])),
                    "has_bbox": '"bbox"' in raw or "block_bbox" in raw,
                    "has_image_ref": "image" in raw.lower(),
                    "fitz_word_order_dependency": "word" in raw.lower() or "bbox" in raw,
                    "rebuild_candidate": ('"bbox"' in raw or "image" in raw.lower()),
                    "note": "pack sec.5 :77 - new pdfplumber GT is NOT comparable with stored fitz word order; DO NOT self-decide rebuild (Ying decides)",
                })
            except Exception as e:
                rows.append({"file": fn, "status": "PARSE_ERROR", "error": str(e)[:200]})
    emit("r005_v10_gt_inventory.jsonl", rows)
    print("V10_GT_FILES=%d" % len(rows))
    return 0


DISPATCH = {"env": cmd_env, "pins": cmd_pins, "v4": cmd_v4,
            "fixture": cmd_fixture, "v1": cmd_v1, "v10": cmd_v10}
if CMD not in DISPATCH:
    print("UNKNOWN_CMD=%s" % CMD, file=sys.stderr)
    sys.exit(2)
sys.exit(DISPATCH[CMD]())
PYEOF
log "probe written: $PROBE"

# ---- 4) env / version evidence ------------------------------------------------
log "=== 4/12 env + version evidence ==="
"$PY" "$PROBE" env "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_env.log" 2>&1
record env stdout $?
PIN_DRIFT="$(sed -n 's/^PIN_DRIFT_COUNT=//p' "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null | tail -1 | tr -d '[:space:]')"
case "$PIN_DRIFT" in
  ''|*[!0-9]*)
    PIN_DRIFT="UNKNOWN"
    log "WARN: PIN_DRIFT_COUNT unreadable -> treated as drift (no forced pass)"
    ;;
esac
[ -s "$OUT_DIR/${PREFIX}_env_drift.json" ] || log "WARN: env_drift.json absent -> counted in MISSING_EVIDENCE"
GPU_OK=0
if grep -q "^paddle_gpu=True" "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null; then GPU_OK=1; fi
if grep -q "^nvidia_smi=ERR\|^nvidia_smi=MISSING" "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null; then GPU_OK=0; fi
log "pin_drift=$PIN_DRIFT gpu_ok=$GPU_OK (see ${PREFIX}_env.txt)"
[ "$GPU_REQUIRED" = "1" ] && [ "$GPU_OK" = "0" ] && log "WARN: GPU unavailable -> BLOCKED(7), not a self-heal path"

# ---- 5) production-pin recheck (review v1.1 P0-5 / P0-6) ---------------------
if [ "$RUN_PINS" = "1" ]; then
  log "=== 5/12 production-pin recheck (P0-5 hex Tr3 / P0-6 exception class) ==="
  "$PY" "$PROBE" pins "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_pins.log" 2>&1
  record pins stdout $?
else
  record pins skipped 0
fi

# ---- 6) V4 scale semantics ----------------------------------------------------
if [ "$RUN_V4" = "1" ]; then
  log "=== 6/12 V4 scale + PADDLE_PDX_PDF_RENDER_SCALE official source ==="
  "$PY" "$PROBE" v4 "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_v4.log" 2>&1
  record v4 stdout $?
else
  record v4 skipped 0
fi

# ---- 7) M1 readiness probe (R-006 boundary) ----------------------------------
M1_READY=0
MAIN_ENGINE="$REPO_DIR/backend/app/services/layout_engine_ppstructure.py"
if [ -f "$MAIN_ENGINE" ] && ! grep -qE "get_pixmap|fitz\.Matrix" "$MAIN_ENGINE"; then
  M1_READY=1
fi
log "M1_READY=$M1_READY (0 = still fitz-rasterized, pack sec.0: M1 belongs to R-006)"
V1_STATE="UNRUN"
if [ "$MODE" = "m1" ]; then
  if [ "$M1_READY" != "1" ]; then
    log "M1 not landed -> V1/V3 UNRUN (no fake run on the old chain)"
    record v1 unrun 4
  else
    log "=== 7/12 V1/V3 schema diff + 50p perf (GPU, may take minutes) ==="
    V1_ABS="$V1_PDF"
    case "$V1_ABS" in /*) ;; *) V1_ABS="$REPO_DIR/$V1_PDF" ;; esac
    [ -f "$V1_ABS" ] || die "V1_PDF not found: $V1_ABS"
    # pack sec.1 V1 item 2 needs 50+ pages; repo samples are <=3 pages,
    # so build a synthetic 50p fixture first (provenance recorded, never hidden).
    R005_V1_PDF="$V1_ABS" R005_V1_PAGES="$V1_PAGES" \
      "$PY" "$PROBE" fixture "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_fixture.log" 2>&1
    record fixture stdout $?
    R005_V1_PDF="$V1_ABS" R005_V1_PAGES="$V1_PAGES" \
      R005_V1_TIMEOUT="$V1_TIMEOUT" \
      "$PY" "$PROBE" v1 "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_v1.log" 2>&1
    rc=$?; record v1 stdout "$rc"
    if [ "$rc" = "0" ] && [ -s "$OUT_DIR/${PREFIX}_v1_schema_diff.jsonl" ] \
       && ! grep -q '"status": "UNRUN"\|"status": "TIMEOUT"\|"status": "V1_DIRECT_FEED_UNSUPPORTED"\|"status": "V1_RENDER_PATH_ERROR"' \
            "$OUT_DIR/${PREFIX}_v1_schema_diff.jsonl"; then
      V1_STATE="OK"
    else
      V1_STATE="UNRUN_OR_TIMEOUT"
      log "WARN: V1 readings incomplete -> truthful UNRUN, see ${PREFIX}_v1.log"
    fi
  fi
else
  record v1 out_of_scope 0
  log "V1/V3 deferred (MODE=evidence; M1 belongs to R-006)"
fi

# ---- 8) V6 preprocessing-chain evidence (Ying decides) ----------------------
V6_MD="$OUT_DIR/${PREFIX}_v6_chain.md"
if [ "$RUN_V6" = "1" ]; then
  log "=== 8/12 V6 preprocessing-chain anchors (evidence only) ==="
  {
    echo "# R-005 V6 preprocessing-chain placement - Cloud evidence (Ying decides)"
    echo
    echo "> pack sec.1 V6 belongs to Ying (GPU/business). This script lists file:line anchors"
    echo "> only and never decides the placement. HEAD=$HEAD_NOW ref=$RUN_REF date=$(date -Iseconds)"
    echo
    echo '## 1 chain hits (git grep, reproducible)'
    echo '```'
    ( cd "$REPO_DIR" && git grep -n -E "preprocess|coordinate_space|angle_deg|use_doc_unwarping" \
        -- 'backend/app' 2>/dev/null | head -80 ) || echo "(no hits)"
    echo '```'
    echo
    echo '## 2 pending decisions (fill in; script must not decide)'
    echo '- [ ] After predict(pdf) direct feed, where does preprocess (deskew/unwarp/coordinate_space) sit?'
    echo '- [ ] Do angle_deg / coordinate_space still gate proof_render.py skips?'
    echo '- [ ] Is layout_engine_subprocess.py synced? (pack sec.1 V5 single-point convergence)'
    echo
    echo '## 3 page attribution (pack sec.1 V2)'
    echo '```'
    ( cd "$REPO_DIR" && git grep -n -E "page_num \+ 1|page_num\+1|_parse_result" \
        -- 'backend/app/services/layout_engine_ppstructure.py' 2>/dev/null | head -30 ) || echo "(no hits)"
    echo '```'
    echo
    echo "> Owner: Ying (GPU/business). Return with the artifact bundle to runs/R-005/steps/"
  } > "$V6_MD"
  record v6 stdout 0
else
  echo "# V6 skipped (RUN_V6=0)" > "$V6_MD"; record v6 skipped 0
fi

# ---- 9) V10 GT fault inventory ------------------------------------------------
if [ "$RUN_V10" = "1" ]; then
  log "=== 9/12 V10 GT fault inventory ==="
  R005_GT_DIR="$REPO_DIR/$GT_DIR" "$PY" "$PROBE" v10 "$OUT_DIR" "$REPO_DIR" \
    > "$OUT_DIR/${PREFIX}_v10.log" 2>&1
  record v10 stdout $?
else
  record v10 skipped 0
fi

# ---- 10) V11 scale inventory + C0 recount ------------------------------------
V11_TXT="$OUT_DIR/${PREFIX}_v11_inventory.txt"
if [ "$RUN_V11" = "1" ]; then
  log "=== 10/12 V11 inventory + C0 fitz recount ==="
  {
    echo "R-005 V11 inventory / C0 zero-hit recount (reproducible commands kept verbatim)"
    echo "HEAD=$HEAD_NOW ref=$RUN_REF date=$(date -Iseconds)"
    echo
    echo "[cmd] git grep -l -E 'import fitz|from fitz' -- backend/app"
    ( cd "$REPO_DIR" && git grep -l -E 'import fitz|from fitz' -- backend/app || true )
    echo
    echo "[cmd] git grep -c -E 'fitz[.]' -- backend/tests"
    ( cd "$REPO_DIR" && git grep -c -E 'fitz[.]' -- backend/tests || true )
    echo
    echo "[cmd] git grep -l -E 'import fitz|from fitz' -- test_data/scripts scripts/trial"
    ( cd "$REPO_DIR" && git grep -l -E 'import fitz|from fitz' -- test_data/scripts scripts/trial || true )
    echo
    echo "[cmd] find test_data/testfiles -name '*.pdf' | wc -l"
    find "$REPO_DIR/test_data/testfiles" -name '*.pdf' 2>/dev/null | wc -l
    echo "[cmd] find <GT_DIR> -name '*.gt.json' | wc -l"
    find "$REPO_DIR/$GT_DIR" -name '*.gt.json' 2>/dev/null | wc -l
    echo
    echo "[C0] rg -l 'import fitz|from fitz' --glob '!backend/app/services/layout_engine_*.py' (pack sec.8)"
    ( cd "$REPO_DIR" && git grep -l -E 'import fitz|from fitz' \
        -- . ':(exclude,glob)backend/app/services/layout_engine_*.py' 2>/dev/null | head -60 ) || true
    echo "NOTE: review v1.1 P0-1/P1-4 - C0 as written also hits TEMP/bus, scripts/cloud, docs;"
    echo "      zero-hit is NOT reachable without scoping. Report truthfully."
  } > "$V11_TXT"
  record v11 stdout 0
else
  echo "# V11 skipped (RUN_V11=0)" > "$V11_TXT"; record v11 skipped 0
fi

# ---- 11) G5 E1 pin + test registry -------------------------------------------
G5_TXT="$OUT_DIR/${PREFIX}_g5_pin.txt"
if [ "$RUN_G5" = "1" ]; then
  log "=== 11/12 G5 E1 pin + test registry audit ==="
  G5_RC=0
  {
    echo "R-005 G5 E1 pin (5 specs / 15 cases, as-of v1.13.0) - no semantic downgrade"
    echo "[cmd] python scripts/check_e2e_allowlist.py"
    ( cd "$REPO_DIR" && "$PY" scripts/check_e2e_allowlist.py ) 2>&1
    rc1=$?; echo "check_e2e_allowlist_rc=$rc1"
    echo
    echo "[cmd] python -c json.load(scripts/e2e_suite_pin.json)"
    ( cd "$REPO_DIR" && "$PY" -c "import json;print(json.load(open('scripts/e2e_suite_pin.json',encoding='utf-8')))" ) 2>&1
    rc2=$?; echo "suite_pin_rc=$rc2"
    echo
    echo "NOTE: pack sec.8 G5 requires new tests registered in backend/tests/test_registry.json."
  } > "$G5_TXT"
  grep -q "^check_e2e_allowlist_rc=0$" "$G5_TXT" || G5_RC=1
  grep -q "^suite_pin_rc=0$" "$G5_TXT" || G5_RC=1
  record g5 stdout "$G5_RC"
else
  echo "# G5 skipped (RUN_G5=0)" > "$G5_TXT"; record g5 skipped 0
fi

# ---- 12) judge + summary + verdict draft + return manifest + tar -------------
log "=== 12/12 judge + artifacts ==="
REQUIRED=(
  "${PREFIX}_env.txt" "${PREFIX}_env_drift.json" "${PREFIX}_pins_recheck.txt"
  "${PREFIX}_v4_scale.txt" "${PREFIX}_v6_chain.md" "${PREFIX}_v10_gt_inventory.jsonl"
  "${PREFIX}_v11_inventory.txt" "${PREFIX}_g5_pin.txt" "${PREFIX}_rc.tsv"
)
MISSING=0
for f in "${REQUIRED[@]}"; do
  if [ ! -s "$OUT_DIR/$f" ]; then MISSING=$((MISSING + 1)); log "WARN: missing evidence $f"; fi
done
if [ "$MODE" = "m1" ] && [ "$M1_READY" = "1" ]; then
  for f in "${PREFIX}_v1_schema_diff.jsonl" "${PREFIX}_v1_perf.jsonl" \
           "${PREFIX}_v1_fixture.json"; do
    [ -s "$OUT_DIR/$f" ] || MISSING=$((MISSING + 1))
  done
fi

JUDGE_OUT="$(judge_verdict "$RC_FILE" "$MODE" "$M1_READY" "$GPU_OK" "$PIN_DRIFT" "$MISSING" "$V1_STATE")"
VERDICT="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^VERDICT=//p')"
REASON="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^REASON=//p')"

SUMMARY="$OUT_DIR/${PREFIX}_summary.txt"
{
  echo "R-005 / P-046 v2 Cloud evidence - machine summary (primary carry-back item)"
  echo "HEAD=$HEAD_NOW ref=$RUN_REF MODE=$MODE date=$(date -Iseconds)"
  echo "EXPECTED_HEAD=$EXPECTED_HEAD STRICT_HEAD=$STRICT_HEAD AUTO_FF=$AUTO_FF"
  echo "PY=$PY VENV_DIR=${VENV_DIR:-<none>}"
  echo "--- env pins ---"; grep -E '^(pypdf|PyMuPDF|paddlex|paddleocr|paddlepaddle-gpu|PIN_DRIFT_COUNT|nvidia_smi|paddle_gpu)=' \
    "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null || echo "(env missing)"
  echo "--- production-pin recheck (review v1.1 P0-5/P0-6) ---"
  grep -E '^(A[1-6] |G[1-3] |P0-[56] |C/(normal|encrypted|corrupt|empty) )' \
    "$OUT_DIR/${PREFIX}_pins_recheck.txt" 2>/dev/null || echo "(pins missing)"
  echo "--- V4 ---"; grep -E '^(fitz Matrix|pypdfium2|equal=|env PADDLE|paddlex_status|RENDER_SCALE_VERIFY|source_hits)' \
    "$OUT_DIR/${PREFIX}_v4_scale.txt" 2>/dev/null || echo "(v4 missing)"
  echo "--- V1/V3 ---"
  echo "M1_READY=$M1_READY V1_STATE=$V1_STATE V1_PDF=$V1_PDF V1_PAGES=$V1_PAGES"
  [ -s "$OUT_DIR/${PREFIX}_v1_fixture.json" ] && cat "$OUT_DIR/${PREFIX}_v1_fixture.json"
  [ -s "$OUT_DIR/${PREFIX}_v1_schema_diff.jsonl" ] && tail -3 "$OUT_DIR/${PREFIX}_v1_schema_diff.jsonl"
  [ -s "$OUT_DIR/${PREFIX}_v1_perf.jsonl" ] && tail -3 "$OUT_DIR/${PREFIX}_v1_perf.jsonl"
  echo "--- V10 GT ---"; head -20 "$OUT_DIR/${PREFIX}_v10_gt_inventory.jsonl" 2>/dev/null || true
  echo "--- rc (step/side/rc) ---"; cat "$RC_FILE"
  echo "--- judge (does NOT replace agentD review / Ying verdict) ---"
  printf '%s\n' "$JUDGE_OUT"
} > "$SUMMARY"

# verdict draft for Ying / agentD
DRAFT="$OUT_DIR/${PREFIX}_verdict_draft.md"
{
  echo "# R-005 Cloud evidence verdict DRAFT (generated; paste readings verbatim)"
  echo
  echo "> Sign-off: Ying (Cloud Studio GPU) -> return runs/R-005/steps/r005-cloud-verdict.md -> agentD review"
  echo "> Anchor: baseline=$EXPECTED_HEAD measured HEAD=$HEAD_NOW ref=$RUN_REF date=$(date -I)"
  echo "> Machine verdict: **$VERDICT** ($REASON)"
  echo "> Machine verdict is NOT a gate: V6/V10/V11 belong to Ying; M1 belongs to R-006."
  echo
  echo "## 0 env / versions (verbatim from ${PREFIX}_env.txt)"
  echo '```'; grep -E '^(pypdf|PyMuPDF|paddlex|paddleocr|paddlepaddle-gpu|PIN_DRIFT_COUNT|nvidia_smi|paddle_gpu)=' \
    "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 1 production-pin recheck (review v1.1 P0-5 / P0-6)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_pins_recheck.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 2 V4 scale / PADDLE_PDX_PDF_RENDER_SCALE official source"
  echo '```'; cat "$OUT_DIR/${PREFIX}_v4_scale.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 3 V1/V3 (M1 direct feed, belongs to R-006)"
  echo "- M1_READY=$M1_READY V1_STATE=$V1_STATE MODE=$MODE"
  echo "- [ ] schema diff zero drift / [ ] drift (attach ${PREFIX}_v1_schema_diff.jsonl, stop + report)"
  echo "- [ ] 50p memory/latency present (${PREFIX}_v1_perf.jsonl) / [ ] UNRUN (M1 absent, reported)"
  echo "- [ ] entry identified: pack says PaddleX pipeline.predict(pdf), repo uses PPStructureV3"
  echo "      (${PREFIX}_v1_schema_diff.jsonl ENTRY row; do NOT substitute silently)"
  echo "- [ ] fixture provenance checked (${PREFIX}_v1_fixture.json): if synthetic=true,"
  echo "      the 50p numbers are NOT acceptance-grade; supply a real long doc via V1_PDF"
  echo
  echo "## 4 V6 / V10 / V11 (decide one by one)"
  echo "- [ ] V6 placement: ____ (${PREFIX}_v6_chain.md)"
  echo "- [ ] V10 text-layer GT immunity: ____ ; bitmap baseline rebuild list: ____"
  echo "      (${PREFIX}_v10_gt_inventory.jsonl; DO NOT self-trigger a rebuild)"
  echo "- [ ] V11 freeze-marker vs rebuild: ____ (${PREFIX}_v11_inventory.txt)"
  echo
  echo "## 5 G5 / C0"
  echo "- [ ] E1 pin 5 specs / 15 cases no semantic downgrade (${PREFIX}_g5_pin.txt)"
  echo "- [ ] C0 zero-hit recount (${PREFIX}_v11_inventory.txt; review P1-4 scope needs clarification first)"
  echo
  echo "## 6 gate decision (agentD fills after review)"
  echo "- [ ] EVIDENCE_READY -> register evidence; still NOT a P-046 closure (M1 = R-006)"
  echo "- [ ] BLOCKED(7) -> stop + report to Ying, no self-heal branch"
  echo "- reviewer / date: ____"
} > "$DRAFT"

# return manifest: what must be carried back from Cloud (no bus-push.sh on Linux)
MANIFEST="$OUT_DIR/${PREFIX}_return_manifest.md"
TARBALL="${PREFIX}_artifacts_${HEAD_NOW}_$(date +%Y%m%d_%H%M%S).tar.gz"
{
  echo "# R-005 Cloud - data to carry back (manual push-back; script never auto-pushes)"
  echo
  echo "> No bus-push.sh on Cloud Linux (the kit is PowerShell, local host only)."
  echo "> git push is a red line. This script only lands artifacts + packs + writes this list;"
  echo "> the push-back action is performed by Ying on the local host after download."
  echo "> Machine verdict: **$VERDICT** ($REASON) HEAD=$HEAD_NOW $(date -Iseconds)"
  echo
  echo "## 1 one-shot commands (Cloud Studio)"
  echo '```bash'
  echo "bash r005_cloud_verify.sh                 # evidence (default)"
  echo "MODE=m1 bash r005_cloud_verify.sh         # after M1 lands: add V1/V3"
  echo "bash r005_cloud_verify.sh --self-test     # local logic self-test, no GPU"
  echo '```'
  echo
  echo "## 2 required carry-back data (all inside the tarball)"
  echo "| File | Purpose | Priority |"
  echo "|---|---|---|"
  echo "| \`$TARBALL\` | full artifact bundle | REQUIRED |"
  echo "| \`${PREFIX}_summary.txt\` | machine summary | REQUIRED (primary) |"
  echo "| \`${PREFIX}_verdict_draft.md\` | Ying sign-off template | REQUIRED |"
  echo "| \`${PREFIX}_env.txt\` / \`${PREFIX}_env_drift.json\` | pins / GPU readings | REQUIRED (P1-1) |"
  echo "| \`${PREFIX}_pins_recheck.txt\` | P0-5/P0-6 Cloud reproduction | REQUIRED |"
  echo "| \`${PREFIX}_v4_scale.txt\` | V4 + RENDER_SCALE source hits | REQUIRED |"
  echo "| \`${PREFIX}_v1_schema_diff.jsonl\` / \`${PREFIX}_v1_perf.jsonl\` | V1/V3 (MODE=m1 only) | REQUIRED if present |"
  echo "| \`${PREFIX}_v1_fixture.json\` | 50p fixture provenance (synthetic flag + sha256 + source) | REQUIRED if MODE=m1 |"
  echo "| \`${PREFIX}_v1_50p_synthetic.pdf\` | NOT packed (binary); reproducible from source PDF + page count, sha256 in json |"
  echo "| \`${PREFIX}_v6_chain.md\` | preprocessing anchors + pending decisions | REQUIRED |"
  echo "| \`${PREFIX}_v10_gt_inventory.jsonl\` | GT fault inventory | REQUIRED |"
  echo "| \`${PREFIX}_v11_inventory.txt\` | inventory + C0 recount | REQUIRED |"
  echo "| \`${PREFIX}_g5_pin.txt\` | E1 pin recheck | REQUIRED |"
  echo "| \`${PREFIX}_rc.tsv\` / \`${PREFIX}_probe.py\` / \`${PREFIX}_*.log\` | reproducible evidence | recommended |"
  echo
  echo "## 3 push-back target and commands (local PowerShell, NOT on Cloud)"
  echo '```powershell'
  echo "# (a) push verdict .md to bus (local host; pick the -Prefix matching your identity)"
  echo "& 'D:\\3_PROJECTS\\eWorkers\\agent-bus\\tools\\bus-transfer\\bus-push.ps1' \"
  echo "  -File '<local>/r005-cloud-verdict.md' -Path 'runs/R-005/steps/r005-cloud-verdict.md' \"
  echo "  -Prefix zcode -Msg 'R-005 Cloud evidence verdict'"
  echo "# (b) land the bundle under docs/R&D/runs/R-005/, update docs/R&D/README.md runs index"
  echo "python scripts/docs_refs_audit.py --check-rnd-index   # expect 0/0"
  echo "# (c) bus-refs.md append-only entry: bus path @ sha"
  echo '```'
  echo "> Do NOT push the tarball to bus directly (>100KB binary red line + .md-only path"
  echo "> allowlist). Merge the readings into the verdict .md, then push that .md."
  echo
  echo "## 4 discipline"
  echo "- Local has no GPU: never claim cloud verified; only register readings after unpacking."
  echo "- Criteria are fixed in advance; missing evidence = BLOCKED(7), never a forced pass."
  echo "- V6/V10/V11 belong to Ying, review belongs to agentD; M1 is R-006, P-046 stays open."
} > "$MANIFEST"

PACK_FILES=("${PREFIX}_summary.txt" "${PREFIX}_verdict_draft.md" "${PREFIX}_return_manifest.md"
            "${PREFIX}_rc.tsv" "${PREFIX}_env.txt" "${PREFIX}_env_drift.json" "${PREFIX}_probe.py")
for f in "${PREFIX}_env.log" "${PREFIX}_pins.log" "${PREFIX}_pins_recheck.txt" \
         "${PREFIX}_v4.log" "${PREFIX}_v4_scale.txt" "${PREFIX}_v1.log" \
         "${PREFIX}_v1_schema_diff.jsonl" "${PREFIX}_v1_perf.jsonl" \
         "${PREFIX}_v1_fixture.json" "${PREFIX}_fixture.log" \
         "${PREFIX}_v6_chain.md" "${PREFIX}_v10.log" "${PREFIX}_v10_gt_inventory.jsonl" \
         "${PREFIX}_v11_inventory.txt" "${PREFIX}_g5_pin.txt"; do
  [ -f "$OUT_DIR/$f" ] && PACK_FILES+=("$f")
done
( cd "$OUT_DIR" && tar -czf "$TARBALL" "${PACK_FILES[@]}" ) || die "tar failed"
log "artifacts packed: $OUT_DIR/$TARBALL"

log "=== done; carry back per ${PREFIX}_return_manifest.md ==="
printf '%s\n' "$JUDGE_OUT"
if [ "$VERDICT" = "EVIDENCE_READY" ]; then
  log "evidence ready (NOT a gate: V6/V10/V11 pending Ying; M1 belongs to R-006)"
  exit 0
fi
log "=== STOP: BLOCKED(7) - report to Ying, no self-heal ==="
exit 7
