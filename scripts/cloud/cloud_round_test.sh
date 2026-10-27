#!/usr/bin/env bash
# =============================================================================
# cloud_round_test.sh — 云测轮次一键金样例（golden sample）
# 规则/约定：scripts/cloud/README.md（本脚本 = README 的可执行形态）
#
# 出处：P-034 云测第 4 轮实证脚本（docs/R&D/runs/P034/p034_round4_cloud_test.sh，
# 2026-10-27，HEAD c2b46e2，tampa on/off 双向 + 通道自证全链通过）。
# 后续云测轮次复用本脚本：只改环境变量，不改流程。
#
# 用法（云端 Linux，任意临时目录）：
#   bash cloud_round_test.sh
#   REPO_DIR=/path/to/DocuVision bash cloud_round_test.sh      # 仓库非默认位置
#
# 流程：版本核验(自动 pull) -> 契约单测 -> 旗标 ON 起服务跑夹具(通道自证)
#       -> 旗标 OFF 跑夹具 x3(分母稳定性) -> 新判据判定 -> 产物落本脚本同目录
#
# 产物：<PREFIX>_on.json / <PREFIX>_off_{1,2,3}.json / run_on.log / run_off.log
#       / <PREFIX>_summary.txt（判定读数，回传重点）
# =============================================================================
set -uo pipefail

# ---- 可配置参数（环境变量覆盖；默认值 = P-034 worked example）----------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRANCH="${BRANCH:-}"                      # 空 = 当前分支
EXPECTED_HEAD="${EXPECTED_HEAD:-}"        # 空 = 仅告警不阻断；钉版本时传短 hash
PROMPT_CHECK="${PROMPT_CHECK:-backend/app/services/kie/kie_configs/coi.yaml:v3.2}"  # path:version，空 = 跳过
FIXTURE="${FIXTURE:-test_data/testfiles/coi/coi_acord25_tampa_sample.pdf}"
DOC_TYPE="${DOC_TYPE:-coi}"
FIELDS="${FIELDS:-carrier,policy_type,eff_date,exp_date,limits}"   # 逗号分隔
BOILER="${BOILER:-A.M. Best,VII or Better}"                        # 样板句特征，逗号分隔
CHANNEL_GREP="${CHANNEL_GREP:-KIE text-first}"                     # 通道自证日志锚
UNIT_TESTS="${UNIT_TESTS:-tests/test_kie_field_merge.py tests/test_kie_domain_consistency.py tests/evidence/test_evidence_text_first.py tests/test_kie_return_raw_contract.py}"
RUN_UNIT="${RUN_UNIT:-1}"
PORT="${PORT:-8000}"
START_CMD="${START_CMD:-python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}}"
PREFIX="${PREFIX:-round}"
export FIELDS BOILER PREFIX

log() { echo "[cloud-round] $*"; }
die() { echo "[cloud-round][FATAL] $*" >&2; exit 1; }
PY="$(command -v python3 || command -v python)" || die "python not found"

SERVER_PID=""; PID_FILE="$SCRIPT_DIR/.cloud_round_server_pid"
stop_server() {
  if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
    kill "$SERVER_PID" 2>/dev/null; sleep 3
    kill -9 "$SERVER_PID" 2>/dev/null
  fi
  SERVER_PID=""
}
trap stop_server EXIT

# ---- 0) 定位仓库 ------------------------------------------------------------
REPO_DIR="${REPO_DIR:-}"
if [ -z "$REPO_DIR" ]; then
  for d in "$HOME/DocuVision" "$HOME/docuvision" "$PWD"; do
    [ -f "$d/backend/app/services/kie/kie_configs/coi.yaml" ] && REPO_DIR="$d" && break
  done
fi
[ -n "$REPO_DIR" ] || die "未找到仓库，请指定: REPO_DIR=/path/to/DocuVision bash $0"
log "REPO_DIR = $REPO_DIR"

# ---- 1) 版本核验（自动 pull）------------------------------------------------
cd "$REPO_DIR" || die "无法进入 $REPO_DIR"
[ -n "$BRANCH" ] || BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git pull --ff-only origin "$BRANCH" || die "git pull 失败（有本地改动？先 stash）"
HEAD_NOW="$(git rev-parse --short HEAD)"
log "HEAD = $HEAD_NOW (branch=$BRANCH)"
if [ -n "$EXPECTED_HEAD" ]; then
  [ "$HEAD_NOW" = "$EXPECTED_HEAD" ] || die "版本不符: 期望 $EXPECTED_HEAD, 实际 $HEAD_NOW"
else
  log "WARN: EXPECTED_HEAD 未钉版本，读数可比性自担"
fi
if [ -n "$PROMPT_CHECK" ]; then
  PC_PATH="${PROMPT_CHECK%%:*}"; PC_VER="${PROMPT_CHECK#*:}"
  grep -q "prompt_version: ${PC_VER}" "$REPO_DIR/$PC_PATH" \
    || die "prompt 版本不符: $PC_PATH 期望 ${PC_VER}"
fi
[ -f "$FIXTURE" ] || die "夹具不存在: $REPO_DIR/$FIXTURE"
log "版本核验通过"

# ---- 2) 契约单测（快速，先证代码面；UNIT_TESTS 空或 RUN_UNIT=0 跳过）--------
if [ "$RUN_UNIT" = "1" ] && [ -n "$UNIT_TESTS" ]; then
  # shellcheck disable=SC2086
  ( cd backend && DOCUVISION_EVIDENCE_TEXT_FIRST=0 "$PY" -m pytest $UNIT_TESTS -q ) \
    || die "契约单测未全绿"
  log "契约单测通过"
fi

# ---- 服务起停工具 -----------------------------------------------------------
wait_up() {
  for _ in $(seq 1 60); do
    code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/docs" 2>/dev/null || true)"
    [ "$code" = "200" ] && return 0
    sleep 2
  done
  return 1
}
start_server() {  # $1=flag值  $2=日志路径
  ( cd backend && DOCUVISION_EVIDENCE_TEXT_FIRST="$1" \
      nohup $START_CMD > "$2" 2>&1 & echo $! > "$PID_FILE" )
  SERVER_PID="$(cat "$PID_FILE")"
  wait_up || die "服务未在 120s 内就绪（$2 尾部: $(tail -5 "$2")）"
  log "服务就绪 (flag=$1, pid=$SERVER_PID)"
}

submit_and_wait() {  # $1=输出json路径
  local resp task_id status=""
  resp="$(curl -s -X POST "$BASE_URL/api/v1/analyze" \
    -F "file=@$REPO_DIR/$FIXTURE" \
    -F "enable_kie=true" -F "document_type=$DOC_TYPE" -F "enable_layout=true")"
  task_id="$(printf '%s' "$resp" | "$PY" -c "import sys,json;print(json.load(sys.stdin).get('task_id',''))" 2>/dev/null || true)"
  [ -n "$task_id" ] || die "提交失败: $resp"
  log "task_id = $task_id"
  for _ in $(seq 1 180); do
    status="$("$PY" - "$task_id" "$PORT" <<'PYEOF'
import sys, json, urllib.request
task_id, port = sys.argv[1], sys.argv[2]
try:
    d = json.load(urllib.request.urlopen(f"http://localhost:{port}/api/v1/tasks/{task_id}"))
    print(d.get("status", ""))
except Exception:
    print("")
PYEOF
)" || status=""
    case "$status" in
      completed) break ;;
      failed)    die "任务失败: $task_id" ;;
    esac
    sleep 5
  done
  [ "$status" = "completed" ] || die "轮询超时: $task_id"
  curl -s "$BASE_URL/api/v1/tasks/$task_id" > "$1"
  log "结果已存 $1"
}

# ---- 3) ON 侧：通道自证 + 判据数据 ------------------------------------------
BASE_URL="http://localhost:${PORT}"
log "=== ON 侧开始 (flag=1) ==="
start_server 1 "$SCRIPT_DIR/run_on.log"
submit_and_wait "$SCRIPT_DIR/${PREFIX}_on.json"
ON_HITS="$(grep -c "$CHANNEL_GREP" "$SCRIPT_DIR/run_on.log" || true)"
log "ON 通道自证: grep '$CHANNEL_GREP' = $ON_HITS (期望 >=1)"
stop_server

# ---- 4) OFF 侧 x3：分母稳定性协议 -------------------------------------------
log "=== OFF 侧开始 (flag=0, x3) ==="
start_server 0 "$SCRIPT_DIR/run_off.log"
for i in 1 2 3; do
  submit_and_wait "$SCRIPT_DIR/${PREFIX}_off_${i}.json"
done
OFF_HITS="$(grep -c "$CHANNEL_GREP" "$SCRIPT_DIR/run_off.log" || true)"
log "OFF 通道自证: grep '$CHANNEL_GREP' = $OFF_HITS (期望 =0)"
stop_server

# ---- 5) 判定（判据口径见 scripts/cloud/README.md §判定）---------------------
cd "$SCRIPT_DIR"
"$PY" - > "$SCRIPT_DIR/${PREFIX}_summary.txt" <<'JUDGE'
import json, os
FIELDS = [f for f in os.environ.get("FIELDS", "").split(",") if f]
BOILER = tuple(b for b in os.environ.get("BOILER", "").split(",") if b)
PREFIX = os.environ.get("PREFIX", "round")

def fields_of(path):
    d = json.load(open(path, encoding="utf-8"))
    if isinstance(d.get("kie_fields"), dict):
        return d["kie_fields"]
    r = d.get("result")
    if isinstance(r, dict) and isinstance(r.get("kie_fields"), dict):
        return r["kie_fields"]
    return {}

runs = [f"{PREFIX}_on.json", f"{PREFIX}_off_1.json", f"{PREFIX}_off_2.json", f"{PREFIX}_off_3.json"]
data = {name: fields_of(name) for name in runs}
for name in runs:
    kf = data[name]
    print(f"== {name} ==")
    missing = [k for k in FIELDS if k not in kf]
    for k in FIELDS:
        v = kf.get(k, "<KEY MISSING>")
        mark = "  <<BOILERPLATE" if any(b in str(v) for b in BOILER) else ""
        print(f"  {k}: {v!r}{mark}")
    if missing:
        print(f"  !! never-omit 违约(键缺失): {missing}")
    print()

on = data[f"{PREFIX}_on.json"]
off_vals = {k: [data[f"{PREFIX}_off_{i}.json"].get(k, "<MISSING>") for i in (1, 2, 3)] for k in FIELDS}
print("== 判定（键存在 + OFF 多数分母；口径见 scripts/cloud/README.md）==")
for k in FIELDS:
    ov = off_vals[k]
    majority = max(set(ov), key=list(ov).count) if ov else "<MISSING>"
    print(f"  {k}: ON={on.get(k,'<MISSING>')!r}  OFF多数={majority!r}  OFF×3={ov!r}")
print("判定口径: 键缺失一律记退化; 值退化以 OFF×3 多数为分母; 样板句字样出现即 FAIL。")
JUDGE

{
  echo "HEAD=$HEAD_NOW  branch=$BRANCH  fixture=$FIXTURE  doc_type=$DOC_TYPE  date=$(date -Iseconds)"
  echo "channel ON hits=$ON_HITS (期望>=1) / OFF hits=$OFF_HITS (期望=0)"
} >> "$SCRIPT_DIR/${PREFIX}_summary.txt"

log "=== 完成，回传产物（与本 .sh 同目录）==="
ls -l "$SCRIPT_DIR"/run_on.log "$SCRIPT_DIR"/run_off.log \
      "$SCRIPT_DIR"/${PREFIX}_on.json "$SCRIPT_DIR"/${PREFIX}_off_*.json \
      "$SCRIPT_DIR"/${PREFIX}_summary.txt
log "判定读数见 ${PREFIX}_summary.txt"
