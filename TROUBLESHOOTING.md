# 🔍 系统诊断与修复指南

## 当前问题

你在访问 `/design/5` 时看到 "All connection attempts failed" 错误。

### 原因分析

1. **设计ID不存在**: ID为5的设计在数据库中不存在（这是正常的）
2. **Socket.IO连接问题**: 页面尝试建立WebSocket连接但失败

---

## ✅ 快速解决方案

### 方案1: 从首页创建新设计（推荐）⭐

1. **访问首页**: http://localhost:3000

2. **点击"示例 1"按钮**

3. **点击"生成设计"**

4. **系统会自动创建新的设计ID并跳转**

### 方案2: 直接访问首页

在浏览器地址栏输入并回车：
```
http://localhost:3000
```

---

## 🧪 验证系统状态

### 测试1: 后端API
在新标签页打开：
- http://localhost:8000

应该看到：
```json
{
  "message": "Circuit Design API Gateway",
  "version": "1.0.0",
  "websocket": "Socket.io available at /socket.io"
}
```

### 测试2: API文档
在新标签页打开：
- http://localhost:8000/docs

应该看到Swagger UI界面

### 测试3: 前端首页
在新标签页打开：
- http://localhost:3000

应该看到CircuitGPT主页面

---

## 🔧 如果仍然有问题

### 重启服务

```powershell
# 停止所有服务
.\STOP.ps1

# 等待3秒
Start-Sleep -Seconds 3

# 重新启动
.\START.ps1
```

### 清理缓存

```powershell
# 停止服务
.\STOP.ps1

# 清理前端构建
cd frontend
Remove-Item -Recurse -Force .next

# 重新启动
cd ..
.\START.ps1
```

---

## 📋 正确的使用流程

### 步骤1: 访问首页
```
http://localhost:3000
```

### 步骤2: 创建设计
- 选择示例或输入自己的需求
- 点击"生成设计"

### 步骤3: 自动跳转
- 系统会创建新设计（如ID=1）
- 自动跳转到 `/design/1`

### 步骤4: 查看结果
- 等待生成完成
- 查看原理图、仿真等

---

## ⚠️ 注意事项

### 不要直接访问 /design/{id}

❌ **错误**: 直接在地址栏输入 `/design/5`  
✅ **正确**: 从首页创建设计，让系统自动跳转

### 设计ID说明

- 设计ID由后端自动生成
- 第一个设计的ID通常是1
- 每创建一个新设计，ID递增
- 访问不存在的ID会显示404错误

---

## 🎯 立即操作

### 选项A: 在当前标签页
点击页面上的 **"返回首页"** 按钮

### 选项B: 新标签页
按 `Ctrl+T` 打开新标签，访问：
```
http://localhost:3000
```

### 选项C: 刷新地址栏
选中地址栏，删除 `/design/5`，只保留：
```
http://localhost:3000
```
然后按回车

---

## ✅ 系统健康检查

运行以下命令验证所有服务：

```powershell
# 检查前端
curl http://localhost:3000

# 检查后端
curl http://localhost:8000

# 检查端口
Get-NetTCPConnection -LocalPort 3000,8000
```

如果都返回正常，说明系统运行良好，只是访问了错误的URL。

---

## 📚 相关文档

- [ALL_SYSTEMS_GO.md](ALL_SYSTEMS_GO.md) - 完整系统状态
- [READY_TO_USE.md](READY_TO_USE.md) - 使用指南
- [QUICKSTART.md](QUICKSTART.md) - 快速参考

---

**现在请访问首页开始正确的使用流程！** 🚀

http://localhost:3000
