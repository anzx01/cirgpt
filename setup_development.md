# 开发环境搭建脚本要点

## 1. 系统要求

### 硬件要求
- CPU: 4核以上
- 内存: 8GB以上
- 磁盘空间: 50GB以上

### 软件要求
- Docker: 20.10.0+（用于容器化部署）
- Docker Compose: 1.29.0+（用于管理多个容器）
- Node.js: 18.0.0+（用于前端开发）
- Python: 3.9.0+（用于后端和AI服务开发）
- Git: 2.30.0+（用于版本控制）

## 2. 环境搭建步骤

### 2.1 克隆项目代码
```bash
git clone <项目仓库地址>
cd cirgpt
```

### 2.2 安装依赖

#### 2.2.1 前端依赖安装
```bash
cd frontend
npm install
cd ..
```

#### 2.2.2 后端依赖安装
```bash
cd backend
pip install -r requirements.txt
cd ..
```

#### 2.2.3 AI服务依赖安装
```bash
cd ai_service
pip install -r requirements.txt
cd ..
```

#### 2.2.4 EDA工具服务依赖安装
```bash
cd eda_tools
pip install -r requirements.txt
cd ..
```

### 2.3 配置环境变量

#### 2.3.1 复制环境变量模板
```bash
# 前端
cp frontend/.env.local.example frontend/.env.local

# 后端
cp backend/.env.example backend/.env

# AI服务
cp ai_service/.env.example ai_service/.env

# EDA工具服务
cp eda_tools/.env.example eda_tools/.env
```

#### 2.3.2 修改环境变量配置
根据实际情况修改各个服务的环境变量配置文件，特别是以下关键配置：
- `SECRET_KEY`：用于JWT认证的密钥
- `DB_URL`：数据库连接URL
- `REDIS_URL`：Redis连接URL
- 各个服务的地址配置

### 2.4 初始化数据库
```bash
cd backend
python -m app.database.init_db
cd ..
```

### 2.5 下载AI模型（可选）
```bash
cd ai_service
python -m scripts.download_model
cd ..
```

## 3. 启动服务

### 3.1 使用Docker Compose启动所有服务（推荐）
```bash
docker-compose up -d
```

### 3.2 手动启动各个服务

#### 3.2.1 启动Redis服务
```bash
redis-server
```

#### 3.2.2 启动后端API服务
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

#### 3.2.3 启动AI服务
```bash
cd ai_service
uvicorn app.main:app --reload --port 8001
```

#### 3.2.4 启动EDA工具服务
```bash
cd eda_tools
uvicorn app.main:app --reload --port 8002
```

#### 3.2.5 启动Celery Worker
```bash
cd backend
celery -A app.celery_config worker --loglevel=info
```

#### 3.2.6 启动Celery Beat
```bash
cd backend
celery -A app.celery_config beat --loglevel=info
```

#### 3.2.7 启动前端服务
```bash
cd frontend
npm run dev
```

## 4. 测试服务

### 4.1 检查服务状态
```bash
# 检查Docker服务状态
docker-compose ps

# 检查API服务是否正常运行
curl http://localhost:8000/api/health

# 检查前端服务是否正常运行
curl http://localhost:3000
```

### 4.2 运行测试

#### 4.2.1 前端测试
```bash
cd frontend
npm test
```

#### 4.2.2 后端测试
```bash
cd backend
pytest -v
```

#### 4.2.3 AI服务测试
```bash
cd ai_service
pytest -v
```

#### 4.2.4 EDA工具服务测试
```bash
cd eda_tools
pytest -v
```

## 5. 开发工具配置

### 5.1 VS Code配置
推荐安装以下扩展：
- Python（用于Python开发）
- JavaScript and TypeScript（用于前端开发）
- Docker（用于Docker容器管理）
- REST Client（用于API测试）
- ESLint（用于代码检查）
- Prettier（用于代码格式化）

### 5.2 代码风格规范
- 前端：使用ESLint和Prettier进行代码检查和格式化
- 后端：使用Flake8和Black进行代码检查和格式化

## 6. 常见问题和解决方案

### 6.1 端口被占用
**问题**：启动服务时提示端口被占用
**解决方案**：
1. 查看占用端口的进程
```bash
# Windows
netstat -ano | findstr :<端口号>

# Linux/Mac
lsof -i :<端口号>
```
2. 结束占用端口的进程
```bash
# Windows
taskkill /PID <进程ID> /F

# Linux/Mac
kill -9 <进程ID>
```
3. 或修改服务配置文件中的端口号

### 6.2 依赖安装失败
**问题**：安装依赖时提示错误
**解决方案**：
1. 确保使用了正确的Python版本
2. 升级pip到最新版本
```bash
pip install --upgrade pip
```
3. 检查网络连接是否正常
4. 尝试使用国内镜像源（针对Python依赖）
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 6.3 数据库连接失败
**问题**：启动服务时提示数据库连接失败
**解决方案**：
1. 检查数据库服务是否正常运行
2. 检查数据库连接URL是否正确
3. 确保数据库用户有足够的权限
4. 检查数据库是否已经创建

## 7. 开发流程

### 7.1 代码提交流程
1. 创建特性分支
```bash
git checkout -b feature/<特性名称>
```
2. 编写代码
3. 运行测试
4. 提交代码
```bash
git add .
git commit -m "<提交信息>"
git push origin feature/<特性名称>
```
5. 创建Pull Request

### 7.2 代码审查流程
1. 团队成员进行代码审查
2. 解决审查中提出的问题
3. 合并代码到主分支

### 7.3 部署流程
1. 合并代码到主分支
2. 运行CI/CD流水线
3. 自动构建和部署到测试环境
4. 手动部署到生产环境（可选）

## 8. 监控和日志

### 8.1 查看容器日志
```bash
docker-compose logs -f <服务名称>
```

### 8.2 查看应用日志
日志文件存储在`logs`目录下：
- 前端日志：`logs/frontend.log`
- 后端日志：`logs/api.log`
- AI服务日志：`logs/ai_service.log`
- EDA工具服务日志：`logs/eda_service.log`

### 8.3 性能监控
- 使用Docker stats查看容器资源使用情况
```bash
docker stats
```
- 使用Prometheus和Grafana进行更详细的性能监控（可选）

## 9. 安全注意事项

### 9.1 环境变量安全
- 不要将敏感信息（如密钥、密码等）硬编码到代码中
- 使用环境变量或配置文件存储敏感信息
- 不要将包含敏感信息的配置文件提交到版本控制系统

### 9.2 依赖安全
- 定期更新依赖到最新版本
- 使用安全扫描工具检查依赖的安全漏洞
```bash
# Python依赖安全检查
pip-audit

# 前端依赖安全检查
npm audit
```

### 9.3 网络安全
- 配置适当的CORS策略
- 使用HTTPS协议（在生产环境中）
- 实现适当的认证和授权机制
- 对用户输入进行验证和过滤

## 10. 附录

### 10.1 项目结构
```
cirgpt/
├── frontend/          # 前端服务（Next.js）
├── backend/           # 后端API网关服务（FastAPI）
├── ai_service/        # AI电路设计服务（Python）
├── eda_tools/         # EDA工具服务（Python）
├── storage/           # 存储目录
├── logs/              # 日志目录
├── docker-compose.yml # Docker Compose配置文件
└── setup_development.md # 开发环境搭建文档
```

### 10.2 服务端口列表
| 服务名称 | 端口号 | 协议 |
|---------|-------|------|
| 前端服务 | 3000  | HTTP |
| 后端API服务 | 8000 | HTTP |
| AI服务 | 8001  | HTTP |
| EDA工具服务 | 8002 | HTTP |
| Redis | 6379  | TCP |

### 10.3 联系方式
- 项目负责人：<负责人姓名> <联系方式>
- 技术支持：<技术支持联系方式>
