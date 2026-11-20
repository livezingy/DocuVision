#!/usr/bin/env bash
# =============================================================================
# cloud_r003_r004_verify.sh - R-003 (P-042) + R-004 (P-043) Cloud-side one-shot
#
# Source of truth:
#   runs/R-003/contract.md (P-042 Egress: batch export / Sheets / 幂等 / 同源同值 / per-order)
#   runs/R-004/contract.md (P-043 n8n 集成包: webhook 对账 / 文档==55 / OpenAPI / 闭环)
#   runs/R-003/pack.md + runs/R-004/pack.md sec.4 (测试分工矩阵)
# Skeleton: scripts/cloud/r005_cloud_verify.sh (版本核验 / 自包含探针 / 判定 / verdict 草稿 / tar)
# Discipline: scripts/cloud/README.md + kernel testing.md / constraints.md
#
# Usage (Cloud Studio GPU / Linux, from scripts/cloud/):
#   bash cloud_r003_r004_verify.sh                  # 默认：契约单测面（无需 GPU/凭据）
#   RUN_E2E=1 bash cloud_r003_r004_verify.sh        # 追加 R-004 闭环验证（需 GPU + n8n + 后端）
#   RUN_SHEETS=1 GOOGLE_CRED=/path/sa.json bash ...  # 追加 R-003 Sheets 真连接（需 Google 凭据）
#   bash cloud_r003_r004_verify.sh --self-test      # 本机判定逻辑 mock 自测（无 GPU/依赖）
#   EXPECTED_HEAD=<sha> STRICT_HEAD=1 bash cloud_r003_r004_verify.sh
#
# Hard boundaries (no forced-pass):
#   - 契约单测（pytest）本机即可跑，不依赖 GPU；这是本脚本的"可自动化核心"。
#   - R-004 闭环（AC1）需 GPU（analyze 成功才有 task.completed）+ n8n + 后端；未满足 = UNRUN。
#   - R-003 Sheets 真连接需 Google 服务账号凭据；未提供 = UNRUN（凭据红线：不进仓不进日志）。
#   - SSRF 回调可达性 = Ying 决策，脚本不裁决。
#   - 本机无 GPU ⇒ 不宣称云端已验证；闭环面证据只在 tar 解包核验后登记。
#   - 云端无 bus-push.sh（kit 为 PowerShell 本地宿主）；脚本只落盘 + 打包 + 回传清单，不 push。
#
# Artifacts in OUT_DIR (carry-back payload):
#   r34_env.txt / r34_rc.tsv / r34_summary.txt / r34_verdict_draft.md
#   r34_contract_r004.txt / r34_contract_r003.txt / r34_e1_pin.txt / r34_docs_audit.txt
#   r34_full_pytest.txt（RUN_FULL=1）/ r34_e2e.txt（RUN_E2E=1）/ r34_sheets.txt（RUN_SHEETS=1）
#   r34_probe.py / r34_return_manifest.md / r34_*.log
#   r34_artifacts_<HEAD>_<timestamp>.tar.gz
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-r34}"
VENV_DIR="${VENV_DIR-$HOME/docuvision_env}"   # set VENV_DIR= to skip activation
REPO_DIR="${REPO_DIR:-}"
OUT_DIR="${OUT_DIR:-}"                        # empty = $REPO_DIR/test_data/local/r003_r004_cloud
BRANCH="${BRANCH:-}"
EXPECTED_HEAD="${EXPECTED_HEAD:-}"            # 正式轮次必填（kernel forbids un-pinned runs）
STRICT_HEAD="${STRICT_HEAD:-0}"
AUTO_FF="${AUTO_FF:-0}"
MODE="${MODE:-contract}"                      # contract | e2e | sheets | all
RUN_FULL="${RUN_FULL:-0}"                     # 1 = 全量 backend pytest（AC5，较长）
RUN_E2E="${RUN_E2E:-0}"                       # 1 = R-004 闭环验证（需 GPU + n8n + 后端）
RUN_SHEETS="${RUN_SHEETS:-0}"                 # 1 = R-003 Sheets 真连接（需 GOOGLE_CRED）
GOOGLE_CRED="${GOOGLE_CRED:-}"                # Google 服务账号 JSON 路径（不进仓不进日志）
GOOGLE_SHEET_ID="${GOOGLE_SHEET_ID:-}"        # 测试 Sheet ID
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
N8N_DB="${N8N_DB:-}"                          # n8n database.sqlite 路径（闭环观察用）
N8N_WORKFLOW_ID="${N8N_WORKFLOW_ID:-CchvJFmkgAkaO1pc}"
E2E_POLL_SEC="${E2E_POLL_SEC:-60}"            # 闭环观察轮询窗口（秒）
GPU_REQUIRED="${GPU_REQUIRED:-1}"

# 契约单测清单（gate = 仓内测试文件名；可被环境变量覆盖）
# 注意：路径相对 backend/（脚本 cd backend 后执行），故必须带 tests/ 前缀
R004_TESTS="${R004_TESTS:-tests/test_webhook_service.py tests/test_route_inventory.py tests/test_openapi_snapshot.py tests/test_route_doc_reconciliation.py}"
R003_TESTS="${R003_TESTS:-tests/test_batch_export_service.py tests/test_export_service.py}"

log() { echo "[r34] $*"; }
die() { echo "[r34][FATAL] $*" >&2; exit 2; }

# ---- Verdict: single bash-only source of truth (shared with --self-test) -----
# Args: rc_file mode gpu_ok missing e2e_state sheets_state
#   e2e_state / sheets_state: OK | UNRUN | FAIL
# Criteria fixed in advance:
#   EVIDENCE_READY = contract tests all rc==0 AND no required evidence missing
#     AND (e2e OK-or-UNRUN) AND (sheets OK-or-UNRUN)
#   BLOCKED(7) = any contract rc!=0 / missing evidence / e2e enabled but FAIL
#     / sheets enabled but FAIL / e2e enabled and GPU_REQUIRED but no GPU
judge_verdict() {
  local rc_file="$1" mode="$2" gpu_ok="$3" missing="$4" e2e_state="$5" sheets_state="$6"
  local fails=0 reason="" verdict="EVIDENCE_READY" step side rc
  while IFS=$'\t' read -r step side rc; do
    [ -z "${step:-}" ] && continue
    if [ "${rc:-}" != "0" ]; then
      fails=$((fails + 1)); reason="${reason} ${step}/${side}=rc${rc}"
    fi
  done < "$rc_file"
  [ "$fails" -eq 0 ] || verdict="BLOCKED(7)"
  if [ "$missing" -gt 0 ]; then
    verdict="BLOCKED(7)"; reason="${reason} MISSING_EVIDENCE(${missing})"
  fi
  if [ "$e2e_state" = "FAIL" ]; then
    verdict="BLOCKED(7)"; reason="${reason} E2E_FAIL"
  fi
  if [ "$sheets_state" = "FAIL" ]; then
    verdict="BLOCKED(7)"; reason="${reason} SHEETS_FAIL"
  fi
  if [ "$e2e_state" = "OK" ] || [ "$mode" = "e2e" ] || [ "$mode" = "all" ]; then
    if [ "$GPU_REQUIRED" = "1" ] && [ "$gpu_ok" != "1" ] && [ "$e2e_state" != "UNRUN" ]; then
      verdict="BLOCKED(7)"; reason="${reason} NO_GPU(e2e requires GPU)"
    fi
  fi
  if [ -z "$reason" ]; then
    reason="contract tests green; e2e=${e2e_state} sheets=${sheets_state} (UNRUN = 环境/凭据未备，如实申报，非本脚本强行通过)"
  fi
  echo "VERDICT=${verdict}"
  echo "REASON=${reason# }"
}

# ---- --self-test --------------------------------------------------------------
SELF_TEST=0
for arg in "$@"; do
  case "$arg" in
    --self-test) SELF_TEST=1 ;;
    -h|--help) sed -n '2,34p' "$0"; exit 0 ;;
    *) die "unknown arg: $arg (only --self-test / --help)" ;;
  esac
done
if [ "$SELF_TEST" = "1" ]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  ok=0; total=0
  assert_verdict() {
    total=$((total + 1))
    printf '%b' "$3" > "$TMP/rc.tsv"
    out="$(judge_verdict "$TMP/rc.tsv" "$4" "$5" "$6" "$7" "$8")"
    if printf '%s' "$out" | grep -qF "$1" && printf '%s' "$out" | grep -qF "$2"; then
      ok=$((ok + 1))
    else
      echo "[r34][SELFTEST-FAIL] expect VERDICT~$1 REASON~$2, got: $out" >&2
    fi
  }
  assert_verdict "EVIDENCE_READY" "contract tests green" "" contract 0 0 UNRUN UNRUN
  assert_verdict "EVIDENCE_READY" "e2e=OK" "" all 1 0 OK UNRUN
  assert_verdict "EVIDENCE_READY" "sheets=OK" "" all 1 0 UNRUN OK
  assert_verdict "BLOCKED(7)" "rc1" "c\ts\t1\n" contract 0 0 UNRUN UNRUN
  assert_verdict "BLOCKED(7)" "MISSING_EVIDENCE" "" contract 0 3 UNRUN UNRUN
  assert_verdict "BLOCKED(7)" "E2E_FAIL" "" all 1 0 FAIL UNRUN
  assert_verdict "BLOCKED(7)" "SHEETS_FAIL" "" all 1 0 UNRUN FAIL
  assert_verdict "BLOCKED(7)" "NO_GPU" "" e2e 0 0 OK UNRUN
  echo "[r34][SELFTEST] ${ok}/${total} passed"
  [ "$ok" -eq "$total" ] || exit 1
  exit 0
fi

case "$MODE" in contract|e2e|sheets|all) ;; *) die "MODE must be contract|e2e|sheets|all, got=$MODE" ;; esac
case "$MODE" in e2e|all) RUN_E2E=1 ;; esac
case "$MODE" in sheets|all) RUN_SHEETS=1 ;; esac
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
    [ -f "$d/backend/app/main.py" ] && REPO_DIR="$d" && break
    d="$(dirname "$d")"
  done
fi
[ -n "$REPO_DIR" ] || die "repo not found; set REPO_DIR=/path/to/DocuVision"
[ -f "$REPO_DIR/backend/requirements.txt" ] || die "REPO_DIR does not look like DocuVision: $REPO_DIR"
log "REPO_DIR=$REPO_DIR"
[ -n "$OUT_DIR" ] || OUT_DIR="$REPO_DIR/test_data/local/r003_r004_cloud"
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
  if git fetch origin "$BRANCH" 2>/dev/null; then
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
  log "WARN: EXPECTED_HEAD not pinned - comparability at your own risk (formal round MUST pin)"
fi
log "HEAD=$HEAD_NOW ref=$RUN_REF MODE=$MODE"

# ---- 3) self-contained Python probe (artifact: reproducible) ----------------
cat > "$PROBE" <<'PYEOF'
#!/usr/bin/env python3
"""R-003 + R-004 Cloud probe. Self-contained; generated by cloud_r003_r004_verify.sh.

Subcommands: env | e2e_precheck | e2e_observe | sheets
All output is ASCII text. Readings are evidence; verdict belongs to agentD / Ying.
"""
import json
import os
import sys
import time

CMD = sys.argv[1] if len(sys.argv) > 1 else ""
OUT = sys.argv[2] if len(sys.argv) > 2 else "."
REPO = sys.argv[3] if len(sys.argv) > 3 else "."


def cmd_env():
    import importlib.metadata as md
    names = ["PyMuPDF", "pypdf", "pypdfium2", "paddleocr", "paddlex",
             "paddlepaddle-gpu", "paddlepaddle", "gspread", "Pillow", "requests"]
    lines = ["R-003/R-004 Cloud env / version evidence",
             "python=%s" % sys.version.split()[0], ""]
    for n in names:
        try:
            lines.append("%s=%s" % (n, md.version(n)))
        except Exception:
            lines.append("%s=MISSING" % n)
    gpu = {"nvidia_smi": "MISSING", "paddle_gpu": "UNKNOWN"}
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                            "--format=csv,noheader"], capture_output=True, text=True, timeout=20)
        gpu["nvidia_smi"] = r.stdout.strip() if r.returncode == 0 else "ERR"
    except Exception as e:
        gpu["nvidia_smi"] = "ERR:" + str(e)[:80]
    try:
        import paddle
        gpu["paddle_gpu"] = str(paddle.device.is_compiled_with_cuda())
    except Exception as e:
        gpu["paddle_gpu"] = "UNAVAILABLE:" + type(e).__name__
    lines += ["", "nvidia_smi=%s" % gpu["nvidia_smi"], "paddle_gpu=%s" % gpu["paddle_gpu"]]
    with open(os.path.join(OUT, "r34_env.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("paddle_gpu=%s nvidia_smi=%s" % (gpu["paddle_gpu"], gpu["nvidia_smi"][:50]))
    return 0


def _get(url, token=None, timeout=8):
    import urllib.request
    req = urllib.request.Request(url)
    if token:
        # webhooks.py:35 reads X-DocuVision-Admin-Token; Authorization/Bearer is NOT accepted.
        req.add_header("X-DocuVision-Admin-Token", token)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def cmd_e2e_precheck():
    """R-004 closure precheck: backend health + webhook subscribe state + n8n DB + CSV dir."""
    backend = os.environ.get("R34_BACKEND_URL", "http://127.0.0.1:8000")
    lines = ["R-004 closure precheck (AC1 前置三件 + 环境)"]
    try:
        s, body = _get(backend + "/health")
        lines.append("backend_health=%s %s" % (s, body[:120]))
    except Exception as e:
        lines.append("backend_health=ERR %s" % str(e)[:120])
    # webhook 订阅注册状态（需 token；token 经环境变量注入，不进日志）
    tok = os.environ.get("R34_WEBHOOK_ADMIN_TOKEN", "")
    if tok:
        try:
            s, body = _get(backend + "/api/v1/webhooks", token=tok)
            lines.append("webhook_list_http=%s" % s)
            lines.append("webhook_list_body=%s" % body[:200])
        except Exception as e:
            lines.append("webhook_list=ERR %s" % str(e)[:120])
    else:
        lines.append("webhook_list=SKIP (R34_WEBHOOK_ADMIN_TOKEN not set)")
    # n8n DB 可读性 + execution_entity 状态
    ndb = os.environ.get("R34_N8N_DB", "")
    if ndb and os.path.isfile(ndb):
        lines.append("n8n_db=present %s" % ndb)
        lines.append("n8n_db_hint=observe step reads execution_entity via sqlite3; 见 r34_e2e.txt")
    else:
        lines.append("n8n_db=MISSING (set R34_N8N_DB to n8n database.sqlite for full observe)")
    # CSV 落盘目录（watch dir）
    watch = os.environ.get("R34_WATCH_DIR", "")
    if watch:
        import glob
        csvs = glob.glob(os.path.join(watch, "*.csv"))
        lines.append("watch_dir=%s csv_count=%d" % (watch, len(csvs)))
        for c in csvs[-5:]:
            lines.append("  csv=%s mtime=%s" % (c, time.ctime(os.path.getmtime(c))))
    else:
        lines.append("watch_dir=UNSET (set R34_WATCH_DIR to CSV 落盘目录)")
    with open(os.path.join(OUT, "r34_e2e_precheck.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def cmd_e2e_observe():
    """R-004 closure observe: poll n8n execution_entity for mode=trigger success + CSV landing.

    Read-only. Requires sqlite3 module + R34_N8N_DB + R34_WATCH_DIR.
    Polls R34_E2E_POLL_SEC seconds; reports evidence, never fakes a pass.
    """
    import glob
    import sqlite3
    ndb = os.environ.get("R34_N8N_DB", "")
    wf = os.environ.get("R34_N8N_WORKFLOW_ID", "CchvJFmkgAkaO1pc")
    watch = os.environ.get("R34_WATCH_DIR", "")
    window = int(os.environ.get("R34_E2E_POLL_SEC", "60"))
    lines = ["R-004 closure observe (evidence only)", "window_sec=%d" % window]
    if not ndb or not os.path.isfile(ndb):
        lines.append("UNRUN: R34_N8N_DB missing/unreadable")
        with open(os.path.join(OUT, "r34_e2e.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("E2E=UNRUN")
        return 0
    trig_before = 0
    con = sqlite3.connect(ndb)
    try:
        cur = con.cursor()
        cur.execute("select count(*) from execution_entity where mode='trigger' and status='success'")
        trig_before = cur.fetchone()[0]
    except Exception as e:
        lines.append("sqlite_err=%s" % str(e)[:120])
    finally:
        con.close()
    lines.append("trigger_success_before=%d" % trig_before)
    csv_before = len(glob.glob(os.path.join(watch, "*.csv"))) if watch else -1
    lines.append("csv_before=%d" % csv_before)
    time.sleep(window)
    trig_after = trig_before
    try:
        con = sqlite3.connect(ndb)
        cur = con.cursor()
        cur.execute("select count(*) from execution_entity where mode='trigger' and status='success'")
        trig_after = cur.fetchone()[0]
        lines.append("trigger_success_after=%d" % trig_after)
        cur.execute("select id,status,createdAt from execution_entity where workflowId=? order by id desc limit 5",
                    (wf,))
        for row in cur.fetchall():
            lines.append("  exec=%s status=%s created=%s" % row)
        con.close()
    except Exception as e:
        lines.append("sqlite_err_after=%s" % str(e)[:120])
    csv_after = len(glob.glob(os.path.join(watch, "*.csv"))) if watch else -1
    lines.append("csv_after=%d" % csv_after)
    if trig_after > trig_before:
        lines.append("E2E_TRIGGER=OK (+%d trigger success)" % (trig_after - trig_before))
    else:
        lines.append("E2E_TRIGGER=NO_NEW (no new trigger success in window)")
    with open(os.path.join(OUT, "r34_e2e.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("E2E_TRIGGER_AFTER=%d BEFORE=%d CSV_AFTER=%d" % (trig_after, trig_before, csv_after))
    return 0


def cmd_sheets():
    """R-003 Sheets 真连接 + 幂等：走被测服务 export_batch_to_sheets（upsert 语义）。

    2026-11-17 轮4 教训：直接 ws.append_row 两次是纯追加 API，必然重复行——
    幂等语义由 sheets_export_service._upsert_rows（按 task_id 删旧插新）保证，
    探针必须调用被测服务两次（同一 batch），断言行数不翻倍。
    独立 worksheet（MappedRows-e2e-<ts>）：run1 走 created_header 分支，
    run2 走 upsert（delete+append）分支，两条路径都被真实覆盖。
    """
    cred = os.environ.get("R34_GOOGLE_CRED", "")
    sheet_id = os.environ.get("R34_GOOGLE_SHEET_ID", "")
    lines = ["R-003 Sheets 真连接 e2e（被测服务 upsert 幂等：同 batch 跑两次不重复行）"]
    if not cred or not os.path.isfile(cred):
        lines.append("UNRUN: R34_GOOGLE_CRED missing (凭据前置见 pack §5，AgentE 执行)")
        with open(os.path.join(OUT, "r34_sheets.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("SHEETS=UNRUN")
        return 0
    if not sheet_id:
        lines.append("UNRUN: R34_GOOGLE_SHEET_ID missing")
        with open(os.path.join(OUT, "r34_sheets.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print("SHEETS=UNRUN")
        return 0
    try:
        sys.path.insert(0, os.path.join(REPO, "backend"))
        from app.services.batch_models import BatchJob, BatchTask, TaskStatus
        from app.services.sheets_export_service import export_batch_to_sheets

        ts = int(time.time())
        task = BatchTask(
            task_id="e2e_%d" % ts,
            file_path="/tmp/r34_e2e_sample.png",
            file_name="e2e_sample.png",
        )
        task.status = TaskStatus.COMPLETED
        task.result = {
            "mapped_table_rows": [
                {"po_number": "PO-E2E-001", "quantity": "2", "unit_price": "10.5"}
            ],
            "mapped_table_fields": ["po_number", "quantity", "unit_price"],
        }
        batch = BatchJob(
            batch_id="e2e_batch_%d" % ts,
            name="r34-sheets-e2e",
            tasks=[task],
            options={},
            total_tasks=1,
        )
        ws_name = "MappedRows-e2e-%d" % ts
        s1 = export_batch_to_sheets(
            batch, credentials_file=cred, spreadsheet_id=sheet_id, worksheet_name=ws_name
        )
        import gspread as _g
        sh = _g.service_account(filename=cred).open_by_key(sheet_id)
        ws1 = sh.worksheet(ws_name)
        rows_1 = len(ws1.get_all_values())
        s2 = export_batch_to_sheets(
            batch, credentials_file=cred, spreadsheet_id=sheet_id, worksheet_name=ws_name
        )
        rows_2 = len(ws1.get_all_values())
        lines.append("sheet_id=%s worksheet=%s" % (sheet_id, ws_name))
        lines.append("run1=%s" % json.dumps(s1, ensure_ascii=False))
        lines.append("run2=%s" % json.dumps(s2, ensure_ascii=False))
        lines.append("rows_after_run1=%d rows_after_run2=%d" % (rows_1, rows_2))
        idem = (rows_2 == rows_1) and s2.get("replaced_tasks", 0) >= 1 \
            and s2.get("created_header") is False
        lines.append("idempotent=%s (expect rows equal + replaced_tasks>=1 + upsert branch)" % idem)
        lines.append("SHEETS=OK" if idem else "SHEETS=FAIL idempotent")
    except Exception as e:
        lines.append("SHEETS=ERR %s: %s" % (type(e).__name__, str(e)[:200]))
    with open(os.path.join(OUT, "r34_sheets.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("SHEETS_DONE")
    return 0


DISPATCH = {"env": cmd_env, "e2e_precheck": cmd_e2e_precheck,
            "e2e_observe": cmd_e2e_observe, "sheets": cmd_sheets}
if CMD not in DISPATCH:
    print("UNKNOWN_CMD=%s" % CMD, file=sys.stderr)
    sys.exit(2)
sys.exit(DISPATCH[CMD]())
PYEOF
log "probe written: $PROBE"

# ---- 4) env evidence ---------------------------------------------------------
log "=== 4 env + version evidence ==="
"$PY" "$PROBE" env "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_env.log" 2>&1
record env stdout $?
GPU_OK=0
if grep -q "^paddle_gpu=True" "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null; then GPU_OK=1; fi
if grep -q "^nvidia_smi=ERR\|^nvidia_smi=MISSING" "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null; then GPU_OK=0; fi
log "gpu_ok=$GPU_OK"

# ---- 5) R-004 contract tests (pytest) ---------------------------------------
log "=== 5 R-004 contract tests ==="
R004_TXT="$OUT_DIR/${PREFIX}_contract_r004.txt"
if [ -n "$R004_TESTS" ]; then
  {
    echo "R-004 contract tests (AC2 webhook 对账 / AC3 文档==55 / AC4 OpenAPI)"
    echo "[cmd] cd backend && PYTHONPATH=. pytest -q $R004_TESTS"
  } > "$R004_TXT"
  ( cd "$REPO_DIR/backend" && PYTHONPATH=. "$PY" -m pytest -q $R004_TESTS ) \
    >> "$R004_TXT" 2>&1
  record r004_contract stdout $?
else
  echo "# R-004 contract tests skipped (R004_TESTS empty)" > "$R004_TXT"
  record r004_contract skipped 0
fi

# ---- 6) R-003 contract tests (pytest) ---------------------------------------
log "=== 6 R-003 contract tests ==="
R003_TXT="$OUT_DIR/${PREFIX}_contract_r003.txt"
if [ -n "$R003_TESTS" ]; then
  {
    echo "R-003 contract tests (AC1/AC2/AC6 batch export / AC3 同源同值)"
    echo "[cmd] cd backend && PYTHONPATH=. pytest -q $R003_TESTS"
  } > "$R003_TXT"
  ( cd "$REPO_DIR/backend" && PYTHONPATH=. "$PY" -m pytest -q $R003_TESTS ) \
    >> "$R003_TXT" 2>&1
  record r003_contract stdout $?
else
  echo "# R-003 contract tests skipped (R003_TESTS empty)" > "$R003_TXT"
  record r003_contract skipped 0
fi

# ---- 7) E1 pin + docs_refs_audit ---------------------------------------------
log "=== 7 E1 pin + docs_refs_audit ==="
E1_TXT="$OUT_DIR/${PREFIX}_e1_pin.txt"
{
  echo "R-003 E1 pin（5 specs / 15 用例，只增不减语义）+ R-004 AC5 交付物对账"
  echo "[cmd] python scripts/check_e2e_allowlist.py"
  ( cd "$REPO_DIR" && "$PY" scripts/check_e2e_allowlist.py ) 2>&1
  echo "check_e2e_allowlist_rc=$?"
} > "$E1_TXT"
grep -q "^check_e2e_allowlist_rc=0$" "$E1_TXT" || E1_RC=1
record e1_pin stdout "${E1_RC:-0}"

DOC_TXT="$OUT_DIR/${PREFIX}_docs_audit.txt"
{
  echo "R-004 AC5 交付物落仓对账"
  echo "[cmd] python scripts/docs_refs_audit.py --check-rnd-index"
  ( cd "$REPO_DIR" && "$PY" scripts/docs_refs_audit.py --check-rnd-index ) 2>&1
  echo "docs_refs_audit_rc=$?"
} > "$DOC_TXT"
grep -q "^docs_refs_audit_rc=0$" "$DOC_TXT" || DOC_RC=1
record docs_audit stdout "${DOC_RC:-0}"

# ---- 8) full pytest (optional) -----------------------------------------------
FULL_TXT="$OUT_DIR/${PREFIX}_full_pytest.txt"
if [ "$RUN_FULL" = "1" ]; then
  log "=== 8 full backend pytest (AC5/AC6, may be long) ==="
  {
    echo "R-003/R-004 full backend pytest"
    echo "[cmd] cd backend && PYTHONPATH=. pytest -q"
  } > "$FULL_TXT"
  ( cd "$REPO_DIR/backend" && PYTHONPATH=. "$PY" -m pytest -q ) >> "$FULL_TXT" 2>&1
  record full_pytest stdout $?
else
  echo "# full pytest skipped (RUN_FULL=0)" > "$FULL_TXT"
  record full_pytest skipped 0
fi

# ---- 9) R-004 e2e closure (conditional: GPU + n8n + backend) -----------------
E2E_TXT="$OUT_DIR/${PREFIX}_e2e.txt"
E2E_STATE="UNRUN"
if [ "$RUN_E2E" = "1" ]; then
  log "=== 9 R-004 closure e2e (requires GPU + n8n + backend) ==="
  R34_BACKEND_URL="$BACKEND_URL" R34_WEBHOOK_ADMIN_TOKEN="${R34_WEBHOOK_ADMIN_TOKEN:-}" \
    R34_N8N_DB="$N8N_DB" R34_WATCH_DIR="${R34_WATCH_DIR:-}" \
    "$PY" "$PROBE" e2e_precheck "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_e2e_precheck.log" 2>&1
  record e2e_precheck stdout $?
  log "提示：请确认 PO 测试邮件已发送到授权邮箱（或经 n8n/Graph 触发），脚本将观察 $E2E_POLL_SEC 秒"
  R34_N8N_DB="$N8N_DB" R34_N8N_WORKFLOW_ID="$N8N_WORKFLOW_ID" \
    R34_WATCH_DIR="${R34_WATCH_DIR:-}" R34_E2E_POLL_SEC="$E2E_POLL_SEC" \
    "$PY" "$PROBE" e2e_observe "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_e2e_observe.log" 2>&1
  record e2e_observe stdout $?
  if grep -q "E2E_TRIGGER=OK" "$OUT_DIR/${PREFIX}_e2e.txt" 2>/dev/null; then
    E2E_STATE="OK"
  elif grep -q "UNRUN" "$OUT_DIR/${PREFIX}_e2e.txt" 2>/dev/null; then
    E2E_STATE="UNRUN"
  else
    E2E_STATE="FAIL"
  fi
  log "e2e_state=$E2E_STATE"
else
  echo "# R-004 closure e2e skipped (RUN_E2E=0; 需 GPU + n8n + 后端)" > "$E2E_TXT"
  record e2e skipped 0
fi

# ---- 10) R-003 Sheets real (conditional: Google cred) -------------------------
SHEETS_TXT="$OUT_DIR/${PREFIX}_sheets.txt"
SHEETS_STATE="UNRUN"
if [ "$RUN_SHEETS" = "1" ]; then
  log "=== 10 R-003 Sheets real e2e (requires Google service account) ==="
  R34_GOOGLE_CRED="$GOOGLE_CRED" R34_GOOGLE_SHEET_ID="$GOOGLE_SHEET_ID" \
    "$PY" "$PROBE" sheets "$OUT_DIR" "$REPO_DIR" > "$OUT_DIR/${PREFIX}_sheets.log" 2>&1
  record sheets stdout $?
  if grep -q "SHEETS=OK" "$OUT_DIR/${PREFIX}_sheets.txt" 2>/dev/null; then
    SHEETS_STATE="OK"
  elif grep -q "SHEETS=FAIL\|SHEETS=ERR" "$OUT_DIR/${PREFIX}_sheets.txt" 2>/dev/null; then
    SHEETS_STATE="FAIL"
  fi
  log "sheets_state=$SHEETS_STATE"
else
  echo "# R-003 Sheets real e2e skipped (RUN_SHEETS=0; 需 Google 凭据)" > "$SHEETS_TXT"
  record sheets skipped 0
fi

# ---- 11) judge + summary + verdict draft + return manifest + tar ------------
log "=== 11 judge + artifacts ==="
REQUIRED=("${PREFIX}_env.txt" "${PREFIX}_contract_r004.txt" "${PREFIX}_contract_r003.txt"
          "${PREFIX}_e1_pin.txt" "${PREFIX}_docs_audit.txt" "${PREFIX}_rc.tsv")
MISSING=0
for f in "${REQUIRED[@]}"; do
  [ -s "$OUT_DIR/$f" ] || { MISSING=$((MISSING + 1)); log "WARN: missing evidence $f"; }
done
[ "$RUN_E2E" = "1" ] && [ ! -s "$OUT_DIR/${PREFIX}_e2e.txt" ] && MISSING=$((MISSING + 1))
[ "$RUN_SHEETS" = "1" ] && [ ! -s "$OUT_DIR/${PREFIX}_sheets.txt" ] && MISSING=$((MISSING + 1))

JUDGE_OUT="$(judge_verdict "$RC_FILE" "$MODE" "$GPU_OK" "$MISSING" "$E2E_STATE" "$SHEETS_STATE")"
VERDICT="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^VERDICT=//p')"
REASON="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^REASON=//p')"

SUMMARY="$OUT_DIR/${PREFIX}_summary.txt"
{
  echo "R-003 (P-042) + R-004 (P-043) Cloud - machine summary (primary carry-back item)"
  echo "HEAD=$HEAD_NOW ref=$RUN_REF MODE=$MODE date=$(date -Iseconds)"
  echo "EXPECTED_HEAD=${EXPECTED_HEAD:-<unpinned>} STRICT_HEAD=$STRICT_HEAD"
  echo "PY=$PY VENV_DIR=${VENV_DIR:-<none>}"
  echo "--- env ---"; grep -E '^(paddlepaddle-gpu|paddleocr|paddlex|paddle_gpu|nvidia_smi|gspread)=' \
    "$OUT_DIR/${PREFIX}_env.txt" 2>/dev/null || echo "(env missing)"
  echo "--- R-004 contract tail ---"; tail -8 "$OUT_DIR/${PREFIX}_contract_r004.txt" 2>/dev/null || true
  echo "--- R-003 contract tail ---"; tail -8 "$OUT_DIR/${PREFIX}_contract_r003.txt" 2>/dev/null || true
  echo "--- e2e ---"; cat "$OUT_DIR/${PREFIX}_e2e.txt" 2>/dev/null || echo "e2e_state=$E2E_STATE"
  echo "--- sheets ---"; cat "$OUT_DIR/${PREFIX}_sheets.txt" 2>/dev/null || echo "sheets_state=$SHEETS_STATE"
  echo "--- rc (step/side/rc) ---"; cat "$RC_FILE"
  echo "--- judge (does NOT replace agentD review / Ying verdict) ---"
  printf '%s\n' "$JUDGE_OUT"
} > "$SUMMARY"

DRAFT="$OUT_DIR/${PREFIX}_verdict_draft.md"
{
  echo "# R-003 + R-004 Cloud evidence verdict DRAFT (generated; paste readings verbatim)"
  echo
  echo "> Sign-off: Ying (Cloud Studio GPU) -> return runs/R-004/attachments/ -> agentD review"
  echo "> Anchor: baseline=${EXPECTED_HEAD:-unpinned} measured HEAD=$HEAD_NOW ref=$RUN_REF date=$(date -I)"
  echo "> Machine verdict: **$VERDICT** ($REASON)"
  echo "> Machine verdict is NOT a gate: e2e/sheets 的 UNRUN 是环境/凭据未备，非本脚本强行通过。"
  echo
  echo "## 1 R-004 contract (AC2 webhook / AC3 文档==55 / AC4 OpenAPI)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_contract_r004.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 2 R-003 contract (AC1/2/6 batch export / AC3 同源同值)"
  echo '```'; cat "$OUT_DIR/${PREFIX}_contract_r003.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 3 E1 pin + docs audit"
  echo '```'; cat "$OUT_DIR/${PREFIX}_e1_pin.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo '```'; cat "$OUT_DIR/${PREFIX}_docs_audit.txt" 2>/dev/null || echo "(missing)"; echo '```'
  echo
  echo "## 4 R-004 closure e2e (AC1, GPU 依赖)"
  echo "- [ ] e2e_state=$E2E_STATE（UNRUN = GPU/n8n/后端未备，见 ${PREFIX}_e2e.txt）"
  echo "    - trigger success 是否 +N / CSV 是否落盘（${PREFIX}_e2e.txt）"
  echo "    - 闭环面 = task.completed 回调 → CSV，本机无 GPU 不可证，Cloud 轮次收口"
  echo
  echo "## 5 R-003 Sheets real (凭据依赖)"
  echo "- [ ] sheets_state=$SHEETS_STATE（UNRUN = Google 凭据未备，见 ${PREFIX}_sheets.txt）"
  echo "    - 幂等断言 after == rows_before + 1"
  echo
  echo "## 6 gate decision (agentD fills after review)"
  echo "- [ ] EVIDENCE_READY -> register readings; e2e/sheets UNRUN 项仍按 backog 走 Cloud 轮次"
  echo "- [ ] BLOCKED(7) -> stop + report to Ying, no self-heal branch"
  echo "- reviewer / date: ____"
} > "$DRAFT"

MANIFEST="$OUT_DIR/${PREFIX}_return_manifest.md"
TARBALL="${PREFIX}_artifacts_${HEAD_NOW}_$(date +%Y%m%d_%H%M%S).tar.gz"
{
  echo "# R-003 + R-004 Cloud - data to carry back (manual push-back; script never auto-pushes)"
  echo
  echo "> No bus-push.sh on Cloud Linux (kit = PowerShell, local host only). git push = red line."
  echo "> Machine verdict: **$VERDICT** ($REASON) HEAD=$HEAD_NOW $(date -Iseconds)"
  echo
  echo "## 1 one-shot commands (Cloud Studio)"
  echo '```bash'
  echo "bash cloud_r003_r004_verify.sh                 # 契约单测面（无需 GPU/凭据）"
  echo "RUN_FULL=1 bash cloud_r003_r004_verify.sh      # 追加全量 pytest"
  echo "RUN_E2E=1 N8N_DB=/path/to/database.sqlite R34_WATCH_DIR=/files/watch \\"
  echo "  R34_WEBHOOK_ADMIN_TOKEN=... bash cloud_r003_r004_verify.sh   # 追加 R-004 闭环"
  echo "RUN_SHEETS=1 GOOGLE_CRED=/path/sa.json GOOGLE_SHEET_ID=... \\"
  echo "  bash cloud_r003_r004_verify.sh               # 追加 R-003 Sheets 真连接"
  echo "bash cloud_r003_r004_verify.sh --self-test     # 本机判定逻辑自测，无 GPU"
  echo '```'
  echo
  echo "## 2 required carry-back data (inside tarball)"
  echo "| File | Purpose | Priority |"
  echo "|---|---|---|"
  echo "| \`$TARBALL\` | full artifact bundle | REQUIRED |"
  echo "| \`${PREFIX}_summary.txt\` | machine summary | REQUIRED (primary) |"
  echo "| \`${PREFIX}_verdict_draft.md\` | Ying sign-off template | REQUIRED |"
  echo "| \`${PREFIX}_env.txt\` | GPU/paddle/gspread 版本 | REQUIRED |"
  echo "| \`${PREFIX}_contract_r004.txt\` / \`${PREFIX}_contract_r003.txt\` | 契约单测 | REQUIRED |"
  echo "| \`${PREFIX}_e1_pin.txt\` / \`${PREFIX}_docs_audit.txt\` | E1 pin / 交付物对账 | REQUIRED |"
  echo "| \`${PREFIX}_e2e.txt\` / \`${PREFIX}_sheets.txt\` | 闭环 / Sheets 证据（RUN_*=1 时） | REQUIRED if present |"
  echo "| \`${PREFIX}_rc.tsv\` / \`${PREFIX}_probe.py\` / \`${PREFIX}_*.log\` | 可复现证据 | recommended |"
  echo
  echo "## 3 push-back target (local PowerShell, NOT on Cloud)"
  echo '```powershell'
  echo "& 'D:\\3_PROJECTS\\eWorkers\\agent-bus\\tools\\bus-transfer\\bus-push.ps1' \""
  echo "  -File '<local>/r003-r004-cloud-verdict.md' -Path 'runs/R-004/steps/r003-r004-cloud-verdict.md' \""
  echo "  -Prefix zcode -Msg 'R-003/R-004 Cloud evidence verdict'"
  echo "python scripts/docs_refs_audit.py --check-rnd-index   # expect 0/0"
  echo '```'
  echo "> Do NOT push the tarball to bus directly (>100KB binary red line). Merge readings into verdict .md then push."
  echo
  echo "## 4 discipline"
  echo "- Local no GPU: never claim cloud verified; register readings only after unpacking."
  echo "- Criteria fixed in advance; missing evidence = BLOCKED(7), never forced pass."
  echo "- e2e (GPU) / sheets (凭据) 的 UNRUN 如实申报，按 cloud-test-backlog 走后续轮次。"
} > "$MANIFEST"

PACK_FILES=("${PREFIX}_summary.txt" "${PREFIX}_verdict_draft.md" "${PREFIX}_return_manifest.md"
            "${PREFIX}_rc.tsv" "${PREFIX}_env.txt" "${PREFIX}_probe.py")
for f in "${PREFIX}_contract_r004.txt" "${PREFIX}_contract_r003.txt" "${PREFIX}_e1_pin.txt" \
         "${PREFIX}_docs_audit.txt" "${PREFIX}_full_pytest.txt" "${PREFIX}_e2e.txt" \
         "${PREFIX}_e2e_precheck.txt" "${PREFIX}_sheets.txt" "${PREFIX}_env.log" \
         "${PREFIX}_e2e_precheck.log" "${PREFIX}_e2e_observe.log" "${PREFIX}_sheets.log"; do
  [ -f "$OUT_DIR/$f" ] && PACK_FILES+=("$f")
done
( cd "$OUT_DIR" && tar -czf "$TARBALL" "${PACK_FILES[@]}" ) || die "tar failed"
log "artifacts packed: $OUT_DIR/$TARBALL"

log "=== done; carry back per ${PREFIX}_return_manifest.md ==="
printf '%s\n' "$JUDGE_OUT"
if [ "$VERDICT" = "EVIDENCE_READY" ]; then
  log "evidence ready (e2e/sheets UNRUN 项按 backlog 走后续 Cloud 轮次，非本脚本强行通过)"
  exit 0
fi
log "=== STOP: BLOCKED(7) - report to Ying, no self-heal ==="
exit 7
