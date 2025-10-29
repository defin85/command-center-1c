# Installation Service

HTTP API service для получения списка баз 1С через RAC CLI.

## Описание

Installation Service предоставляет REST API для взаимодействия с 1C:Enterprise кластером через утилиту RAC (Remote Administration Console). Сервис работает на Windows и предназначен для интеграции с Django Orchestrator.

## Архитектура

```
Django Orchestrator (Linux) → HTTP → Installation Service (Windows) → rac.exe → 1C RAS
```

## Возможности

- Получение списка информационных баз 1С кластера
- Поддержка кратких и детальных запросов
- Автоматическое декодирование Windows-1251 в UTF-8
- Graceful shutdown
- Health checks

## API Endpoints

### GET /health
Проверка работоспособности сервиса

**Response:**
```json
{
  "status": "ok",
  "service": "installation-service"
}
```

### GET /ready
Проверка готовности сервиса

**Response:**
```json
{
  "status": "ready",
  "service": "installation-service"
}
```

### GET /api/v1/infobases

Получение списка информационных баз

**Query Parameters:**
- `server` - адрес RAS сервера (default: `localhost:1545`)
- `cluster_user` - имя администратора кластера (опционально)
- `cluster_pwd` - пароль администратора кластера (опционально)
- `detailed` - получить детальную информацию (default: `false`)

**Response (Success 200):**
```json
{
  "status": "success",
  "cluster_id": "635eff68-bf69-4e12-a7c9-2967527fc237",
  "cluster_name": "Кластер 1С",
  "total_count": 2,
  "infobases": [
    {
      "uuid": "e1092854-3660-11e7-6b9e-d017c292ea7a",
      "name": "BUH",
      "description": "Бухгалтерия",
      "dbms": "MSSQLServer",
      "db_server": "sql-server\\instance",
      "db_name": "BUH_DB",
      "db_user": "sa",
      "security_level": 0,
      "connection_string": "/S\"server\\BUH\"",
      "locale": "ru"
    }
  ],
  "duration_ms": 1250,
  "timestamp": "2025-10-28T12:00:00Z"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "error": "failed_to_get_cluster_info",
  "message": "Failed to connect to RAS server: connection refused",
  "timestamp": "2025-10-28T12:00:00Z"
}
```

**Error Codes:**
- `invalid_parameter` - неверные параметры запроса (400)
- `cluster_not_found` - кластер не найден (404)
- `rac_not_found` - RAC executable не найден (503)
- `failed_to_connect_to_ras` - не удалось подключиться к RAS (502)
- `request_timeout` - превышен timeout запроса (504)
- `failed_to_get_cluster_info` - ошибка получения информации о кластере (500)
- `failed_to_get_infobase_list` - ошибка получения списка баз (500)

## Конфигурация

### Конфигурационный файл (configs/config.yaml)

```yaml
# RAC Configuration
rac:
  path: "C:\\Program Files\\1cv8\\8.3.27.1786\\bin\\rac.exe"
  timeout_seconds: 180

# API Server Configuration
api_server:
  port: 8085
  shutdown_timeout_seconds: 30

# Logging
log_level: "info"
log_format: "text"
```

### Environment Variables

Переменные окружения переопределяют значения из config.yaml:

- `RAC_PATH` - путь к rac.exe
- `RAC_TIMEOUT_SECONDS` - timeout для RAC команд
- `API_SERVER_PORT` - порт HTTP API сервера
- `API_SERVER_SHUTDOWN_TIMEOUT` - timeout graceful shutdown
- `LOG_LEVEL` - уровень логирования (debug, info, warn, error)
- `LOG_FORMAT` - формат логов (text, json)
- `CONFIG_PATH` - путь к config файлу (default: configs/config.yaml)

## Запуск

### Локально

```bash
# Из директории installation-service
go run cmd/main.go

# Или скомпилированный бинарник
go build -o bin/installation-service.exe ./cmd
./bin/installation-service.exe
```

### С конфигурационным файлом

```bash
CONFIG_PATH=/path/to/config.yaml ./bin/installation-service.exe
```

### С переменными окружения

```bash
RAC_PATH="C:\1C\rac.exe" \
API_SERVER_PORT=9000 \
LOG_LEVEL=debug \
./bin/installation-service.exe
```

## Разработка

### Структура проекта

```
installation-service/
├── cmd/
│   └── main.go              # Entry point
├── internal/
│   ├── api/
│   │   ├── router.go        # Gin router setup
│   │   └── handlers/
│   │       ├── health.go    # Health check handlers
│   │       └── infobases.go # Infobases handlers
│   ├── cluster/
│   │   ├── types.go         # Data types
│   │   ├── manager.go       # ClusterManager interface
│   │   ├── rac_manager.go   # RAC implementation
│   │   └── rac_parser.go    # RAC output parser
│   └── config/
│       └── config.go        # Configuration
├── configs/
│   └── config.yaml          # Configuration file
├── go.mod
├── go.sum
└── README.md
```

### Зависимости

- `github.com/gin-gonic/gin` - HTTP framework
- `golang.org/x/text` - Windows-1251 декодирование
- `gopkg.in/yaml.v3` - YAML конфигурация
- `github.com/commandcenter1c/commandcenter/shared` - Shared utilities (logger)

### Сборка

```bash
go build -o bin/installation-service.exe ./cmd
```

### Тестирование

```bash
go test ./...
```

## Производительность

### Режимы работы

**Summary mode** (`detailed=false`, по умолчанию):
- Быстрый запрос (1-2 секунды)
- Минимальная информация (UUID, Name, Description)
- Одна RAC команда

**Detailed mode** (`detailed=true`):
- Медленный запрос (зависит от количества баз)
- Полная информация (DBMS, DB Server, Connection String и т.д.)
- N+1 RAC команд (1 для списка + N для деталей каждой базы)

### Timeouts

- Per-command timeout: 30 секунд
- Total request timeout: 180 секунд (настраивается)
- Graceful shutdown: 30 секунд (настраивается)

## Интеграция с Django Orchestrator

### Python клиент

```python
import requests

# Получить краткий список баз
response = requests.get(
    "http://windows-server:8085/api/v1/infobases",
    params={"server": "localhost:1545"}
)
data = response.json()

# Получить детальную информацию
response = requests.get(
    "http://windows-server:8085/api/v1/infobases",
    params={
        "server": "localhost:1545",
        "detailed": "true"
    }
)
data = response.json()
```

## Troubleshooting

### RAC executable not found

**Ошибка:** `rac_not_found`

**Решение:**
1. Проверьте путь к rac.exe в конфигурации
2. Убедитесь, что 1C:Enterprise установлен
3. Укажите полный путь через `RAC_PATH` environment variable

### Connection refused

**Ошибка:** `failed_to_connect_to_ras`

**Решение:**
1. Проверьте, что RAS сервер запущен
2. Проверьте адрес и порт RAS сервера
3. Проверьте firewall правила

### Request timeout

**Ошибка:** `request_timeout`

**Решение:**
1. Увеличьте `timeout_seconds` в конфигурации
2. Используйте `detailed=false` для быстрых запросов
3. Проверьте производительность 1C сервера

## License

MIT
