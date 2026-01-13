# 🚀 Quick Start Guide - AI Circuit Designer

## Windows 用户 - 最简单的方式

### 方法 1: 双击批处理文件（推荐）

1. **安装所有依赖**
   - 双击 `INSTALL.bat`
   - 等待所有依赖安装完成

2. **启动所有服务**
   - 双击 `START.bat`
   - 5个新窗口会自动打开（Backend API, AI Service, EDA Service, Celery Worker, Frontend）

3. **访问应用**
   - 打开浏览器访问: http://localhost:3000

### 方法 2: 使用 PowerShell 脚本

1. **打开 PowerShell**（在项目根目录）

2. **安装依赖**
   ```powershell
   .\install-all.ps1
   ```

3. **启动服务**
   ```powershell
   .\start-all.ps1
   ```

4. **停止服务**
   ```powershell
   .\stop-all.ps1
   ```

---

## 手动启动（高级用户）

### 前置条件

- ✅ Python 3.10+
- ✅ Node.js 18+
- ✅ Redis 服务器

### 步骤 1: 安装 Redis

```powershell
# Windows (使用 winget)
winget install Redis.Redis

# 或者下载安装
# https://github.com/microsoftarchive/redis/releases
```

### 步骤 2: 安装依赖

```powershell
# 后端
cd backend
pip install -r requirements.txt

# AI 服务
cd ..\ai_service
pip install -r requirements.txt

# EDA 工具
cd ..\eda_tools
pip install -r requirements.txt

# 前端
cd ..\frontend
npm install
```

### 步骤 3: 初始化数据库

```powershell
cd ..\backend
python init_db.py
```

### 步骤 4: 启动 Redis（新终端）

```powershell
redis-server
```

### 步骤 5: 启动所有服务（5个独立终端）

**终端 1 - Backend API:**
```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

**终端 2 - AI Service:**
```powershell
cd ai_service
python -m uvicorn app.main:app --reload --port 8001
```

**终端 3 - EDA Service:**
```powershell
cd eda_tools
python -m uvicorn app.main:app --reload --port 8002
```

**终端 4 - Celery Worker:**
```powershell
cd backend
python start_worker.py
```

**终端 5 - Frontend:**
```powershell
cd frontend
npm run dev
```

### 步骤 6: 访问应用

打开浏览器访问: **http://localhost:3000**

---

## 🧪 测试系统

### 测试输入

在首页输入:
```
Design a 555 timer LED blinker circuit with 1 Hz frequency
```

### 预期结果

1. ✅ 设计创建成功
2. ✅ 实时进度更新（10% → 100%）
3. ✅ 原理图显示（可缩放、下载）
4. ✅ 仿真波形（电压、电流）
5. ✅ PCB 布局图
6. ✅ BOM 表格（可导出 CSV）

---

## 🛠️ 故障排查

### 问题: Python 未找到

**解决:**
```powershell
# 检查 Python 是否安装
python --version

# 如果未安装，从以下位置下载
# https://www.python.org/downloads/

# 或使用虚拟环境
~\.virtualenvs\VMware_Workstation-MvaHhlZC\Scripts\Activate.ps1
```

### 问题: Redis 未运行

**解决:**
```powershell
# 启动 Redis
redis-server

# 或者检查 Redis 是否已安装
redis-cli --version
```

### 问题: 端口被占用

**解决:**
```powershell
# 查看占用端口的进程
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# 终止进程
taskkill /PID <进程ID> /F
```

### 问题: 依赖安装失败

**解决:**
```powershell
# 清除缓存并重新安装
cd backend
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall

# 前端
cd frontend
rm -rf node_modules
npm cache clean --force
npm install
```

### 问题: 模块导入错误

**解决:**
```powershell
# 确保在正确的目录
# Backend API 必须从 backend/ 目录启动
cd backend
python -m uvicorn app.main:app --port 8000

# AI Service 必须从 ai_service/ 目录启动
cd ai_service
python -m uvicorn app.main:app --port 8001
```

---

## 📊 服务状态检查

### 检查服务是否运行

在浏览器中访问:
- Backend API: http://localhost:8000/docs
- AI Service: http://localhost:8001/docs
- EDA Service: http://localhost:8002/docs

如果看到 FastAPI 文档页面，说明服务正常运行！

### 检查数据库

```powershell
cd backend
python init_db.py
```

应该看到:
```
✓ Database initialized successfully!
✓ Tables created:
  - circuit_designs
  - design_history
```

---

## 📝 开发提示

### 查看 API 文档

- Backend: http://localhost:8000/docs
- AI: http://localhost:8001/docs
- EDA: http://localhost:8002/docs

### 查看日志

每个服务的终端窗口会显示实时日志输出。

### 停止服务

- 在各个终端窗口按 `Ctrl + C`
- 或者运行: `.\stop-all.ps1`

---

## 🎯 下一步

1. ✅ 系统已安装
2. ✅ 所有服务已启动
3. ✅ 浏览器访问 http://localhost:3000
4. 🎉 开始设计电路！

---

## 💾 文件说明

| 文件 | 说明 |
|------|------|
| `INSTALL.bat` | Windows 安装脚本（双击运行）|
| `START.bat` | Windows 启动脚本（双击运行）|
| `install-all.ps1` | PowerShell 安装脚本|
| `start-all.ps1` | PowerShell 启动脚本|
| `stop-all.ps1` | PowerShell 停止脚本|
| `QUICK_START.md` | 本文件 |

---

**需要帮助？** 查看:
- `BACKEND_SETUP.md` - 后端详细设置
- `FRONTEND_SETUP.md` - 前端详细设置
- `MVP_COMPLETE.md` - 完整项目文档
