# CircuitGPT Windows 批处理脚本完整清单

## ✅ 已创建的脚本

### 🎯 主要脚本

| 文件 | 功能 | 使用方式 |
|------|------|----------|
| **menu.bat** ⭐ | 交互式主菜单 | 双击运行 |
| **start-all.bat** | 启动全部服务 | 双击运行 |
| **stop-all.bat** | 停止全部服务 | 双击运行 |
| **status.bat** | 查看服务状态 | 双击运行 |

### 📦 前端脚本

| 文件 | 功能 |
|------|------|
| **start-frontend.bat** | 启动前端服务 |
| **stop-frontend.bat** | 停止前端服务 |

### 🔧 后端脚本

| 文件 | 功能 |
|------|------|
| **start-backend.bat** | 启动后端服务 |
| **stop-backend.bat** | 停止后端服务 |

### 🛠️ 工具脚本

| 文件 | 功能 |
|------|------|
| **create-shortcut.bat** | 创建桌面快捷方式 |
| **install.sh** | Linux/Mac安装脚本 |
| **start.sh** | Linux/Mac启动脚本 |

### 📄 文档

| 文件 | 说明 |
|------|------|
| **README.md** | 脚本使用指南 |

---

## 🚀 快速开始（3步）

### 第1步: 创建桌面快捷方式（可选）

```
双击 create-shortcut.bat
```

### 第2步: 启动服务

**方法A: 使用主菜单（推荐）**
```
双击桌面的 "CircuitGPT" 快捷方式
或
双击 scripts/menu.bat
→ 选择 [1] 启动全部服务
```

**方法B: 直接启动**
```
双击 scripts/start-all.bat
```

### 第3步: 访问应用

浏览器打开：http://localhost:3000

---

## 📋 脚本功能对照表

### 服务管理

| 需求 | 脚本 | 说明 |
|------|------|------|
| 启动全部 | start-all.bat | 后端 + 前端 |
| 启动前端 | start-frontend.bat | 仅前端 |
| 启动后端 | start-backend.bat | 仅后端 |
| 停止全部 | stop-all.bat | 关闭所有服务 |
| 停止前端 | stop-frontend.bat | 仅关闭前端 |
| 停止后端 | stop-backend.bat | 仅关闭后端 |
| 查看状态 | status.bat | 检查运行状态 |

### 辅助功能

| 需求 | 脚本 |
|------|------|
| 主菜单 | menu.bat |
| 创建快捷方式 | create-shortcut.bat |
| 查看文档 | README.md |

---

## 🎓 使用场景

### 场景1: 日常开发

```bash
# 早上开始工作
双击 menu.bat → [1] 启动全部

# 开发中（自动热重载，无需重启）
编辑代码 → 保存 → 浏览器自动刷新

# 下班
双击 menu.bat → [4] 停止全部
```

### 场景2: 前端开发（不需要后端）

```bash
双击 start-frontend.bat
# 如果后端API不可用，会看到友好的错误提示
```

### 场景3: 后端开发（不需要前端）

```bash
双击 start-backend.bat
# 访问 http://localhost:8000/docs 查看API文档
```

### 场景4: 调试问题

```bash
1. 双击 status.bat           # 查看当前状态
2. 双击 stop-all.bat          # 停止所有服务
3. 等待3秒
4. 双击 start-all.bat         # 重新启动
5. 查看启动窗口���日志输出
```

---

## 🔥 核心特性

### ✅ 自动化

- ✅ 自动检查依赖
- ✅ 自动激活虚拟环境
- ✅ 自动创建必要目录
- ✅ 自动记录进程ID
- ✅ 自动清理PID文件

### ✅ 智能化

- ✅ 智能判断服务状态
- ✅ 智能查找进程
- ✅ 智能错误提示
- ✅ 智能端口检查

### ✅ 用户友好

- ✅ 中文界面
- ✅ 彩色输出
- ✅ 详细日志
- ✅ 友好错误提示
- ✅ 交互式菜单

---

## 🛡️ 安全特性

### 进程管理

- ✅ PID文件追踪
- ✅ 确认提示（防止误操作）
- ✅ 仅停止相关进程
- ✅ 清理僵尸进程

### 配置检查

- ✅ 检查 .env 文件
- ✅ 检查 node_modules
- ✅ 检查虚拟环境
- ✅ 提供修复建议

---

## 📊 文件结构

```
scripts/
├── 📋 主菜单
│   └── menu.bat                    # 交互式控制面板
│
├── 🚀 启动脚本
│   ├── start-all.bat              # 启动全部
│   ├── start-frontend.bat         # 启动前端
│   └── start-backend.bat          # 启动后端
│
├── 🛑 停止脚本
│   ├── stop-all.bat               # 停止全部
│   ├── stop-frontend.bat          # 停止前端
│   └── stop-backend.bat           # 停止后端
│
├── 📊 状态脚本
│   └── status.bat                 # 查看状态
│
├── 🛠️ 工具脚本
│   ├── create-shortcut.bat        # 创建快捷方式
│   ├── install.sh                 # Linux安装
│   └── start.sh                   # Linux启动
│
├── 📁 运行时文件
│   └── .pids/                     # PID文件目录
│       ├── frontend.pid           # 前端进程ID
│       └── backend.pid            # 后端进程ID
│
└── 📚 文档
    ├── README.md                  # 使用指南
    └── SCRIPTS_INDEX.md           # 本文件
```

---

## 🎨 自定义配置

### 修改端口

**前端端口** (默认 3000):
```
编辑 frontend/.env.local
PORT=3001
```

**后端端口** (默认 8000):
```
编辑 start-backend.bat
修改: --port 8000 → --port 8001
```

### 修改启动行为

**静默启动** (不显示窗口):
```batch
REM 在启动脚本中
start "Title" /MIN /B command
```

**自动打开浏览器**:
```batch
REM 在 start-all.bat 末尾添加
start http://localhost:3000
```

---

## 💡 高级用法

### 1. 开机自动启动

创建任务计划:
```
任务计划程序 → 创建基本任务
触发器: 启动时
操作: start-all.bat
```

### 2. 定时重启服务

创建任务计划:
```
触发器: 每天凌晨3点
操作: 
  1. stop-all.bat
  2. 等待10秒
  3. start-all.bat
```

### 3. 批量操作

创建自定义脚本:
```batch
@echo off
call stop-all.bat
cd frontend && npm install
cd ../backend && pip install -r requirements.txt
call start-all.bat
```

---

## 🔍 故障排查

### 脚本无法执行

**原因**: 执行策略限制

**解决**:
```powershell
# PowerShell (管理员)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 中文乱码

**原因**: 控制台编码问题

**解决**: 脚本开头已包含 `chcp 65001`，如仍乱码：
```
控制面板 → 区域 → 管理 → 更改系统区域设置
勾选 "Beta: 使用UTF-8"
```

### 找不到命令

**原因**: PATH 环境变量未配置

**解决**:
```
1. 右键"此电脑" → 属性 → 高级系统设置
2. 环境变量 → Path → 编辑
3. 添加 Python 和 Node.js 路径
4. 重启命令行
```

---

## 📈 性能优化

### 启动速度优化

1. **使用SSD**: 将项目放在SSD上
2. **关闭杀毒**: 排除项目目录
3. **预编译**: 首次 `npm run build`

### 运行性能优化

1. **增加内存**: Node.js 使用 `NODE_OPTIONS=--max-old-space-size=4096`
2. **减少热重载**: 生产环境使用 `npm run start`

---

## 🎉 总结

### ✅ 功能完整

- 7个核心脚本
- 3个辅助工具
- 完整文档

### ✅ 易于使用

- 双击运行
- 交互式菜单
- 详细提示

### ✅ 功能强大

- 自动化管理
- 智能检测
- 安全可靠

---

**脚本版本**: v1.0  
**创建日期**: 2026-06-10  
**维护状态**: ✅ 活跃维护

**推荐使用**: `menu.bat` 🌟
