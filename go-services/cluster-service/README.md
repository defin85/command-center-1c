# cluster-service

Go микросервис для мониторинга и управления кластерами 1С через gRPC протокол (ras-grpc-gw).

**Статус:** 📋 К реализации (Phase 1, Week 3-4)

---

## 🎯 Описание

`cluster-service` предоставляет REST API для мониторинга кластеров 1С:Предприятие 8.3 через современный gRPC протокол. Сервис использует [ras-grpc-gw](https://github.com/v8platform/ras-grpc-gw) для взаимодействия с RAS (Remote Administration Server) на порту 1545.

### Основные возможности

- ✅ Получение списка кластеров 1С
- ✅ Получение списка информационных баз (infobases)
- ✅ Мониторинг активных сессий
- ✅ High-performance через gRPC (latency <100ms)
- ✅ Connection pooling
- ✅ Асинхронные операции

---

## 🔀 Разделение ответственности с batch-service

| Аспект | cluster-service | batch-service |
|--------|----------------|---------------|
| **Протокол** | gRPC (ras-grpc-gw) | subprocess (v8platform/api) |
| **Назначение** | Мониторинг кластеров | Установка расширений |
| **Операции** | Чтение метаданных | Модификация конфигураций |
| **Latency** | <100ms (p50) | 30-60 секунд (установка) |
| **Throughput** | 1000+ req/min | 100+ ops/min (batch) |
| **Use case** | Real-time мониторинг | Batch операции |

### Как они дополняют друг друга

```
┌─────────────────────┐
│   Orchestrator      │
└──────┬─────────┬────┘
       │         │
       │         └──────────────┐
       │                        │
   ┌───▼──────────┐      ┌─────▼────────────┐
   │ cluster-     │      │ batch-           │
   │ service      │      │ service          │
   │              │      │                  │
   │ Monitoring:  │      │ Management:      │
   │ - Clusters   │      │ - Install .cfe   │
   │ - Infobases  │      │ - Batch install  │
   │ - Sessions   │      │ - Config update  │
   └──────┬───────┘      └─────┬────────────┘
          │                    │
    ┌─────▼──────┐      ┌──────▼─────┐
    │ ras-grpc-  │      │ 1cv8.exe   │
    │ gw (gRPC)  │      │ subprocess │
    └─────┬──────┘      └──────┬─────┘
          │                    │
          └──────────┬─────────┘
                     │
              ┌──────▼──────┐
              │ RAS + 1C    │
              │ Cluster     │
              └─────────────┘
```

**Workflow пример:**

1. **cluster-service**: Получить список баз → GET /api/v1/infobases
2. **Orchestrator**: Выбрать базы для установки расширения
3. **batch-service**: Установить расширение на N баз → POST /api/v1/extensions/batch-install

---

## 🔄 О форке ras-grpc-gw

### Почему форк?

Оригинальный `v8platform/ras-grpc-gw` находится в ALPHA статусе и не готов для production использования. Форк `defin85/ras-grpc-gw` создан для:

- ✅ Контроля над стабильностью и багфиксами
- ✅ Добавления production-ready features
- ✅ Кастомизации под специфику проекта (700+ баз)
- ✅ Независимости от активности upstream

### Ключевые доработки в форке

**Must-have (Phase 0):**
- Unit тесты (coverage > 70%)
- Structured logging (zap)
- Health check endpoints (/health, /ready)
- Graceful shutdown
- Error handling с retry logic
- Connection timeout configuration

**Nice-to-have (Phase 2+):**
- Prometheus metrics
- Connection pooling для 700+ баз
- Circuit breaker для защиты от cascade failures
- TLS/mTLS support

### Версионирование

Форк использует Semantic Versioning с суффиксом `-cc`:
- `v1.0.0-cc` - первый production-ready release
- `v1.0.1-cc` - bugfix releases
- `v1.1.0-cc` - feature releases

### Репозиторий

- **Форк:** https://github.com/defin85/ras-grpc-gw
- **Upstream:** https://github.com/v8platform/ras-grpc-gw
- **Docker image:** `ghcr.io/defin85/ras-grpc-gw:v1.0.0-cc`

### Синхронизация с upstream

Ежемесячная синхронизация с оригинальным репозиторием через процедуру описанную в `docs/UPSTREAM_SYNC.md` форка.

---

## 🏗️ Архитектура

### High-Level Компоненты

```
┌─────────────────────────────────────────────────────┐
│         cluster-service (Go + Gin)                  │
│                                                     │
│  ┌───────────────────────────────────────────────┐ │
│  │         HTTP API Layer (REST)                 │ │
│  │  GET /clusters, /infobases, /sessions        │ │
│  └──────────────────┬────────────────────────────┘ │
│                     │                               │
│  ┌──────────────────▼────────────────────────────┐ │
│  │       MonitoringService                       │ │
│  │       (gRPC Client Wrapper)                   │ │
│  │                                               │ │
│  │  - GetClusters()                              │ │
│  │  - GetInfobases()                             │ │
│  │  - GetSessions()                              │ │
│  └──────────────────┬────────────────────────────┘ │
│                     │                               │
└─────────────────────┼───────────────────────────────┘
                      │ gRPC
         ┌────────────▼─────────────┐
         │   ras-grpc-gw            │
         │   (v8platform)           │
         │                          │
         │   Port: 9999             │
         └────────────┬─────────────┘
                      │ RAS Binary Protocol
              ┌───────▼────────┐
              │   RAS Server   │
              │   Port: 1545   │
              └────────────────┘
```

### Структура проекта

```
cluster-service/
├── cmd/
│   └── main.go                          # Entry point
├── internal/
│   ├── api/
│   │   ├── router.go                    # Route configuration
│   │   └── handlers/
│   │       └── monitoring.go            # HTTP handlers
│   ├── service/
│   │   └── monitoring_service.go        # gRPC client wrapper
│   ├── models/
│   │   ├── cluster.go                   # Domain models
│   │   └── infobase.go
│   └── config/
│       └── config.go                    # Configuration
├── go.mod
├── go.sum
└── README.md
```

---

## 📡 API Спецификация

### Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "cluster-service",
  "version": "1.0.0"
}
```

---

### Get Clusters

Получение списка кластеров 1С.

```bash
GET /api/v1/clusters?server=localhost:1545
```

**Query Parameters:**
- `server` (required) - RAS server address with port

**Response:**
```json
{
  "clusters": [
    {
      "uuid": "e3b0c442-98fc-1c14-b39f-92d1282048c0",
      "name": "Local cluster",
      "host": "localhost",
      "port": 1541
    }
  ]
}
```

**Curl Example:**
```bash
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"
```

---

### Get Infobases

Получение списка информационных баз в кластере.

```bash
GET /api/v1/infobases?server=localhost:1545&cluster=<uuid>
```

**Query Parameters:**
- `server` (required) - RAS server address
- `cluster` (optional) - Cluster UUID (если не указан - все базы)

**Response:**
```json
{
  "infobases": [
    {
      "uuid": "e94fc632-f38d-4866-8c39-3e98a6341c88",
      "name": "dev",
      "dbms": "MSSQLServer",
      "db_server": "localhost",
      "db_name": "dev_db"
    },
    {
      "uuid": "f21ab419-82c7-4d5a-9c2f-1e7b3a4d5c6e",
      "name": "delans_unf",
      "dbms": "MSSQLServer",
      "db_server": "localhost",
      "db_name": "delans_unf_db"
    }
  ]
}
```

**Curl Example:**
```bash
curl "http://localhost:8088/api/v1/infobases?server=localhost:1545"
```

---

### Get Sessions (Phase 2)

Получение активных сессий пользователей.

```bash
GET /api/v1/sessions?server=localhost:1545&cluster=<uuid>
```

**Query Parameters:**
- `server` (required) - RAS server address
- `cluster` (optional) - Cluster UUID
- `infobase` (optional) - Infobase UUID (фильтр по базе)

**Response:**
```json
{
  "sessions": [
    {
      "session_id": 1234,
      "infobase_uuid": "e94fc632-f38d-4866-8c39-3e98a6341c88",
      "user_name": "admin",
      "app_id": "1CV8C",
      "started_at": "2025-01-17T10:30:00Z",
      "last_active_at": "2025-01-17T10:45:00Z"
    }
  ]
}
```

---

## 🛠️ Технологический стек

### Core
- **Go:** 1.21+
- **HTTP Framework:** Gin 1.9+
- **gRPC:** google.golang.org/grpc 1.60+

### Dependencies
- **ras-grpc-gw:** github.com/defin85/ras-grpc-gw - форк gRPC gateway для RAS протокола (custom build)
- **Gin:** github.com/gin-gonic/gin

### External Services
- **ras-grpc-gw Gateway:** gRPC gateway для RAS протокола (Port 9999)
- **RAS Server:** Remote Administration Server 1С (Port 1545)

---

## ⚙️ Конфигурация

### Environment Variables

```bash
# HTTP Server
export SERVER_HOST=0.0.0.0
export SERVER_PORT=8088

# gRPC Gateway (ras-grpc-gw)
export GRPC_GATEWAY_ADDR=localhost:9999

# Logging
export LOG_LEVEL=info  # debug, info, warn, error
```

### Пример .env

```env
# cluster-service configuration

# HTTP Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8088

# ras-grpc-gw Gateway
GRPC_GATEWAY_ADDR=localhost:9999

# Logging
LOG_LEVEL=info
```

---

## 🚀 Быстрый старт

### Предварительные требования

- Go 1.21+
- Docker & Docker Compose
- **Форк ras-grpc-gw:** https://github.com/defin85/ras-grpc-gw
- Доступ к RAS серверу 1С (порт 1545)

**Примечание:** cluster-service использует форк `defin85/ras-grpc-gw` вместо оригинального пакета. Форк должен быть склонирован рядом с monorepo для Docker Compose build.

### Структура проектов

```
~/projects/
├── command-center-1c/           # Monorepo
│   └── go-services/
│       └── cluster-service/     # Этот сервис
└── ras-grpc-gw/                 # Форк (отдельный репозиторий)
```

### 1. Установка зависимостей

```bash
cd go-services/cluster-service
go mod download
```

### 2. Конфигурация

```bash
# Скопировать .env пример
cp .env.example .env

# Отредактировать под свое окружение
nano .env
```

### 3. Запуск сервиса

```bash
# Development mode
go run cmd/main.go

# Production build
go build -o cluster-service.exe cmd/main.go
./cluster-service.exe
```

Сервер запустится на `http://localhost:8088`

### 4. Проверка работы

```bash
# Health check
curl http://localhost:8088/health

# Get clusters
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"
```

---

## 🔨 Development Workflow

### Сценарий 1: Разработка только cluster-service

```bash
# Запустить ras-grpc-gw из Docker Hub
docker-compose up -d ras-grpc-gw

# Запустить cluster-service локально
cd go-services/cluster-service
export GRPC_GATEWAY_ADDR=localhost:9999
go run cmd/main.go
```

### Сценарий 2: Разработка форка и cluster-service одновременно

```bash
# Terminal 1: Запустить ras-grpc-gw локально
cd ~/projects/ras-grpc-gw
go run cmd/ras-grpc-gw/main.go

# Terminal 2: Запустить cluster-service локально
cd ~/projects/command-center-1c/go-services/cluster-service
export GRPC_GATEWAY_ADDR=localhost:9999
go run cmd/main.go

# Terminal 3: Тестирование
curl "http://localhost:8088/api/v1/clusters?server=localhost:1545"
```

### Сценарий 3: Тестирование в Docker

```bash
cd ~/projects/command-center-1c

# Пересобрать оба сервиса
docker-compose build ras-grpc-gw cluster-service

# Запустить
docker-compose up -d

# Логи
docker-compose logs -f ras-grpc-gw cluster-service

# Тестирование
curl "http://localhost:8088/api/v1/clusters?server=host.docker.internal:1545"
```

---

## 🐳 Deployment

### Docker Compose

```yaml
services:
  # ras-grpc-gw (форк)
  ras-grpc-gw:
    build:
      context: ../../ras-grpc-gw  # Путь к форку (рядом с monorepo)
      dockerfile: Dockerfile
    image: ghcr.io/defin85/ras-grpc-gw:v1.0.0-cc
    container_name: cc1c-ras-grpc-gw
    ports:
      - "9999:9999"
    environment:
      - RAS_SERVER=${RAS_SERVER:-host.docker.internal:1545}
      - LOG_LEVEL=${LOG_LEVEL:-info}
      - GRPC_PORT=9999
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:9999/health"]
      interval: 10s
      timeout: 3s
      retries: 3
    networks:
      - commandcenter-network

  # cluster-service
  cluster-service:
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/command-center-1c/cluster-service:dev
    container_name: cc1c-cluster-service
    ports:
      - "8088:8088"
    environment:
      - GRPC_GATEWAY_ADDR=ras-grpc-gw:9999
      - LOG_LEVEL=${LOG_LEVEL:-info}
    depends_on:
      ras-grpc-gw:
        condition: service_healthy  # Ждём пока форк будет готов
    networks:
      - commandcenter-network

networks:
  commandcenter-network:
    driver: bridge
```

### Dockerfile (пример)

```dockerfile
FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN go build -o cluster-service cmd/main.go

FROM alpine:latest
RUN apk --no-cache add ca-certificates

WORKDIR /root/
COPY --from=builder /app/cluster-service .

EXPOSE 8088
CMD ["./cluster-service"]
```

---

## 🔧 Development

### Сборка

```bash
# Сборка для текущей платформы
go build -o cluster-service.exe cmd/main.go

# Cross-compile для Linux
GOOS=linux GOARCH=amd64 go build -o cluster-service cmd/main.go
```

### Тесты

```bash
# Run all tests
go test ./...

# With coverage
go test -cover ./...

# Verbose output
go test -v ./...
```

### Форматирование

```bash
# Format code
go fmt ./...

# Lint
golangci-lint run
```

### Отладка

```bash
# Run with debug logging
export LOG_LEVEL=debug
go run cmd/main.go

# View gRPC traffic (if needed)
export GRPC_GO_LOG_VERBOSITY_LEVEL=99
export GRPC_GO_LOG_SEVERITY_LEVEL=info
```

---

## 📅 Timeline реализации

### Phase 0: Fork ras-grpc-gw Setup (Week 3, 5 дней)

**Цель:** Подготовить форк ras-grpc-gw к production использованию

#### Sprint 0.1: Fork & Initial Audit (3 дня)

- [ ] Создание форка `defin85/ras-grpc-gw`
- [ ] Настройка CI/CD (GitHub Actions)
- [ ] Аудит кодовой базы (FORK_AUDIT.md)
- [ ] Setup development environment
- [ ] Настройка Docker build

**Deliverables:**
- ✅ Форк готов к разработке
- ✅ CI/CD pipeline настроен
- ✅ Документация FORK_CHANGELOG.md

#### Sprint 0.2: Critical Fixes & Testing (2 дня)

- [ ] Unit тесты (coverage > 70%)
- [ ] Integration тесты с mock RAS
- [ ] Fix: Network error handling
- [ ] Add: Structured logging (zap)
- [ ] Add: Graceful shutdown
- [ ] Add: Health check endpoints

**Deliverables:**
- ✅ Test coverage > 70%
- ✅ Критические баги исправлены
- ✅ Release v1.0.0-cc готов
- ✅ Docker image: ghcr.io/defin85/ras-grpc-gw:v1.0.0-cc

---

### Phase 1: Core Integration (Week 4-5, 10 дней)

**Цель:** Интеграция cluster-service с форком ras-grpc-gw

#### Sprint 1.1: cluster-service + Fork Integration (5 дней)

- [ ] Добавить dependency на форк в go.mod
- [ ] Реализовать MonitoringService (gRPC client)
- [ ] Реализовать API handlers (GET /clusters, /infobases)
- [ ] Unit тесты (coverage > 70%)

**Deliverables:**
- ✅ cluster-service использует форк
- ✅ API endpoints работают
- ✅ Unit tests проходят

#### Sprint 1.2: Docker Compose Integration (5 дней)

- [ ] Docker Compose с обоими сервисами
- [ ] E2E тесты с реальным RAS
- [ ] Performance testing (latency < 100ms p50)
- [ ] Обновление документации

**Deliverables:**
- ✅ docker-compose up запускает оба сервиса
- ✅ E2E тесты проходят
- ✅ Latency p50 < 100ms

---

### Phase 2: Production Features (Week 6-8, 15 дней)

**Цель:** Добавить production-ready features

#### Sprint 2.1: Monitoring & Observability (5 дней)

**В форке ras-grpc-gw:**
- [ ] Prometheus metrics
- [ ] Health checks (/health, /ready)
- [ ] Structured logging с trace ID

**В cluster-service:**
- [ ] Интеграция метрик
- [ ] Response time tracking
- [ ] Error tracking

**Deliverables:**
- ✅ Prometheus scraping работает
- ✅ Health checks проходят

#### Sprint 2.2: Advanced Features (5 дней)

**В форке ras-grpc-gw:**
- [ ] Connection pooling
- [ ] Circuit breaker
- [ ] TLS support

**В cluster-service:**
- [ ] Redis caching layer
- [ ] TTL configuration

**Deliverables:**
- ✅ Connection pool работает (700+ баз)
- ✅ Circuit breaker защищает
- ✅ TLS настроен

#### Sprint 2.3: Testing & Bug Fixes (5 дней)

- [ ] Load testing (1000+ req/min)
- [ ] Bug fixes из тестирования
- [ ] Documentation updates

---

### Phase 3: Scale & Optimize (Week 9-12, 20 дней)

**Цель:** Production deployment с полным мониторингом

#### Sprint 3.1: Load Testing (5 дней)

- [ ] k6 scripts для нагрузочного тестирования
- [ ] Target: 1000+ req/min
- [ ] Target: 100+ concurrent connections
- [ ] Latency p99 < 300ms

#### Sprint 3.2: Production Hardening (5 дней)

- [ ] Kubernetes manifests
- [ ] Rolling updates strategy
- [ ] Auto-scaling configuration
- [ ] Production deployment

#### Sprint 3.3: Monitoring Dashboards (5 дней)

- [ ] Grafana dashboards
- [ ] Alerting rules
- [ ] Runbook documentation

#### Sprint 3.4: Final Testing (5 дней)

- [ ] Production smoke tests
- [ ] Performance validation
- [ ] Security audit
- [ ] Team training

**Deliverables:**
- ✅ Production deployment работает
- ✅ Grafana dashboards настроены
- ✅ Alerts настроены
- ✅ Команда обучена

---

**Общий timeline:** 12 недель (50 рабочих дней)
**Укладываемся в:** Balanced approach (16 недель) с запасом 4 недели

---

## 📊 Метрики успеха

| Метрика | Target | Measurement |
|---------|--------|-------------|
| **Latency** |
| GetClusters (p50) | < 50ms | Prometheus histogram |
| GetClusters (p99) | < 200ms | Prometheus histogram |
| GetInfobases (p50) | < 100ms | Prometheus histogram |
| GetInfobases (p99) | < 300ms | Prometheus histogram |
| **Throughput** |
| Requests per minute | > 1000 req/min | Prometheus counter |
| Concurrent requests | 100+ | Load testing |
| **Reliability** |
| Success rate | > 99% | Prometheus counter |
| gRPC connection uptime | > 99.9% | Custom metric |
| **Performance** |
| Memory usage | < 100 MB | Resource monitoring |
| CPU usage | < 20% (idle) | Resource monitoring |

---

## 🛣️ Roadmap

### Phase 0: Fork Setup (Week 3) - ТЕКУЩАЯ ФАЗА

- [ ] Создать форк defin85/ras-grpc-gw
- [ ] Настроить CI/CD для форка
- [ ] Провести аудит кодовой базы
- [ ] Добавить unit тесты (coverage > 70%)
- [ ] Реализовать must-have features
  - [ ] Structured logging
  - [ ] Health checks
  - [ ] Graceful shutdown
  - [ ] Error handling
- [ ] Выпустить v1.0.0-cc release
- [ ] Опубликовать Docker image

### Phase 1: Core Integration (Week 4-5)

- [x] Структура проекта создана
- [ ] Добавить dependency на форк в go.mod
- [ ] MonitoringService implementation (gRPC client)
- [ ] API endpoints (clusters, infobases)
- [ ] Unit tests + E2E tests
- [ ] Docker Compose setup
- [ ] Performance testing (latency < 100ms p50)
- [ ] Documentation

### Phase 2: Production Features (Week 6-8)

- [ ] Prometheus metrics (форк + service)
- [ ] Health checks в обоих сервисах
- [ ] Connection pooling в форке
- [ ] Circuit breaker в форке
- [ ] TLS support в форке
- [ ] Redis caching layer в service
- [ ] Load testing (1000+ req/min)

### Phase 3: Scale & Optimize (Week 9-12)

- [ ] k6 load testing scripts
- [ ] Kubernetes manifests
- [ ] Auto-scaling configuration
- [ ] Grafana dashboards
- [ ] Alerting rules
- [ ] Production deployment
- [ ] Team training

### Future Enhancements (Post-Phase 3)

- [ ] Sessions monitoring endpoint
- [ ] Management operations (terminate session, etc)
- [ ] GraphQL API (alternative to REST)
- [ ] WebSocket support (real-time updates)
- [ ] Admin UI (React dashboard)
- [ ] Advanced filtering and search

---

## 🔗 Связанные компоненты

### Internal Services
- **batch-service:** `go-services/batch-service/` - Установка расширений
- **api-gateway:** `go-services/api-gateway/` - Маршрутизация HTTP (будет)
- **Orchestrator:** `orchestrator/` - Django orchestration service

### External Dependencies
- **ras-grpc-gw:** https://github.com/v8platform/ras-grpc-gw
- **v8platform/ras:** https://github.com/v8platform/ras (IBIS SDK reference)

### Documentation
- **Project README:** `README.md`
- **Roadmap:** `docs/ROADMAP.md`
- **Architecture:** `docs/IBIS_SERVICE_HYBRID_ARCHITECTURE.md` (legacy)

---

## 🐛 Troubleshooting

### Проблема: "connection refused" при обращении к ras-grpc-gw

**Решение:**
1. Проверить что ras-grpc-gw запущен: `docker ps | grep ras-grpc-gw`
2. Проверить порт: `netstat -an | grep 9999`
3. Проверить переменную окружения: `echo $GRPC_GATEWAY_ADDR`

---

### Проблема: "empty response" от GetInfobases

**Решение:**
1. Проверить что RAS Server доступен: `telnet localhost 1545`
2. Проверить что в кластере есть базы: через 1C консоль администрирования
3. Включить debug logging: `LOG_LEVEL=debug`

---

### Проблема: высокая latency (>500ms)

**Решение:**
1. Проверить connection pool settings в gRPC client
2. Проверить сетевую латентность до ras-grpc-gw: `ping <gateway_host>`
3. Включить gRPC tracing для диагностики

---

## 📚 Дополнительные ресурсы

### Документация 1С
- **RAC vs RAS:** `docs/1C_RAS_vs_RAC.md`
- **RAC Commands:** `docs/1C_RAC_COMMANDS.md`
- **Security:** `docs/1C_RAC_SECURITY.md`

### Примеры кода
- **MonitoringService:** См. `docs/IBIS_SERVICE_HYBRID_ARCHITECTURE.md` (код референс)
- **batch-service:** См. `go-services/batch-service/` (структура проекта)

---

## 👥 Contributing

Этот сервис является частью CommandCenter1C monorepo.

**Соглашения:**
- Следуй структуре проекта (cmd/, internal/, pkg/)
- Пиши unit tests (coverage > 70%)
- Используй Go fmt/lint перед коммитом
- Документируй публичные API в комментариях

**Commit messages:**
```
[cluster-service] Add GetSessions endpoint

Implements Phase 2 feature for session monitoring
```

---

## 📄 Лицензия

Часть проекта CommandCenter1C

---

**Версия:** 2.0
**Последнее обновление:** 2025-01-30
**Статус:** 📋 Phase 0 - Fork Setup (Week 3)
**Форк:** https://github.com/defin85/ras-grpc-gw
