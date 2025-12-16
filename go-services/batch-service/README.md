# batch-service

Go микросервис для хранения файлов расширений 1С (.cfe) и извлечения их метаданных.

## Возможности

- ✅ Upload/List/Delete для хранилища расширений
- ✅ Извлечение метаданных из `.cfe` (через `v8platform/api`)
- ✅ Graceful shutdown
- ✅ Health check endpoint

## Требования

- Go 1.21+
- 1С:Предприятие 8.3 (1cv8.exe)
- Доступ к серверным базам 1С

## Быстрый старт

### 1. Установка зависимостей

```bash
cd go-services/batch-service
go mod download
```

### 2. Конфигурация (environment variables)

```bash
# HTTP Server
export SERVER_HOST=0.0.0.0
export SERVER_PORT=8087

# gRPC Gateway (ras-grpc-gw) - для будущего функционала
export GRPC_GATEWAY_ADDR=localhost:9999

# 1cv8.exe path
export EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"
export V8_DEFAULT_TIMEOUT=300  # seconds (5 minutes)
```

### 3. Запуск

```bash
go run cmd/main.go
```

Сервер запустится на `http://localhost:8087`

## API Endpoints

### Health Check

```bash
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "batch-service",
  "version": "1.0.0"
}
```

### Extension Storage (internal)

> Эти endpoints используются Orchestrator’ом. Остальные операции (install/delete/rollback/backups) выполняются event-driven через Redis Streams.

```bash
POST   /storage/upload
GET    /storage/list
GET    /storage/:name/metadata
DELETE /storage/:name
GET    /metadata/:file
```

## Архитектура

```
cmd/
  └── main.go              # Entry point
internal/
  ├── api/
  │   ├── router.go        # Route configuration
  │   └── handlers/
  │       ├── storage.go   # Storage handlers
  │       └── metadata.go  # Metadata extraction handlers
  ├── service/
  │   └── extension_installer.go # Business logic (uses v8platform/api)
  ├── models/
  │   └── extension.go     # Request/Response models
  └── config/
      └── config.go        # Configuration
```

## Зависимости

- `github.com/gin-gonic/gin` - HTTP framework
- `github.com/v8platform/api` - 1C platform API wrapper

## Development

### Сборка

```bash
go build -o batch-service.exe cmd/main.go
```

### Тесты

```bash
go test ./...
```

### Форматирование

```bash
go fmt ./...
```

## Roadmap

- [x] Phase 1: Базовая структура
- [x] Phase 2: Extension storage + metadata API
- [ ] Phase 4: MonitoringService через ras-grpc-gw
- [ ] Phase 5: Интеграция с Orchestrator

## Лицензия

Часть проекта CommandCenter1C
