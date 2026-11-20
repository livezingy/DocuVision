#!/usr/bin/env bash
# r004_retest_judge.sh — R-004 标准重测判读器（runbook 2026-11-20 阶段 5/6 的可执行形态）
#
# 职责边界：只读取证 + 预写死判定 + 产物打包。不重建（rebuild 脚本管）、不注册（rebuild REGISTER=1 或
# runbook 阶段 3 管）、不发邮件（人工注入点）。verdict 生产者 = agentD + Ying 签——本脚本读数非过闸。
#
# 用法（云端，发完 PO 邮件后运行；或先运行让它轮询等待）:
#   bash r004_retest_judge.sh                       # 快照 watch 目录 → 轮询新 CSV（默认至多 900s）→ 判读 → 打包
#   TIMEOUT=1200 POLL=20 bash r004_retest_judge.sh  # 自定义轮询窗口
#   NEW_TASK_ID=<id> bash r004_retest_judge.sh      # 已知 task_id（跳过轮询直接判读）
#   BACKEND_LOG=/workspace/DocuVision/debug/backend.log bash r004_retest_judge.sh  # 提供 5.2 判据的日志源
#
# 纪律：判据预写死不因读数回改；本机 bash -n 校验过，云端首跑 = 实测轮（UNRUN 如实标注，不自愈）。
set -uo pipefail

WATCH_DIR="${WATCH_DIR:-/workspace/DocuVision/debug/n8n-watch}"
REPO_DIR="${REPO_DIR:-/workspace/DocuVision}"
SPACE_URL="${SPACE_URL:-https://9f15e4b797f34bc08ac399937544b368--5678.ap-shanghai2.cloudstudio.club}"
BACKEND_LOG="${BACKEND_LOG:-}"
TIMEOUT="${TIMEOUT:-900}"
POLL="${POLL:-30}"
NEW_TASK_ID="${NEW_TASK_ID:-}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${OUT:-$REPO_DIR/debug/r004_retest_$STAMP}"

log(){ echo "[$(date +%H:%M:%S)] $*"; }
die(){ log "❌ $*"; exit 1; }

command -v python3 >/dev/null || die "python3 不可用"
[ -d "$WATCH_DIR" ] || die "watch 目录不存在: $WATCH_DIR（rebuild 脚本运行过才有）"
mkdir -p "$OUT"

# ---------- 0. 快照 + 轮询等待新 CSV ----------
declare -A SEEN
for f in "$WATCH_DIR"/*.csv; do [ -e "$f" ] && SEEN["$(basename "$f")"]=1; done
BASELINE=$(ls "$WATCH_DIR"/*.csv 2>/dev/null | wc -l)
log "起始快照: watch 目录现有 $BASELINE 个 CSV（已知 task 视为基线，不参与本轮判定）"

if [ -z "$NEW_TASK_ID" ]; then
  log "== 轮询等待新 CSV（至多 ${TIMEOUT}s，每 ${POLL}s）——现在发 PO 邮件 =="
  DEADLINE=$(( $(date +%s) + TIMEOUT ))
  while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    for f in "$WATCH_DIR"/*.csv; do
      [ -e "$f" ] || continue
      b=$(basename "$f" .csv)
      if [ -z "${SEEN[$b]:-}" ]; then NEW_TASK_ID="$b"; break; fi
    done
    [ -n "$NEW_TASK_ID" ] && break
    sleep "$POLL"
  done
fi

# ---------- 判据③ CSV 落盘（先做，决定整体走向）----------
CSV="$WATCH_DIR/${NEW_TASK_ID:-__none__}.csv"
CSV_OK=0
if [ -n "$NEW_TASK_ID" ] && [ -f "$CSV" ]; then
  cp "$CSV" "$OUT/"
  CSV_LINES=$(wc -l < "$CSV" | tr -d ' ')
  MARKER=$(grep -c "__no_kie_fields__" "$CSV" 2>/dev/null || true)
  MARKER="${MARKER:-0}"
  echo "task_id=$NEW_TASK_ID csv_lines=$CSV_LINES marker_rows=$MARKER (判据: lines>=16 且 marker==0)" > "$OUT/csv_summary.txt"
  if [ "$CSV_LINES" -ge 16 ] && [ "$MARKER" -eq 0 ]; then CSV_OK=1; log "✅ 判据③ CSV: $NEW_TASK_ID $CSV_LINES 行真字段"; else log "❌ 判据③ CSV: 行数/marker 不达标（见 csv_summary.txt）"; fi
else
  echo "csv_missing（超时 ${TIMEOUT}s 未见新 CSV）" > "$OUT/csv_summary.txt"
  log "❌ 判据③ CSV: 超时未见新 CSV——查 PO subject 关键字 / Outlook 凭据 / 5678 公网访问 / Flow C 注册"
fi

# ---------- 判据① execution mode=trigger success（SQLite 直读仲裁法，handoff v3 §4）----------
TRIGGER_OK=0
if docker cp n8nDocker:/home/node/.n8n/database.sqlite "$OUT/execution_entity.sqlite" >/dev/null 2>&1; then
  python3 - "$OUT/execution_entity.sqlite" > "$OUT/executions.txt" <<'PYEOF'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
rows = list(db.execute("SELECT id, mode, status, startedAt FROM execution_entity ORDER BY id DESC LIMIT 8"))
hit = any(r[1] == "trigger" and str(r[2]).lower() == "success" for r in rows)
print("TRIGGER_SUCCESS=" + ("yes" if hit else "no"))
for r in rows:
    print(r)
PYEOF
  grep -q "TRIGGER_SUCCESS=yes" "$OUT/executions.txt" && TRIGGER_OK=1
  [ "$TRIGGER_OK" -eq 1 ] && log "✅ 判据① execution: trigger success 在案" || log "❌ 判据① execution: 无 trigger success 新记录"
else
  echo "TRIGGER_SUCCESS=unrun (docker cp 失败——容器不在跑?)" > "$OUT/executions.txt"
  log "⚠️ 判据① execution: UNRUN（docker cp 失败）"
fi

# ---------- 判据② 后端管线锚（fields_count=16 + dispatch）----------
ANCHOR_OK=0
if [ -n "$BACKEND_LOG" ] && [ -f "$BACKEND_LOG" ]; then
  grep -E "KIE step completed|dispatch" "$BACKEND_LOG" | tail -8 > "$OUT/backend_anchors.txt" 2>/dev/null
  if grep -q "fields_count=16" "$OUT/backend_anchors.txt"; then
    ANCHOR_OK=1; log "✅ 判据② 后端锚: fields_count=16 在案"
  else
    log "❌ 判据② 后端锚: 未见 fields_count=16（查 document_type=invoice / KIE 白名单）"
  fi
else
  echo "(BACKEND_LOG 未提供——按 runbook 5.2 用 docker logs <backend> 手工取证后回填)" > "$OUT/backend_anchors.txt"
  log "⚠️ 判据② 后端锚: UNRUN（BACKEND_LOG 未设置；不影响其余判据，summary 如实标注）"
fi

# ---------- 判据④ 平台域名透传 ----------
HEALTH=$(curl -s --max-time 10 "$SPACE_URL/healthz" 2>/dev/null || true)
echo "$HEALTH" > "$OUT/healthz.txt"
HEALTH_OK=0
echo "$HEALTH" | grep -q '"status":"ok"' && HEALTH_OK=1
[ "$HEALTH_OK" -eq 1 ] && log "✅ 判据④ 透传: healthz ok" || log "❌ 判据④ 透传: $HEALTH"

# ---------- 判定（预写死：①∧③ 必须；②/④ UNRUN 不掩盖 FAIL）----------
{
  echo "== R-004 标准重测判读 $STAMP =="
  echo "task_id=$NEW_TASK_ID"
  echo "① execution trigger success: $([ "$TRIGGER_OK" -eq 1 ] && echo PASS || echo FAIL/UNRUN)"
  echo "② backend fields_count=16:   $([ "$ANCHOR_OK" -eq 1 ] && echo PASS || echo FAIL/UNRUN)"
  echo "③ CSV 16 行真字段:           $([ "$CSV_OK" -eq 1 ] && echo PASS || echo FAIL)"
  echo "④ healthz 透传:              $([ "$HEALTH_OK" -eq 1 ] && echo PASS || echo FAIL)"
  if [ "$TRIGGER_OK" -eq 1 ] && [ "$CSV_OK" -eq 1 ]; then
    echo "判定: 端到端穿越 PASS（①③ 达成；②/④ 见上行，UNRUN 项按 runbook 手工补证）"
  else
    echo "判定: FAIL——L2 仅作排障 fallback 不进验收（runbook 阶段 L2），排障后须重跑邮件触发穿越"
  fi
} > "$OUT/summary.txt"

log "===== summary.txt ====="
cat "$OUT/summary.txt"

# ---------- 产物打包 ----------
tar czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")" 2>/dev/null \
  && log "产物包: $OUT.tar.gz（回传本机解包核验后方可登记读数——本机不宣称云端已验证）" \
  || log "⚠️ 打包失败（证据文件仍在 $OUT/）"

[ "$TRIGGER_OK" -eq 1 ] && [ "$CSV_OK" -eq 1 ] && exit 0 || exit 1
