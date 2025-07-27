# UserProxy Docker 部署指南

## 项目简介

UserProxy 是一个基于 FastAPI 的 WebSocket 代理服务，使用 Redis 进行数据存储。

## 环境要求

- Docker
- Docker Compose

## 环境配置

### 1. 环境变量文件设置

项目提供了分离的环境配置：

```bash
# 复制环境变量示例文件
cp config/env.prod.example .env.prod
cp config/env.dev.example .env.dev

# 编辑环境变量文件，根据实际情况修改配置
nano .env.prod
nano .env.dev
```

### 2. 重要配置说明

- **生产环境** (`.env.prod`): 使用外部Redis服务，需要配置 `REDIS_URL`
- **开发环境** (`.env.dev`): 使用本地Redis容器，`REDIS_URL=redis://redis:6379`

## 快速开始

### 1. 生产环境部署

```bash
# 构建并启动应用服务（不包含Redis）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

### 2. 开发环境部署

```bash
# 启动开发环境（包含本地Redis和源代码挂载）
docker-compose -f docker-compose-dev.yaml up -d

# 查看开发环境日志
docker-compose -f docker-compose-dev.yaml logs -f app-dev
```

### 3. 停止服务

```bash
# 停止生产环境服务
docker-compose down

# 停止开发环境服务
docker-compose -f docker-compose-dev.yaml down

# 停止开发环境服务并删除数据卷
docker-compose -f docker-compose-dev.yaml down -v
```

## 服务说明

### 生产环境服务 (docker-compose.yaml)
- **应用服务 (app)**: 端口8000，使用外部Redis
- **环境变量**: 从 `.env.prod` 文件加载
- **启动命令**: `poetry run userproxy-prod`

### 开发环境服务 (docker-compose-dev.yaml)
- **应用服务 (app-dev)**: 端口8001，支持源代码热重载
- **Redis服务 (redis)**: 端口6379，本地开发用
- **环境变量**: 从 `.env.dev` 文件加载
- **启动命令**: `poetry run userproxy-dev`

## 环境变量配置

### 生产环境 (.env.prod)
```env
ENVIRONMENT=production
REDIS_URL=redis://your-production-redis-host:6379
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
DEBUG=false
SECRET_KEY=your-production-secret-key-here
```

### 开发环境 (.env.dev)
```env
ENVIRONMENT=development
REDIS_URL=redis://redis:6379
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=DEBUG
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production
```

## 构建镜像

```bash
# 构建镜像
docker build -t userproxy:latest .

# 运行容器
docker run -p 8000:8000 --env-file .env.prod userproxy:latest
```

## 日志管理

应用日志会输出到 `./logs` 目录，该目录已挂载到容器中。

## 网络配置

- **生产环境**: 使用 `userproxy-network`
- **开发环境**: 使用 `userproxy-dev-network`

## 故障排除

1. **端口冲突**: 如果8000或6379端口被占用，可以在配置文件中修改端口映射
2. **权限问题**: 确保 `logs` 目录有适当的写入权限
3. **Redis连接失败**: 
   - 开发环境：检查Redis容器是否正常启动
   - 生产环境：检查外部Redis服务是否可访问
4. **环境变量问题**: 确保 `.env.prod` 或 `.env.dev` 文件存在且配置正确

## 开发建议

- 开发时使用 `docker-compose-dev.yaml`，支持源代码热重载和本地Redis
- 生产环境使用 `docker-compose.yaml`，连接外部Redis服务
- 定期备份Redis数据卷（开发环境）
- 确保生产环境的Redis服务有适当的备份策略
