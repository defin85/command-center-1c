---
description: Build Docker images for all components
---

Собрать Docker образы для всех компонентов проекта.

## Действия

1. **Перейти в корневую директорию**
   ```bash
   cd /c/1CProject/command-center-1c
   ```

2. **Собрать все образы**
   ```bash
   docker-compose build
   ```

3. **Или собрать конкретный сервис**
   ```bash
   docker-compose build api-gateway
   docker-compose build orchestrator
   docker-compose build frontend
   docker-compose build worker
   ```

4. **Проверить собранные образы**
   ```bash
   docker images | grep command-center
   ```

## Параметры

- `--no-cache` - собрать без кэша (полная пересборка)
- `--pull` - always pull latest base images

## Примеры

```bash
# Собрать все
docker-compose build

# Собрать без кэша (чистая сборка)
docker-compose build --no-cache

# Собрать конкретный сервис
docker-compose build api-gateway

# Собрать и запустить
docker-compose build && docker-compose up -d

# Собрать с progress output
docker-compose build --progress=plain
```

## Troubleshooting

**Build fails with "base image not found":**
```bash
# Pull latest base images
docker-compose build --pull

# Или вручную
docker pull python:3.11-slim
docker pull golang:1.21-alpine
docker pull node:18-alpine
docker pull postgres:15-alpine
docker pull redis:7-alpine
```

**Out of disk space:**
```bash
# Clean up old images
docker image prune -a

# Remove dangling images
docker image prune
```

**Permission denied:**
```bash
# Add current user to docker group (Linux)
sudo usermod -aG docker $USER
newgrp docker
```

**Build takes too long:**
```bash
# Check what's happening
docker-compose build --progress=plain api-gateway

# Build in parallel (with make)
make build-docker-parallel
```

## Verification

После успешной сборки:

```bash
# Проверить что образы созданы
docker images | grep command-center

# Запустить тесты в containers
docker-compose run --rm orchestrator pytest
docker-compose run --rm api-gateway go test ./...
```

## Связанные Commands

- `dev-start` - запустить собранные образы
- `test-all` - запустить тесты
- `deploy-staging` - отправить образы в staging
