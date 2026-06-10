# 🚀 CircuitGPT 超简单启动指南

## ✨ 最简单的方法（推荐）

在项目根目录有两个文件：

### 启动服务
```
右键点击: START.ps1
选择: "使用 PowerShell 运行"
```

### 停止服务
```
右键点击: STOP.ps1
选择: "使用 PowerShell 运行"
```

---

## 🎯 或者用命令行

### 启动
```powershell
cd G:\aiprj\cirgpt
.\START.ps1
```

### 停止
```powershell
cd G:\aiprj\cirgpt
.\STOP.ps1
```

---

## 📋 完整脚本列表

### 项目根目录（最简单）
- `START.ps1` - 启动全部 ⭐⭐⭐
- `STOP.ps1` - 停止全部 ⭐⭐⭐

### scripts 目录（更多功能）
- `quick-start.ps1` - 快速启动
- `start-all.ps1` - 启动全部
- `stop-all.ps1` - 停止全部
- `status.ps1` - 查看状态

---

## 🔧 如果遇到"无法运行脚本"错误

打开 PowerShell（管理员），运行：

```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

或者，右键文件 → 属性 → 解除锁定

---

## ✅ 验证安装

```powershell
# 检查依赖
Test-Path frontend\node_modules  # 应该返回 True
Test-Path backend\.env           # 应该返回 True

# 检查端口
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

---

## 🎉 就这么简单！

1. 双击或右键运行 `START.ps1`
2. 等待10秒
3. 浏览器自动打开 http://localhost:3000
4. 开始使用！

完成后运行 `STOP.ps1` 停止服务。

---

**推荐**: 创建 START.ps1 的桌面快捷方式，以后一键启动！
