# CircuitGPT 批处理脚本使用指南

## 📁 脚本列表

### 主控制脚本

| 文件 | 功能 | 说明 |
|------|------|------|
| **menu.bat** | 主菜单 | 交互式控制面板，推荐使用 ⭐ |
| **start-all.bat** | 启动全部 | 同时启动前端和后端 |
| **stop-all.bat** | 停止全部 | 同时停止前端和后端 |
| **status.bat** | 查看状态 | 检查服务运行状态 |

### 前端脚本

| 文件 | 功能 |
|------|------|
| **start-frontend.bat** | 启动前端服务 (http://localhost:3000) |
| **stop-frontend.bat** | 停止前端服务 |

### 后端脚本

| 文件 | 功能 |
|------|------|
| **start-backend.bat** | 启动后端服务 (http://localhost:8000) |
| **stop-backend.bat** | 停止后端服务 |

---

## 🚀 快速开始

### 方法1: 使用主菜单（推荐）⭐

双击 `menu.bat` 打开控制面板：

```
========================================
      CircuitGPT 控制面板
========================================

 [1] 启动全部服务
 [2] 启动前端服务
 [3] 启动后端服务

 [4] 停止全部服务
 [5] 停止前端服务
 [6] 停止后端服务

 [7] 查看服务状态
 [8] 查看安装报告
 [9] 打开浏览器

 [0] 退出
```

### 方法2: 直接启动

1. **启动全部服务**
   - 双击 `start-all.bat`
   - 等待5-10秒
   - 浏览器访问 http://localhost:3000

2. **只启动前端**
   - 双击 `start-frontend.bat`

3. **只启动后端**
   - 双击 `start-backend.bat`

---

## 📝 使用说明

### 启动服务

1. **首次使用**
   ```
   双击 menu.bat
   → 选择 [1] 启动全部服务
   → 等待服务启动
   ```

2. **服务将在后台运行**
   - 可以关闭启动窗口
   - 服务继续运行
   - 使用 `status.bat` 查看状态

### 停止服务

1. **正常停止**
   ```
   双击 menu.bat
   → 选择 [4] 停止全部服务
   ```

2. **单独停止**
   - 前端: 双击 `stop-frontend.bat`
   - 后端: 双击 `stop-backend.bat`

3. **强制停止**
   - 如果正常停止失败
   - 打开任务管理器 (Ctrl+Shift+Esc)
   - 结束 `node.exe` 和 `python.exe` 进程

### 查看状态

```
双击 status.bat
```

输出示例：
```
[前端服务]
  状态: [运行中]
  进程ID: 12345
  地址: http://localhost:3000

[后端服务]
  状态: [运行中]
  进程ID: 67890
  地址: http://localhost:8000
```

---

## 🔧 脚本功能详解

### start-all.bat

- ✅ 自动启动后端和前端
- ✅ 检查服务是否启动成功
- ✅ 显示访问地址
- ✅ 自动打开日志窗口

**使用场景**: 开发时一键启动全部服务

### stop-all.bat

- ✅ 停止所有CircuitGPT相关进程
- ✅ 清理PID文件
- ✅ 显示停止状态

**使用场景**: 下班/关机前停止服务

### status.bat

- ✅ 检查服务运行状态
- ✅ 显示进程ID
- ✅ 检查端口占用
- ✅ 显示访问地址

**使用场景**: 调试时检查服务状态

---

## 🐛 常见问题

### 问题1: 启动失败 - 端口被占用

**错误信息**: `Port 3000/8000 is already in use`

**解决方法**:
```
1. 运行 status.bat 查看占用情况
2. 运行 stop-all.bat 停止旧进程
3. 或在任务管理器中手动结束 node.exe/python.exe
4. 重新启动
```

### 问题2: 前端无法连接后端

**检查步骤**:
```
1. 运行 status.bat 确认后端已启动
2. 浏览器访问 http://localhost:8000
3. 检查 backend/.env 中的配置
4. 查看后端日志窗口的错误信息
```

### 问题3: 停止脚本无效

**解决方法**:
```
方法1: 使用任务管理器
  Ctrl+Shift+Esc → 结束 node.exe 和 python.exe

方法2: 使用命令行
  taskkill /F /IM node.exe
  taskkill /F /IM python.exe
```

### 问题4: 找不到Python/Node

**错误信息**: `'python' 不是内部或外部命令`

**解决方法**:
```
1. 确认已安装 Python 和 Node.js
2. 将其添加到系统 PATH
3. 重启命令行窗口
```

---

## 📂 文件结构

```
scripts/
├── menu.bat              # 主菜单 ⭐
├── start-all.bat         # 启动���部
├── stop-all.bat          # 停止全部
├── status.bat            # 查看状态
├── start-frontend.bat    # 启动前端
├── stop-frontend.bat     # 停止前端
├── start-backend.bat     # 启动后端
├── stop-backend.bat      # 停止后端
└── .pids/                # PID文件目录（自动创建）
    ├── frontend.pid      # 前端进程ID
    └── backend.pid       # 后端进程ID
```

---

## 🎯 推荐工作流程

### 日常开发

1. **开始工作**
   ```
   双击 menu.bat → [1] 启动全部服务
   等待启动完成
   浏览器访问 http://localhost:3000
   ```

2. **开发过程**
   - 前端自动热重载（保存即生效）
   - 后端自动热重载（修改代码即生效）
   - 无需重启服务

3. **结束工作**
   ```
   双击 menu.bat → [4] 停止全部服务
   或直接关闭电脑（服务会自动停止）
   ```

### 调试问题

1. **检查状态**
   ```
   双击 status.bat
   ```

2. **重启服务**
   ```
   menu.bat → [4] 停止全部
   等待3秒
   menu.bat → [1] 启动全部
   ```

3. **查看日志**
   - 启动窗口会保持打开
   - 显示实时日志
   - 关闭窗口不影响服务运行

---

## 💡 高级技巧

### 1. 创建桌面快捷方式

右键 `menu.bat` → 创建快捷方式 → 拖到桌面

### 2. 自定义端口

编辑 `frontend/.env.local`:
```env
PORT=3001
```

编辑启动脚本，修改 `--port` 参数

### 3. 后台静默启动

修改 `start-all.bat`，将 `start ""` 改为 `start "" /MIN`

### 4. 启动时自动打开浏览器

在 `start-all.bat` 末尾添加:
```batch
start http://localhost:3000
```

---

## 📞 获取帮助

1. **查看日志**: 启动窗口会显示实时日志
2. **检查配置**: `backend/.env` 和 `frontend/.env.local`
3. **查看文档**: `INSTALLATION_COMPLETE.md`
4. **运行诊断**: `status.bat`

---

**最后更新**: 2026-06-10  
**脚本版本**: v1.0  
**状态**: ✅ 就绪
