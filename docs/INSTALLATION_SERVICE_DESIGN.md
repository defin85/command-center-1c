# Installation Service - Детальный план реализации

**Дата:** 2025-10-27
**Проект:** CommandCenter1C
**Версия:** 1.0
**Статус:** Утверждено

---

## Утвержденное решение

✅ **Архитектура:** Вариант A - Windows Service (изолированный)
✅ **Технология:** Go + 1cv8.exe CLI
✅ **Инфраструктура:** Windows Server 2022 (существующий)

---

## Обзор проблемы

### Контекст

CommandCenter1C требует автоматизации настройки OData публикаций для 700 баз 1С:Бухгалтерия 3.0 (SQL bases).

**Текущая проблема:**
- OData требует ручной настройки через Конфигуратор в каждой базе
- Ручная настройка 700 баз = недели работы

**Требуемое решение:**
- Автоматическая установка CFE расширения "ODataAutoConfig" на все базы
- Время установки: < 2 часов
- Параллельная обработка: минимум 10 баз одновременно
- Real-time мониторинг прогресса в UI
- Интеграция с существующей архитектурой CommandCenter1C

### Связанные документы

- `docs/TZ_ODATA_AUTOMATION.md` - Исходное техническое задание
- `CLAUDE.md` - Архитектура проекта
- `docs/ROADMAP.md` - Общий roadmap проекта

---

## Архитектура решения

### Высокоуровневая диаграмма

```
┌─────────────────────────────────────────────────────────────────────────┐
│                             LINUX INFRASTRUCTURE                         │
│  ┌─────────────┐       ┌──────────────┐       ┌─────────────┐          │
│  │   Frontend  │◄─WS───┤  API Gateway │◄─HTTP─┤ Orchestrator│          │
│  │   (React)   │       │     (Go)     │       │   (Django)  │          │
│  └─────────────┘       └──────────────┘       └──────┬──────┘          │
│                                                        │                 │
│                                                 ┌──────▼──────┐          │
│                                                 │   Celery    │          │
│                                                 │   Worker    │          │
│                                                 └──────┬──────┘          │
│                                                        │                 │
│                        ┌───────────────────────────────▼───────────┐    │
│                        │          Redis Queue                      │    │
│                        │  [installation_tasks]                     │    │
│                        └───────────────────────────────────────────┘    │
└────────────────────────────────────────┬───────────────────────────────┘
                                         │ Redis protocol (pub/sub + queue)
                                         │
┌────────────────────────────────────────▼───────────────────────────────┐
│                        WINDOWS INSTALLATION NODE                        │
│                         (Windows Server 2022)                           │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │      Windows Installation Service (Go)                     │        │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │        │
│  │  │ Redis Client │  │ Task Executor│  │ Progress Pub │     │        │
│  │  │  (Consumer)  │  │   (10 pool)  │  │   (Redis)    │     │        │
│  │  └──────┬───────┘  └──────┬───────┘  └──────▲───────┘     │        │
│  │         │                  │                  │             │        │
│  │         └──────────────────▼──────────────────┘             │        │
│  │                      Task Queue                             │        │
│  └─────────────────────────────┬──────────────────────────────┘        │
│                                 │                                        │
│  ┌──────────────────────────────▼──────────────────────────────┐       │
│  │              1C Automation Layer                             │       │
│  │  ┌──────────────────────────────────────────────┐           │       │
│  │  │     1cv8.exe (CONFIG mode)                   │           │       │
│  │  │  - LoadCfg (загрузка CFE)                    │           │       │
│  │  │  - UpdateDBCfg (применение расширения)       │           │       │
│  │  └─────────────────┬────────────────────────────┘           │       │
│  └────────────────────┼─────────────────────────────────────────       │
│                       │                                                 │
│  ┌────────────────────▼──────────────────────────────────┐             │
│  │            1C Server (srvr1c)                          │             │
│  │  ╔════════════════════════════════════════════════╗   │             │
│  │  ║  База #1  ║  База #2  ║ ... ║  База #700      ║   │             │
│  │  ║  (SQL)    ║  (SQL)    ║ ... ║  (SQL)          ║   │             │
│  │  ╚════════════════════════════════════════════════╝   │             │
│  └────────────────────────────────────────────────────────             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Поток работы (end-to-end)

```
1. User (Frontend): Кликает "Установить OData на все базы"
   ↓
2. Frontend → API Gateway: POST /api/v1/databases/batch-install-extension/
   ↓
3. API Gateway → Orchestrator: Forward request
   ↓
4. Orchestrator: Создает Celery task
   ↓
5. Celery Worker: Публикует 700 задач в Redis queue "installation_tasks"
   ↓
6. Installation Service (Windows): Long polling Redis queue
   ↓
7. Installation Service: Забирает 10 задач параллельно
   ↓
8. Go Worker: Запускает 1cv8.exe CONFIG для каждой базы
   ↓
9. 1cv8.exe: Подключается к 1C Server → устанавливает CFE
   ↓
10. Installation Service: Публикует прогресс → Redis pub/sub
    ↓
11. Orchestrator: Subscribe Redis → обновляет БД → WebSocket → Frontend
    ↓
12. Frontend: Обновляет UI (real-time): "450/700 (64%)"
    ↓
13. Повтор шагов 7-12 для всех 700 баз
    ↓
14. Завершение: Installation Service обновляет финальный статус через API
```

---

## Компоненты системы

### 1. Go микросервис `installation-service` (Windows Server 2022)

#### Структура проекта

```
command-center-1c/
└── installation-service/              # Новый компонент
    ├── cmd/
    │   └── main.go                    # Entry point
    ├── internal/
    │   ├── config/
    │   │   ├── config.go              # Конфигурация (Redis, 1C paths)
    │   │   └── config_test.go
    │   ├── queue/
    │   │   ├── consumer.go            # Redis queue consumer
    │   │   └── consumer_test.go
    │   ├── executor/
    │   │   ├── pool.go                # Worker pool (10 горутин)
    │   │   ├── task.go                # Task execution logic
    │   │   └── executor_test.go
    │   ├── onec/
    │   │   ├── installer.go           # 1cv8.exe wrapper
    │   │   ├── connection.go          # Формирование строки подключения
    │   │   └── onec_test.go
    │   └── progress/
    │       ├── publisher.go           # Redis pub/sub для прогресса
    │       └── publisher_test.go
    ├── config.yaml                    # Конфигурация
    ├── config.example.yaml            # Пример конфигурации
    ├── Dockerfile.windows             # Для Windows containers (опционально)
    ├── go.mod
    ├── go.sum
    ├── Makefile
    └── README.md
```

#### Ключевые операции

1. **Подключение к Redis queue** (`installation_tasks`)
2. **Параллельная обработка** 10 задач (configurable)
3. **Вызов 1cv8.exe:**
   ```bash
   1cv8.exe CONFIG /S"server\base" /N"user" /P"pwd"
            /LoadCfg "ext.cfe" -Extension "ODataAutoConfig"
   1cv8.exe CONFIG /S"server\base" /N"user" /P"pwd"
            /UpdateDBCfg -Extension "ODataAutoConfig"
   ```
4. **Публикация прогресса** в Redis pub/sub (`installation_progress`)
5. **HTTP health check endpoint** (`:5555/health`)

#### Конфигурация (config.yaml)

```yaml
redis:
  host: "redis.commandcenter.local"   # или IP Linux хоста
  port: 6379
  password: ""                         # если требуется
  queue: "installation_tasks"
  progress_channel: "installation_progress"
  db: 0

onec:
  platform_path: "C:\\Program Files\\1cv8\\8.3.23.1912\\bin\\1cv8.exe"
  timeout_seconds: 300
  server_name: "server1c"              # Имя 1C Server

executor:
  max_parallel: 10                     # Количество горутин
  retry_attempts: 3
  retry_delay_seconds: 30

orchestrator:
  api_url: "http://orchestrator.local:8000"
  api_token: "${INSTALLATION_SERVICE_TOKEN}"

server:
  health_check_port: 5555

logging:
  level: "info"                        # debug, info, warn, error
  file: "C:\\Logs\\installation-service.log"
  max_size_mb: 100
  max_backups: 5
  max_age_days: 30
```

---

### 2. Django Orchestrator - расширение (Backend)

#### Новые файлы

```python
orchestrator/apps/databases/
├── models.py                          # + ExtensionInstallation model
├── serializers.py                     # + ExtensionInstallationSerializer
├── views.py                           # + новые endpoints
├── tasks.py                           # + Celery tasks
└── migrations/
    └── 00XX_extension_installation.py
```

#### Новая модель

```python
# orchestrator/apps/databases/models.py

class ExtensionInstallation(models.Model):
    """Статус установки расширения на базу 1С"""

    database = models.ForeignKey(
        Database,
        on_delete=models.CASCADE,
        related_name='extension_installations'
    )
    extension_name = models.CharField(
        max_length=255,
        default="ODataAutoConfig"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("failed", "Failed")
        ],
        default="pending"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'databases_extension_installation'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['database', 'extension_name']),
        ]

    def __str__(self):
        return f"{self.extension_name} on {self.database.name} - {self.status}"
```

#### Новые API endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/api/v1/databases/batch-install-extension/` | Массовая установка расширения |
| GET | `/api/v1/databases/installation-progress/{task_id}/` | Real-time прогресс установки |
| GET | `/api/v1/databases/{id}/extension-status/` | Статус установки для конкретной базы |
| POST | `/api/v1/databases/{id}/retry-installation/` | Повторить неудачную установку |

#### Celery task

```python
# orchestrator/apps/databases/tasks.py

@shared_task
def queue_extension_installation(database_ids: List[int], extension_config: dict):
    """
    Отправляет задачи установки расширения в Redis queue
    для Windows Installation Service

    Args:
        database_ids: Список ID баз для установки
        extension_config: {
            "name": "ODataAutoConfig",
            "path": "C:\\Extensions\\ODataAutoConfig.cfe"
        }
    """
    redis_client = get_redis_client()

    for db_id in database_ids:
        try:
            db = Database.objects.get(id=db_id)

            # Создать запись об установке
            installation = ExtensionInstallation.objects.create(
                database=db,
                extension_name=extension_config["name"],
                status="pending"
            )

            # Подготовить задачу для Windows Service
            task_data = {
                "task_id": str(installation.id),
                "database_id": db.id,
                "connection_string": f'/S"{db.server_name}\\{db.database_name}"',
                "username": db.username,
                "password": decrypt_password(db.password_encrypted),
                "extension_path": extension_config["path"],
                "extension_name": extension_config["name"]
            }

            # Отправить в Redis queue
            redis_client.lpush("installation_tasks", json.dumps(task_data))

        except Database.DoesNotExist:
            logger.error(f"Database {db_id} not found")
            continue
        except Exception as e:
            logger.error(f"Error queuing installation for database {db_id}: {e}")
            continue

    return {
        "status": "queued",
        "total_tasks": len(database_ids)
    }


@shared_task
def subscribe_installation_progress():
    """
    Подписывается на Redis pub/sub канал для обновления прогресса установки
    Запускается как фоновый Celery worker
    """
    redis_client = get_redis_client()
    pubsub = redis_client.pubsub()
    pubsub.subscribe("installation_progress")

    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                data = json.loads(message['data'])
                update_installation_status(data)

                # Отправить обновление через WebSocket
                send_websocket_update(data)

            except Exception as e:
                logger.error(f"Error processing progress message: {e}")
```

---

### 3. Frontend - UI для мониторинга (React)

#### Новые компоненты

```typescript
frontend/src/
├── pages/
│   └── InstallationMonitorPage.tsx    # Страница мониторинга установки
├── components/
│   ├── InstallationProgressBar.tsx    # Прогресс-бар (real-time)
│   ├── InstallationStatusTable.tsx    # Таблица со статусами баз
│   └── BatchInstallButton.tsx         # Кнопка "Установить OData"
└── api/
    └── installation.ts                # API клиент
```

#### Основной функционал

1. **Кнопка запуска установки** - в Django Admin или отдельная страница
2. **WebSocket подключение** для real-time обновлений
3. **Прогресс-бар:** "Установлено 450/700 (64%)"
4. **Таблица детализации:**
   - База данных
   - Статус (pending/in_progress/completed/failed)
   - Время выполнения
   - Сообщение об ошибке
5. **Фильтры:** Все / Успешные / Неудачные
6. **Кнопка "Повторить"** для failed установок

---

## Технические детали

### Формат команды 1cv8.exe

```bash
# Шаг 1: Загрузка CFE расширения
"C:\Program Files\1cv8\8.3.23.1912\bin\1cv8.exe" CONFIG ^
  /S"server1c\BaseName" ^
  /N"ODataUser" ^
  /P"password" ^
  /LoadCfg "C:\Extensions\ODataAutoConfig.cfe" ^
  -Extension "ODataAutoConfig"

# Шаг 2: Обновление конфигурации БД (применение расширения)
"C:\Program Files\1cv8\8.3.23.1912\bin\1cv8.exe" CONFIG ^
  /S"server1c\BaseName" ^
  /N"ODataUser" ^
  /P"password" ^
  /UpdateDBCfg ^
  -Extension "ODataAutoConfig"
```

**Важные параметры:**
- `/S"server\base"` - подключение к SQL базе через сервер приложений
- `/N"user"` - имя пользователя 1С
- `/P"password"` - пароль пользователя
- `/LoadCfg` - загрузка конфигурации/расширения из файла
- `/UpdateDBCfg` - обновление конфигурации БД
- `-Extension "Name"` - указывает что это расширение, а не конфигурация

### Формат задачи в Redis queue

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": 123,
  "connection_string": "/S\"server1c\\Base001\"",
  "username": "ODataUser",
  "password": "decrypted_password",
  "extension_path": "C:\\Extensions\\ODataAutoConfig.cfe",
  "extension_name": "ODataAutoConfig"
}
```

### Формат прогресса в Redis pub/sub

```json
{
  "event": "task_completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": 123,
  "database_name": "Base001",
  "status": "success",
  "duration_seconds": 45,
  "timestamp": "2025-10-27T12:30:00Z",
  "error_message": null
}
```

**События:**
- `task_started` - началась установка на базу
- `task_progress` - промежуточный прогресс (если доступно)
- `task_completed` - успешное завершение
- `task_failed` - ошибка установки

---

## План реализации (8 дней)

### Этап 1: Django Backend (1.5 дня)

**Задачи:**
- [ ] Создать модель `ExtensionInstallation` + миграция
- [ ] Создать serializers для API
- [ ] Реализовать endpoints:
  - `POST /batch-install-extension/`
  - `GET /installation-progress/{task_id}/`
  - `GET /{id}/extension-status/`
  - `POST /{id}/retry-installation/`
- [ ] Реализовать Celery tasks:
  - `queue_extension_installation`
  - `subscribe_installation_progress`
- [ ] Настроить Redis pub/sub subscriber
- [ ] Unit tests для API

**Зависимости:** Нет

**Deliverables:**
- Миграция БД применена
- API endpoints доступны и протестированы
- Celery tasks работают

---

### Этап 2: Go Installation Service - Core (2 дня)

**Задачи:**
- [ ] Инициализировать Go модуль `installation-service`
- [ ] Реализовать `internal/config` - чтение config.yaml
- [ ] Реализовать `internal/queue/consumer.go`:
  - Redis client подключение
  - Long polling queue "installation_tasks"
  - Парсинг задач из JSON
  - Error handling и reconnect logic
- [ ] Реализовать `internal/executor/pool.go`:
  - Worker pool с 10 горутинами
  - Task queue (channel)
  - Graceful shutdown (context cancellation)
  - Concurrent safe operations
- [ ] Health check endpoint HTTP server (`:5555/health`)
- [ ] Логирование (zerolog или logrus)
- [ ] Unit tests

**Зависимости:** Нет (можно параллельно с Этапом 1)

**Deliverables:**
- Go сервис компилируется
- Подключается к Redis
- Health check endpoint работает
- Тесты проходят

---

### Этап 3: Go Installation Service - 1C Integration (1.5 дня)

**Задачи:**
- [ ] Реализовать `internal/onec/installer.go`:
  - Функция `InstallExtension(task Task) error`
  - Формирование команды `1cv8.exe CONFIG ...`
  - Выполнение через `exec.Command`
  - Обработка stdout/stderr
  - Timeout control (300 сек)
  - Retry механизм (3 попытки с exponential backoff)
  - Детальное логирование каждого шага
- [ ] Реализовать `internal/onec/connection.go`:
  - Формирование строки подключения `/S"server\base"`
  - Валидация параметров (server name, base name, credentials)
  - Escape специальных символов в строке подключения
- [ ] Интеграционные тесты:
  - Mock 1cv8.exe для тестирования
  - Тест успешной установки
  - Тест timeout
  - Тест retry logic

**Зависимости:** Этап 2

**Deliverables:**
- Успешный вызов 1cv8.exe
- Обработка всех edge cases
- Логи содержат полную информацию
- Тесты покрывают все сценарии

---

### Этап 4: Go Installation Service - Progress Tracking (1 день)

**Задачи:**
- [ ] Реализовать `internal/progress/publisher.go`:
  - Redis pub/sub client
  - Публикация событий:
    - `task_started` (task_id, db_id, timestamp)
    - `task_progress` (task_id, db_id, status, percentage)
    - `task_completed` (task_id, db_id, duration, status)
    - `task_failed` (task_id, db_id, error_message)
  - Buffered channel для async публикации
  - Error handling при недоступности Redis
- [ ] Интеграция с executor:
  - Отправка события перед началом задачи
  - Отправка события после завершения (success/failure)
  - Отправка промежуточных обновлений (если доступно)
- [ ] HTTP endpoint для финального обновления статуса в Orchestrator:
  - `POST /api/update-status` (вызывается из Go service → Django API)
- [ ] Unit tests

**Зависимости:** Этап 3

**Deliverables:**
- События публикуются в Redis
- Django Orchestrator получает события
- HTTP callbacks работают
- Тесты проходят

---

### Этап 5: Frontend UI (1 день)

**Задачи:**
- [ ] Создать `InstallationMonitorPage.tsx`:
  - Layout страницы
  - Кнопка "Установить OData на все базы"
  - Confirmation dialog с предупреждением
  - API call → `POST /batch-install-extension/`
  - Навигация после запуска
- [ ] Создать `InstallationProgressBar.tsx`:
  - WebSocket подключение к Orchestrator
  - Real-time обновление прогресса
  - Показать: "Установлено X/700 (Y%)"
  - Animated progress bar
  - ETA (estimated time of arrival)
- [ ] Создать `InstallationStatusTable.tsx`:
  - Таблица со всеми базами (Ant Design Table)
  - Колонки: ID, База, Статус, Время, Длительность, Ошибка
  - Status badges с цветами
  - Фильтры: Все / В процессе / Успешные / Неудачные
  - Поиск по имени базы
  - Кнопка "Повторить" для failed (inline action)
  - Пагинация (100 записей на страницу)
- [ ] API клиент (`api/installation.ts`)
- [ ] WebSocket integration
- [ ] Роутинг + навигация

**Зависимости:** Этап 1, Этап 4

**Deliverables:**
- UI страница доступна
- Real-time обновления работают
- Все действия (запуск, повтор) работают
- Responsive design

---

### Этап 6: Testing & Integration (1 день)

**Задачи:**
- [ ] Создать тестовую среду:
  - 10-20 тестовых баз 1С (SQL) на test 1C Server
  - Тестовый CFE файл (минимальное расширение)
  - Настроить config.yaml для test окружения
- [ ] End-to-end тест:
  - Запустить установку через UI (10 баз)
  - Проверить real-time обновления в UI
  - Верифицировать установку расширений в базах
  - Проверить OData endpoints после установки
  - Проверить логи на всех уровнях (Django, Go, Redis)
- [ ] Нагрузочное тестирование:
  - Симуляция установки на 100 баз
  - Проверка параллелизма (10 горутин работают)
  - Мониторинг CPU/Memory на Windows Server
  - Мониторинг 1C Server load
  - Проверка Redis queue depth
- [ ] Error scenarios:
  - Неверные credentials
  - Недоступность 1C Server
  - Timeout (база заблокирована)
  - Redis connection lost
  - Проверка retry logic
- [ ] Исправление багов

**Зависимости:** Этапы 1-5

**Deliverables:**
- Успешная установка на 10-20 тестовых баз
- Нагрузочные тесты пройдены
- Все edge cases обработаны
- Баги исправлены
- Документация обновлена

---

### Этап 7: Deployment (0.5 дня)

**Задачи:**
- [ ] Сборка Go бинарника для Windows:
  ```bash
  GOOS=windows GOARCH=amd64 go build -o installation-service.exe cmd/main.go
  ```
- [ ] Копирование на Windows Server 2022:
  - Бинарник: `C:\Services\installation-service\`
  - Конфигурация: `C:\Services\installation-service\config.yaml`
  - CFE файл: `C:\Extensions\ODataAutoConfig.cfe`
- [ ] Настройка `config.yaml` (production значения):
  - Redis host (production IP)
  - 1C platform path
  - 1C Server name
  - Orchestrator API URL + token
  - Logging paths
- [ ] Создание Windows Service (через NSSM или sc.exe):
  ```bash
  nssm install InstallationService "C:\Services\installation-service\installation-service.exe"
  nssm set InstallationService AppDirectory "C:\Services\installation-service"
  nssm set InstallationService Start SERVICE_AUTO_START
  ```
- [ ] Настройка автозапуска + recovery policy
- [ ] Проверка подключения:
  - Redis connectivity test
  - 1C Server connectivity test
  - Orchestrator API test
- [ ] Настройка Windows Firewall (открыть порт 5555 для health check)
- [ ] Настройка логирования (log rotation)

**Зависимости:** Этап 6

**Deliverables:**
- Windows Service установлен и запущен
- Health check endpoint доступен
- Логи пишутся корректно
- Автозапуск настроен

---

### Этап 8: Pilot & Production (1 день)

**Задачи:**

#### Pilot (50 баз):
- [ ] Выбрать 50 тестовых баз (не критичные для бизнеса)
- [ ] Создать backup баз (опционально, если возможно откатить)
- [ ] Запланировать установку в нерабочее время
- [ ] Запустить установку через UI
- [ ] Мониторинг прогресса:
  - Отслеживать логи Installation Service
  - Отслеживать CPU/Memory на Windows Server и 1C Server
  - Отслеживать UI (real-time updates)
- [ ] Проверка результатов:
  - Верифицировать OData endpoints на всех 50 базах
  - Проверить, что расширения активны
  - Тест запросов к OData
- [ ] Анализ ошибок:
  - Собрать все failed установки
  - Определить причины (credentials, timeout, etc.)
  - Исправить проблемы
  - Повторить failed установки
- [ ] Измерение метрик:
  - Среднее время установки на базу
  - Success rate (цель: ≥ 95%)
  - Пиковая нагрузка на серверы

#### Production (700 баз):
- [ ] Финальная проверка всех систем
- [ ] Запланировать установку в ночное время (минимальная нагрузка)
- [ ] Уведомить команду о начале установки
- [ ] Запустить массовую установку на все 700 баз
- [ ] Continuous мониторинг:
  - Dashboard с real-time прогрессом
  - Алерты при критичных ошибках
  - Логи в реальном времени
- [ ] Время выполнения: ~2 часа (700 баз / 10 параллельно × 60 сек/база)
- [ ] Post-deployment verification:
  - Подсчет успешных установок (цель: ≥ 665 из 700)
  - Список всех failed установок
  - Верификация OData endpoints (выборочная проверка 50-100 баз)
  - Проверка регистрации баз в Orchestrator (API)
- [ ] Обработка failed установок:
  - Анализ причин
  - Retry с исправлением проблем
  - Ручная установка для проблемных баз (если необходимо)
- [ ] Документирование:
  - Итоговый отчет (success rate, время, проблемы)
  - Lessons learned
  - Рекомендации для будущих массовых операций

**Зависимости:** Этап 7

**Deliverables:**
- Pilot успешно завершен (≥ 95% success rate на 50 базах)
- Production установка завершена (≥ 665 из 700 баз)
- OData endpoints доступны и работают
- Отчет о результатах
- Документация обновлена

---

## Метрики успеха

| Метрика | Целевое значение | Как измерять |
|---------|------------------|--------------|
| **Throughput** | 10-50 баз/час | Installation Service logs (completed tasks per hour) |
| **Latency (per base)** | < 60 секунд | `task_completed.duration_seconds` в Redis events |
| **Success Rate** | ≥ 95% (665+ из 700) | `ExtensionInstallation.status = "completed"` count |
| **Total Time (700 bases)** | < 3 часа | Pilot measurement → production target |
| **Retry Success** | ≥ 50% failed → success | Retry attempts logging и final success rate |
| **System Load** | CPU < 80%, Memory < 90% | Prometheus/Performance Monitor на Windows Server |
| **Redis Queue Depth** | < 100 (в пике) | Redis INFO command, `llen installation_tasks` |
| **Error Rate** | < 5% fatal errors | Error logs count / total tasks |

---

## Риски и митигация

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **1cv8.exe зависает на базе** | Средняя | Высокое | Timeout 300 сек + `exec.Command.Kill()`. Retry механизм (3 попытки). Логирование зависших баз для ручной обработки. |
| **Неверные credentials для баз** | Средняя | Среднее | Валидация credentials перед queue. Test connection в Orchestrator при добавлении базы. Централизованное хранение credentials. |
| **Блокировки баз пользователями** | Высокая | Среднее | Установка в ночное время (02:00-06:00). Проверка монопольного режима перед установкой. Retry с увеличенной задержкой (30 сек → 60 сек → 120 сек). |
| **Network timeout (1C Server недоступен)** | Низкая | Высокое | Connection pooling. Health check 1C Server перед началом массовой установки. Алерты при недоступности. Автоматическая остановка queue при критичных ошибках. |
| **Redis connection lost** | Низкая | Высокое | Reconnect logic с exponential backoff. Буферизация events при недоступности Redis. Health check Redis перед запуском. |
| **Перегрузка 1C Server** | Средняя | Высокое | Начать с `max_parallel: 5` на pilot. Мониторинг CPU/Memory 1C Server. Динамическая регулировка параллелизма (throttling). Circuit breaker при высокой нагрузке. |
| **Недостаточно места на диске (логи)** | Низкая | Среднее | Log rotation настроен (max 100MB × 5 файлов). Мониторинг disk space. Архивация старых логов. |
| **CFE файл поврежден/недоступен** | Низкая | Критичное | Проверка MD5 checksum перед началом. Backup копия CFE на нескольких серверах. Валидация CFE перед массовой установкой (test на 1 базе). |

---

## Нефункциональные требования

### Производительность

- **Latency:** < 60 секунд на установку в одну базу
- **Throughput:** 10-50 баз в час (зависит от `max_parallel`)
- **Scalability:** Поддержка до 1000 баз без архитектурных изменений

### Надежность

- **Availability:** 99% (Windows Service должен работать постоянно)
- **Retry logic:** 3 попытки с exponential backoff
- **Graceful shutdown:** Завершение текущих задач перед остановкой сервиса
- **Data consistency:** Статус в БД должен соответствовать реальности

### Безопасность

- **Credentials:** Хранение паролей в зашифрованном виде (Django)
- **API token:** Installation Service использует токен для вызовов Orchestrator API
- **Network:** Firewall правила (только необходимые порты)
- **Audit log:** Все операции логируются с timestamp и user context

### Мониторинг и Observability

- **Логирование:**
  - Structured logs (JSON format)
  - Log levels: DEBUG, INFO, WARN, ERROR
  - Rotation: max 100MB × 5 backups
- **Метрики:** (Phase 3 - интеграция с Prometheus)
  - Tasks processed (counter)
  - Task duration (histogram)
  - Error rate (gauge)
  - Queue depth (gauge)
- **Health checks:**
  - HTTP endpoint `/health` (200 OK / 503 Service Unavailable)
  - Redis connectivity
  - Disk space

### Maintenance

- **Deployment:** Single binary deployment (Go)
- **Configuration:** YAML файл (hot reload не требуется - restart сервиса)
- **Updates:** Graceful restart (завершить текущие задачи → остановить → обновить → запустить)
- **Rollback:** Backup предыдущего бинарника + config

---

## После реализации

### Обновления документации

1. **ТЗ (`docs/TZ_ODATA_AUTOMATION.md`):**
   - Изменить примеры с файловых баз на SQL
   - Обновить `config.json` формат
   - Добавить раздел "Реализация"

2. **Создать эксплуатационную документацию:**
   - `docs/INSTALLATION_SERVICE_GUIDE.md` - руководство по использованию
   - `docs/INSTALLATION_SERVICE_TROUBLESHOOTING.md` - частые проблемы и решения
   - `docs/INSTALLATION_SERVICE_DEPLOYMENT.md` - deployment процедура

3. **Обновить `CLAUDE.md`:**
   - Добавить Installation Service в архитектурную диаграмму
   - Обновить список компонентов системы

4. **Обновить `docs/ROADMAP.md`:**
   - Installation Service = Phase 0 (prerequisite)
   - Отметить как completed

### Мониторинг (Phase 3)

После завершения Phase 3 (Monitoring & Observability):

1. **Prometheus метрики для Installation Service:**
   ```
   installation_service_tasks_total{status="completed|failed"}
   installation_service_task_duration_seconds{quantile="0.5|0.9|0.99"}
   installation_service_queue_depth
   installation_service_errors_total
   installation_service_up
   ```

2. **Grafana dashboard:**
   - Real-time queue depth
   - Task completion rate
   - Average task duration
   - Error rate
   - 1C Server CPU/Memory (если доступно)

3. **Алерты:**
   - Installation Service down
   - Error rate > 10%
   - Queue depth > 500 (backlog)
   - Task duration > 5 минут (зависание)

### Будущие улучшения

1. **Dynamic scaling:**
   - Автоматическое увеличение `max_parallel` при низкой нагрузке
   - Throttling при высокой нагрузке на 1C Server

2. **Advanced scheduling:**
   - Cron-based массовые установки
   - Поддержка maintenance windows для каждой базы

3. **Multi-server support:**
   - Поддержка нескольких 1C Servers
   - Load balancing между серверами

4. **Extension versioning:**
   - Поддержка обновления расширений (не только установка)
   - Rollback расширений
   - Version management

5. **Advanced monitoring:**
   - Интеграция с 1C технологическим журналом
   - Детальная аналитика производительности
   - Предсказание проблемных баз (ML)

---

## Контакты и роли

| Роль | Ответственность | Контакт |
|------|-----------------|---------|
| **Project Owner** | Утверждение архитектуры, приоритеты | [Имя] |
| **Architect** | Архитектурное проектирование | [Имя] |
| **Backend Developer (Django)** | Django Orchestrator расширение | [Имя] |
| **Backend Developer (Go)** | Installation Service | [Имя] |
| **Frontend Developer** | React UI для мониторинга | [Имя] |
| **DevOps Engineer** | Deployment, infrastructure | [Имя] |
| **QA Engineer** | Testing, verification | [Имя] |
| **1C Administrator** | 1C Server, базы, credentials | [Имя] |

---

## Приложения

### A. Формат JSON для задачи

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": 123,
  "database_name": "Base001",
  "connection_string": "/S\"server1c\\Base001\"",
  "username": "ODataUser",
  "password": "P@ssw0rd123",
  "extension_path": "C:\\Extensions\\ODataAutoConfig.cfe",
  "extension_name": "ODataAutoConfig",
  "retry_count": 0,
  "created_at": "2025-10-27T12:00:00Z"
}
```

### B. Формат JSON для прогресса

```json
{
  "event": "task_completed",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "database_id": 123,
  "database_name": "Base001",
  "status": "success",
  "duration_seconds": 45,
  "timestamp": "2025-10-27T12:00:45Z",
  "error_message": null,
  "metadata": {
    "retry_count": 0,
    "1c_version": "8.3.23.1912"
  }
}
```

### C. Пример config.yaml (production)

```yaml
redis:
  host: "10.0.1.50"                    # Production Redis IP
  port: 6379
  password: "${REDIS_PASSWORD}"
  queue: "installation_tasks"
  progress_channel: "installation_progress"
  db: 0
  max_retries: 3
  retry_delay_seconds: 5

onec:
  platform_path: "C:\\Program Files\\1cv8\\8.3.23.1912\\bin\\1cv8.exe"
  timeout_seconds: 300
  server_name: "prod-1c-server"
  kill_timeout_seconds: 30

executor:
  max_parallel: 10
  retry_attempts: 3
  retry_delay_seconds: 30
  retry_backoff_multiplier: 2          # 30s, 60s, 120s
  task_timeout_seconds: 600

orchestrator:
  api_url: "http://10.0.1.51:8000"    # Production Orchestrator IP
  api_token: "${INSTALLATION_SERVICE_TOKEN}"
  timeout_seconds: 30

server:
  health_check_port: 5555
  shutdown_timeout_seconds: 300        # Время на завершение текущих задач

logging:
  level: "info"
  file: "C:\\Logs\\installation-service.log"
  max_size_mb: 100
  max_backups: 5
  max_age_days: 30
  compress: true
```

### D. Windows Service установка (NSSM)

```powershell
# Скачать NSSM: https://nssm.cc/download
# Установить в C:\Tools\nssm\

# Создать сервис
C:\Tools\nssm\nssm.exe install InstallationService "C:\Services\installation-service\installation-service.exe"

# Настроить сервис
C:\Tools\nssm\nssm.exe set InstallationService AppDirectory "C:\Services\installation-service"
C:\Tools\nssm\nssm.exe set InstallationService DisplayName "1C Installation Service"
C:\Tools\nssm\nssm.exe set InstallationService Description "Automated 1C OData extension installation service"
C:\Tools\nssm\nssm.exe set InstallationService Start SERVICE_AUTO_START

# Настроить логирование
C:\Tools\nssm\nssm.exe set InstallationService AppStdout "C:\Logs\installation-service-stdout.log"
C:\Tools\nssm\nssm.exe set InstallationService AppStderr "C:\Logs\installation-service-stderr.log"

# Настроить recovery (автоматический перезапуск при падении)
C:\Tools\nssm\nssm.exe set InstallationService AppExit Default Restart
C:\Tools\nssm\nssm.exe set InstallationService AppRestartDelay 5000

# Запустить сервис
C:\Tools\nssm\nssm.exe start InstallationService

# Проверить статус
C:\Tools\nssm\nssm.exe status InstallationService
```

---

## Changelog

| Версия | Дата | Автор | Изменения |
|--------|------|-------|-----------|
| 1.0 | 2025-10-27 | Architect + Orchestrator | Initial version - детальный план реализации |

---

**Утверждено для реализации:** 2025-10-27
**Срок реализации:** 8 рабочих дней
**Следующие шаги:** Запуск Coder → Reviewer pipeline
