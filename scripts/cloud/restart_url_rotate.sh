#!/usr/bin/env bash
# =============================================================================
# restart_url_rotate.sh - n8n 公网 URL 轮换后的联动重置助手（Cloud GPU / DinD）
#
# 背景（R-004 AC1 闭环，2026-11-17 handoff §3 + 用户 A1~A5 流程）：
#   Cloudflare quick tunnel 的 trycloudflare URL 随机、cloudflared 重启即换。
#   换 URL 后五处联动：n8n 容器 env（WEBHOOK_URL / N8N_EDITOR_BASE_URL /
#   DOCUVISION_CALLBACK_URL）重建 + Azure redirect URI 补注册 + 重新注册订阅。
#
# 本脚本自动执行 A2~A4（后端健康检查 → 重置重建 n8n + import workflow →
#   注册订阅）。手动步骤（脚本只打印，不执行）：Azure（B）、浏览器建号/凭据/发布
#   （C）、发 PO 邮件（D）、verify（A5）。
#
# 红线：admin token 只在 docker -e / curl header 传递，绝不 echo 明文、绝不写日志。
#   破坏性：默认 RESET_VOLUME=1 会 docker volume rm n8n_data（清空工作流/凭据/账号）。
#
# Usage:
#   bash restart_url_rotate.sh <new_tunnel_url>      # 自动执行 A2~A4
#   DRY_RUN=1 bash restart_url_rotate.sh <url>       # 只打印不执行（token 掩码）
#   N8N_IMAGE=... WF_JSON=... RESET_VOLUME=0 bash ... # 覆盖 image/模板路径/不删卷
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log() { echo "[urlrotate] $*"; }
die() { echo "[urlrotate][FATAL] $*" >&2; exit 2; }

# ---- 输入 --------------------------------------------------------------------
NEW_URL="${NEW_URL:-${1:-}}"
[ -n "$NEW_URL" ] || die "缺新 URL：bash restart_url_rotate.sh <new_tunnel_url>"
NEW_URL="${NEW_URL%/}"   # 去尾斜杠

DRY_RUN="${DRY_RUN:-0}"
RESET_VOLUME="${RESET_VOLUME:-1}"                       # 1 = 删卷（清空账号/凭据/工作流，回到 setup 页）
N8N_IMAGE="${N8N_IMAGE:-n8nio/n8n}"                     # 以你上次用的 image 为准，可覆盖
WF_JSON="${WF_JSON:-}"                       # 空 = 自动解析（优先 repo 唯一真源，见 REPO_DIR 定位后）
WEBHOOK_PATH="${WEBHOOK_PATH:-docuvision-outlook-watch-csv}"

# ---- 定位 repo + 后端 env -----------------------------------------------------
REPO_DIR="${REPO_DIR:-}"
if [ -z "$REPO_DIR" ]; then
  d="$SCRIPT_DIR"
  while [ "$d" != "/" ]; do
    [ -f "$d/backend/app/main.py" ] && REPO_DIR="$d" && break
    d="$(dirname "$d")"
  done
fi
[ -n "$REPO_DIR" ] || die "repo not found; set REPO_DIR=/path/to/DocuVision"
ENV_FILE="$REPO_DIR/backend/.env"
[ -f "$ENV_FILE" ] || die "backend .env not found: $ENV_FILE"

# ---- 模板来源解析（漂移修复，2026-11-18）----------------------------------------
# 教训（R-004 AC1 replay）：服务器侧副本 /workspace/secrets/n8n/... 若停留在旧版（缺
# responseFormat=json，且 Code 节点为 eachItem+数组返回——后者在 n8n 2.x 必报
# A 'json' property isn't an object），每次 URL 轮换都会重新导入坏模板。repo 模板
# （2026-11-18+：responseFormat=json + allItems 模式加固版 Code 节点）是唯一真源；
# secrets 副本仅作 repo 缺失时的回退，导入前有双 guard。
if [ -z "$WF_JSON" ]; then
  REPO_WF_JSON="$REPO_DIR/docs/integrations/n8n/docuvision-v1.1-outlook.json"
  if [ -f "$REPO_WF_JSON" ]; then
    WF_JSON="$REPO_WF_JSON"
    log "WF_JSON 默认取 repo 唯一真源：$WF_JSON"
  else
    WF_JSON="/workspace/secrets/n8n/docuvision-v1.1-outlook.json"
    log "WARN: repo 模板缺失，回退服务器副本 $WF_JSON（导入前有 responseFormat guard）"
  fi
fi

# ---- 提取 admin token（handoff §3 教训：重建容器前必须先取）------------------
TOKEN="$(grep -E '^WEBHOOK_ADMIN_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"')"
[ -n "$TOKEN" ] || die "WEBHOOK_ADMIN_TOKEN 空或未取到（检查 $ENV_FILE）"
log "token extracted (len=${#TOKEN})；明文不回显"

# ---- 派生 URL ----------------------------------------------------------------
WEBHOOK_URL="$NEW_URL"
N8N_EDITOR_BASE_URL="$NEW_URL"
# 回调 URL = n8n Flow B webhook 节点「Production URL」。默认 {NEW_URL}/webhook/<path>；
# 若你实例不带 /webhook 前缀，以 n8n UI 显示为准，或用 DOCUVISION_CALLBACK_URL 覆盖。
DOCUVISION_CALLBACK_URL="${DOCUVISION_CALLBACK_URL:-${WEBHOOK_URL}/webhook/${WEBHOOK_PATH}}"

# ---- A2: 后端健康检查 ---------------------------------------------------------
log "=== A2: 后端健康检查 ==="
if [ "$DRY_RUN" = "1" ]; then
  echo "[DRY_RUN] curl -fsS http://127.0.0.1:8000/health"
else
  curl -fsS http://127.0.0.1:8000/health >/dev/null || die "后端 health 不通（先拉起后端）"
  log "backend OK"
fi

# ---- A2+A3: 重置并重建 n8n 容器 + import workflow -----------------------------
log "=== A2+A3: 重置并重建 n8n + import workflow ==="
if [ "$DRY_RUN" = "1" ]; then
  echo "[DRY_RUN] docker rm -f n8nDocker"
  [ "$RESET_VOLUME" = "1" ] && echo "[DRY_RUN] docker volume rm n8n_data"
  echo "[DRY_RUN] docker run -d --name n8nDocker -p 5678:5678 -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \\"
  echo "          -e WEBHOOK_URL='$WEBHOOK_URL' -e N8N_EDITOR_BASE_URL='$N8N_EDITOR_BASE_URL' \\"
  echo "          -e DOCUVISION_CALLBACK_URL='$DOCUVISION_CALLBACK_URL' -e DOCUVISION_WEBHOOK_ADMIN_TOKEN='<TOKEN>' \\"
  echo "          -e DOCUVISION_BASE_URL='http://host.docker.internal:8000' -e DOCUVISION_WATCH_DIR='/files/watch' \\"
  echo "          -v n8n_data:/home/node/.n8n -v /workspace/DocuVision/debug/n8n-watch:/files/watch \\"
  echo "          --add-host host.docker.internal:host-gateway $N8N_IMAGE"
  echo "[DRY_RUN] 等待 n8n 就绪（curl /healthz）"
  echo "[DRY_RUN] guards: responseFormat=json + runOnceForAllItems in $WF_JSON（缺失则 die）"
  echo "[DRY_RUN] docker cp $WF_JSON n8nDocker:/tmp/wf.json"
  echo "[DRY_RUN] docker exec n8nDocker n8n import:workflow --input=/tmp/wf.json"
else
  docker rm -f n8nDocker 2>/dev/null || true
  if [ "$RESET_VOLUME" = "1" ]; then
    log "WARN: 删除卷 n8n_data（清空工作流/凭据/owner 账号 → 浏览器回到 setup 页）"
    docker volume rm n8n_data 2>/dev/null || true
  fi
  docker run -d --name n8nDocker \
    -p 5678:5678 \
    -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
    -e WEBHOOK_URL="$WEBHOOK_URL" \
    -e N8N_EDITOR_BASE_URL="$N8N_EDITOR_BASE_URL" \
    -e DOCUVISION_CALLBACK_URL="$DOCUVISION_CALLBACK_URL" \
    -e DOCUVISION_WEBHOOK_ADMIN_TOKEN="$TOKEN" \
    -e DOCUVISION_BASE_URL="http://host.docker.internal:8000" \
    -e DOCUVISION_WATCH_DIR="/files/watch" \
    -v n8n_data:/home/node/.n8n \
    -v /workspace/DocuVision/debug/n8n-watch:/files/watch \
    --add-host host.docker.internal:host-gateway \
    "$N8N_IMAGE" || die "docker run 失败"
  log "等待 n8n 就绪..."
  ready=0
  for i in $(seq 1 30); do
    curl -fsS http://127.0.0.1:5678/healthz >/dev/null 2>&1 && { ready=1; break; }
    sleep 2
  done
  [ "$ready" = "1" ] || die "n8n 60s 未就绪（检查容器日志：docker logs n8nDocker）"
  log "n8n ready"
  [ -f "$WF_JSON" ] || die "workflow JSON 缺失：$WF_JSON（先上传更新后的模板到该路径）"
  # 导入前 guard：拒绝两类已知坏模板（见 docs/integrations/n8n/README.md §8）
  # 1) 缺 responseFormat=json（GET 节点 autodetect）；2) Code 节点仍为 eachItem 模式
  #    （n8n 2.x 拒绝数组返回 → A 'json' property isn't an object，真因）
  grep -Eq '"responseFormat"[[:space:]]*:[[:space:]]*"json"' "$WF_JSON" \
    || die "模板 $WF_JSON 缺 responseFormat=json（旧版 GET 节点 autodetect）——用 docs/integrations/n8n/ 当前模板更新后再跑"
  grep -q 'runOnceForAllItems' "$WF_JSON" \
    || die "模板 $WF_JSON 的 Code 节点缺 runOnceForAllItems（eachItem+数组返回在 n8n 2.x 报 A 'json' property isn't an object）——用 docs/integrations/n8n/ 当前模板更新后再跑"
  docker cp "$WF_JSON" n8nDocker:/tmp/wf.json || die "docker cp 失败"
  docker exec n8nDocker n8n import:workflow --input=/tmp/wf.json \
    || log "WARN: import 失败（可改在浏览器 C 步导入 + publish）"
fi

# ---- A4: 注册订阅 -------------------------------------------------------------
log "=== A4: 注册 webhook 订阅 ==="
if [ "$DRY_RUN" = "1" ]; then
  echo "[DRY_RUN] curl -X POST http://127.0.0.1:8000/api/v1/webhooks \\"
  echo "          -H 'X-DocuVision-Admin-Token: <TOKEN>' \\"
  echo "          --data-urlencode 'url=$DOCUVISION_CALLBACK_URL' \\"
  echo "          --data-urlencode 'events=task.completed' \\"
  echo "          --data-urlencode 'secret=${DOCUVISION_WEBHOOK_SECRET:-}'"
else
  curl -sS -X POST "http://127.0.0.1:8000/api/v1/webhooks" \
    -H "X-DocuVision-Admin-Token: $TOKEN" \
    --data-urlencode "url=$DOCUVISION_CALLBACK_URL" \
    --data-urlencode "events=task.completed" \
    --data-urlencode "secret=${DOCUVISION_WEBHOOK_SECRET:-}"
  echo
fi

# ---- B / C / D 手动步骤（只打印）----------------------------------------------
log "=== B: Azure 补注册 redirect URI（手动，Ying）==="
echo "  Outlook OAuth redirect URI：${N8N_EDITOR_BASE_URL}/rest/oauth2-credential/callback"
echo
log "=== C: 浏览器（手动，Azure 完成后）==="
echo "  1. 打开 ${N8N_EDITOR_BASE_URL} → setup 页创建 owner 账号（新邮箱）"
echo "  2. Credentials → Add credential → Microsoft Outlook OAuth2 API"
echo "     → 核对 Redirect URL 框显示新公网形态 → 填 Client ID/Secret → Sign in with Microsoft"
echo "  3. 打开已导入 workflow → Outlook Trigger 节点配好 credential → Publish"
echo
log "=== D: 发 PO 邮件（手动）==="
echo "  其他邮箱 → 向 Outlook 账号发含附件、主题含 PO 关键字的邮件"
echo

# ---- A5: verify（B/C/D 后手动）------------------------------------------------
log "=== A5: verify（B/C/D 完成后执行）==="
cat <<EOF
TOKEN=\$(grep -E '^WEBHOOK_ADMIN_TOKEN=' ${ENV_FILE} | head -1 | cut -d= -f2- | tr -d '"')
EXPECTED_HEAD=0f3d7bd RUN_E2E=1 E2E_POLL_SEC=180 \\
  N8N_DB=\$(docker volume inspect n8n_data --format '{{.Mountpoint}}')/database.sqlite \\
  R34_WATCH_DIR=/workspace/DocuVision/debug/n8n-watch \\
  R34_WEBHOOK_ADMIN_TOKEN="\$TOKEN" bash cloud_r003_r004_verify.sh
EOF
echo
log "=== 顺序：A2~A4（本脚本自动）→ B → C → D → A5 ==="
