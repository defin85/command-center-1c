# batch-service

Go микросервис для установки расширений в 1С:Предприятие с использованием `v8platform/api`.

## Возможности

- ✅ Установка расширений (.cfe) через REST API
- ✅ Batch установка на множество баз параллельно
- ✅ Использование `v8platform/api` (high-level SDK)
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

---

### Install Extension (Single Base)

```bash
POST /api/v1/extensions/install
Content-Type: application/json
```

**Request Body:**
```json
{
  "server": "localhost:1541",
  "infobase_name": "dev",
  "username": "admin",
  "password": "password",
  "extension_path": "C:\\extensions\\ODataAutoConfig.cfe",
  "extension_name": "ODataAutoConfig",
  "update_db_config": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Extension 'ODataAutoConfig' installed successfully on 'dev'",
  "duration_seconds": 45.2
}
```

---

### Batch Install Extension

```bash
POST /api/v1/extensions/batch-install
Content-Type: application/json
```

**Request Body:**
```json
{
  "infobases": [
    {
      "server": "localhost:1541",
      "infobase_name": "dev",
      "username": "admin",
      "password": "password",
      "extension_path": "C:\\extensions\\ODataAutoConfig.cfe",
      "extension_name": "ODataAutoConfig",
      "update_db_config": true
    },
    {
      "server": "localhost:1541",
      "infobase_name": "delans_unf",
      "username": "admin",
      "password": "password",
      "extension_path": "C:\\extensions\\ODataAutoConfig.cfe",
      "extension_name": "ODataAutoConfig",
      "update_db_config": true
    }
  ],
  "parallel_workers": 10
}
```

**Response:**
```json
{
  "total": 2,
  "success": 2,
  "failed": 0,
  "results": [
    {
      "infobase": "dev",
      "status": "success",
      "duration_seconds": 45.2
    },
    {
      "infobase": "delans_unf",
      "status": "success",
      "duration_seconds": 50.1
    }
  ]
}
```

## Архитектура

```
cmd/
  └── main.go              # Entry point
internal/
  ├── api/
  │   ├── router.go        # Route configuration
  │   └── handlers/
  │       └── extensions.go # HTTP handlers
  ├── service/
  │   └── extension_installer.go # Business logic (uses v8platform/api)
  ├── models/
  │   ├── cluster.go
  │   ├── infobase.go
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
- [x] Phase 2: ExtensionInstaller через v8platform/api
- [x] Phase 3: REST API endpoints
- [ ] Phase 4: MonitoringService через ras-grpc-gw
- [ ] Phase 5: Интеграция с Orchestrator

## Лицензия

Часть проекта CommandCenter1C
