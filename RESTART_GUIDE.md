# 🔄 CircuitGPT 服务完全重启指南

**目的**: 应用运放电路修复  
**状态**: 代码已修复，需要重启服务

---

## ✅ 已完成的修复

1. ✅ 修改了 `eda_tools/circuit_ir.py`
2. ✅ 清理了Python缓存
3. ✅ 启动了新的EDA服务（端口8003）
4. ✅ 更新了 `backend/.env` (EDA_SERVICE_URL=8003)
5. ✅ 验证端口8003工作正常

---

## ⚠️ 当前状态

- ✅ EDA服务（8003）：使用**新代码**✅
- ❌ EDA服务（8002）：使用**旧代码**❌  
- ❌ 后端服务（8000）：连接到**8002**❌
- ✅ 前端服务（3000）：正常运行

---

## 🔧 需要执行的操作

### 方案1: 完全重启所有服务 ⭐推荐

```powershell
# 1. 停止所有服务
cd G:\aiprj\cirgpt
.\STOP-ALL-SERVICES.ps1

# 2. 等待5秒确保所有进程结束
Start-Sleep -Seconds 5

# 3. 手动检查并杀死残留进程
Get-Process -Name python,node -ErrorAction SilentlyContinue | Stop-Process -Force

# 4. 重新启动所有服务
.\START-ALL-SERVICES.ps1

# 5. 等待15秒让所有服务启动
Start-Sleep -Seconds 15

# 6. 验证服务
curl http://localhost:8000  # 后端
curl http://localhost:8001  # AI
curl http://localhost:8003  # EDA (新端口)
curl http://localhost:3000  # 前端
```

### 方案2: 手动重启服务（分步）

**步骤1: 停止所有Python服务**
```powershell
Get-Process -Name python | Stop-Process -Force
Start-Sleep -Seconds 3
```

**步骤2: 启动后端（新窗口1）**
```powershell
cd G:\aiprj\cirgpt\backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**步骤3: 启动AI服务（新窗口2）**
```powershell
cd G:\aiprj\cirgpt\ai_service
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**步骤4: 启动EDA服务（新窗口3）**
```powershell
cd G:\aiprj\cirgpt\eda_tools
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8003
```
**注意**: 端口是**8003**，不是8002！

**步骤5: 启动前端（新窗口4）**
```powershell
cd G:\aiprj\cirgpt\frontend
npm run dev
```

---

## 🧪 验证修复

重启后，测试运放电路：

### 1. 访问前端
```
http://localhost:3000
```

### 2. 输入设计需求
```
Create an inverting op-amp amplifier with gain of 10
```

### 3. 检查生成的Netlist

应该包含：
- ✅ `XU1 0 SUMMING OUTPUT VCC VEE OPAMP_IDEAL`
- ✅ `R1 IN SUMMING 10k`
- ✅ `R2 OUTPUT SUMMING 100k`
- ✅ `.subckt OPAMP_IDEAL`
- ❌ **不应该包含**: `EGAIN OUT 0 IN 0`

### 4. 检查原理图

应该显示：
- ✅ 运放符号（三角形）
- ✅ 输入电阻
- ✅ 反馈电阻
- ✅ 电源连接

---

## 📋 故障排除

### 问题: 仍然显示旧电路

**原因**: 后端连接到旧的EDA服务（8002）

**解决**:
```powershell
# 1. 确认backend/.env中的配置
cat backend\.env | Select-String "EDA_SERVICE"
# 应该显示: EDA_SERVICE_URL=http://localhost:8003

# 2. 如果不对，手动修改
notepad backend\.env
# 修改为: EDA_SERVICE_URL=http://localhost:8003

# 3. 完全重启后端
Get-Process -Name python | Where-Object {
    (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*8000*"
} | Stop-Process -Force

cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 问题: 端口8003被占用

**解决**: 杀死旧进程
```powershell
Get-Process -Name python | Where-Object {
    (Get-WmiObject Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine -like "*8003*"
} | Stop-Process -Force
```

### 问题: 无法连接EDA服务

**检查**:
```powershell
curl http://localhost:8003/
# 应该返回: {"message":"EDA Circuit Design Tools","version":"1.0.0"}
```

---

## 📊 服务端口总结

| 服务 | 旧端口 | 新端口 | 状态 |
|------|--------|--------|------|
| 前端 | 3000 | 3000 | 不变 |
| 后端 | 8000 | 8000 | 不变 |
| AI服务 | 8001 | 8001 | 不变 |
| EDA服务 | 8002 | **8003** | ✅ **已更改** |

---

## ✅ 检查清单

重启后检查：

- [ ] 后端服务运行在8000
- [ ] AI服务运行在8001
- [ ] EDA服务运行在**8003**（不是8002）
- [ ] 前端服务运行在3000
- [ ] backend/.env 配置 EDA_SERVICE_URL=http://localhost:8003
- [ ] 创建新的运放设计
- [ ] Netlist包含XU1和.subckt
- [ ] 原理图显示完整

---

## 🎯 立即执行

```powershell
# 复制粘贴这些命令：

cd G:\aiprj\cirgpt
.\STOP-ALL-SERVICES.ps1
Start-Sleep -Seconds 5
Get-Process -Name python,node -ErrorAction SilentlyContinue | Stop-Process -Force
.\START-ALL-SERVICES.ps1
```

然后等待15秒，访问 http://localhost:3000 测试！

---

**重要提示**: 必须使用端口**8003**，因为只有这个端口的EDA服务有修复后的代码！

---

*重启指南: RESTART-001*  
*创建时间: 2026-06-10*
