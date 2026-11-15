#!/usr/bin/env bash
# =============================================================================
# t1_render_downstream_test.sh — R-002 T1/T1b 渲染下游验证 · 云端一键
#
# 真源：bus runs/R-002/pack.md v1.2 §3/§6（agent-bus@cb827680，Ying 22:16 批「①A ②③照建议」）
#       + attachments/t1_render_compare.py / t1b_downstream_diff.py / t1b-verdict-template.md
# 骨架：scripts/cloud/cloud_round_test.sh（版本核验 / 通道自证 / 判定 / 产物打包）
#
# 用法（云端 Linux，在 scripts/cloud/ 下执行）：
#   bash t1_render_downstream_test.sh                       # preflight：基线四闸 + 渲染对比（不构成过闸）
#   MODE=t1b bash t1_render_downstream_test.sh              # pack v1.2 过闸面：双渲染集 → T1b GPU diff（exit 0=PASS/3=DRIFT/4=UNRUN）
#   MODE=full RENDER_ENGINE_VAR=... ENGINE_PROOF_GREP=pypdfium2 bash t1_render_downstream_test.sh   # 四闸双侧（佐证形态）
#   REPO_DIR=/path/to/DocuVision bash t1_render_downstream_test.sh
#   bash t1_render_downstream_test.sh --self-test           # 本机判定逻辑 mock 自测（不装依赖/不跑 GPU）
#
# 执行顺序：
#   0 环境(venv) → 1 仓库定位 → 2 版本核验 → 3 双引擎依赖
#   → 4 生成双引擎渲染对比集
#   → 5/6 四闸 fitz 基线（+ pdfium 侧, MODE=full；t1b 默认跳过, RUN_GATES=1 可跑佐证）
#   → 6b T1b GPU 双集 diff（MODE=t1b 的过闸面）→ 7 通道自证 + 读数 diff（full）
#   → 8 P-027 三指标(可选) → 9 判定 → 10 verdict 草稿（t1b 按其模板）→ 11 产物打包 tar.gz
#
# 纪律（pack v1.2 §3/§5 + kernel testing.md）：
#   - T1b 过闸面 = 预写死判据（块数一致 ∧ type 序列一致 ∧ 同 type IoU>=0.9 占比>=95%），exit 0/3/4 直接裁决。
#   - 像素差本身不是 fail 判据；漂移 = 停 + 回报 Ying，无自愈分支。
#   - preflight/full 四闸形态为佐证（pack v1.2 注 2），不构成过闸；禁止硬凑通过。
#   - 本机无 GPU ⇒ 不宣称云端已验证；结论以本脚本产物 + agentD 审读为准。
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-t1}"
VENV_DIR="${VENV_DIR:-$HOME/docuvision_env}"          # 空 = 跳过激活（用系统 python）
REPO_DIR="${REPO_DIR:-}"
BRANCH="${BRANCH:-}"                                  # 空 = 当前分支
PACK_BRANCH="${PACK_BRANCH:-chore/p046-agpl-replacement}"
EXPECTED_HEAD="${EXPECTED_HEAD:-8fc9345}"            # pack §2 写稿日锚；置空 = 跳过钉版
STRICT_HEAD="${STRICT_HEAD:-0}"                      # 1 = HEAD 逐字等于 EXPECTED_HEAD
AUTO_FF="${AUTO_FF:-0}"                              # 1 = 显式允许 git merge --ff-only origin/<BRANCH>
PDF_DIR="${PDF_DIR:-test_data/testfiles/pdf}"
RENDER_OUT="${RENDER_OUT:-}"                         # 空 = $REPO_DIR/test_data/local/t1_renders
INSTALL_DEPS="${INSTALL_DEPS:-1}"                    # venv 内装 pymupdf/pypdfium2/pillow（不进 requirements）
ALLOW_SYSTEM_PIP="${ALLOW_SYSTEM_PIP:-0}"           # VENV_DIR 为空时，允许系统 pip 需显式置 1
MODE="${MODE:-preflight}"                            # preflight | full | t1b（pack v1.2 过闸面）
RENDER_ENGINE_VAR="${RENDER_ENGINE_VAR:-DOCUVISION_PDF_RENDER_ENGINE}"
RENDER_ENGINE_PDFIUM="${RENDER_ENGINE_PDFIUM:-pdfium}"
ENGINE_PROOF_GREP="${ENGINE_PROOF_GREP:-pypdfium2}"  # 通道自证锚（pdfium 侧日志必须命中）
READING_GREP="${READING_GREP:-passed|failed|restamp|sanity|roi|PASSED|FAILED}"
P027_CMD="${P027_CMD:-}"                             # P-027 仪器命令（只比对禁重算）；空 = 未执行
PACK_PNGS="${PACK_PNGS:-0}"                          # 1 = 渲染 PNG 一并打包（体积大）
GATES="${GATES:-tests/evidence/test_golden_baseline.py tests/test_table_alignment.py tests/test_table_backfill.py tests/test_formula_step_pdf_roi.py}"
T1B_ARGS="${T1B_ARGS:---gpu}"                        # t1b 模式传给 t1b_downstream_diff.py 的附加参数（默认 --gpu）
RUN_GATES="${RUN_GATES:-0}"                          # t1b 模式默认跳过四闸（佐证非过闸，pack v1.2 注 2）；1 = 强制跑

log() { echo "[t1] $*"; }
die() { echo "[t1][FATAL] $*" >&2; exit 1; }

# ---- 判定（纯 bash，单一真源；--self-test 与正式轮次共用）--------------------
# 参数: rc.tsv 通道自证命中数 读数漂移数 MODE t1b_exit
judge_verdict() {
  local rc_file="$1" proof_hits="$2" drifts="$3" mode="$4" t1b_rc="${5:-}"
  local fails=0 reason="" verdict="PASS_GATE" gate side rc
  while IFS=$'\t' read -r gate side rc; do
    [ -z "${gate:-}" ] && continue
    if [ "${rc:-}" != "0" ]; then
      fails=$((fails + 1)); reason="${reason} ${gate}/${side}=rc${rc}"
    fi
  done < "$rc_file"
  [ "$fails" -eq 0 ] || verdict="BLOCKED(7)"
  if [ "$mode" = "t1b" ]; then
    # pack v1.2：过闸面 = t1b_downstream_diff.py 预写死判据，exit 0/3/4 直接裁决
    case "$t1b_rc" in
      0) : ;;
      3) verdict="BLOCKED(7)"; reason="${reason} T1B_DRIFT(t1b_downstream_diff exit=3, 任一页漂移)" ;;
      4) verdict="BLOCKED(7)"; reason="${reason} T1B_UNRUN(t1b_downstream_diff exit=4, 引擎/结构不 ready)" ;;
      *) verdict="BLOCKED(7)"; reason="${reason} T1B_FAIL(exit=${t1b_rc:-none})" ;;
    esac
  elif [ "$mode" = "full" ]; then
    if [ "$proof_hits" -lt 1 ]; then
      verdict="BLOCKED(7)"; reason="${reason} NO_SWITCH_FACE(channel-proof=0, 无渲染源切换面/通道未证)"
    fi
    if [ "$drifts" -gt 0 ]; then
      verdict="BLOCKED(7)"; reason="${reason} READING_DRIFT=${drifts}(下游读数不一致)"
    fi
  else
    verdict="BLOCKED(7)"; reason="${reason} PREFLIGHT_ONLY(pdfium 侧未跑, 不构成过闸)"
  fi
  if [ -z "$reason" ]; then
    if [ "$mode" = "t1b" ]; then
      reason="T1b 判据全绿（块数一致 ∧ type 序列一致 ∧ 同 type IoU>=0.9 占比>=95%，全部页一致）"
    else
      reason="四闸 rc 全 0 / 通道自证通过 / 双侧读数一致"
    fi
  fi
  echo "VERDICT=${verdict}"
  echo "REASON=${reason# }"
}

# ---- --self-test：本机 mock 判定逻辑（不碰 venv/GPU/pytest）-------------------
SELF_TEST=0
for arg in "$@"; do
  case "$arg" in
    --self-test) SELF_TEST=1 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) die "未知参数: $arg（仅支持 --self-test / --help）" ;;
  esac
done
if [ "$SELF_TEST" = "1" ]; then
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  ok=0; total=0
  assert_verdict() { # 期望 VERDICT 子串  期望 REASON 子串  rc内容  proof  drifts  mode  t1b_exit
    total=$((total + 1))
    printf '%b' "$3" > "$TMP/rc.tsv"
    out="$(judge_verdict "$TMP/rc.tsv" "$4" "$5" "$6" "$7")"
    if printf '%s' "$out" | grep -qF "$1" && printf '%s' "$out" | grep -qF "$2"; then
      ok=$((ok + 1))
    else
      echo "[t1][SELFTEST-FAIL] 期望 VERDICT~$1 REASON~$2，实际：$out" >&2
    fi
  }
  assert_verdict "PASS_GATE" "四闸 rc 全 0" \
    "g1\tfitz\t0\ng1\tpdfium\t0\ng2\tfitz\t0\ng2\tpdfium\t0\n" 3 0 full ""
  assert_verdict "BLOCKED(7)" "rc1" \
    "g1\tfitz\t0\ng1\tpdfium\t1\n" 3 0 full ""
  assert_verdict "BLOCKED(7)" "NO_SWITCH_FACE" \
    "g1\tfitz\t0\ng1\tpdfium\t0\n" 0 0 full ""
  assert_verdict "BLOCKED(7)" "READING_DRIFT" \
    "g1\tfitz\t0\ng1\tpdfium\t0\n" 3 2 full ""
  assert_verdict "BLOCKED(7)" "PREFLIGHT_ONLY" \
    "g1\tfitz\t0\n" 0 0 preflight ""
  assert_verdict "PASS_GATE" "T1b 判据全绿" \
    "" 0 0 t1b 0
  assert_verdict "BLOCKED(7)" "T1B_DRIFT" \
    "" 0 0 t1b 3
  assert_verdict "BLOCKED(7)" "T1B_UNRUN" \
    "" 0 0 t1b 4
  assert_verdict "BLOCKED(7)" "T1B_FAIL" \
    "" 0 0 t1b 2
  echo "[t1][SELFTEST] ${ok}/${total} passed"
  [ "$ok" -eq "$total" ] || exit 1
  exit 0
fi

case "$MODE" in
  preflight|full|t1b) ;;
  *) die "MODE 仅支持 preflight|full|t1b，实际=$MODE" ;;
esac

# ---- 0) 虚拟环境（金样例口径）------------------------------------------------
if [ -n "$VENV_DIR" ]; then
  [ -f "$VENV_DIR/bin/activate" ] || die "虚拟环境不存在: $VENV_DIR/bin/activate（VENV_DIR= 可跳过）"
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  log "已激活虚拟环境: $VENV_DIR"
fi
PY="$(command -v python3 || command -v python)" || die "python not found"
log "PY = $PY ($("$PY" -V 2>&1))"

# ---- 1) 定位仓库（锚：backend/app/services/pdf_raster.py）--------------------
if [ -z "$REPO_DIR" ]; then
  d="$SCRIPT_DIR"
  while [ "$d" != "/" ]; do
    [ -f "$d/backend/app/services/pdf_raster.py" ] && REPO_DIR="$d" && break
    d="$(dirname "$d")"
  done
fi
[ -n "$REPO_DIR" ] || die "未找到仓库，请指定 REPO_DIR=/path/to/DocuVision"
[ -f "$REPO_DIR/backend/app/services/pdf_raster.py" ] || die "REPO_DIR 不像 DocuVision: $REPO_DIR"
[ -f "$SCRIPT_DIR/t1_render_compare.py" ] || die "缺渲染对比脚本: $SCRIPT_DIR/t1_render_compare.py"
if [ "$MODE" = "t1b" ]; then
  [ -f "$SCRIPT_DIR/t1b_downstream_diff.py" ] || die "缺 T1b 执行件: $SCRIPT_DIR/t1b_downstream_diff.py（pack v1.2 附件，见 §6 注 1 落位）"
fi
log "REPO_DIR = $REPO_DIR"

# ---- 2) 版本核验（detached HEAD 安全；默认不自动快进）------------------------
#   detached HEAD 时 git rev-parse --abbrev-ref HEAD 返回字面量 "HEAD"，
#   fetch origin HEAD 只更新 FETCH_HEAD，merge origin/HEAD 必失败——故用 symbolic-ref 判定。
cd "$REPO_DIR" || die "无法进入 $REPO_DIR"
CUR_BRANCH="$(git symbolic-ref -q --short HEAD 2>/dev/null || true)"   # detached = 空
[ "$BRANCH" = "HEAD" ] && BRANCH=""                                    # 防御旧解析残留
if [ -n "$BRANCH" ]; then
  [ "$CUR_BRANCH" = "$BRANCH" ] \
    || log "WARN: 当前引用 '${CUR_BRANCH:-detached}' ≠ BRANCH=$BRANCH（脚本不自动切分支）"
else
  BRANCH="$CUR_BRANCH"
fi
RUN_REF="${CUR_BRANCH:-detached}"
[ "$RUN_REF" = "$PACK_BRANCH" ] \
  || log "WARN: 当前引用 $RUN_REF ≠ pack 建议分支 $PACK_BRANCH（基线读数可比性自担）"
[ -d "$REPO_DIR/$PDF_DIR" ] || die "PDF 样本目录不存在: $REPO_DIR/$PDF_DIR"

if [ -n "$BRANCH" ]; then
  if git fetch origin "$BRANCH"; then
    log "已同步远端引用 origin/$BRANCH（仅同步，不改工作区）"
  elif [ "$AUTO_FF" = "1" ]; then
    die "git fetch 失败且 AUTO_FF=1（快进必须有远端分支）"
  else
    log "WARN: git fetch origin/$BRANCH 失败（远端无该分支/离线）；AUTO_FF=0 不需要远端，继续以本地检出核验"
  fi
else
  log "WARN: detached HEAD —— 跳过 fetch/ff-only，仅以当前检出 commit 做基线核验"
fi
HEAD_NOW="$(git rev-parse --short HEAD)"
if [ -n "$EXPECTED_HEAD" ]; then
  git cat-file -e "${EXPECTED_HEAD}^{commit}" 2>/dev/null \
    || die "EXPECTED_HEAD=$EXPECTED_HEAD 不在本地仓库（浅克隆？先 git fetch --unshallow，或置空跳过）"
fi
if [ "$AUTO_FF" = "1" ]; then
  [ -n "$BRANCH" ] && [ "$CUR_BRANCH" = "$BRANCH" ] \
    || die "AUTO_FF=1 需要正常分支（当前 $RUN_REF）；detached HEAD 不支持快进"
  git merge --ff-only "origin/$BRANCH" \
    || die "快进失败（本地分叉或有改动？先检查，不在新 HEAD 上顺手跑）"
  HEAD_NOW="$(git rev-parse --short HEAD)"
  log "已快进到 origin/$BRANCH：$HEAD_NOW"
else
  log "AUTO_FF=0：不自动快进，实测版本 = 当前检出 $HEAD_NOW（避免跑到已替换的新 HEAD 上）"
fi
log "HEAD = $HEAD_NOW (ref=$RUN_REF, fetch-target=${BRANCH:-none})"
if [ -n "$EXPECTED_HEAD" ]; then
  if [ "$STRICT_HEAD" = "1" ]; then
    [ "$HEAD_NOW" = "$EXPECTED_HEAD" ] || die "版本不符(严格锁定): 期望 $EXPECTED_HEAD 实际 $HEAD_NOW"
  elif git merge-base --is-ancestor "$EXPECTED_HEAD" HEAD; then
    log "版本核验通过(基线包含): $EXPECTED_HEAD 已合入 $HEAD_NOW"
  else
    die "版本不符: $EXPECTED_HEAD 未合入 $HEAD_NOW
  诊断: git merge-base $EXPECTED_HEAD HEAD ; git log --oneline $EXPECTED_HEAD..HEAD -5
  ① 检出契约基线: git fetch --unshallow origin main && git checkout --detach $EXPECTED_HEAD
  ② 当前 HEAD 比基线旧或分叉: 按 pack §2 重跑 A1–A7 锚点并回报 Ying 裁决；未经裁决不得 EXPECTED_HEAD= 置空硬跑"
  fi
else
  log "WARN: 未钉 EXPECTED_HEAD，读数可比性自担"
fi
[ -z "$RENDER_OUT" ] && RENDER_OUT="$REPO_DIR/test_data/local/t1_renders"
mkdir -p "$RENDER_OUT" || die "无法创建渲染输出目录: $RENDER_OUT"

# ---- 3) 双引擎依赖（临时对比用，不进 requirements）---------------------------
ENV_TXT="$SCRIPT_DIR/${PREFIX}_env.txt"
{
  echo "HEAD=$HEAD_NOW  branch=$RUN_REF  expected=$EXPECTED_HEAD  date=$(date -Iseconds)"
  echo "PY=$PY  MODE=$MODE  PDF_DIR=$PDF_DIR  RENDER_OUT=$RENDER_OUT"
} > "$ENV_TXT"
if [ "$INSTALL_DEPS" = "1" ]; then
  if [ -z "$VENV_DIR" ] && [ "$ALLOW_SYSTEM_PIP" != "1" ]; then
    die "系统 python 下拒绝自动 pip（设 VENV_DIR 或 ALLOW_SYSTEM_PIP=1）"
  fi
  "$PY" -m pip install pymupdf pypdfium2 pillow >> "$ENV_TXT" 2>&1 \
    || die "依赖安装失败，见 $ENV_TXT"
fi
"$PY" - >> "$ENV_TXT" <<'PY' || die "依赖不可导入（fitz / pypdfium2 / PIL）"
import importlib
for name in ("fitz", "pypdfium2", "PIL"):
    m = importlib.import_module(name)
    ver = None
    for attr in ("__version__", "V_PYPDFIUM2", "V_LIBPDFIUM", "VersionBind"):
        v = getattr(m, attr, None)
        if isinstance(v, str) and v:
            ver = v
            break
    print(f"{name}={ver or 'n/a'}")
PY
log "依赖版本已记入 $ENV_TXT"

# ---- 4) 生成双引擎渲染对比集 -------------------------------------------------
RENDER_LOG="$SCRIPT_DIR/${PREFIX}_render.log"
log "=== 4/11 生成双引擎渲染对比集 ==="
"$PY" "$SCRIPT_DIR/t1_render_compare.py" --pdf-dir "$REPO_DIR/$PDF_DIR" --out "$RENDER_OUT" \
  > "$RENDER_LOG" 2>&1 || die "渲染对比脚本失败，见 $RENDER_LOG"
REPORT="$RENDER_OUT/t1_report.jsonl"
[ -s "$REPORT" ] || die "渲染报告为空: $REPORT"
cp "$REPORT" "$SCRIPT_DIR/${PREFIX}_report.jsonl"
"$PY" - "$REPORT" > "$SCRIPT_DIR/${PREFIX}_render_summary.txt" <<'PY' || die "渲染报告解析失败"
import json, sys
rows = [json.loads(x) for x in open(sys.argv[1], encoding="utf-8") if x.strip()]
pcts = [r["changed_px_pct"] for r in rows if r.get("size_match")]
print(f"pages={len(rows)} pdfs={len({r['pdf'] for r in rows})}")
print(f"size_match={sum(bool(r.get('size_match')) for r in rows)}/{len(rows)}")
print(f"identical={sum(bool(r.get('identical')) for r in rows)}/{len(rows)}")
print(f"changed_px_pct_range={min(pcts) if pcts else 'n/a'}..{max(pcts) if pcts else 'n/a'}")
print("NOTE: 像素差本身不是 fail 判据（pack §3 T1）；下游三闸读数才是裁决面")
PY
log "渲染对比完成: $(head -1 "$SCRIPT_DIR/${PREFIX}_render_summary.txt")"

# ---- 5/6) 四闸：fitz 基线（+ MODE=full 时 pdfium 侧双跑）---------------------
RC_FILE="$SCRIPT_DIR/${PREFIX}_rc.tsv"
: > "$RC_FILE"
run_gate() { # $1=side  $2=gate  $3=log
  local side="$1" gate="$2" logfile="$3" rc=0
  if [ "$side" = "pdfium" ]; then
    ( cd "$REPO_DIR/backend" && env PYTHONPATH=. \
        "$RENDER_ENGINE_VAR=$RENDER_ENGINE_PDFIUM" "$PY" -m pytest "$gate" -v ) \
      > "$logfile" 2>&1 || rc=$?
  else
    ( cd "$REPO_DIR/backend" && env PYTHONPATH=. "$PY" -m pytest "$gate" -v ) \
      > "$logfile" 2>&1 || rc=$?
  fi
  printf '%s\t%s\t%s\n' "$(basename "$gate")" "$side" "$rc" >> "$RC_FILE"
  grep -E "$READING_GREP" "$logfile" 2>/dev/null \
    | sed -E 's/in [0-9]+\.[0-9]+s/in Xs/g; s/in [0-9]+s/in Xs/g; s/[[:space:]]+/ /g' \
    > "$logfile.readings" || true
  log "  $(basename "$gate") / $side : rc=$rc"
}
for gate in $GATES; do
  [ -f "$REPO_DIR/backend/$gate" ] || die "闸门测试文件不存在: backend/$gate"
done
if [ "$MODE" = "t1b" ] && [ "$RUN_GATES" != "1" ]; then
  log "=== 5/6 四闸跳过（MODE=t1b：过闸面 = T1b GPU diff；RUN_GATES=1 可跑逻辑层佐证）==="
else
  log "=== 5/11 四闸 fitz 基线 ==="
  for gate in $GATES; do
    run_gate fitz "$gate" "$SCRIPT_DIR/${PREFIX}_gate_$(basename "$gate" .py)__fitz.log"
  done
  if [ "$MODE" = "full" ]; then
    log "=== 6/11 四闸 pdfium 侧（$RENDER_ENGINE_VAR=$RENDER_ENGINE_PDFIUM）==="
    for gate in $GATES; do
      run_gate pdfium "$gate" "$SCRIPT_DIR/${PREFIX}_gate_$(basename "$gate" .py)__pdfium.log"
    done
  else
    log "=== 6/11 pdfium 侧跳过（MODE=preflight）==="
  fi
fi

# ---- 6b) T1b GPU 下游双集 diff（MODE=t1b 的过闸面；判据预写死，pack v1.2 §3）----
T1B_RC=""
T1B_LOG="$SCRIPT_DIR/${PREFIX}_t1b.log"
if [ "$MODE" = "t1b" ]; then
  log "=== 6b/11 T1b GPU 下游双集 diff（t1b_downstream_diff.py $T1B_ARGS）==="
  ( cd "$REPO_DIR" && "$PY" "$SCRIPT_DIR/t1b_downstream_diff.py" \
      --fitz-dir "$RENDER_OUT/fitz" --pdfium-dir "$RENDER_OUT/pdfium" \
      --out "$SCRIPT_DIR/${PREFIX}_t1b_report.jsonl" $T1B_ARGS ) \
    > "$T1B_LOG" 2>&1
  T1B_RC=$?
  log "T1b exit=$T1B_RC（0=PASS / 3=DRIFT / 4=UNRUN）"
  tail -n 3 "$T1B_LOG" | sed 's/^/  /'
fi

# ---- 7) 通道自证 + 读数 diff（防「无切换面假通过」）--------------------------
PROOF_HITS=0; DRIFTS=0
DRIFTS_LABEL="N/A(no side-by-side)"      # preflight/t1b 下无双侧对比，不做数值判定
if [ "$MODE" = "full" ]; then
  PROOF_HITS="$(cat "$SCRIPT_DIR"/${PREFIX}_gate_*__pdfium.log 2>/dev/null \
    | grep -c "$ENGINE_PROOF_GREP" || true)"
  for f in "$SCRIPT_DIR"/${PREFIX}_gate_*__fitz.log.readings; do
    [ -f "$f" ] || continue
    other="${f/__fitz.log.readings/__pdfium.log.readings}"
    if [ ! -f "$other" ] || ! diff -q "$f" "$other" >/dev/null 2>&1; then
      DRIFTS=$((DRIFTS + 1)); log "WARN: 读数差异 $(basename "$f")"
    fi
  done
  DRIFTS_LABEL="$DRIFTS"
fi
log "通道自证命中=$PROOF_HITS（期望>=1, full） 读数漂移=$DRIFTS_LABEL（full 期望=0）"

# ---- 8) P-027 三指标（只比对禁重算；命令未提供即如实标注未执行）-------------
P027_STATUS="SKIPPED(仪器命令未提供)"
if [ -n "$P027_CMD" ]; then
  if bash -c "$P027_CMD" > "$SCRIPT_DIR/${PREFIX}_p027.log" 2>&1; then
    P027_STATUS="EXECUTED(读数见 ${PREFIX}_p027.log；只比对禁重算)"
  else
    P027_STATUS="FAILED(见 ${PREFIX}_p027.log)"
  fi
fi
log "P-027: $P027_STATUS"

# ---- 9) 判定 ---------------------------------------------------------------
JUDGE_OUT="$(judge_verdict "$RC_FILE" "$PROOF_HITS" "$DRIFTS" "$MODE" "$T1B_RC")"
VERDICT="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^VERDICT=//p')"
REASON="$(printf '%s\n' "$JUDGE_OUT" | sed -n 's/^REASON=//p')"
SUMMARY="$SCRIPT_DIR/${PREFIX}_summary.txt"
{
  echo "R-002 T1/T1b 渲染下游验证 · 机检汇总"
  echo "HEAD=$HEAD_NOW branch=$RUN_REF MODE=$MODE date=$(date -Iseconds)"
  echo "EXPECTED_HEAD=$EXPECTED_HEAD STRICT_HEAD=$STRICT_HEAD"
  echo "--- 渲染对比 ---"; cat "$SCRIPT_DIR/${PREFIX}_render_summary.txt"
  if [ "$MODE" = "t1b" ]; then
    echo "--- T1b GPU 双集 diff ---"
    echo "t1b_exit=$T1B_RC (0=PASS / 3=DRIFT / 4=UNRUN)"
    echo "t1b_stdout_tail:"; tail -n 3 "$T1B_LOG" | sed 's/^/  /'
  fi
  echo "--- 四闸 rc (gate/side/rc) ---"; cat "$RC_FILE"
  echo "--- 通道自证 / 读数 ---"
  echo "channel_proof_hits=$PROOF_HITS (grep '$ENGINE_PROOF_GREP'; 期望>=1, full)"
  echo "reading_drifts=$DRIFTS_LABEL (full 期望=0)"
  echo "P027=$P027_STATUS"
  echo "--- 机检结论（不替代 agentD 审读 / Ying 回填）---"
  printf '%s\n' "$JUDGE_OUT"
} > "$SUMMARY"

# ---- 10) verdict 草稿（MODE=t1b 按 t1b-verdict-template.md；其余按 T1 模板）----
VERDICT_DRAFT="$SCRIPT_DIR/${PREFIX}_verdict_draft.md"
if [ "$MODE" = "t1b" ]; then
  {
    echo "# R-002 T1b verdict · GPU 下游双集 diff（脚本生成草稿，pack v1.2）"
    echo
    echo "> 回填人：Ying（Cloud Studio GPU 侧）；判据预写死见 t1b_downstream_diff.py 文件头；读数 = stdout 汇总行 + t1b_report.jsonl，逐字粘贴禁止改数"
    echo "> 回填后 push bus \`runs/R-002/t1b-verdict.md\` → agentD 审读 → 过闸令 → AgentE 进 T2"
    echo "> 取证锚：基线=$EXPECTED_HEAD · 实测 HEAD=$HEAD_NOW · branch=$RUN_REF · 执行日=$(date -I)"
    echo "> 机检结论：**$VERDICT**（$REASON）——t1b_exit=$T1B_RC"
    echo
    echo "## 0 执行环境"
    echo "- 引擎：PPStructureEngine(use_gpu)；pypdfium2 = ____（预期 5.13.0，实测见 ${PREFIX}_env.txt）"
    echo "- 命令（逐字）：见 pack v1.2 §6 步 1-2（t1_render_compare.py → t1b_downstream_diff.py $T1B_ARGS）"
    echo
    echo "## 1 逐页读数（${PREFIX}_t1b_report.jsonl）"
    echo "| tag | n_a/n_b | count_equal | type_seq_equal | iou09_ratio | page_ok |"
    echo "|---|---|---|---|---|---|"
    if [ -s "$SCRIPT_DIR/${PREFIX}_t1b_report.jsonl" ]; then
      "$PY" - "$SCRIPT_DIR/${PREFIX}_t1b_report.jsonl" <<'PY'
import json, sys
for line in open(sys.argv[1], encoding="utf-8"):
    if not line.strip():
        continue
    r = json.loads(line)
    ratio = r.get("iou09_ratio")
    print(f"| {r.get('tag','')} | {r.get('n_a','')}/{r.get('n_b','')} | {r.get('count_equal','')} | {r.get('type_seq_equal','')} | {'' if ratio is None else ratio} | {r.get('page_ok','')} |")
PY
    fi
    echo
    echo "## 2 汇总行（脚本 stdout 逐字）"
    echo '```'
    grep -E '^VERDICT=' "$T1B_LOG" 2>/dev/null || echo "VERDICT=____ pages_ok=__/9 report=${PREFIX}_t1b_report.jsonl"
    echo '```'
    echo
    echo "## 3 结论（勾选其一）"
    echo "- ☐ PASS（9/9 页一致 → 过闸，AgentE 进 T2）"
    echo "- ☐ DRIFT（任一页漂移 → 停 + 回报 Ying 重裁：候选 = 渲染参数对齐实验 / 引擎重评，无自愈）"
    echo "- ☐ UNRUN（引擎不 ready / 结构无法归一 → 附报错原文，err 字段逐字粘贴）"
    echo
    echo "## 4 P-027 状态注记（不阻塞本闸）"
    echo "$P027_STATUS"
    echo
    echo "## 5 过闸判定（agentD 审读后填）"
    echo "- 审读人/日期：____"
  } > "$VERDICT_DRAFT"
else
  {
    echo "# R-002 T1 verdict · 渲染下游验证（脚本生成草稿）"
    echo
    echo "> 回填人：Ying（Cloud Studio / 本机执行，pack §6 命令清单）"
    echo "> 注意：pack v1.2 起 T1 过闸路径由 T1b 承接（t1b-verdict-template.md）——本稿仅作 preflight/佐证形态留档，不构成过闸申请"
    echo "> 回填后 push bus \`runs/R-002/t1-verdict.md\` → agentD 审读"
    echo "> 取证锚：origin/main 基线=$EXPECTED_HEAD · 实测 HEAD=$HEAD_NOW · branch=$RUN_REF · 执行日=$(date -I)"
    echo "> 机检结论：**$VERDICT**（$REASON）——仅为机检，逐项读数由 Ying 复核后填"
    echo
    echo "## 0 T1 渲染对比读数（t1_render_compare.py 输出摘要）"
    cat "$SCRIPT_DIR/${PREFIX}_render_summary.txt" | sed 's/^/- /'
    echo "- 逐页报告：${PREFIX}_report.jsonl（全文随 verdict 附）；报告文件 t1_renders/t1_report.jsonl"
    echo
    echo "## 1-3 三闸 + 四闸读数（命令逐字 + 输出片段由 Ying 粘贴）"
    echo "| gate | fitz rc | pdfium rc | 读数 diff | 人工结论 |"
    echo "|---|---|---|---|---|"
    awk -F'\t' '{print $1"\t"$2"\t"$3}' "$RC_FILE" | while IFS=$'\t' read -r g s r; do
      echo "| $g | $([ "$s" = fitz ] && echo "$r" || echo '—') | $([ "$s" = pdfium ] && echo "$r" || echo '—') | 见 ${PREFIX}_gate_*__*.log.readings | 待填 |"
    done
    echo
    echo "- 闸 A 金样 45 restamp 分布：☐ 一致 / ☐ 漂移（停+回报）"
    echo "- 闸 B 表格对齐 + reason 契约 / 回填 sanity：☐ 过 / ☐ 漂移"
    echo "- 闸 C 公式 ROI：☐ 过 / ☐ 漂移"
    echo "- 通道自证（pdfium 侧日志含 '$ENGINE_PROOF_GREP'）：hits=$PROOF_HITS（0 = 无切换面，结论无效）"
    echo
    echo "## 4 三指标快查（P-027，只比对禁重算）"
    echo "grid_f1 ____（基线 0.8989）· S-TEDS ____（0.8399）· 表召回 ____（0.8300）"
    echo "P027_CMD 状态：$P027_STATUS"
    echo
    echo "## 5 过闸判定（agentD 审读后填）"
    echo "- ☐ 三闸全绿 → T1 过闸令，AgentE 进 T3"
    echo "- ☐ 任一闸漂移 → 选型级风险上呈 Ying 重裁（换参数 / 重新选型 / 商业许可），T3 冻结"
    echo "- 审读人/日期：____"
  } > "$VERDICT_DRAFT"
fi

# ---- 11) 产物打包 ----------------------------------------------------------
TARBALL="${PREFIX}_artifacts_${HEAD_NOW}_$(date +%Y%m%d_%H%M%S).tar.gz"
PACK_FILES=(
  "${PREFIX}_env.txt" "${PREFIX}_render.log" "${PREFIX}_render_summary.txt"
  "${PREFIX}_report.jsonl" "${PREFIX}_rc.tsv" "${PREFIX}_summary.txt"
  "${PREFIX}_verdict_draft.md"
)
if [ -f "$SCRIPT_DIR/${PREFIX}_p027.log" ]; then PACK_FILES+=("${PREFIX}_p027.log"); fi
if [ "$MODE" = "t1b" ]; then
  # UNRUN 早退时 t1b_report.jsonl 可能尚未创建（引擎构造前 return），按存在性纳入，防 tar stat 失败
  [ -f "$SCRIPT_DIR/${PREFIX}_t1b_report.jsonl" ] && PACK_FILES+=("${PREFIX}_t1b_report.jsonl")
  [ -f "$SCRIPT_DIR/${PREFIX}_t1b.log" ] && PACK_FILES+=("${PREFIX}_t1b.log")
fi
(
  cd "$SCRIPT_DIR" || exit 1
  # shellcheck disable=SC2086
  set -- ${PREFIX}_gate_*.log ${PREFIX}_gate_*.log.readings   # t1b 模式下可能为空
  if [ "$PACK_PNGS" = "1" ]; then
    if [ "$#" -gt 0 ]; then
      tar -czf "$TARBALL" "${PACK_FILES[@]}" "$@" \
          -C "$(dirname "$RENDER_OUT")" "$(basename "$RENDER_OUT")"
    else
      tar -czf "$TARBALL" "${PACK_FILES[@]}" \
          -C "$(dirname "$RENDER_OUT")" "$(basename "$RENDER_OUT")"
    fi
  else
    if [ "$#" -gt 0 ]; then
      tar -czf "$TARBALL" "${PACK_FILES[@]}" "$@"
    else
      tar -czf "$TARBALL" "${PACK_FILES[@]}"
    fi
  fi
) || die "产物打包失败（PACK_PNGS=1 时 PNG 目录一并入包）"
log "产物已打包: $SCRIPT_DIR/$TARBALL"
log "判定读数见 ${PREFIX}_summary.txt / verdict 草稿见 ${PREFIX}_verdict_draft.md"
printf '%s\n' "$JUDGE_OUT"

# preflight / BLOCKED 都不是过闸：退出 7（对应 BLOCKED(7)），不硬凑通过
if [ "$VERDICT" = "PASS_GATE" ]; then
  if [ "$MODE" = "t1b" ]; then
    log "=== T1b 机检过闸（仍须 agentD 审读 + Ying 回填 t1b-verdict 后 AgentE 方可进 T2）==="
  else
    log "=== 机检过闸（仍须 agentD 审读 + Ying 回填后放行；pack v1.2 起过闸路径由 T1b 承接）==="
  fi
  exit 0
fi
log "=== 停：BLOCKED(7) — 按 pack §3 T1b「漂移/缺证 = 停 + 回报 Ying，无自愈分支」==="
exit 7
