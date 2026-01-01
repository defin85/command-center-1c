# Batch Service Sprint 1 - Testing Guide

> Руководство по тестированию реализованных endpoint'ов для Sprint 1 (Priority 1)

**Дата:** 2025-11-08
**Sprint:** 1 (Priority 1 - Базовый CRUD)
**Реализованные задачи:** DeleteExtension, ListExtensions, Validator, Error handling, Django integration

---

## Запуск сервиса

```bash
cd /c/1CProject/command-center-1c

# Запустить batch-service
./scripts/dev/restart-all.sh --service=batch-service

# Проверить что сервис запущен
curl http://localhost:8087/health
```

**Ожидаемый ответ:**
```json
{
  "status": "healthy",
  "service": "batch-service",
  "version": "1.0.0"
}
```

---

## 1. DeleteExtension endpoint

**Endpoint:** `POST /api/v1/extensions/delete`

**Пример запроса:**
```bash
curl -X POST http://localhost:8087/api/v1/extensions/delete \
  -H "Content-Type: application/json" \
  -d '{
    "server": "localhost:1541",
    "infobase_name": "dev",
    "username": "admin",
    "password": "password",
    "extension_name": "ODataAutoConfig"
  }'
```

**Успешный ответ (200 OK):**
```json
{
  "message": "Extension deleted successfully",
  "extension_name": "ODataAutoConfig"
}
```

**Ошибка - расширение не найдено (500):**
```json
{
  "error": "ERR_EXTENSION_NOT_FOUND: Extension not found in infobase (details: ...)"
}
```

**Ошибка - неверный пароль (500):**
```json
{
  "error": "ERR_AUTH_FAILED: Authentication failed (details: ...)"
}
```

---

## 2. ListExtensions endpoint

**Endpoint:** `GET /api/v1/extensions/list`

**Пример запроса:**
```bash
curl -X GET "http://localhost:8087/api/v1/extensions/list?server=localhost:1541&infobase_name=dev&username=admin&password=password"
```

**Успешный ответ (200 OK):**
```json
{
  "extensions": [],
  "count": 0,
  "warning": "ListExtensions is using stub implementation. ConfigurationRepositoryReport format requires empirical testing on real 1C database."
}
```

**Примечание:** ListExtensions сейчас возвращает пустой список с предупреждением, так как парсинг ConfigurationRepositoryReport требует эмпирического тестирования на реальной базе 1С. Это указано в коде с TODO комментарием.

---

## 3. Validator для .cfe файлов

Валидатор автоматически используется в Install endpoint.

**Тест 1: Валидный файл**
```bash
# Создать тестовый .cfe файл
echo "test content" > /tmp/test_extension.cfe

curl -X POST http://localhost:8087/api/v1/extensions/install \
  -H "Content-Type: application/json" \
  -d '{
    "server": "localhost:1541",
    "infobase_name": "dev",
    "username": "admin",
    "password": "password",
    "extension_path": "/tmp/test_extension.cfe",
    "extension_name": "TestExtension",
    "update_db_config": true
  }'
```

**Тест 2: Файл не существует (400 Bad Request)**
```bash
curl -X POST http://localhost:8087/api/v1/extensions/install \
  -H "Content-Type: application/json" \
  -d '{
    "server": "localhost:1541",
    "infobase_name": "dev",
    "username": "admin",
    "password": "password",
    "extension_path": "/tmp/nonexistent.cfe",
    "extension_name": "Test",
    "update_db_config": true
  }'
```

**Ожидаемый ответ:**
```json
{
  "error": "File validation failed: file not found: /tmp/nonexistent.cfe"
}
```

**Тест 3: Path traversal атака (400 Bad Request)**
```bash
curl -X POST http://localhost:8087/api/v1/extensions/install \
  -H "Content-Type: application/json" \
  -d '{
    "server": "localhost:1541",
    "infobase_name": "dev",
    "username": "admin",
    "password": "password",
    "extension_path": "../../etc/passwd",
    "extension_name": "Test",
    "update_db_config": true
  }'
```

**Ожидаемый ответ:**
```json
{
  "error": "File validation failed: invalid path: contains '..' (path traversal detected)"
}
```

**Тест 4: Неправильное расширение (400 Bad Request)**
```bash
curl -X POST http://localhost:8087/api/v1/extensions/install \
  -H "Content-Type: application/json" \
  -d '{
    "server": "localhost:1541",
    "infobase_name": "dev",
    "username": "admin",
    "password": "password",
    "extension_path": "/tmp/test.txt",
    "extension_name": "Test",
    "update_db_config": true
  }'
```

**Ожидаемый ответ:**
```json
{
  "error": "File validation failed: invalid file extension (must be .cfe)"
}
```

---

## 4. Error handling

Structured errors возвращаются для всех операций.

**Тест - база не найдена:**
```bash
curl -X POST http://localhost:8087/api/v1/extensions/delete \
  -H "Content-Type: application/json" \
  -d '{
    "server": "localhost:1541",
    "infobase_name": "nonexistent",
    "username": "admin",
    "password": "password",
    "extension_name": "Test"
  }'
```

**Ожидаемый ответ:**
```json
{
  "error": "ERR_INFOBASE_NOT_FOUND: Infobase not found (details: ...)"
}
```

---

## 5. Django integration

**Предварительная настройка:**
```bash
# Убедитесь что Django Orchestrator запущен
./scripts/dev/restart-all.sh --service=orchestrator

# Проверить что callback endpoint доступен
curl http://localhost:8000/api/v1/databases/extensions/installation/callback/
# Ожидается: 405 Method Not Allowed (потому что нужен POST)
```

**Тест callback вручную (имитация batch-service → Django):**
```bash
curl -X POST http://localhost:8000/api/v1/databases/extensions/installation/callback/ \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": "some-uuid-here",
    "extension_name": "TestExtension",
    "status": "completed",
    "duration_seconds": 45.5,
    "error_message": null
  }'
```

**Ожидаемый ответ (если installation существует):**
```json
{
  "status": "ok"
}
```

**Ожидаемый ответ (если installation не найден):**
```json
{
  "error": "No pending installation found for database some-uuid-here and extension TestExtension"
}
```

---

## Переменные окружения

Добавьте в `.env.local`:
```bash
# Batch Service Configuration
ORCHESTRATOR_URL=http://localhost:8000
PLATFORM_1C_BIN_PATH=C:\Program Files\1cv8\8.3.27.1786\bin
V8_DEFAULT_TIMEOUT=300
```

---

## Созданные файлы

**Go сервисы (batch-service):**
- `internal/service/extension_deleter.go` - DeleteExtension логика
- `internal/service/extension_lister.go` - ListExtensions логика (stub)
- `internal/service/extension_validator.go` - Валидация .cfe файлов
- `internal/api/handlers/delete.go` - DELETE endpoint handler
- `internal/api/handlers/list.go` - LIST endpoint handler
- `pkg/v8errors/parser.go` - Structured error handling
- `internal/infrastructure/django/client.go` - Django HTTP client
- `cmd/main.go` - Обновлен (инициализация новых сервисов)
- `internal/api/router.go` - Обновлен (новые routes)
- `internal/config/config.go` - Обновлен (ORCHESTRATOR_URL)

**Django (orchestrator):**
- `apps/databases/views.py` - Добавлен `installation_callback` view
- `apps/databases/urls.py` - Добавлен URL для callback

**Документация:**
- `docs/BATCH_SERVICE_SPRINT1_TESTING.md` - Этот файл

---

## Статус задач Sprint 1

| Задача | Статус | Комментарий |
|--------|--------|-------------|
| DeleteExtension endpoint | ✅ Completed | Полностью реализовано |
| ListExtensions endpoint | ✅ Completed | Stub реализация с TODO для парсинга |
| Validator для .cfe | ✅ Completed | Path traversal защита, size limits |
| Error handling | ✅ Completed | Structured errors с кодами |
| Django integration | ✅ Completed | Callback механизм реализован |

---

## Следующие шаги (Sprint 2+)

**Sprint 2:**
- Реализовать парсинг ConfigurationRepositoryReport для ListExtensions
- Добавить retry logic с exponential backoff
- Async job tracking для batch операций

**Sprint 3:**
- UpdateExtension с проверкой версий
- Batch delete endpoint
- Production-ready features

**Sprint 4 (опционально):**
- Extension storage (upload/download)
- Metadata extraction
- Rollback механизм

---

**Версия:** 1.0
**Автор:** Claude (AI Coder)
**Дата создания:** 2025-11-08
