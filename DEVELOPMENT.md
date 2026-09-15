# DEVELOPMENT.md — 三条硬规范

1. **文件行数预算 500**：backend/app 与 scripts 下新文件超 500 行 CI 即红；
   存量超标文件在 scripts/file_size_allowlist.json 里棘轮管理（只减不增，
   缩小后跑 `python scripts/lint_file_size.py --update` 下调记录）。

2. **路由只进域 router**：新路由写进 backend/app/routers/ 对应域文件
   （必要时新建域），main.py 出现路由装饰器 = CI 红。main.py 只是装配层。

3. **叶子模块禁止 import app.main**：可独立测试的模块（渲染器、纯计算、
   后处理器）不得依赖 FastAPI 应用对象；需要共享状态的走 core/runtime.py。
   新服务模块的单测必须能在不启动 app 的情况下 import 通过。
