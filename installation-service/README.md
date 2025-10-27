# Installation Service

Go микросервис для автоматической установки расширений 1С через `1cv8.exe` на Windows Server.

## Обзор

Installation Service - компонент системы CommandCenter1C, отвечающий за массовую установку расширений (CFE) в базы 1С:Бухгалтерия 3.0.

**Ключевые возможности:**
- Параллельная обработка до 50 баз одновременно
- Интеграция с Redis queue для получения задач
- Health check endpoint для мониторинга
- Graceful shutdown с завершением текущих задач
- Автоматические retry при ошибках

## Архитектура

```
Redis Queue → Consumer → Worker Pool (10 goroutines) → 1cv8.exe → 1C Bases
                              ↓
                        Progress Publisher → Redis Pub/Sub → Orchestrator
```

### Текущий статус: Stage 4 (Progress Tracking) ✅

**Реализовано:**
- ✅ Конфигурация (YAML + environment variables)
- ✅ Redis queue consumer (BRPOP)
- ✅ Worker pool с параллельной обработкой
- ✅ Task definition и result handling
- ✅ Health check HTTP endpoint
- ✅ Graceful shutdown
- ✅ Интеграция с 1cv8.exe (real installation via CONFIG mode)
- ✅ Retry механизм с exponential backoff
- ✅ Timeout handling (context-based)
- ✅ Безопасное логирование (пароли маскируются)
- ✅ Redis pub/sub для progress tracking
- ✅ Progress events (task_started, task_completed, task_failed)
- ✅ Unit tests для progress publisher

**TODO (Stage 5):**
- ⏳ HTTP callback в Django Orchestrator (опционально)
- ⏳ File logging with rotation

## Быстрый старт

### Требования

- Go 1.21+
- Redis 7+
- Windows Server 2022 (для production)
- 1C Platform 8.3.23+ установлен

### Установка

```bash
# Клонировать репозиторий
cd installation-service

# Скачать зависимости
make deps

# Скопировать конфигурацию
cp config.example.yaml config.yaml

# Отредактировать config.yaml под свое окружение
# Минимум: redis.host, onec.platform_path, orchestrator.api_token
```

### Конфигурация

Отредактируйте `config.yaml`:

```yaml
redis:
  host: "localhost"              # Redis server
  port: 6379
  queue: "installation_tasks"    # Queue name

onec:
  platform_path: "C:\\Program Files\\1cv8\\8.3.23.1912\\bin\\1cv8.exe"
  timeout_seconds: 300           # Timeout for each 1cv8.exe operation
  server_name: "server1c"        # 1C Server name for connection strings

executor:
  max_parallel: 10               # Parallel workers
  retry_attempts: 3              # Number of retry attempts for failed installations
  retry_delay_seconds: 30        # Initial delay between retries (exponential backoff)

orchestrator:
  api_url: "http://localhost:8000"
  api_token: "your-token-here"   # Get from Django admin
```

#### 1C Platform Configuration

- `platform_path`: Полный путь к исполняемому файлу 1cv8.exe (должен быть доступен для чтения и выполнения)
- `timeout_seconds`: Максимальное время выполнения каждой операции (LoadCfg, UpdateDBCfg). По умолчанию 300 секунд (5 минут)
- `server_name`: Имя 1C Server для формирования строк подключения

**Пример строки подключения:** `/S"server1c\DatabaseName"`

**Важно:**
- Путь к 1cv8.exe должен быть корректным и доступным
- Timeout должен учитывать размер CFE файла и скорость сети
- 1C Server должен быть доступен по сетевому имени

**Progress Channel:**
```yaml
redis:
  progress_channel: "installation_progress"  # Pub/sub channel for progress events
```

**Environment variables (optional):**
- `REDIS_HOST` - overrides redis.host
- `REDIS_PASSWORD` - overrides redis.password
- `INSTALLATION_SERVICE_TOKEN` - overrides orchestrator.api_token
- `CONFIG_PATH` - path to config file (default: `config.yaml`)

### Запуск

```bash
# Development (runs with go run)
make run

# Build binary first
make build

# Run binary
./bin/installation-service.exe
```

### Health Check

```bash
# Check service health
curl http://localhost:5555/health

# Expected response:
# {"status":"ok","service":"installation-service","version":"1.0.0-stage2"}

# Ready check (for Kubernetes)
curl http://localhost:5555/ready
```

## Разработка

### Структура проекта

```
installation-service/
├── cmd/
│   └── main.go                 # Entry point
├── internal/
│   ├── config/                 # Configuration
│   │   └── config.go
│   ├── queue/                  # Redis consumer
│   │   └── consumer.go
│   ├── executor/               # Worker pool
│   │   ├── task.go
│   │   └── pool.go
│   ├── onec/                   # 1C integration (Stage 3)
│   │   └── installer.go
│   └── progress/               # Progress tracking (Stage 4)
│       └── publisher.go
├── config.yaml                 # Configuration
├── config.example.yaml         # Example configuration
├── Makefile                    # Build automation
├── go.mod
└── README.md
```

### Makefile команды

```bash
make deps          # Download dependencies
make build         # Build binary
make build-windows # Build for Windows (cross-compile)
make run           # Run application
make test          # Run tests
make fmt           # Format code
make vet           # Run go vet
make clean         # Remove build artifacts
make help          # Show all commands
```

### Тестирование

```bash
# Run all tests
make test

# Run tests with coverage
make test-verbose

# View coverage report
open coverage.html
```

### Формат задачи (JSON в Redis queue)

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": 123,
  "database_name": "Base001",
  "connection_string": "/S\"server1c\\Base001\"",
  "username": "ODataUser",
  "password": "P@ssw0rd",
  "extension_path": "C:\\Extensions\\ODataAutoConfig.cfe",
  "extension_name": "ODataAutoConfig",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}
```

### Отправка тестовой задачи в Redis

```bash
# Using redis-cli
redis-cli LPUSH installation_tasks '{
  "task_id": "test-1",
  "database_id": 1,
  "database_name": "TestBase",
  "connection_string": "/S\"localhost\\TestBase\"",
  "username": "Admin",
  "password": "",
  "extension_path": "C:\\Extensions\\Test.cfe",
  "extension_name": "TestExtension",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}'

# Check service logs to see task processing
```

## Progress Tracking

Сервис публикует события прогресса в Redis pub/sub канал для real-time мониторинга:

### События

- `task_started` - Начало выполнения задачи
- `task_completed` - Успешное завершение задачи
- `task_failed` - Ошибка выполнения задачи
- `task_progress` - Промежуточный прогресс (опционально)

### Формат события

```json
{
  "event": "task_completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": 123,
  "database_name": "Base001",
  "status": "success",
  "duration_seconds": 45,
  "timestamp": "2025-10-27T12:00:00Z"
}
```

**Поля события:**
- `event` - тип события (task_started, task_completed, task_failed)
- `task_id` - уникальный идентификатор задачи
- `database_id` - ID базы данных
- `database_name` - имя базы данных (опционально)
- `status` - статус выполнения (in_progress, success, failed)
- `duration_seconds` - длительность выполнения в секундах
- `timestamp` - время события в формате RFC3339
- `error_message` - сообщение об ошибке (только для failed)
- `metadata` - дополнительные данные (опционально)

### Подписка на события

```bash
# Subscribe to progress events
redis-cli SUBSCRIBE installation_progress

# You will see:
# 1) "message"
# 2) "installation_progress"
# 3) "{\"event\":\"task_started\",\"task_id\":\"test-1\",...}"
```

### Использование в Python (Orchestrator)

```python
import redis
import json

# Create Redis client
r = redis.Redis(host='localhost', port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe('installation_progress')

# Listen for events
for message in pubsub.listen():
    if message['type'] == 'message':
        event = json.loads(message['data'])
        print(f"Event: {event['event']}, Task: {event['task_id']}, Status: {event['status']}")

        # Update database
        # Send WebSocket to frontend
        # etc.
```

## Deployment

### Windows Service (Production)

```powershell
# Build for Windows
make build-windows

# Copy to server
Copy-Item bin/installation-service.exe C:\Services\installation-service\
Copy-Item config.yaml C:\Services\installation-service\

# Install as Windows Service (using NSSM)
nssm install InstallationService "C:\Services\installation-service\installation-service.exe"
nssm set InstallationService AppDirectory "C:\Services\installation-service"
nssm set InstallationService Start SERVICE_AUTO_START

# Start service
nssm start InstallationService

# Check status
nssm status InstallationService
```

### Мониторинг

**Логи:**
- Console output (stdout/stderr) для development
- File logging (TODO: Stage 4)

**Metrics (TODO: Stage 3):**
- Prometheus integration
- Grafana dashboards

**Health checks:**
- HTTP endpoint: `http://<host>:5555/health`
- Redis connectivity check
- Readiness probe: `http://<host>:5555/ready`

## Troubleshooting

### Service не запускается

```bash
# Check config file syntax
cat config.yaml

# Check Redis connectivity
redis-cli -h <redis_host> -p 6379 PING

# Check logs
tail -f installation-service.log
```

### Задачи не обрабатываются

```bash
# Check queue depth
redis-cli LLEN installation_tasks

# Check if consumer is connected
curl http://localhost:5555/health

# Check worker pool logs
# Look for "Worker started" messages
```

### 1cv8.exe errors (Stage 3+)

```bash
# Check platform path
ls "C:\Program Files\1cv8\8.3.23.1912\bin\1cv8.exe"

# Check 1C Server availability
# Try manual connection via 1C:Enterprise

# Check credentials in task JSON
# Username/password must be valid
```

## Roadmap

### Stage 2 - Core Implementation ✅
- [x] Configuration system
- [x] Redis queue consumer
- [x] Worker pool
- [x] Health check endpoint
- [x] Graceful shutdown

### Stage 3 - 1C Integration ✅
- [x] 1cv8.exe wrapper (`internal/onec/installer.go`)
- [x] Command builder (/LoadCfg, /UpdateDBCfg)
- [x] Process execution with timeout (context-based)
- [x] Retry mechanism with exponential backoff
- [x] Error handling and logging
- [x] Password sanitization in logs
- [x] Unit tests for core functionality

### Stage 4 - Progress Tracking ✅
- [x] Redis pub/sub publisher (`internal/progress/publisher.go`)
- [x] Progress events (task_started, task_completed, task_failed)
- [x] Integration with executor pool
- [x] Unit tests with miniredis
- [x] Context-aware publishing
- [x] Error handling for publishing failures
- [ ] HTTP callback to Orchestrator (optional)
- [ ] File logging with rotation (optional)

### Stage 5 - Production Hardening
- [ ] Prometheus metrics
- [ ] Advanced error recovery
- [ ] Performance optimization
- [ ] Load testing (700 bases)

## Связанные документы

- [Installation Service Design](../docs/INSTALLATION_SERVICE_DESIGN.md) - Детальный план реализации
- [CLAUDE.md](../CLAUDE.md) - Архитектура CommandCenter1C
- [ROADMAP.md](../docs/ROADMAP.md) - Общий roadmap проекта

## Лицензия

Internal project - CommandCenter1C

## Авторы

CommandCenter1C Development Team
