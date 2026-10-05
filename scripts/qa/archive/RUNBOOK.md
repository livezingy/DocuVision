# sciextract RUNBOOK——端点回填与冒烟（2026-10-03）

交接对象：用户（云端操作 + 端点回填）。脚本侧已离线自检（matcher 3/3、prompt 构建 OK）。
端点三件套**只走环境变量**，不写进任何文件、不进 git、不进投标物料。

## 0. 云端起服务（用户，Cloud Studio A10）

vLLM（推荐，权重已在盘上则跳过下载）：

```
python -m vllm.entrypoints.openai.api_server \
  --model <Qwen2.5-VL-3B权重路径> --served-model-name qwen25vl3b --port 8000
```

或 Ollama：`ollama serve` + `ollama pull qwen2.5:7b`（天然带 /v1）。
安全：Cloud Studio 公网映射 URL 是"知道即可访问"——起服务时带 `--api-key <随机token>`，
用完关机。试点闸不过 3B 时换 `Qwen2.5-7B-Instruct`（bf16 14GB，A10 装得下）。

## 1. 冒烟（回填 URL 后，本地跑）

```
curl -s -H "Authorization: Bearer $SCIX_API_KEY" $SCIX_BASE_URL/models
```

期望：JSON 里 `data[].id` 含 `SCIX_MODEL` 填的值。通了再发一条最小对话：

```
curl -s -X POST "$SCIX_BASE_URL/chat/completions" -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SCIX_API_KEY" \
  -d '{"model":"<SCIX_MODEL>","messages":[{"role":"user","content":"Reply with JSON only: {\"ok\":true}"}],"temperature":0}'
```

## 2. 环境变量注入

PowerShell（当前会话有效）：

```
$env:SCIX_BASE_URL = "https://<实例>-8000.<域名>/v1"
$env:SCIX_API_KEY  = "<token，无鉴权则空串>"
$env:SCIX_MODEL    = "qwen25vl3b"
```

Git Bash：`export SCIX_BASE_URL=... SCIX_API_KEY=... SCIX_MODEL=...`

## 3. 试点闸（先闸后跑，不赌 3B 能力）

```
cd D:\4_AgentBuddy\Qoder\bids\2026-10-sciextract
python extract_qwen.py --in ingest/pub_bmc.blocks.json --pages 1-5 --out out/pilot_bmc_3b.jsonl
```

读数在 stdout 末行：`findings=… exact=… hyphen=… miss=… survival=…% call_errors=…`
**过闸线：survival ≥70% 且 call_errors=0**；不过 → 换 7B 重跑本行（改 served-model-name）。
hedge 保真第二闸：从 `out/pilot_bmc_3b.jsonl` 抽 20 条人工判读（保真/去hedge/加hedge），
去 hedge 率 >15% 同样换档。产物 `out/*.calls.jsonl` 是逐调用台账（墙钟+token 用量，
喂给后续 cost/runtime 报告）。

## 4. 全量矩阵（闸过后再来）

```
python extract_qwen.py --in ingest/<paper>.blocks.json --out out/<paper>_base.jsonl     # 全 10 页基线
```

变体（两阶段 verifier / 分块粒度）待 `verify_quotes.py` 正式版落地后按 PLAN §6 步骤 6–7 排。
摄取对比（DV analyze API 通道）另立 `dv_ingest.py`，不在本 RUNBOOK。

## 5. 已知坑（本目录实测）

- 控制台必须 ASCII：Windows GBK 遇 `\xa0` 直接炸（`ascii_text()` 已兜底；新脚本照抄此纪律）。
- `json.load` 一律 `encoding='utf-8'`（默认 GBK 读不了 EPMC 件）。
- 模型输出容忍 markdown 围栏（`strip_fences` 抓最外层 `{...}`），解析失败进 calls 台账不静默。
- 重试上限 3 次指数退避，最终失败 `CALL-FAIL` 可见并计入 `call_errors`。
