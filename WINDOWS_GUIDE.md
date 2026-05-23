# 🚀 Windows 快速启动指南（你的系统配置）

## 📍 你的系统路径
- **Python:** `python`
- **Node.js:** `C:\Program Files\nodejs\node.exe`

---

## ⚡ 最简单的方式（推荐）

### **第 1 步：安装所有依赖**
```powershell
.\INSTALL-FULL.bat
```

这个脚本会：
- ✅ 使用你的 Python 路径安装所有依赖
- ✅ 使用你的 Node.js 路径安装前端依赖
- ✅ 验证所有安装
- ✅ 创建必要的目录

**等待时间：** 约 5-10 分钟（首次安装）

### **第 2 步：启动 Redis**
打开**新的 PowerShell 窗口**，运行：
```powershell
redis-server
```

**⚠️ 如果 Redis 未安装：**
```powershell
# 使用 winget 安装
winget install Redis.Redis

# 然后启动
redis-server
```

**保持这个窗口运行！** 不要关闭它。

### **第 3 步：启动所有服务**
回到**原来的 PowerShell 窗口**，运行：
```powershell
.\START-FULL.bat
```

**会自动打开 5 个新窗口：**
1. Backend API (端口 8000)
2. AI Service (端口 8001)
3. EDA Service (端口 8002)
4. Celery Worker
5. Frontend (端口 3000)

### **第 4 步：访问应用**
打开浏览器，访问：
```
http://localhost:3000
```

**🎉 完成！**

---

## 🛑 停止服务

### **方法 1：使用停止脚本**
```powershell
.\STOP.bat
```

### **方法 2：手动停止**
直接关闭所有打开的命令窗口即可

**注意：** Redis 窗口保持运行，下次启动时不需要重新启动 Redis

---

## 🔄 下次使用（日常开发）

Redis 第一次启动后可以一直运行，之后只需：

```powershell
# 启动所有服务
.\START-FULL.bat
```

就这么简单！

---

## 📊 服务端口说明

| 服务 | 端口 | URL |
|------|------|-----|
| Frontend | 3000 | http://localhost:3000 |
| Backend API | 8000 | http://localhost:8000/docs |
| AI Service | 8001 | http://localhost:8001/docs |
| EDA Service | 8002 | http://localhost:8002/docs |
| Redis | 6379 | - |

---

## 🧪 快速测试

1. **打开** http://localhost:3000
2. **点击** "Start Designing Now"
3. **输入** "Design a 555 timer LED blinker circuit"
4. **点击** "Generate Circuit"
5. **观察** 实时进度更新（10% → 100%）
6. **探索** 4 个标签页的结果

---

## ⚠️ 常见问题

### **问题 1：Redis 未运行**
**现象：** 服务启动失败，显示连接 Redis 错误

**解决：**
```powershell
# 新窗口启动 Redis
redis-server
```

### **问题 2：端口被占用**
**现象：** 服务无法启动，提示端口已被使用

**解决：**
```powershell
# 查看占用端口的进程
netstat -ano | findstr :8000
netstat -ano | findstr :3000

# 终止进程
taskkill /PID <进程ID> /F
```

### **问题 3：依赖安装失败**
**现象：** 安装过程中出现错误

**解决：**
```powershell
# 清除缓存，重新安装
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --force-reinstall
```

### **问题 4：Python 路径错误**
**现象：** 提示找不到 Python

**解决：**
确认 `python` 存在，如果路径不同，编辑 `INSTALL-FULL.bat` 和 `START-FULL.bat`，修改 `PYTHON_EXE` 变量

---

## 📝 可用的脚本文件

| 脚本 | 说明 |
|------|------|
| `INSTALL-FULL.bat` | 安装所有依赖（推荐） |
| `START-FULL.bat` | 启动所有服务（推荐） |
| `STOP.bat` | 停止所有服务 |
| `INSTALL-CUSTOM.bat` | 备用安装脚本 |
| `START-CUSTOM.bat` | 备用启动脚本 |

---

## 💡 开发技巧

### **查看日志**
每个服务的窗口都会显示实时日志输出

### **重启单个服务**
如果某个服务出问题，只需关闭对应的窗口，然后在该目录手动重启：
```powershell
# 例如重启 Backend API
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### **查看 API 文档**
- Backend: http://localhost:8000/docs
- AI: http://localhost:8001/docs
- EDA: http://localhost:8002/docs

---

## 🎯 完整工作流程示例

```powershell
# PowerShell 窗口 1（主窗口）
cd <project-root>
.\INSTALL-FULL.bat          # 首次安装，只需运行一次

# PowerShell 窗口 2（Redis）
redis-server                # 保持运行

# PowerShell 窗口 1（主窗口）
.\START-FULL.bat            # 启动所有服务

# 浏览器
访问 http://localhost:3000  # 使用应用

# 完成后
.\STOP.bat                  # 停止服务
```

---

## 📚 相关文档

- `QUICK_START.md` - 通用快速开始指南
- `BACKEND_SETUP.md` - 后端详细设置
- `FRONTEND_SETUP.md` - 前端详细设置
- `MVP_COMPLETE.md` - 项目完成报告

---

**祝你使用愉快！🎉**

有问题随时查看本文档或运行 `.\INSTALL-FULL.bat` 重新安装。
