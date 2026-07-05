# TalkAgent Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY .env ./

# 创建数据和模型目录
RUN mkdir -p data/uploads data/chroma data/conversations models

# Gradio 端口
EXPOSE 7860

# 启动命令
CMD ["python", "-m", "app.main"]
