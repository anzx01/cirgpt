# 开发环境配置说明

## ⚠️ 重要：SECRET_KEY 必须设置

在运行后端服务之前，您必须在 `.env` 文件中设置一个安全的 `SECRET_KEY`。

## 快速开始

1. **生成安全密钥**

```bash
# 方法1：使用Python生成（推荐）
python -c 'import secrets; print(secrets.token_urlsafe(32))'

# 方法2：使用OpenSSL生成
openssl rand -base64 32
```

2. **创建 .env 文件**

```bash
cp .env.example .env
```

3. **编辑 .env 文件，将生成的密钥填入 SECRET_KEY**

```env
SECRET_KEY=你生成的随机密钥字符串
```

## 示例配置

开发环境：
```env
SECRET_KEY=生成的32字符以上随机字符串
DEBUG=true
DB_URL=sqlite:///./app.db
REDIS_URL=redis://localhost:6379
AI_SERVICE_URL=http://localhost:8001
EDA_SERVICE_URL=http://localhost:8002
CORS_ORIGINS=http://localhost:3000
```

生产环境：
```env
SECRET_KEY=生成的32字符以上随机字符串
DEBUG=false
DB_URL=postgresql://user:password@localhost:5432/circuitgpt
REDIS_URL=redis://:password@redis:6379
AI_SERVICE_URL=http://ai-service:8001
EDA_SERVICE_URL=http://eda-service:8002
CORS_ORIGINS=https://yourdomain.com
```

## 常见错误

### 错误1: SECRET_KEY is required

**原因**: 未设置 SECRET_KEY 环境变量

**解决**: 按照上述步骤创建 .env 文件并设置 SECRET_KEY

### 错误2: SECRET_KEY is insecure

**原因**: SECRET_KEY 太短或使用了不安全的默认值

**解决**: 使用至少32个字符的随机字符串

## 安全建议

- ✅ 使用随机生成的密钥
- ✅ 密钥长度至少32个字符
- ✅ 不要提交 .env 文件到版本控制
- ✅ 定期更换生产环境密钥
- ❌ 不要使用简单的字符串如 "secret"、"password"
- ❌ 不要在代码中硬编码密钥
