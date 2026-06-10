# 🚀 CircuitGPT 启动指南 (Windows PowerShell)

## ⚠️ 重要提示

如果你在 PowerShell 中遇到编码问题，请使用 PowerShell 脚本（.ps1）而不是批处理文件（.bat）。

---

## 🎯 推荐方式：使用 PowerShell 脚本

### 1. 启动服务

```powershell
# 在 PowerShell 中
cd G:\aiprj\cirgpt\scripts
.\start-all.ps1
```

### 2. 查看状态

```powershell
.\status.ps1
```

### 3. 停止服务

```powershell
.\stop-all.ps1
```

---

## 🔧 如果遇到执行策略错误

PowerShell 可能会报错：
```
无法加载文件 xxx.ps1，因为在此系统上禁止运行脚本
```

**解决方法：**

```powershell
# 以管理员身份打开 PowerShell，运行：
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 或者临时绕过：
powershell -ExecutionPolicy Bypass -File .\start-all.ps1
```

---

## 🎨 替代方式1：使用 CMD (命令提示符)

批处理文件在 CMD 中工作正常：

```cmd
# 打开 CMD (不是 PowerShell)
cd G:\aiprj\cirgpt\scripts
start-all.bat
```

---

## 🎨 替代方式2：手动启动

### 启动前端
```powershell
cd G:\aiprj\cirgpt\frontend
npm run dev
```

### 启动后端（新窗口）
```powershell
cd G:\aiprj\cirgpt\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📝 脚本对照表

| 功能 | PowerShell | CMD批处理 |
|------|-----------|-----------|
| 启动全部 | `.\start-all.ps1` | `start-all.bat` |
| 停止全部 | `.\stop-all.ps1` | `stop-all.bat` |
| 查看状态 | `.\status.ps1` | `status.bat` |

---

## 🎯 快速测试

在 PowerShell 中运行：

```powershell
# 1. 进入脚本目录
cd G:\aiprj\cirgpt\scripts

# 2. 启动服务
.\start-all.ps1

# 3. 等待10秒后检查状态
Start-Sleep -Seconds 10
.\status.ps1

# 4. 打开浏览器
Start-Process "http://localhost:3000"
```

---

## 🐛 问题排查

### 问题1：批处理文件显示乱码

**原因**：PowerShell 对批处理文件的编码支持有问题

**解决**：使用 PowerShell 脚本（.ps1）或在 CMD 中运行 .bat 文件

### 问题2：无法执行 .ps1 文件

**解决**：
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 问题3：找不到 npm/python 命令

**解决**：确认已安装并添加到 PATH 环境变量

---

## ✅ 验证安装

```powershell
# 检查 Node.js
node --version

# 检查 Python
python --version

# 检查前端依赖
Test-Path G:\aiprj\cirgpt\frontend\node_modules

# 检查后端配置
Test-Path G:\aiprj\cirgpt\backend\.env
```

---

## 🎉 一切就绪！

现在你可以：

1. **使用 PowerShell 脚本**（推荐）
   ```powershell
   .\start-all.ps1
   ```

2. **或使用 CMD 批处理**
   ```cmd
   start-all.bat
   ```

3. **或手动启动**
   ```powershell
   # 前端
   cd frontend && npm run dev
   
   # 后端（新窗口）
   cd backend && python -m uvicorn app.main:app --reload
   ```

访问：**http://localhost:3000**

---

**提示**：推荐使用 PowerShell 脚本，它们有彩色输出和更好的错误处理！🌈
