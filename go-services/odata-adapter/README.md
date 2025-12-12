# OData Adapter

Микросервис для интеграции с базами 1C через OData протокол.

## Назначение

OData Adapter предоставляет:
- Выполнение OData-запросов к базам 1C
- Batch-операции с ограничением по времени (< 15 сек)
- Интеграция с Event Bus через Redis Streams
- REST API для синхронных запросов

## Архитектура

```
                                    ┌─────────────────┐
                                    │   Redis         │
                                    │  (Event Bus)    │
                                    └────────┬────────┘
                                             │
┌─────────────┐     ┌─────────────┐     ┌────▼────────┐     ┌─────────────┐
│ Orchestrator│────▶│ API Gateway │────▶│OData Adapter│────▶│  1C Bases   │
│  (Django)   │     │    (Go)     │     │    (Go)     │     │   (OData)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Конфигурация

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `ODATA_ADAPTER_PORT` | `8189` | Порт HTTP сервера |
| `SERVER_HOST` | `0.0.0.0` | Хост сервера |
| `SERVER_READ_TIMEOUT` | `10s` | Таймаут чтения |
| `SERVER_WRITE_TIMEOUT` | `15s` | Таймаут записи |
| `SERVER_SHUTDOWN_TIMEOUT` | `30s` | Таймаут graceful shutdown |
| `REDIS_HOST` | `localhost` | Хост Redis |
| `REDIS_PORT` | `6379` | Порт Redis |
| `REDIS_PASSWORD` | `` | Пароль Redis |
| `REDIS_DB` | `0` | Номер БД Redis |
| `REDIS_PUBSUB_ENABLED` | `false` | Включить Event Bus |
| `ODATA_DEFAULT_TIMEOUT` | `10s` | Таймаут OData запросов |
| `ODATA_MAX_BATCH_SIZE` | `500` | Максимум записей в batch |
| `ODATA_MAX_BATCH_TIMEOUT` | `14s` | Максимальное время batch (< 15s!) |
| `LOG_LEVEL` | `info` | Уровень логирования |

## Критические ограничения

- **Транзакции 1C < 15 секунд** - КРИТИЧНО! Все batch-операции должны укладываться в это время
- **Batch размер: 100-500 записей** - оптимальный диапазон для производительности
- **Параллельные соединения: 3-5** на базу данных

## API Endpoints

### Health Check

```
GET /health
GET /ready
```

### OData Operations (TODO)

```
POST /api/v2/odata/query    # Выполнить OData запрос
POST /api/v2/odata/batch    # Выполнить batch операцию
```

## Локальный запуск

```bash
# Из корня проекта
cd go-services/odata-adapter
go mod download
go run ./cmd/main.go
```

## Сборка

```bash
go build -ldflags "-X github.com/commandcenter1c/commandcenter/odata-adapter/internal/version.Version=1.0.0" -o bin/cc1c-odata-adapter ./cmd/main.go
```

## Структура проекта

```
odata-adapter/
├── cmd/
│   └── main.go              # Entry point
├── internal/
│   ├── api/
│   │   └── rest/
│   │       ├── router.go    # HTTP router
│   │       └── health.go    # Health endpoints
│   ├── config/
│   │   └── config.go        # Configuration
│   ├── server/
│   │   └── server.go        # HTTP server wrapper
│   └── version/
│       └── version.go       # Version info
├── go.mod
└── README.md
```

## TODO

- [ ] OData client implementation
- [ ] Batch operations
- [ ] Event handlers for Redis Streams
- [ ] Rate limiting
- [ ] Circuit breaker
- [ ] Metrics (Prometheus)
