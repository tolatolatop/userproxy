# 使用Python 3.11作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装poetry
RUN pip install poetry==2.1.1

# 配置poetry不创建虚拟环境（因为Docker容器本身就是隔离的）
RUN poetry config virtualenvs.create false

# 复制poetry配置文件
COPY pyproject.toml poetry.lock ./

# 安装依赖
RUN poetry install --only=main --no-root

# 复制源代码
COPY src/ ./src/

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# 暴露端口（根据FastAPI应用需要调整）
EXPOSE 8000

# 启动命令
CMD ["poetry", "run", "userproxy-prod"] 