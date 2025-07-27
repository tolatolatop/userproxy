# UserProxy Docker 部署指南

## 项目简介

UserProxy 是一个基于 FastAPI 的 WebSocket 代理服务，使用 Redis 进行数据存储。

## 环境要求

- Docker
- Docker Compose

## 快速开始

### 1. 生产环境部署

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f app
```

### 2. 开发环境部署

```bash
# 启动开发环境（包含源代码挂载）
docker-compose --profile dev up -d app-dev

# 查看开发环境日志
docker-compose logs -f app-dev
```

### 3. 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止服务并删除数据卷
docker-compose down -v
```

## 服务说明

### 应用服务 (app)
- **端口**: 8000
- **环境变量**:
  - `REDIS_URL`: Redis连接地址
  - `PYTHONPATH`: Python路径
- **启动命令**: `poetry run userproxy-prod`

### Redis服务 (redis)
- **端口**: 6379
- **数据持久化**: 启用AOF
- **数据卷**: redis_data

### 开发环境服务 (app-dev)
- **端口**: 8001
- **特性**: 源代码热重载
- **启动命令**: `poetry run userproxy-dev`

## 环境变量配置

可以通过创建 `.env` 文件来配置环境变量：

```env
REDIS_URL=redis://redis:6379
ENVIRONMENT=production
```

## 构建镜像

```bash
# 构建镜像
docker build -t userproxy:latest .

# 运行容器
docker run -p 8000:8000 userproxy:latest
```

## 日志管理

应用日志会输出到 `./logs` 目录，该目录已挂载到容器中。

## 网络配置

所有服务都在 `userproxy-network` 网络中，确保服务间可以正常通信。

## 故障排除

1. **端口冲突**: 如果8000或6379端口被占用，可以在 `docker-compose.yaml` 中修改端口映射
2. **权限问题**: 确保 `logs` 目录有适当的写入权限
3. **Redis连接失败**: 检查Redis服务是否正常启动

## 开发建议

- 开发时使用 `app-dev` 服务，支持源代码热重载
- 生产环境使用 `app` 服务，性能更优
- 定期备份Redis数据卷
