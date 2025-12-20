# CommandCenter1C - Development Scripts

> Коллекция скриптов для локальной разработки и управления сервисами

---

## 📋 Содержание

- [Обзор](#обзор)
- [Быстрый старт](#быстрый-старт)
- [Скрипты](#скрипты)
  - [start-all.sh](#start-allsh) - Запуск всех сервисов
  - [stop-all.sh](#stop-allsh) - Остановка всех сервисов
  - [restart.sh](#restartsh) - Перезапуск одного сервиса
  - [restart-all.sh](#restart-allsh) - Умный перезапуск с автопересборкой
  - [logs.sh](#logssh) - Просмотр логов
  - [health-check.sh](#health-checksh) - Проверка статуса сервисов
  - [build-and-start.sh](#build-and-startsh) - Сборка + запуск
  - [test-lock-unlock-workflow.sh](#test-lock-unlock-workflowsh) - Smoke tests для RAS Adapter (Week 4)
- [Вспомогательные скрипты](#вспомогательные-скрипты)
  - [../build.sh](#buildsh) - Сборка Go сервисов
- [Типичные сценарии](#типичные-сценарии)
- [Troubleshooting](#troubleshooting)

---

## Обзор

Все скрипты находятся в директории `scripts/dev/` и предназначены для локальной разработки в **Hybrid mode** (Docker для инфраструктуры, процессы на хосте для приложений).

**Режим разработки:**
- **Docker:** PostgreSQL, Redis, ClickHouse, Prometheus, Grafana
- **Процессы на хосте:** Django Orchestrator, Celery, Go сервисы, Frontend

**Доступные сервисы:**
- `orchestrator` - Django Orchestrator (port 8000)
- `celery-worker` - Celery Worker
- `celery-beat` - Celery Beat
- `api-gateway` - Go API Gateway (port 8080)
- `worker` - Go Worker
- `ras` - 1C RAS Server (port 1545)
- `ras-adapter` - Go RAS Adapter (port 8088)
- `frontend` - React Frontend (port 5173)

**Мониторинг и Tracing (Docker, автозапуск):**
- `prometheus` - Metrics collection (port 9090)
- `grafana` - Dashboards & visualization (port 5000)
- `jaeger` - Distributed tracing (port 16686)

---

## Быстрый старт

```bash
# 1. Первый запуск (с пересборкой бинарников)
./scripts/dev/build-and-start.sh

# 2. Проверить статус всех сервисов
./scripts/dev/health-check.sh

# 3. Просмотр логов
./scripts/dev/logs.sh api-gateway

# 4. Перезапуск после изменений кода (с автопересборкой)
./scripts/dev/restart-all.sh

# 5. Остановка в конце дня
./scripts/dev/stop-all.sh
```

---

## RAS Adapter

**Status:** ✅ Production

RAS Adapter provides direct RAS protocol integration (khorevaa/ras-client) для Lock/Unlock operations.

**Commands:**
```bash
# Start (included in start-all.sh)
./bin/cc1c-ras-adapter.exe

# Stop
./scripts/dev/stop-all.sh  # stops all services including ras-adapter

# Restart (smart rebuild)
./scripts/dev/restart-all.sh --service=ras-adapter

# Health check
curl http://localhost:8088/health

# Smoke tests
./scripts/dev/test-lock-unlock-workflow.sh
```

**Endpoints:**
- Health: http://localhost:8088/health
- Clusters: http://localhost:8088/api/v2/list-clusters?server=localhost:1545
- Infobases: http://localhost:8088/api/v2/list-infobases?cluster_id={uuid}
- Lock: POST http://localhost:8088/api/v2/lock-infobase?cluster_id={uuid}&infobase_id={uuid}
- Unlock: POST http://localhost:8088/api/v2/unlock-infobase?cluster_id={uuid}&infobase_id={uuid}

**Architecture:**
```
Worker → Redis Pub/Sub → RAS Adapter (8088) → RAS (1545)
                              ↓ khorevaa/ras-client (direct)
```

---

## Скрипты

### start-all.sh

**Назначение:** Запускает все сервисы проекта локально на хост-машине

**Использование:**
```bash
./scripts/dev/start-all.sh
```

**Опции:** Нет

**Что делает:**
1. **Phase 1:** Проверка и пересборка Go сервисов (умная автопересборка измененных)
2. **Phase 2:** Запускает Docker сервисы:
   - Infrastructure: PostgreSQL, Redis, ClickHouse (опционально)
   - **Monitoring: Prometheus, Grafana** ← автоматически!
3. Применяет Django миграции
4. Запускает Python сервисы (orchestrator, celery-worker, celery-beat)
5. Запускает Go сервисы (api-gateway, worker, ras, ras-adapter)
6. Запускает Frontend (React dev server)

**Особенности:**
- **Умная автопересборка:** проверяет изменения в Go коде и пересобирает только измененные сервисы
- **Мониторинг включен:** Prometheus + Grafana запускаются автоматически на шаге [1/12]
- Автоматически создает `.env.local` из `.env.example` если отсутствует
- Сохраняет PID процессов в `pids/`
- Логи сохраняются в `logs/`
- Ожидает готовности PostgreSQL и Redis перед продолжением

**Важно:** Go сервисы должны быть собраны. Скрипт автоматически пересобирает измененные сервисы, либо используйте `--force-rebuild`.

---

### stop-all.sh

**Назначение:** Останавливает все локально запущенные сервисы

**Использование:**
```bash
./scripts/dev/stop-all.sh
```

**Опции:** Нет

**Что делает:**
1. Останавливает application сервисы в **обратном порядке** запуска (reverse dependencies)
2. Использует graceful shutdown (SIGTERM → wait 10s → SIGKILL если не завершился)
3. Удаляет PID файлы
4. **Останавливает Docker infrastructure** (PostgreSQL, Redis)
5. **Останавливает Docker monitoring** (Prometheus, Grafana)
6. Находит и убивает зависшие процессы по портам если PID файлы потеряны

**Порядок остановки:**
```
Application Services:
  frontend → ras-adapter → worker →
  api-gateway → celery-beat → celery-worker → orchestrator

Docker Services:
  PostgreSQL, Redis → Prometheus, Grafana, Jaeger
```

**Важно:** Начиная с версии 2.6, скрипт останавливает **ВСЕ сервисы**, включая мониторинг. Если хотите остановить только мониторинг: `./scripts/dev/stop-monitoring.sh`

---

### restart.sh

**Назначение:** Перезапускает один конкретный сервис

**Использование:**
```bash
./scripts/dev/restart.sh <service-name>
```

**Аргументы:**
- `<service-name>` - имя сервиса (обязательно)

**Опции:** Нет

**Примеры:**
```bash
# Перезапустить API Gateway
./scripts/dev/restart.sh api-gateway

# Перезапустить Orchestrator
./scripts/dev/restart.sh orchestrator

# Перезапустить Frontend
./scripts/dev/restart.sh frontend
```

**Что делает:**
1. Останавливает указанный сервис (graceful shutdown)
2. Загружает переменные окружения из `.env.local`
3. Запускает сервис снова

**⚠️ Важно:** Этот скрипт **НЕ проверяет изменения в коде** и **НЕ пересобирает** Go бинарники. Для умного перезапуска с автопересборкой используйте `restart-all.sh --service=<name>`.

---

### restart-all.sh

**Назначение:** Умный перезапуск всех сервисов с автоматическим определением изменений и выборочной пересборкой Go сервисов

**Использование:**
```bash
./scripts/dev/restart-all.sh [OPTIONS]
```

**Опции:**

| Опция | Описание |
|-------|----------|
| `--help` | Показать справку |
| `--force-rebuild` | Принудительно пересобрать все Go сервисы |
| `--no-rebuild` | Только перезапуск, без проверки/пересборки |
| `--parallel-build` | Параллельная пересборка (быстрее, но сложнее отлаживать) |
| `--service=<name>` | Перезапустить только один сервис (с проверкой изменений) |
| `--verbose` | Детальный вывод для отладки |

**Примеры:**

```bash
# Smart restart (обнаружение изменений + пересборка только измененных)
./scripts/dev/restart-all.sh

# Принудительная пересборка всех Go сервисов + перезапуск
./scripts/dev/restart-all.sh --force-rebuild

# Только перезапуск, без пересборки (если код не менялся)
./scripts/dev/restart-all.sh --no-rebuild

# Перезапуск только API Gateway с проверкой изменений
./scripts/dev/restart-all.sh --service=api-gateway

# Параллельная пересборка (быстрее)
./scripts/dev/restart-all.sh --parallel-build

# Детальный вывод для отладки
./scripts/dev/restart-all.sh --verbose
```

**Как работает умное определение изменений:**

1. **Проверка Go сервисов:**
   - Находит самый новый `.go` файл в директории сервиса
   - Сравнивает timestamp с бинарником
   - Если исходник новее → пересборка нужна

2. **Проверка shared/ модулей:**
   - Если изменился `go-services/shared/` → пересобирает ВСЕ Go сервисы
   - Показывает предупреждение о причине полной пересборки

3. **Выборочная пересборка:**
   - Пересобирает **только измененные** сервисы
   - Экономия времени: **75-89%** в типичных сценариях

**Преимущества:**
- ✅ Автоматическое определение изменений в коде
- ✅ Пересборка только измененных сервисов
- ✅ Решает проблему Windows Firewall (постоянные запросы разрешения)
- ✅ Красивые имена процессов (`cc1c-api-gateway.exe` вместо `main.exe`)
- ✅ Детальные отчеты о том, что изменилось и пересобралось

**Дополнительная документация:** `scripts/dev/RESTART_ALL_GUIDE.md`

---

### logs.sh

**Назначение:** Просмотр логов конкретного сервиса

**Использование:**
```bash
./scripts/dev/logs.sh <service-name> [lines]
```

**Аргументы:**
- `<service-name>` - имя сервиса или `all` для всех логов (обязательно)
- `[lines]` - количество последних строк для показа (опционально, по умолчанию: 50)

**Примеры:**

```bash
# Просмотр логов API Gateway (tail -f)
./scripts/dev/logs.sh api-gateway

# Последние 100 строк логов Orchestrator + follow
./scripts/dev/logs.sh orchestrator 100

# Просмотр всех логов (по 10 строк с каждого сервиса)
./scripts/dev/logs.sh all

# Последние 200 строк логов Worker
./scripts/dev/logs.sh worker 200
```

**Что делает:**
- Открывает лог файл из `logs/<service-name>.log`
- Показывает последние N строк
- Следит за обновлениями в реальном времени (`tail -f`)
- Для `all` показывает сводку по всем сервисам

**Примечание:** Логи сохраняются в директории `logs/` проекта.

---

### health-check.sh

**Назначение:** Проверяет статус всех сервисов

**Использование:**
```bash
./scripts/dev/health-check.sh
```

**Опции:** Нет

**Что делает:**

1. **Проверка процессов по PID файлам:**
   - Читает PID из `pids/<service>.pid`
   - Проверяет что процесс запущен (`kill -0`)
   - Показывает статус каждого сервиса

2. **Проверка HTTP endpoints:**
   - Frontend: `http://localhost:5173`
   - API Gateway: `http://localhost:8080/health`
   - Orchestrator: `http://localhost:8000/health`
   - RAS Adapter: `http://localhost:8088/health`
   - Batch Service: `http://localhost:8087/health`

3. **Проверка Docker сервисов:**
   - PostgreSQL: проверка контейнера + `pg_isready`
   - Redis: проверка контейнера + `redis-cli ping`
   - ClickHouse: проверка контейнера

4. **Проверка мониторинга (опционально):**
   - Prometheus: проверка контейнера + HTTP health endpoint
   - Grafana: проверка контейнера + HTTP health endpoint
   - Если мониторинг не запущен - показывает инструкцию для запуска

**Пример вывода:**
```
========================================
  CommandCenter1C - Health Check
========================================

[1] Проверка локальных процессов:

  orchestrator: ✓ запущен (PID: 12345)
  celery-worker: ✓ запущен (PID: 12346)
  api-gateway: ✓ запущен (PID: 12348)
  ...

[2] Проверка HTTP endpoints:

  Frontend: ✓ доступен (HTTP 200)
  API Gateway: ✓ доступен (HTTP 200)
  ...

[3] Проверка Docker сервисов:

  postgres: ✓ запущен
  redis: ✓ запущен
  ...
```

**Использование:** Запускайте периодически чтобы убедиться что все сервисы работают корректно.

**Важно:** Начиная с версии 2.6, health-check также проверяет мониторинг (Prometheus, Grafana) в секции [6].

---

### start-monitoring.sh

**Назначение:** Запускает Prometheus + Grafana + Jaeger в Docker контейнерах для мониторинга и tracing

**Использование:**
```bash
./scripts/dev/start-monitoring.sh
```

**Опции:** Нет

**Что делает:**
1. Проверяет что Docker запущен
2. Создает сеть `cc1c-local-network` если не существует
3. Запускает Prometheus (`:9090`), Grafana (`:5000`), Jaeger (`:16686`) через `docker-compose.local.monitoring.yml`
4. Выполняет health checks всех сервисов
5. Выводит URL для доступа

**Доступ:**
- Prometheus: http://localhost:9090
- Grafana: http://localhost:5000 (admin/admin)
- Jaeger: http://localhost:16686 (OpenTelemetry Tracing)
- OTLP gRPC: localhost:4317
- OTLP HTTP: localhost:4318

**Примечание:** Мониторинг теперь **запускается автоматически** с `start-all.sh`. Используйте этот скрипт только если хотите запустить мониторинг отдельно без остальных сервисов.

---

### stop-monitoring.sh

**Назначение:** Останавливает Prometheus + Grafana + Jaeger контейнеры

**Использование:**
```bash
./scripts/dev/stop-monitoring.sh
```

**Опции:** Нет

**Что делает:**
1. Останавливает контейнеры `cc1c-prometheus-local`, `cc1c-grafana-local`, `cc1c-jaeger-local`
2. Удаляет контейнеры
3. **Сохраняет данные** в volumes: `cc1c-prometheus-local-data`, `cc1c-grafana-local-data`

**Примечание:**
- Данные НЕ удаляются, так что метрики и дашборды сохранятся при следующем запуске
- Jaeger использует in-memory storage (данные не сохраняются между перезапусками)
- `stop-all.sh` теперь **автоматически** вызывает `stop-monitoring.sh`

---

### build-and-start.sh

**Назначение:** Универсальный скрипт для сборки всех Go сервисов + запуска всех сервисов

**Использование:**
```bash
./scripts/dev/build-and-start.sh [OPTIONS]
```

**Опции:**

| Опция | Описание |
|-------|----------|
| `--clean` | Очистить бинарники перед сборкой |
| `--help` | Показать справку |

**Примеры:**

```bash
# Сборка + запуск
./scripts/dev/build-and-start.sh

# Очистить старые бинарники + собрать + запустить
./scripts/dev/build-and-start.sh --clean
```

**Что делает:**

**Фаза 1: Сборка Go сервисов**
- Использует `scripts/build.sh` для сборки всех Go сервисов
- Если `--clean` указан → очищает `bin/` перед сборкой
- Fallback на прямую сборку если `build.sh` отсутствует

**Фаза 2: Запуск всех сервисов**
- Делегирует запуск `scripts/dev/start-all.sh`

**Рекомендации:**
- Используйте для **первого запуска** проекта
- Используйте после `git pull` чтобы пересобрать бинарники
- Для ежедневной работы используйте `restart-all.sh` (умнее)

---

### test-lock-unlock-workflow.sh

**Назначение:** Smoke tests для RAS Adapter (Week 4 - NEW)

**Использование:**
```bash
./scripts/dev/test-lock-unlock-workflow.sh
```

**Опции:** Нет

**Что делает:**
1. **Test 1:** Health Check - проверяет что RAS Adapter отвечает
2. **Test 2:** GET /clusters - проверяет подключение к RAS серверу
3. **Test 3:** GET /infobases - получает список информационных баз
4. **Test 4-5:** POST /lock, /unlock - пропускаются (требуют реальные cluster_id и infobase_id)
5. **Test 6:** Redis connectivity - проверяет подключение к Redis
6. **Test 7-8:** Redis Pub/Sub - пропускаются (требуют redis-cli и ручное тестирование)

**Переменные окружения:**
```bash
RAS_ADAPTER_URL=http://localhost:8088    # URL RAS Adapter (default)
REDIS_HOST=localhost                      # Redis host (default)
REDIS_PORT=6379                           # Redis port (default)
```

**Примеры:**

```bash
# Запустить smoke tests с defaults
./scripts/dev/test-lock-unlock-workflow.sh

# Указать другой URL RAS Adapter
RAS_ADAPTER_URL=http://192.168.1.100:8088 ./scripts/dev/test-lock-unlock-workflow.sh
```

**Результат:**
- Exit code 0 если все тесты прошли
- Exit code 1 если хотя бы один тест failed

**Важно:**
- RAS Adapter должен быть запущен
- RAS сервер должен быть доступен на порту 1545
- Redis должен быть запущен

---

## Вспомогательные скрипты

### ../build.sh

**Назначение:** Централизованная сборка всех Go микросервисов с версионированием

**Расположение:** `scripts/build.sh` (на уровень выше `dev/`)

**Использование:**
```bash
./scripts/build.sh [OPTIONS]
```

**Опции:**

| Опция | Описание |
|-------|----------|
| `--service=<name>` | Собрать только указанный сервис (api-gateway, worker, ras-adapter) |
| `--os=<os>` | Целевая ОС (linux, windows, darwin). По умолчанию: текущая ОС |
| `--arch=<arch>` | Целевая архитектура (amd64, arm64). По умолчанию: текущая архитектура |
| `--parallel` | Собрать все сервисы параллельно (быстрее) |
| `--clean` | Очистить `bin/` перед сборкой |
| `--help` | Показать справку |

**Примеры:**

```bash
# Собрать все для текущей ОС
./scripts/build.sh

# Собрать только worker
./scripts/build.sh --service=worker

# Cross-compile для Linux amd64
./scripts/build.sh --os=linux --arch=amd64

# Параллельная сборка всех сервисов (быстрее)
./scripts/build.sh --parallel

# Очистить + собрать параллельно
./scripts/build.sh --clean --parallel
```

**Версионирование:**
- Автоматически определяет версию через `git describe --tags`
- Внедряет версию, commit hash, build time в бинарники
- Бинарники поддерживают флаг `--version`

**Примеры версий:**
- С git tag: `v1.2.3`
- Без git tag: `abc1234` (commit hash)
- Uncommitted changes: `abc1234-dirty`

**Формат бинарников:**
- Windows: `cc1c-<service>.exe`
- Linux/macOS: `cc1c-<service>`

**Выходная директория:** `bin/`

**Поддерживаемые сервисы:**
- `api-gateway` - Go API Gateway
- `worker` - Go Worker
- `ras-adapter` - Go RAS Adapter

---

## Типичные сценарии

### 🚀 Первый запуск проекта

```bash
# 1. Клонировать репозиторий
git clone <repo>
cd command-center-1c

# 2. Создать .env.local (или скопировать .env.example)
cp .env.example .env.local
# Отредактировать .env.local (DB_HOST=localhost, REDIS_HOST=localhost)

# 3. Установить зависимости
cd orchestrator && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt && cd ..
cd frontend && npm install && cd ..
cd go-services/api-gateway && go mod download && cd ../..

# 4. Собрать бинарники + запустить всё
./scripts/dev/build-and-start.sh

# 5. Проверить статус
./scripts/dev/health-check.sh
```

### ☀️ Начало рабочего дня

```bash
# Запустить всё
./scripts/dev/start-all.sh

# Проверить что всё работает
./scripts/dev/health-check.sh
```

### 💻 Во время разработки

```bash
# Изменили код Go сервиса → умный перезапуск (автопересборка)
./scripts/dev/restart-all.sh

# Изменили код Django → перезапуск только Orchestrator
./scripts/dev/restart.sh orchestrator

# Изменили код Frontend → перезапуск только Frontend (hot reload работает автоматически)
./scripts/dev/restart.sh frontend

# Просмотр логов при отладке
./scripts/dev/logs.sh api-gateway

# Проверить статус всех сервисов
./scripts/dev/health-check.sh
```

### 📦 После git pull

```bash
# Пересобрать бинарники + перезапустить
./scripts/dev/restart-all.sh --force-rebuild

# Или
./scripts/dev/stop-all.sh
./scripts/build.sh --clean --parallel
./scripts/dev/start-all.sh
```

### 🌙 Конец рабочего дня

```bash
# Остановить всё
./scripts/dev/stop-all.sh

# Опционально: остановить Docker инфраструктуру
docker-compose -f docker-compose.local.yml down
```

### 🐛 Отладка проблем

```bash
# Проверить статус
./scripts/dev/health-check.sh

# Посмотреть логи проблемного сервиса
./scripts/dev/logs.sh <service-name>

# Перезапустить проблемный сервис
./scripts/dev/restart.sh <service-name>

# Если не помогло → полный перезапуск
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### 🧪 Тестирование RAS Adapter (Week 4)

```bash
# 1. Запустить ras-adapter (если не запущен)
./scripts/dev/start-all.sh

# 2. Smoke tests (автоматические)
./scripts/dev/test-lock-unlock-workflow.sh

# 3. Проверить health
curl http://localhost:8088/health

# 4. Получить список кластеров
curl "http://localhost:8088/api/v2/list-clusters?server=localhost:1545"

# 5. Получить список информационных баз (подставить cluster_id)
curl "http://localhost:8088/api/v2/list-infobases?cluster_id=<UUID>"

# 6. Manual Lock Test (подставить cluster_id и infobase_id)
curl -X POST "http://localhost:8088/api/v2/lock-infobase?cluster_id=<CLUSTER_ID>&infobase_id=<INFOBASE_ID>" \
  -H "Content-Type: application/json" \
  -d '{"db_user":"admin","db_password":"secret"}'

# 7. Manual Unlock Test
curl -X POST "http://localhost:8088/api/v2/unlock-infobase?cluster_id=<CLUSTER_ID>&infobase_id=<INFOBASE_ID>" \
  -H "Content-Type: application/json" \
  -d '{"db_user":"admin","db_password":"secret"}'

# 8. Просмотр логов
./scripts/dev/logs.sh ras-adapter
```

---

## Troubleshooting

### Проблема: Windows Firewall постоянно спрашивает разрешение

**Причина:** Используется `go run` вместо собранных бинарников → каждый раз новая временная директория

**Решение:**
```bash
# Соберите бинарники один раз
./scripts/build.sh

# Теперь используйте restart-all.sh вместо start-all.sh
./scripts/dev/restart-all.sh

# Брандмауэр спросит один раз для каждого сервиса и больше не будет беспокоить
```

### Проблема: Все процессы называются main.exe в Task Manager

**Причина:** Используется `go run` вместо собранных бинарников

**Решение:** См. выше (собрать бинарники)

### Проблема: Сервисы не запускаются

```bash
# 1. Проверить Docker контейнеры (должны быть: postgres, redis)
docker ps

# 2. Проверить логи конкретного сервиса
./scripts/dev/logs.sh <service-name>

# 3. Перезапустить сервис
./scripts/dev/restart.sh <service-name>

# 4. Полный перезапуск всех сервисов
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

### Проблема: Database connection error (Django)

```bash
# 1. Проверить что PostgreSQL запущен
docker ps | grep postgres

# 2. Проверить настройки в .env.local
cat .env.local | grep DB_HOST
# Должно быть: DB_HOST=localhost (НЕ postgres!)

# 3. Перезапустить Orchestrator
./scripts/dev/restart.sh orchestrator
```

### Проблема: PID файлы потеряны или повреждены

```bash
# 1. Очистить все PID файлы
rm -rf pids/*.pid

# 2. Убить процессы вручную по портам
netstat -ano | findstr :8080  # Windows
lsof -i :8080  # Linux/Mac

# 3. Запустить всё заново
./scripts/dev/start-all.sh
```

### Дополнительные ресурсы

- **Полный troubleshooting guide:** [LOCAL_DEVELOPMENT_GUIDE.md](../../docs/LOCAL_DEVELOPMENT_GUIDE.md#troubleshooting)
- **Детальная документация restart-all.sh:** [RESTART_ALL_GUIDE.md](RESTART_ALL_GUIDE.md)
- **1C администрирование:** [1C_ADMINISTRATION_GUIDE.md](../../docs/1C_ADMINISTRATION_GUIDE.md)
- **Главная документация:** [CLAUDE.md](../../CLAUDE.md)

---

## Дополнительная информация

### Директории

```
scripts/dev/
├── README.md                    # Этот файл
├── start-all.sh                 # Запуск всех сервисов
├── stop-all.sh                  # Остановка всех сервисов
├── restart.sh                   # Перезапуск одного сервиса
├── restart-all.sh               # Умный перезапуск с автопересборкой
├── logs.sh                      # Просмотр логов
├── health-check.sh              # Проверка статуса
├── build-and-start.sh           # Сборка + запуск
└── RESTART_ALL_GUIDE.md         # Детальная документация restart-all.sh
```

### Файлы проекта

```
command-center-1c/
├── pids/                        # PID файлы запущенных процессов
├── logs/                        # Логи всех сервисов
├── bin/                         # Собранные Go бинарники
├── .env.local                   # Переменные окружения (локальная разработка)
└── docker-compose.local.yml     # Docker инфраструктура (postgres, redis, clickhouse)
```

### Переменные окружения

Все скрипты загружают переменные окружения из `.env.local` автоматически.

**Важные переменные:**
- `DB_HOST=localhost` - PostgreSQL host (НЕ `postgres`!)
- `REDIS_HOST=localhost` - Redis host (НЕ `redis`!)
- `V8_DEFAULT_TIMEOUT` - Таймаут для операций 1С (по умолчанию: 300 секунд)

### Git Bash совместимость

Все скрипты протестированы и работают в Windows GitBash:
- Используют Unix-style команды (`find`, `stat -c`, `kill`)
- Правильные path separators (`/`)
- Line endings: LF (не CRLF)

---

## Сводная таблица скриптов

| Скрипт | Опции | Аргументы | Назначение |
|--------|-------|-----------|------------|
| `start-all.sh` | нет | нет | Запуск ВСЕХ сервисов (app + infra + monitoring) |
| `stop-all.sh` | нет | нет | Остановка ВСЕХ сервисов (app + infra + monitoring) |
| `restart.sh` | нет | `<service-name>` | Перезапуск одного сервиса |
| `restart-all.sh` | `--help`, `--force-rebuild`, `--no-rebuild`, `--parallel-build`, `--service=<name>`, `--verbose` | нет | Умный перезапуск с автопересборкой |
| `logs.sh` | нет | `<service-name>` `[lines]` | Просмотр логов |
| `start-monitoring.sh` | нет | нет | Запуск только мониторинга (опционально) |
| `stop-monitoring.sh` | нет | нет | Остановка только мониторинга (опционально) |
| `health-check.sh` | нет | нет | Проверка статуса сервисов |
| `build-and-start.sh` | `--clean`, `--help` | нет | Сборка + запуск |
| `../build.sh` | `--service=<name>`, `--os=<os>`, `--arch=<arch>`, `--parallel`, `--clean`, `--help` | нет | Сборка Go сервисов |

---

## Integration with Claude Code

Эти скрипты интегрированы с Claude Code:

**Skills:**
- `cc1c-devops` - DevOps операции

**Commands:**
- `/dev-start` - запустить все
- `/check-health` - проверить статус
- `/restart-service` - перезапустить сервис

**См. также:**
- `.claude/skills/cc1c-devops/SKILL.md` - DevOps skill
- `.claude/commands/dev-start.md` - start command
- `.claude/commands/check-health.md` - health check command
- `.claude/commands/restart-service.md` - restart command

---

---

## Что нового (версия 2.1)

**Дата обновления:** 2025-11-06

### Новые возможности

1. **Умная автопересборка в start-all.sh:**
   - Автоматическое определение измененных Go сервисов
   - Пересборка только измененного (экономия 75-89% времени)
   - Больше НЕ использует `go run` - решена проблема Windows Firewall

2. **Централизованная библиотека функций:**
   - Создан `common-functions.sh` для переиспользования кода
   - Функции доступны в start-all.sh и restart-all.sh
   - DRY принцип - меньше дублирования

3. **Новые флаги для start-all.sh:**
   - `--force-rebuild` - принудительная пересборка всех
   - `--no-rebuild` - быстрый старт без пересборки
   - `--parallel-build` - параллельная сборка
   - `--verbose` - детальный вывод
   - `--help` - справка

4. **Исправлен критический баг:**
   - build.sh больше не зависает при сборке всех сервисов
   - Исправлена обработка ошибок в циклах с `set -e`

### Улучшения

- Все процессы теперь имеют правильные имена (`cc1c-*.exe` вместо `main.exe`)
- Windows Firewall спрашивает разрешение только один раз
- Детальные отчеты о пересборке в конце выполнения
- Улучшенная документация всех скриптов

---

**Версия документации:** 2.2
**Последнее обновление:** 2025-11-27
**Автор:** CommandCenter1C Team

**Изменения v2.2:**
- Удалён cluster-service (заменён на ras-adapter)
- Удалён ras-grpc-gw (не используется)
- Добавлен Jaeger для distributed tracing
- Порт Grafana изменён на 5000
