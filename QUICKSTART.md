# CircuitGPT 快速参考

## 🚀 立即启动

### Windows (PowerShell/CMD)
```cmd
# 前端
scripts\run-frontend.bat

# 或交互式启动
bash scripts/start.sh
```

### Linux/Mac
```bash
# 前端
./scripts/run-frontend.sh

# 或交互式启动
./scripts/start.sh
```

---

## 📍 访问地址

- **前端**: http://localhost:3000
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

---

## ✅ 安装状态

### 前端 ✓
- Next.js: **15.5.19**
- React: **19.2.7**
- 依赖包: 111个

### 后端 ✓
- SECRET_KEY: **已配置**（32字符）
- DEBUG: **true**（开发模式）
- 数据库: **SQLite**

---

## ⌨️ 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+Enter` | 提交设计请求 |
| `Ctrl+S` | 下载当前视图 |
| `ESC` | 关闭对话框 |

---

## 📚 文档

- [INSTALLATION_COMPLETE.md](INSTALLATION_COMPLETE.md) - 完整安装报告
- [discuss/改进总结.md](discuss/改进总结.md) - 改进概述
- [discuss/升级迁移指南.md](discuss/升级迁移指南.md) - 部署指南

---

## 🔧 常用命令

```bash
# 前端
cd frontend
npm run dev      # 开发模式
npm run build    # 构建生产版本
npm run start    # 运行生产版本

# 后端
cd backend
uvicorn app.main:app --reload  # 开发模式（带热重载）
uvicorn app.main:app           # 生产模式

# 检查
node --version   # 检查Node.js版本
python --version # 检查Python版本
```

---

## 🐛 快速故障排除

### 前端无法启动
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### 后端配置错误
```bash
cd backend
python -c "import secrets; print(secrets.token_urlsafe(32))"
# 将生成的密钥填入 .env 的 SECRET_KEY
```

### 端口被占用
```bash
# 使用其他端口
PORT=3001 npm run dev  # 前端
# 或修改 .env.local 中的端口配置
```

---

## 📞 获取帮助

1. 查看 [INSTALLATION_COMPLETE.md](INSTALLATION_COMPLETE.md)
2. 检查浏览器控制台（F12）
3. 查看服务器日志输出

---

**安装完成时间**: 2026-06-10  
**版本**: v1.0 with Usability Improvements  
**状态**: ✅ 就绪
