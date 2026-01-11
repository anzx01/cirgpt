# 构建阶段
FROM python:3.9-alpine AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apk update && apk add --no-cache gcc musl-dev libffi-dev openssl-dev

# 复制依赖文件
COPY requirements.txt ./

# 安装Python依赖（使用wheel缓存）
RUN pip install --upgrade pip && pip wheel --no-cache-dir --wheel-dir=/app/wheels -r requirements.txt

# 运行阶段
FROM python:3.9-alpine

# 设置工作目录
WORKDIR /app

# 安装系统依赖（运行时所需）
RUN apk update && apk add --no-cache libssl1.1 libffi7

# 复制wheel文件并安装依赖
COPY --from=builder /app/wheels /wheels
RUN pip install --no-cache /wheels/*

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8002

# 启动应用
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "2"]