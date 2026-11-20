#!/usr/bin/env bash
# r004_n8n_rebuild.sh — R-004 阶段1/2 前置：n8n 删卷重建 + 5678 端口哨兵（Cloud Studio 端口面板可检测）
#
# 用法（Cloud Studio 终端）:
#   bash r004_n8n_rebuild.sh                    # 默认删卷重建（DEL_VOLUME=1）
#   DEL_VOLUME=0 bash r004_n8n_rebuild.sh       # 保卷重建（幂等重跑/空间重启后恢复用）
# 可选段（默认全关，不影响既有幂等行为）:
#   DEL_VOLUME=1 FRESH_IMPORT=1 bash r004_n8n_rebuild.sh   # 新卷场景：一次性容器 headless 导入工作流 + CLI 激活尝试
#   REGISTER=1 bash r004_n8n_rebuild.sh                     # 兜底：直连后端注册 webhook（前置：后端 run.py 已起）
#                                                           # （标准路径 = runbook 阶段 3 经 n8n API 触发 Flow C；用了本段须登记 flowCVerified=false）
#
# 设计要点:
#   - 宿主 5678 由 python3 哨兵监听（零依赖），转发到桥接口 15678（docker -p 15678:5678）
#   - 端口面板对 5678 的条目 = 哨兵进程；15678 是 docker-proxy，面板是否显示不影响链路
#   - N8N_ENCRYPTION_KEY 幂等固化于 /root/.n8n_enc_key（重跑不换密钥，credentials 不失效）
#   - URL 全链用平台代理域名（无墙透传已实测），Azure redirect URI 无需改动
#   - 容器带 --restart unless-stopped（空间重启后 docker daemon 若自启，容器自动回；哨兵需重跑本脚本）
set -uo pipefail

SPACE_URL="${SPACE_URL:-https://9f15e4b797f34bc08ac399937544b368--5678.ap-shanghai2.cloudstudio.club}"
HOST_PORT="${HOST_PORT:-5678}"
BRIDGE_PORT="${BRIDGE_PORT:-15678}"
IMG="${IMG:-n8nio/n8n:2.48.4}"
REPO_DIR="${REPO_DIR:-/workspace/DocuVision}"
KEY_FILE="/root/.n8n_enc_key"
BRIDGE_SCRIPT="/root/n8n_port_bridge.py"
BRIDGE_PID="/root/n8n_bridge.pid"
BRIDGE_LOG="/root/n8n_bridge.log"
BACKUP_DIR="${BACKUP_DIR:-/workspace/n8n_backup}"
DEL_VOLUME="${DEL_VOLUME:-1}"
FRESH_IMPORT="${FRESH_IMPORT:-0}"
REGISTER="${REGISTER:-0}"

log(){ echo "[$(date +%H:%M:%S)] $*"; }
die(){ log "❌ $*"; exit 1; }

# ---------- 0. 前置检查 ----------
log "== 0. 前置检查 =="
command -v docker >/dev/null || die "docker 不可用"
docker ps >/dev/null 2>&1 || die "docker daemon 无响应"
command -v python3 >/dev/null || die "python3 不可用（哨兵依赖）"
[ -f "$REPO_DIR/backend/.env" ] || die "缺少 $REPO_DIR/backend/.env"
grep -q '^WEBHOOK_ADMIN_TOKEN=' "$REPO_DIR/backend/.env" || die ".env 中无 WEBHOOK_ADMIN_TOKEN"
TOKEN=$(grep -E '^WEBHOOK_ADMIN_TOKEN=' "$REPO_DIR/backend/.env" | head -1 | cut -d= -f2- | tr -d '"')
[ -n "$TOKEN" ] || die "WEBHOOK_ADMIN_TOKEN 为空"
log "前置 OK（token 已从 env 文件提取，不落盘不打印）"

# ---------- 1. 删卷前快照 ----------
if [ "$DEL_VOLUME" = "1" ] && docker volume ls --format '{{.Name}}' | grep -qx n8n_data; then
  log "== 1. 旧卷快照（防手滑，不进 git）=="
  mkdir -p "$BACKUP_DIR"
  BAK="$BACKUP_DIR/n8n_data_$(date +%Y%m%d_%H%M%S).tar.gz"
  docker run --rm -v n8n_data:/from -v "$BACKUP_DIR":/backup alpine \
    sh -c "cd /from && tar czf /backup/$(basename "$BAK") ."
  [ -s "$BAK" ] || die "快照失败，中止删卷"
  log "快照 OK: $BAK ($(du -h "$BAK" | cut -f1))（新实例验证后可删）"
else
  log "== 1. 跳过快照（DEL_VOLUME=$DEL_VOLUME 或卷不存在）=="
fi

# ---------- 2. 停删容器与卷 ----------
log "== 2. 容器与卷操作（DEL_VOLUME=$DEL_VOLUME）=="
docker stop n8nDocker 2>/dev/null || true
docker rm n8nDocker 2>/dev/null || true
if [ "$DEL_VOLUME" = "1" ]; then
  docker volume rm n8n_data 2>/dev/null || true
  if docker volume ls --format '{{.Name}}' | grep -qx n8n_data; then
    die "n8n_data 卷仍存在（可能被其他容器占用）: docker ps -a --filter volume=n8n_data"
  fi
  log "旧卷已删除"
else
  log "保卷模式：n8n_data 保留（凭据/workflow 随固定密钥复活）"
fi

# ---------- 3. 加密密钥（幂等固化）----------
log "== 3. N8N_ENCRYPTION_KEY =="
if [ -s "$KEY_FILE" ]; then
  ENCRYPTION_KEY=$(cat "$KEY_FILE")
  log "复用既有密钥: $KEY_FILE"
else
  ENCRYPTION_KEY=$(openssl rand -hex 24)
  ( umask 177; echo "$ENCRYPTION_KEY" > "$KEY_FILE" )
  log "新密钥已生成并落 $KEY_FILE（权限 0600，禁止入 git）"
fi

# ---------- 3.5 可选：新卷导入工作流（FRESH_IMPORT=1，默认关）----------
# 仅删卷/新卷场景有意义：保卷时 workflow 随卷复活，重复导入会产生同名副本。
# 原理：一次性容器挂 n8n_data 卷做 headless CLI 导入（无 owner/API Key 依赖），
#       在主容器启动前完成，避免与运行中的 n8n 进程争 SQLite。
# 不可自动化的部分（新卷必手工）：① UI owner 首建账户 ② Outlook/Azure AD 凭据
#   Reconnect（OAuth 交互式同意；凭据禁落盘/禁入脚本=红线）③ Public API Key 创建（可选）。
WF_JSON="$REPO_DIR/docs/integrations/n8n/docuvision-v1.1-outlook.json"
WF_ID=""
if [ "$FRESH_IMPORT" = "1" ]; then
  log "== 3.5 FRESH_IMPORT：一次性容器导入工作流 =="
  [ -f "$WF_JSON" ] || die "FRESH_IMPORT 找不到 $WF_JSON（云端须已拉取 feat/r004-p043-n8n-integration @bcf5cbe+）"
  if docker volume ls --format '{{.Name}}' | grep -qx n8n_data; then
    log "n8n_data 卷已存在——跳过导入（防同名副本；确需重灌请 DEL_VOLUME=1）"
  else
    docker volume create n8n_data >/dev/null || die "n8n_data 卷创建失败"
    docker run --rm -v n8n_data:/home/node/.n8n -e N8N_ENCRYPTION_KEY="$ENCRYPTION_KEY" \
      -v "$WF_JSON":/files/import.json:ro "$IMG" \
      n8n import:workflow --input=/files/import.json || die "工作流导入失败"
    WF_ID=$(docker run --rm -v n8n_data:/home/node/.n8n -e N8N_ENCRYPTION_KEY="$ENCRYPTION_KEY" \
      "$IMG" n8n export:workflow --all 2>/dev/null \
      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null || true)
    if [ -n "$WF_ID" ]; then
      log "导入 OK：workflow id=$WF_ID（新卷产生新 id——verify/判读一律用本动态值，勿沿用旧 N8N_WORKFLOW_ID）"
    else
      log "⚠️ workflow id 探测失败（不阻塞；UI 里查看或稍后 n8n export:workflow --all 重探）"
    fi
  fi
fi

# ---------- 4. 重建容器（宿主 BRIDGE_PORT → 容器 5678）----------
log "== 4. 重建容器（镜像 $IMG，宿主 ${BRIDGE_PORT} → 容器 5678）=="
docker pull "$IMG" >/dev/null 2>&1 || log "⚠️ pull 跳过/失败（本地可能已有该镜像层，继续）"
docker run -d --name n8nDocker -p "${BRIDGE_PORT}:5678" \
  --restart unless-stopped \
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e N8N_RESTRICT_FILE_ACCESS_TO=/files/watch \
  -e N8N_ENCRYPTION_KEY="$ENCRYPTION_KEY" \
  -e WEBHOOK_URL="$SPACE_URL" \
  -e N8N_EDITOR_BASE_URL="$SPACE_URL" \
  -e DOCUVISION_CALLBACK_URL="$SPACE_URL/webhook/docuvision-outlook-watch-csv" \
  -e DOCUVISION_WEBHOOK_ADMIN_TOKEN="$TOKEN" \
  -e DOCUVISION_BASE_URL="http://host.docker.internal:8000" \
  -e DOCUVISION_WATCH_DIR="/files/watch" \
  -e DOCUVISION_PO_SUBJECT_KEYWORD="PO" \
  -e DOCUVISION_PO_DOCUMENT_TYPE="invoice" \
  -v n8n_data:/home/node/.n8n \
  -v "$REPO_DIR/debug/n8n-watch:/files/watch" \
  --add-host host.docker.internal:host-gateway \
  "$IMG" || die "容器启动失败"
docker volume ls --format '{{.Name}}' | grep -qx n8n_data || die "n8n_data 卷未创建"
sleep 8

# ---------- 4.6 可选：CLI 激活尝试（FRESH_IMPORT=1 时；失败不阻塞，UI 兜底）----------
if [ "$FRESH_IMPORT" = "1" ] && [ -n "$WF_ID" ]; then
  log "== 4.6 激活尝试（CLI）=="
  if docker exec n8nDocker n8n update:workflow --id="$WF_ID" --active=true >/dev/null 2>&1; then
    log "激活 OK（CLI）"
  else
    log "⚠️ CLI 激活未果（旗标以 n8n update:workflow --help 实测为准）——UI 里 Active 一键兜底；"
    log "   凭据必须 UI Reconnect（OAuth 交互同意，红线禁自动化）；Public API Key 若需 API 侧判读也在 UI 创建"
  fi
fi

# ---------- 5. 5678 端口哨兵 ----------
log "== 5. 5678 端口哨兵（端口面板检测目标）=="
[ -f "$BRIDGE_PID" ] && { kill "$(cat "$BRIDGE_PID")" 2>/dev/null || true; rm -f "$BRIDGE_PID"; log "旧哨兵已清理"; }
LISTEN_CHECK=$(ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null || true)
if echo "$LISTEN_CHECK" | grep -q ":${HOST_PORT} "; then
  die "宿主 ${HOST_PORT} 已被占用：$LISTEN_CHECK | grep ${HOST_PORT}（排查后重跑）"
fi
cat > "$BRIDGE_SCRIPT" <<'PYEOF'
import socket, threading
HOST_PORT, BRIDGE_PORT = 5678, 15678
def pipe(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d:
                break
            b.sendall(d)
    except Exception:
        pass
    finally:
        for s in (a, b):
            try:
                s.close()
            except Exception:
                pass
srv = socket.socket()
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("0.0.0.0", HOST_PORT))
srv.listen(128)
print(f"bridge {HOST_PORT} -> {BRIDGE_PORT} ready", flush=True)
while True:
    c, _ = srv.accept()
    try:
        u = socket.socket()
        u.connect(("127.0.0.1", BRIDGE_PORT))
    except Exception:
        try:
            c.close()
        except Exception:
            pass
        continue
    threading.Thread(target=pipe, args=(c, u), daemon=True).start()
    threading.Thread(target=pipe, args=(u, c), daemon=True).start()
PYEOF
nohup python3 "$BRIDGE_SCRIPT" > "$BRIDGE_LOG" 2>&1 &
echo $! > "$BRIDGE_PID"
sleep 2
ss -ltn 2>/dev/null | grep -q ":${HOST_PORT} " || die "哨兵未监听 ${HOST_PORT}（查 $BRIDGE_LOG）"
log "哨兵 OK: 宿主 ${HOST_PORT} 监听中（pid=$(cat "$BRIDGE_PID")）→ 端口面板应显示 5678"

# ---------- 5.5 可选：Flow C 注册兜底（REGISTER=1，默认关）----------
# 直连后端注册（等价 Flow C 的容器 env 行为）。注意：跳过了 Flow C 节点本身的验证面——
# 用了本段须在重测 summary 如实登记 flowCVerified=false；标准路径 = runbook 阶段 3 经 n8n API 触发 Flow C。
# 前置：后端 run.py 已起（本脚本不拉起后端）。后端重启会清内存订阅（排障链 #8）——重启后重跑 REGISTER=1 即可。
if [ "$REGISTER" = "1" ]; then
  log "== 5.5 REGISTER：后端 webhook 注册兜底 =="
  BE_HEALTH=$(curl -s --max-time 6 "http://localhost:8000/healthz" 2>/dev/null || true)
  echo "$BE_HEALTH" | grep -q '"status":"ok"' || die "后端 :8000 未起（先 python run.py）——REGISTER 需要"
  REG=$(curl -s --max-time 10 -X POST "http://localhost:8000/api/v1/webhooks" \
    -H "X-DocuVision-Admin-Token: $TOKEN" \
    --data-urlencode "url=$SPACE_URL/webhook/docuvision-outlook-watch-csv" \
    --data-urlencode "events=task.completed" \
    --data-urlencode "secret=" || true)
  echo "$REG" | grep -q "subscription_id" && log "注册 OK: $REG" || die "注册失败: $REG（查 DOCUVISION_WEBHOOK_ENABLED / SSRF 门 / token）"
fi

# ---------- 6. 四验 ----------
log "== 6. 验证 =="
PASS=0; TOTAL=4
v1=$(curl -s --max-time 6 "http://localhost:${HOST_PORT}/healthz" 2>/dev/null || true)
if echo "$v1" | grep -q '"status":"ok"'; then log "✅ 1/4 哨兵→容器 healthz OK"; PASS=$((PASS+1)); else log "❌ 1/4 哨兵→容器 healthz: '$v1'"; fi
v2=$(curl -s --max-time 6 "http://127.0.0.1:${BRIDGE_PORT}/healthz" 2>/dev/null || true)
if echo "$v2" | grep -q '"status":"ok"'; then log "✅ 2/4 桥接口 ${BRIDGE_PORT} healthz OK"; PASS=$((PASS+1)); else log "❌ 2/4 桥接口: '$v2'"; fi
ver=$(docker exec n8nDocker n8n --version 2>/dev/null || echo unknown)
if [ "$ver" = "2.48.4" ]; then log "✅ 3/4 版本 $ver（pinned）"; PASS=$((PASS+1)); else log "❌ 3/4 版本异常: $ver"; fi
v4=$(curl -s --max-time 10 "$SPACE_URL/healthz" 2>/dev/null || true)
if echo "$v4" | grep -q '"status":"ok"'; then log "✅ 4/4 平台域名透传 OK"; PASS=$((PASS+1)); else log "❌ 4/4 平台域名: '$v4'（检查端口面板 5678 是否已开公网访问）"; fi

log "== 完成 $PASS/$TOTAL =="
if [ $PASS -eq $TOTAL ]; then
  log "下一步: 端口面板确认 5678【公网访问】开 → 阶段1（n8n 凭据 Reconnect，Azure redirect 无需改）→ 阶段2 冒烟"
  log "新卷全自动程度: FRESH_IMPORT=1 已导入工作流（id 见 3.5 日志）→ 手工: UI owner 首建 + 凭据 Reconnect → REGISTER=1 重跑注册（或 runbook 阶段 3 走 Flow C）"
  log "空间重启后恢复: DEL_VOLUME=0 bash $0（幂等，凭据随固定密钥复活）"
else
  exit 1
fi
