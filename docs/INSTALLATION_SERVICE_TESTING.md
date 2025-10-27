# Installation Service - Testing Guide

**Проект:** CommandCenter1C
**Версия:** 1.0
**Дата:** 2025-10-27

---

## Обзор

Полное руководство по тестированию Installation Service - системы автоматизации установки OData расширений на 700 баз 1С:Бухгалтерия 3.0.

---

## Тестирование компонентов

### 1. Django Backend Testing

#### 1.1. Unit Tests

**Запуск тестов:**
```bash
cd orchestrator

# Запустить все тесты приложения databases
python manage.py test apps.databases.tests.test_extension_installation

# Запустить с coverage
coverage run --source='apps.databases' manage.py test apps.databases
coverage report
coverage html  # Генерирует HTML отчет в htmlcov/

# Целевое покрытие: > 80%
```

**Что тестируется:**
- Модель `ExtensionInstallation` (создание, обновление, constraints)
- Serializers (валидация, десериализация)
- API endpoints (permissions, responses)
- Celery tasks (queue_extension_installation, subscribe_installation_progress)

#### 1.2. API Endpoints Testing

**Предварительные требования:**
- Django development server запущен
- PostgreSQL доступен
- Redis доступен
- Создан API token для авторизации

**Получение токена:**
```bash
cd orchestrator
python manage.py createsuperuser
# Username: admin
# Password: admin123

# В Django shell
python manage.py shell
>>> from rest_framework.authtoken.models import Token
>>> from django.contrib.auth import get_user_model
>>> user = get_user_model().objects.get(username='admin')
>>> token = Token.objects.create(user=user)
>>> print(token.key)
YOUR_API_TOKEN_HERE
```

**Тест 1: Запуск массовой установки (все базы)**

```bash
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -d '{
    "database_ids": "all",
    "extension_config": {
      "name": "ODataAutoConfig",
      "path": "C:\\Extensions\\ODataAutoConfig.cfe"
    }
  }'
```

Ожидаемый ответ:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_databases": 700,
  "status": "queued"
}
```

**Тест 2: Запуск установки на выборочные базы**

```bash
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -d '{
    "database_ids": [1, 2, 3, 4, 5],
    "extension_config": {
      "name": "ODataAutoConfig",
      "path": "C:\\Extensions\\ODataAutoConfig.cfe"
    }
  }'
```

Ожидаемый ответ:
```json
{
  "task_id": "661f9511-f3ac-42e5-b827-557766551111",
  "total_databases": 5,
  "status": "queued"
}
```

**Тест 3: Проверка прогресса установки**

```bash
curl http://localhost:8000/api/v1/databases/installation-progress/YOUR_TASK_ID/ \
  -H "Authorization: Token YOUR_API_TOKEN"
```

Ожидаемый ответ:
```json
{
  "total": 700,
  "completed": 450,
  "failed": 15,
  "in_progress": 10,
  "pending": 225,
  "progress_percent": 66.4,
  "estimated_time_remaining": 1800
}
```

**Тест 4: Получение статуса конкретной базы**

```bash
curl http://localhost:8000/api/v1/databases/1/extension-status/ \
  -H "Authorization: Token YOUR_API_TOKEN"
```

Ожидаемый ответ:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "database_id": 1,
  "database_name": "Base001",
  "extension_name": "ODataAutoConfig",
  "status": "completed",
  "started_at": "2025-10-27T12:00:00Z",
  "completed_at": "2025-10-27T12:00:45Z",
  "error_message": null,
  "duration_seconds": 45,
  "retry_count": 0
}
```

**Тест 5: Повтор неудачной установки**

```bash
curl -X POST http://localhost:8000/api/v1/databases/1/retry-installation/ \
  -H "Authorization: Token YOUR_API_TOKEN"
```

Ожидаемый ответ:
```json
{
  "task_id": "772g0622-g4bd-53f6-c938-668877662222"
}
```

#### 1.3. Celery Tasks Testing

**Тест 1: Проверка очереди Redis**

```bash
# Запустить Celery worker
cd orchestrator
celery -A orchestrator worker -l debug

# В другом терминале - отправить тестовую задачу
redis-cli LLEN installation_tasks
# Должно быть 0 изначально

# Запустить установку через API
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -d '{"database_ids": [1,2,3], "extension_config": {"name": "Test", "path": "C:\\test.cfe"}}'

# Проверить что задачи добавлены в queue
redis-cli LLEN installation_tasks
# Должно быть 3
```

**Тест 2: Проверка pub/sub подписки**

```bash
# Терминал 1: Подписаться на канал прогресса
redis-cli SUBSCRIBE installation_progress

# Терминал 2: Запустить Installation Service (он будет публиковать события)
cd installation-service
make run

# Терминал 3: Отправить тестовую задачу
redis-cli LPUSH installation_tasks '{
  "task_id": "test-1",
  "database_id": 1,
  "database_name": "TestDB",
  "connection_string": "/S\"localhost\\TestDB\"",
  "username": "Admin",
  "password": "",
  "extension_path": "C:\\Extensions\\Test.cfe",
  "extension_name": "TestExtension",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}'

# В терминале 1 должны появиться события:
# - task_started
# - task_completed (или task_failed)
```

---

### 2. Go Installation Service Testing

#### 2.1. Unit Tests

**Запуск тестов:**
```bash
cd installation-service

# Запустить все тесты
make test

# Или напрямую
go test ./... -v

# С coverage
go test ./... -coverprofile=coverage.out
go tool cover -html=coverage.out -o coverage.html
```

**Результат (целевые метрики):**
```
PASS
coverage: 85.0% of statements
ok      github.com/commandcenter1c/commandcenter/installation-service/internal/config    0.045s
ok      github.com/commandcenter1c/commandcenter/installation-service/internal/executor  0.089s
```

**Что тестируется:**
- `internal/config`: Загрузка конфигурации, валидация, env overrides
- `internal/executor`: Worker pool, task execution, graceful shutdown
- `internal/onec`: 1cv8.exe wrapper, retry logic, timeout handling
- `internal/progress`: Redis pub/sub publisher

#### 2.2. Integration Tests с Redis

**Предварительные требования:**
- Redis server запущен на localhost:6379
- Настроен `config.yaml`

**Тест 1: Подключение к Redis**

```bash
# Запустить Redis
docker run -d -p 6379:6379 redis:7

# Или на Windows (если установлен)
redis-server.exe

# Проверить доступность
redis-cli PING
# Ожидаемый ответ: PONG

# Запустить Installation Service
cd installation-service
make run

# В логах должно быть:
# {"level":"info","message":"Connected to Redis"}
# {"level":"info","message":"Progress publisher connected to Redis"}
# {"level":"info","workers":10,"message":"Starting worker pool"}
```

**Тест 2: Обработка тестовой задачи**

```bash
# Терминал 1: Подписаться на события
redis-cli SUBSCRIBE installation_progress

# Терминал 2: Запустить Installation Service
cd installation-service
make run

# Терминал 3: Отправить задачу
redis-cli LPUSH installation_tasks '{
  "task_id": "integration-test-1",
  "database_id": 999,
  "database_name": "IntegrationTestDB",
  "connection_string": "/S\"localhost\\IntegrationTestDB\"",
  "username": "Admin",
  "password": "",
  "extension_path": "C:\\Extensions\\Test.cfe",
  "extension_name": "TestExtension",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}'

# Проверить что задача забрана из queue
redis-cli LLEN installation_tasks
# Должно стать 0

# В терминале 1 должны появиться события:
# 1) "message"
# 2) "installation_progress"
# 3) "{"event":"task_started","task_id":"integration-test-1",...}"
# ...
# 3) "{"event":"task_completed","task_id":"integration-test-1","status":"success",...}"
```

**Тест 3: Health Check**

```bash
# Installation Service должен быть запущен
curl http://localhost:5555/health

# Ожидаемый ответ (если Redis доступен):
{
  "status": "healthy",
  "redis_connected": true,
  "timestamp": "2025-10-27T12:00:00Z"
}

# Если Redis недоступен:
{
  "status": "unhealthy",
  "redis_connected": false,
  "error": "connection refused",
  "timestamp": "2025-10-27T12:00:00Z"
}
```

---

### 3. End-to-End Testing (10-20 тестовых баз)

#### 3.1. Подготовка тестового окружения

**Шаг 1: Создание тестовых баз 1С**

На test 1C Server:
```bash
# Создать 10 тестовых SQL баз
# База 1: /S"test-server\TestDB001"
# База 2: /S"test-server\TestDB002"
# ...
# База 10: /S"test-server\TestDB010"
```

**Шаг 2: Добавить тестовые базы в Django Orchestrator**

```python
# В Django shell
python manage.py shell

from apps.databases.models import Database

test_bases = [
    {"name": f"TestDB{i:03d}", "server_name": "test-server",
     "database_name": f"TestDB{i:03d}", "username": "ODataUser",
     "password": "encrypted_password"}
    for i in range(1, 11)
]

for base in test_bases:
    Database.objects.create(**base)
```

**Шаг 3: Подготовить тестовый CFE файл**

Создать минимальное расширение:
- Название: `TestExtension`
- Файл: `C:\Extensions\TestExtension.cfe`
- Содержимое: Пустое расширение (только для теста)

**Шаг 4: Настроить config.yaml для test окружения**

```yaml
redis:
  host: "test-redis.local"
  port: 6379

onec:
  platform_path: "C:\\Program Files\\1cv8\\8.3.23.1912\\bin\\1cv8.exe"
  server_name: "test-server"
  timeout_seconds: 300

executor:
  max_parallel: 5  # Меньше для test окружения
  retry_attempts: 2
```

#### 3.2. Запуск E2E теста

**Шаг 1: Запустить все сервисы**

```bash
# Терминал 1: PostgreSQL + Redis
docker-compose up -d postgres redis

# Терминал 2: Django Orchestrator
cd orchestrator
python manage.py migrate
python manage.py runserver

# Терминал 3: Celery Worker
cd orchestrator
celery -A orchestrator worker -l info

# Терминал 4: Installation Service (Windows Server)
cd installation-service
.\bin\installation-service.exe

# Терминал 5: Frontend (опционально)
cd frontend
npm start
```

**Шаг 2: Запустить установку через UI**

1. Открыть http://localhost:3000/installation-monitor
2. Нажать "Install Extension on Selected Databases"
3. Выбрать тестовые базы (TestDB001 - TestDB010)
4. Ввести параметры:
   - Extension name: `TestExtension`
   - Extension path: `C:\Extensions\TestExtension.cfe`
5. Подтвердить установку
6. Наблюдать real-time прогресс

**Шаг 3: Мониторинг прогресса**

```bash
# Проверить прогресс через API
curl http://localhost:8000/api/v1/databases/installation-progress/TASK_ID/

# Проверить логи Installation Service
tail -f C:\Logs\installation-service.log

# Проверить события в Redis
redis-cli SUBSCRIBE installation_progress

# Проверить queue depth
redis-cli LLEN installation_tasks
```

**Шаг 4: Верификация результатов**

```bash
# Проверить статусы в БД
cd orchestrator
python manage.py shell

from apps.databases.models import ExtensionInstallation
installations = ExtensionInstallation.objects.all()
print(f"Total: {installations.count()}")
print(f"Completed: {installations.filter(status='completed').count()}")
print(f"Failed: {installations.filter(status='failed').count()}")

# Проверить OData endpoints (если расширение настраивает OData)
curl http://test-server/TestDB001/odata/standard.odata/Catalog_Users
```

#### 3.3. Критерии успешного E2E теста

- ✅ Все задачи попадают в Redis queue
- ✅ Go service забирает задачи из queue
- ✅ 1cv8.exe вызывается корректно
- ✅ События публикуются в Redis pub/sub
- ✅ Django Celery worker получает события
- ✅ БД обновляется с корректными статусами
- ✅ Frontend отображает real-time прогресс
- ✅ Success rate ≥ 90% (9+ из 10 баз)
- ✅ Среднее время установки < 60 секунд на базу
- ✅ Retry работает для failed установок

---

### 4. Нагрузочное тестирование (100 баз)

#### 4.1. Цель

Проверить параллелизм, производительность и стабильность системы под нагрузкой.

#### 4.2. Подготовка

**Вариант 1: Реальные базы (если доступно)**
- Создать 100 тестовых баз на test 1C Server
- Добавить в Django Orchestrator

**Вариант 2: Mock базы**
- Использовать моки (не выполнять реальную установку)
- Настроить Installation Service с коротким timeout

#### 4.3. Конфигурация для нагрузочного теста

```yaml
executor:
  max_parallel: 10  # 10 одновременных установок
  retry_attempts: 3
  retry_delay_seconds: 30
  task_timeout_seconds: 300

logging:
  level: "info"  # Не debug (performance)
```

#### 4.4. Запуск нагрузочного теста

```bash
# 1. Запустить все сервисы
docker-compose up -d

# 2. Запустить Installation Service
cd installation-service
make run

# 3. Отправить задачи на 100 баз через API
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -H "Authorization: Token YOUR_API_TOKEN" \
  -d '{
    "database_ids": "all",  # Если 100 баз в БД
    "extension_config": {
      "name": "LoadTestExtension",
      "path": "C:\\Extensions\\LoadTest.cfe"
    }
  }'

# 4. Начать мониторинг
```

#### 4.5. Мониторинг метрик

**CPU/Memory на Windows Server:**
```powershell
# PowerShell - мониторинг каждые 5 секунд
while ($true) {
    Get-Process installation-service | Select-Object CPU, WorkingSet
    Start-Sleep -Seconds 5
}

# Или через Performance Monitor
perfmon
# Добавить счетчики:
# - Processor: % Processor Time
# - Memory: Available MBytes
# - Process (installation-service): Working Set
```

**CPU/Memory на 1C Server:**
```bash
# Linux
top -p $(pgrep rphost)

# Windows
tasklist /FI "IMAGENAME eq rphost.exe"
```

**Redis Queue Depth:**
```bash
# Мониторинг queue depth каждые 2 секунды
watch -n 2 "redis-cli LLEN installation_tasks"

# Или в цикле
while true; do
  echo "Queue depth: $(redis-cli LLEN installation_tasks)"
  sleep 2
done
```

**Throughput (баз/час):**
```bash
# Записать timestamp начала
START_TIME=$(date +%s)

# После завершения всех задач
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
THROUGHPUT=$((100 * 3600 / DURATION))
echo "Throughput: $THROUGHPUT баз/час"
```

#### 4.6. Ожидаемые метрики

| Метрика | Целевое значение | Критичное значение |
|---------|------------------|--------------------|
| Throughput | 10-50 баз/час | < 5 баз/час |
| Latency per base | < 60 секунд | > 120 секунд |
| Success rate | ≥ 95% | < 90% |
| CPU Windows Server | < 80% | > 95% |
| Memory Windows Server | < 90% | > 95% |
| CPU 1C Server | < 80% | > 95% |
| Redis Queue Depth (max) | < 100 | > 500 |

#### 4.7. Анализ результатов

После завершения нагрузочного теста:

```python
# Django shell - анализ результатов
from apps.databases.models import ExtensionInstallation
from django.db.models import Avg, Count

results = ExtensionInstallation.objects.all()

print("=== Load Test Results ===")
print(f"Total installations: {results.count()}")
print(f"Success rate: {results.filter(status='completed').count() / results.count() * 100:.1f}%")
print(f"Average duration: {results.aggregate(Avg('duration_seconds'))['duration_seconds__avg']:.1f}s")
print(f"Failed: {results.filter(status='failed').count()}")
print(f"Retry attempts: {results.aggregate(Avg('retry_count'))['retry_count__avg']:.1f}")

# Группировка по статусам
print("\n=== Status Distribution ===")
status_dist = results.values('status').annotate(count=Count('id'))
for item in status_dist:
    print(f"{item['status']}: {item['count']}")
```

---

### 5. Error Scenarios Testing

#### 5.1. Неверные credentials

**Тест:**
```bash
# Создать базу с неверными credentials
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -d '{
    "database_ids": [999],
    "extension_config": {"name": "Test", "path": "C:\\test.cfe"}
  }'

# Для базы 999 установить неверный пароль в БД
```

**Ожидаемый результат:**
- Installation Service пытается подключиться
- 1cv8.exe возвращает ошибку аутентификации
- Статус: `task_failed`
- Error message: "Authentication failed" или "Access denied"
- Retry: 3 попытки (все неудачные)

**Проверка:**
```bash
curl http://localhost:8000/api/v1/databases/999/extension-status/
# status: "failed"
# error_message: "Authentication failed..."
# retry_count: 3
```

#### 5.2. Недоступность 1C Server

**Тест:**
```bash
# Остановить 1C Server
# На Windows Server:
net stop "1C:Enterprise Server Agent"

# Или на Linux:
systemctl stop srv1cv8

# Отправить задачу установки
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -d '{"database_ids": [1], "extension_config": {...}}'
```

**Ожидаемый результат:**
- Connection timeout после 300 секунд
- Retry механизм срабатывает
- После 3 попыток: `task_failed`
- Error message: "Connection timeout" или "Server unavailable"

**Проверка:**
```bash
# Проверить логи Installation Service
tail -f C:\Logs\installation-service.log
# Должны быть сообщения:
# - "Attempt 1/3 failed: timeout"
# - "Attempt 2/3 failed: timeout"
# - "Attempt 3/3 failed: timeout"
# - "Task failed after 3 retries"
```

#### 5.3. База заблокирована пользователем

**Тест:**
```bash
# 1. Открыть базу в 1С:Предприятие (пользователь Admin)
# (монопольный режим или активная сессия)

# 2. Попытаться установить расширение
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -d '{"database_ids": [1], "extension_config": {...}}'
```

**Ожидаемый результат:**
- Первая попытка: timeout (база занята)
- Retry с задержкой 30 секунд
- Если база освободилась: success
- Если нет: повтор до 3 попыток

**Проверка:**
```bash
# Мониторинг прогресса
curl http://localhost:8000/api/v1/databases/installation-progress/TASK_ID/

# Проверить retry_count
curl http://localhost:8000/api/v1/databases/1/extension-status/
# retry_count: 1, 2, или 3
```

#### 5.4. Redis connection lost

**Тест:**
```bash
# 1. Запустить Installation Service
cd installation-service
make run

# 2. Во время работы остановить Redis
docker stop redis
# Или
net stop Redis

# 3. Подождать 30 секунд

# 4. Проверить логи
tail -f C:\Logs\installation-service.log
```

**Ожидаемый результат:**
- Reconnect logic срабатывает
- Логи содержат: "Redis connection lost, reconnecting..."
- После восстановления Redis: "Reconnected to Redis"
- Graceful degradation (сервис продолжает работать с текущими задачами)

**Проверка:**
```bash
# Health check должен показать unhealthy
curl http://localhost:5555/health
# {"status": "unhealthy", "redis_connected": false}

# После восстановления Redis
docker start redis

# Health check должен восстановиться
curl http://localhost:5555/health
# {"status": "healthy", "redis_connected": true}
```

#### 5.5. Некорректный CFE файл

**Тест:**
```bash
curl -X POST http://localhost:8000/api/v1/databases/batch-install-extension/ \
  -d '{
    "database_ids": [1],
    "extension_config": {
      "name": "Test",
      "path": "C:\\NonExistent\\File.cfe"
    }
  }'
```

**Ожидаемый результат:**
- 1cv8.exe возвращает ошибку "File not found"
- Статус: `task_failed` (без retry, т.к. ошибка не временная)
- Error message: "Extension file not found: C:\NonExistent\File.cfe"

**Проверка:**
```bash
curl http://localhost:8000/api/v1/databases/1/extension-status/
# status: "failed"
# error_message: "Extension file not found..."
# retry_count: 0  # Не ретраится для file not found
```

---

## Критерии успешного тестирования

### Unit Tests
- ✅ Django: все тесты проходят, coverage ≥ 80%
- ✅ Go: coverage ≥ 85%, все тесты PASS
- ✅ Frontend: компоненты рендерятся без ошибок

### Integration Tests
- ✅ Успешная установка на 10 тестовых баз
- ✅ Real-time обновления в UI работают
- ✅ Корректные статусы в PostgreSQL БД
- ✅ Redis pub/sub доставляет события

### Load Tests (100 баз)
- ✅ Throughput: 10-50 баз/час
- ✅ Success rate: ≥ 95%
- ✅ CPU Windows Server: < 80%
- ✅ Memory Windows Server: < 90%
- ✅ Система стабильна под нагрузкой

### Error Handling
- ✅ Все 5 error scenarios обработаны корректно
- ✅ Retry logic работает (3 попытки)
- ✅ Graceful degradation при недоступности Redis
- ✅ Детальные error messages в логах и БД

---

## Troubleshooting

### Проблема: Тесты падают с "connection refused"

**Решение:**
```bash
# Проверить что Redis запущен
redis-cli PING

# Проверить что PostgreSQL запущен
psql -U postgres -c "SELECT 1"

# Проверить настройки подключения в config
cat config.yaml | grep -A 5 "redis:"
```

### Проблема: Unit tests проходят, но integration тесты падают

**Решение:**
```bash
# Проверить версии зависимостей
cd installation-service
go mod verify

# Очистить кеш и пересобрать
make clean
make build

# Проверить логи на наличие ошибок
tail -f C:\Logs\installation-service.log
```

### Проблема: Низкий success rate в нагрузочных тестах

**Решение:**
1. Уменьшить `max_parallel` (с 10 до 5)
2. Увеличить `timeout_seconds` (с 300 до 600)
3. Проверить нагрузку на 1C Server (может быть перегружен)
4. Проверить network latency между Windows Server и 1C Server

---

## Следующие шаги после успешного тестирования

1. ✅ Code review (Reviewer)
2. ✅ Документирование результатов тестирования
3. ✅ Подготовка к deployment (см. `INSTALLATION_SERVICE_DEPLOYMENT.md`)
4. ✅ Pilot на 50 базах (production-like окружение)
5. ✅ Production deployment на 700 баз

---

**Версия:** 1.0
**Последнее обновление:** 2025-10-27
