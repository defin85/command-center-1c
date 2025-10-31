# Sprint 1.2: Docker Compose Integration - COMPLETED

## Дата завершения
30 октября 2025

## Цели Sprint 1.2
Создать Docker Compose setup для запуска:
1. ras-grpc-gw (форк, порт 9999)
2. cluster-service (наш сервис, порт 8088)

## Выполненные задачи

### 1. Dockerfile для cluster-service
**Файл:** `go-services/cluster-service/Dockerfile`

- Multi-stage build (golang:1.21-alpine + alpine:latest)
- Аргумент VERSION для версионирования бинарника
- Health check на порту 8088
- Минимальный размер образа

**Статус:** ✅ DONE

### 2. .dockerignore для cluster-service
**Файл:** `go-services/cluster-service/.dockerignore`

- Исключены бинарники (*.exe, *.dll, *.so, *.dylib)
- Исключены тестовые файлы (*.test, *.out, coverage.*)
- Исключены IDE файлы (.idea, .vscode)
- Исключены .env, .git

**Статус:** ✅ DONE

### 3. Dockerfile для ras-grpc-gw (обновлен)
**Файл:** `C:/1CProject/ras-grpc-gw/Dockerfile`

- Заменен простой Dockerfile на multi-stage build
- golang:1.24-alpine для сборки
- alpine:latest для runtime
- Health check на порту 8080
- Дефолтная команда с параметрами

**Статус:** ✅ DONE

### 4. .dockerignore для ras-grpc-gw
**Файл:** `C:/1CProject/ras-grpc-gw/.dockerignore`

- Исключены бинарники
- Исключены тестовые и build артефакты
- Исключены docs и tests

**Статус:** ✅ DONE

### 5. docker-compose.yml (обновлен)
**Файл:** `docker-compose.yml` в корне monorepo

Добавлены два новых сервиса:

#### ras-grpc-gw
- **Image:** ras-grpc-gw:v1.0.0-cc
- **Ports:** 9999 (gRPC), 8081 (health check - изменен с 8080 для избежания конфликта)
- **Health Check:** wget на http://localhost:8080/health
- **Command:** `./ras-grpc-gw --host 0.0.0.0:9999 --ras host.docker.internal:1545 --health 0.0.0.0:8080`
- **Restart Policy:** unless-stopped

#### cluster-service
- **Image:** cluster-service:v1.0.0-sprint1
- **Ports:** 8088 (HTTP API)
- **Dependencies:** ras-grpc-gw (с health check condition)
- **Environment Variables:**
  - SERVER_HOST, SERVER_PORT (HTTP сервер)
  - GRPC_GATEWAY_ADDR=ras-grpc-gw:9999
  - GRPC_CONN_TIMEOUT, GRPC_REQUEST_TIMEOUT
  - LOG_LEVEL=info
- **Health Check:** wget на http://localhost:8088/health
- **Restart Policy:** unless-stopped

**Статус:** ✅ DONE

### 6. .env.example (обновлен)
**Файл:** `.env.example` в корне monorepo

Добавлены переменные окружения:
```bash
# RAS gRPC Gateway
RAS_SERVER=host.docker.internal:1545
GRPC_GATEWAY_ADDR=localhost:9999
GRPC_CONN_TIMEOUT=5s
GRPC_REQUEST_TIMEOUT=10s

# Cluster Service
CLUSTER_SERVICE_URL=http://localhost:8088
CLUSTER_SERVICE_TIMEOUT=30
```

**Статус:** ✅ DONE

### 7. .gitignore (проверен)
**Файл:** `.gitignore` в корне monorepo

- Уже содержит все необходимые правила
- .env игнорируется
- Docker артефакты игнорируются

**Статус:** ✅ DONE (без изменений)

### 8. docker/README.md
**Файл:** `docker/README.md`

Создана документация с:
- Quick Start командами
- Описанием сервисов (порты, health endpoints)
- Примерами тестирования (curl команды)
- Troubleshooting секцией
- Development workflow

**Статус:** ✅ DONE

## Технические детали

### Порты
- **9999** - ras-grpc-gw (gRPC)
- **8081** - ras-grpc-gw (health check) - изменен с 8080 для избежания конфликта с api-gateway
- **8088** - cluster-service (HTTP API)

### Docker Images
- `ras-grpc-gw:v1.0.0-cc`
- `cluster-service:v1.0.0-sprint1`

### Build Context Paths
- ras-grpc-gw: `../ras-grpc-gw` (соседняя директория)
- cluster-service: `./go-services/cluster-service`

### Health Checks
Оба сервиса имеют health check с параметрами:
- interval: 10s
- timeout: 3s
- retries: 3
- start_period: 5s

### Dependency Management
cluster-service зависит от ras-grpc-gw:
```yaml
depends_on:
  ras-grpc-gw:
    condition: service_healthy
```

Это гарантирует, что cluster-service запустится ТОЛЬКО после того, как ras-grpc-gw пройдет health check.

## Проверка

### Синтаксис docker-compose.yml
```bash
docker-compose config --quiet
```
**Результат:** ✅ Валиден (warning про obsolete version можно игнорировать)

### Созданные файлы
```
✅ go-services/cluster-service/Dockerfile
✅ go-services/cluster-service/.dockerignore
✅ C:/1CProject/ras-grpc-gw/Dockerfile (обновлен)
✅ C:/1CProject/ras-grpc-gw/.dockerignore
✅ docker-compose.yml (обновлен)
✅ .env.example (обновлен)
✅ docker/README.md
```

## Следующие шаги (Sprint 1.3)

1. **E2E тесты:**
   - Запустить `docker-compose up -d`
   - Проверить health endpoints
   - Протестировать API endpoints cluster-service

2. **Интеграционное тестирование:**
   - Проверить связь cluster-service → ras-grpc-gw → RAS server
   - Протестировать получение списка кластеров
   - Протестировать получение списка infobase

3. **Документация:**
   - Обновить README.md в корне проекта
   - Добавить примеры использования Docker Compose

## Важные замечания

1. **host.docker.internal:**
   - Используется для доступа к localhost хоста из контейнера
   - Работает на Windows/Mac из коробки
   - На Linux может потребоваться `--add-host=host.docker.internal:host-gateway`

2. **Порт 8081 вместо 8080:**
   - Внешний порт для health check ras-grpc-gw изменен на 8081
   - Внутренний порт в контейнере остался 8080
   - Это сделано для избежания конфликта с api-gateway (порт 8080)

3. **Multi-stage builds:**
   - Оба Dockerfile используют multi-stage build
   - Это минимизирует размер итоговых образов
   - Build инструменты не попадают в production образ

## Deliverables Summary

| # | Deliverable | Статус |
|---|-------------|--------|
| 1 | Dockerfile для cluster-service | ✅ DONE |
| 2 | .dockerignore для cluster-service | ✅ DONE |
| 3 | Dockerfile для ras-grpc-gw | ✅ DONE |
| 4 | .dockerignore для ras-grpc-gw | ✅ DONE |
| 5 | docker-compose.yml (обновлен) | ✅ DONE |
| 6 | .env.example (обновлен) | ✅ DONE |
| 7 | .gitignore (проверен) | ✅ DONE |
| 8 | docker/README.md | ✅ DONE |

## Заключение

Sprint 1.2 успешно завершен. Все deliverables выполнены. Docker Compose setup готов для запуска и тестирования.

**Готовность к следующему этапу:** ✅ READY FOR SPRINT 1.3 (E2E Testing)
