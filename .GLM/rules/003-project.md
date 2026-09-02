# 项目事实与测试分层（GLM）

## 环境
- 本地（GLM 沙箱与用户本机）**无 GPU**：只改代码 + 跑纯逻辑/契约 pytest。
- GPU 栈在腾讯 Cloud Studio；工作流：本地改 → git → 云拉取验证。**Git 为真源**。
- 技术栈：paddlepaddle-gpu 3.3.0 / paddleocr 3.3.2 / paddlex 3.3.12 / Qwen2.5-VL。

## 测试分层（先搜后建）
| 层 | 位置 | 本地可跑 |
|----|------|----------|
| 纯逻辑/契约 mock | backend/tests/test_*.py | ✅（GLM 必须全绿） |
| 引擎/GPU 集成 | test_live_api.py、云 checklist | ❌ Cloud Studio |
| UI E2E | frontend/tests/e2e（Playwright） | ❌ 云/本机浏览器 |

## 文档同步
- 契约改动必须同步 living doc（docs/architecture/*）并声明 Doc sync。
- 新增 docs/ 文件要更新 docs/README.md 索引。
- 交付 footer 五项：**Adversarial check | Dead code check | Test placement | Manual test scope | Doc sync**

## 目录卫生
- 运行时目录（uploads/ outputs/ debug/ backend/data/）不进 git。
- docs/R&D/** 除 README 外 local only。
