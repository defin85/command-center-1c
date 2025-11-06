---
description: Build Docker images for all components
---

Собрать Docker images для всех компонентов.

## Usage

```bash
docker-compose build
```

## Build Specific Service

```bash
docker-compose build orchestrator
docker-compose build api-gateway
docker-compose build frontend
docker-compose build worker
```

## Force Rebuild

```bash
docker-compose build --no-cache
```

## When to Use

- После изменения Dockerfiles
- После обновления зависимостей (requirements.txt, go.mod, package.json)
- Перед deployment
- При проблемах с кешем Docker

## Common Issues

**Build fails:**
```bash
# Пересобрать без кеша
docker-compose build --no-cache <service>

# Pull latest base images
docker-compose build --pull
```

**Out of disk space:**
```bash
# Clean up old images
docker image prune -a

# Remove dangling images
docker image prune
```

**Build takes too long:**
```bash
# Check what's happening
docker-compose build --progress=plain api-gateway
```

## Verification

```bash
# Проверить что образы созданы
docker images | grep command-center

# Запустить тесты в containers
docker-compose run --rm orchestrator pytest
docker-compose run --rm api-gateway go test ./...
```

## Related

- `/dev-start` - для локальной разработки (НЕ Docker)
- Skill: `cc1c-devops`
