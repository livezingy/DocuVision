# 🚀 启动 DocuVision

本目录包含了方便启动 DocuVision 的脚本和指南。

## ⚡ 最快启动方式  

### Windows 用户

**方法 1: 批处理脚本（推荐）**
```bash
# 双击运行此文件：
START_DOCUVISION.bat

# 或在 PowerShell/CMD 中运行：
.\START_DOCUVISION.bat
```

**方法 2: PowerShell 脚本**
```powershell
# 运行此脚本：
.\START_DOCUVISION.ps1

# 如果遇到执行策略错误，运行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\START_DOCUVISION.ps1
```

### macOS / Linux 用户

```bash
# 终端 1: 启动后端
cd backend
python run.py

# 终端 2: 打开前端（在后端启动后执行）
# macOS:
open frontend/index.html

# Linux:
xdg-open frontend/index.html
```

## 📋 启动流程说明

这些脚本会自动执行以下步骤：

1. **检查后端状态**
   - 检查 `localhost:8000` 是否已在运行
   - 如果未运行，自动启动后端服务

2. **等待后端就绪**
   - 给予 3 秒时间让后端启动
   - 确保 API 可用

3. **打开前端界面**
   - 在默认浏览器中打开 `http://localhost:8000`
   - 自动显示文档处理界面

## 🔍 验证启动成功

启动脚本执行后，您应该看到：

1. **后端终端输出**:
   ```
   INFO:     Uvicorn running on http://127.0.0.1:8000
   ```

2. **浏览器显示**:
   - 前端 UI 加载
   - 顶部状态栏显示: ✓ API Connected: DocuVision API v1.1.0
   - 左侧上传区域可用

3. **脚本输出**:
   ```
   ========================================
   ✓ DocuVision is ready!
   ========================================
   
   Frontend:  http://localhost:8000
   API Docs:  http://localhost:8000/docs
   Health:    http://localhost:8000/health
   ```

## ⚙️ 手动启动（如果脚本不工作）

### 步骤 1: 启动后端

```bash
cd backend
python run.py
```

如果出现依赖错误，请先安装依赖：
```bash
pip install -r requirements.txt
```

### 步骤 2: 打开前端

在浏览器中访问任何一个：
- `http://localhost:8000` - 直接访问
- `frontend/index.html` - 本地文件打开
- `http://localhost:8001` - 如果运行本地 web 服务器

## 🐛 故障排除

### 问题: 脚本找不到或无法执行

**Windows Batch**:
- 确保您在项目根目录
- 使用完整路径: `C:\path\to\DocuVision\START_DOCUVISION.bat`

**PowerShell**:
- 使用: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- 使用: `& '.\START_DOCUVISION.ps1'`

### 问题: 后端已在运行

脚本会自动检测到这一点并跳过启动。
只需打开前端即可。

### 问题: 端口 8000 已被占用

1. 找到占用该端口的进程:
   ```bash
   # Windows:
   netstat -ano | findstr ":8000"
   
   # Linux/Mac:
   lsof -i :8000
   ```

2. 停止该进程或使用不同的端口

### 问题: 前端无法连接到 API

1. 确保后端已启动
2. 检查 `http://localhost:8000/health` 是否可访问
3. 检查浏览器控制台 (F12) 中的错误信息
4. 尝试硬刷新浏览器 (Ctrl+Shift+R)

## 📚 详细文档

如需了解更多信息，请参考：

- [QUICK_START_GUIDE.md](QUICK_START_GUIDE.md) - 5 分钟快速开始指南
- [README.md](README.md) - 完整项目文档
- [docs/MODEL_SETUP_GUIDE.md](docs/MODEL_SETUP_GUIDE.md) - 模型配置指南

## 🎯 下一步

启动完成后：

1. **上传文档** - 拖拽 PDF 或图片到上传区
2. **运行分析** - 点击"Run Analysis"按钮
3. **查看结果** - 在右侧面板查看识别结果
4. **导出数据** - 选择导出格式（JSON/CSV/Word/Excel）

## 💡 提示

- **首次启动**: 系统会自动下载所需的 AI 模型（可能需要几秒到几分钟）
- **网络要求**: 仅首次启动需要网络下载模型
- **离线使用**: 模型下载完成后可完全离线使用
- **性能**: 首次处理可能较慢，之后会缓存优化

## 🔗 快速链接

| 资源 | 地址 |
|------|------|
| 前端界面 | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |
| 服务器信息 | http://localhost:8000/ |

---

**准备好了吗？开始使用 DocuVision 吧！** 🎉
