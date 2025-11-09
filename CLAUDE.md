# CommandCenter1C - Инструкции для AI агентов

> Микросервисная платформа для централизованного управления 700+ базами 1С

---

## 📚 Навигация

**Быстрый доступ к секциям:**

| Секция | Описание | Время чтения |
|--------|----------|--------------|
| **[🚨 AI AGENT INSTRUCTIONS](#-ai-agent-instructions)** | Критичная информация для AI: quick start, tools, constraints, правила | ⏱️ 2 мин |
| **[📋 PROJECT CONTEXT](#-project-context)** | О проекте: цели, архитектура (краткая), текущая фаза | ⏱️ 3 мин |
| **[🔧 DEVELOPMENT GUIDE](#-development-guide)** | Ежедневная работа: setup, workflow, testing, troubleshooting | ⏱️ 5 мин |
| **[📖 REFERENCE](#-reference)** | Детальная справка: архитектура, структура, tech stack, документация | ⏱️ 10 мин |

**💡 Рекомендация для AI агентов:** Начни с секции "🚨 AI AGENT INSTRUCTIONS" - там вся критичная информация для быстрого старта!

---

## 🚨 AI AGENT INSTRUCTIONS

### ⚡ КРИТИЧНО

**Дата обновления:** 2025-11-08
**Текущая фаза:** Phase 1, Week 2.5-3 (Core Functionality)
**Статус:** 🔄 Sprint 2.1-2.2 В ПРОЦЕССЕ (~25% готово) - Task Queue & Worker Integration
**Режим разработки:** Hybrid (Infrastructure в Docker, Application на хосте)
**Roadmap:** Balanced Approach (14-16 недель) - ТОЛЬКО этот вариант реализуем

**Завершено:** Sprint 1.1-1.4 (Infrastructure, Models, OData, RAS Integration) ✅
**В работе:** Sprint 2.1 (Celery ↔ Worker) 🟡 30%, Sprint 2.2 (Template Engine) 🟡 20%
**Критичные GAPs:** Orchestrator → Worker integration, Template Engine, Real Operation Execution

### 🚀 БЫСТРЫЙ СТАРТ

**Запуск проекта в начале сессии:**
```bash
cd /c/1CProject/command-center-1c
./scripts/dev/start-all.sh        # Умный запуск с автопересборкой
./scripts/dev/health-check.sh     # Проверить статус
```

**Во время разработки:**
```bash
./scripts/dev/restart-all.sh        # Умный перезапуск с автопересборкой
./scripts/dev/restart.sh <service>  # Перезапуск одного сервиса
./scripts/dev/logs.sh <service>     # Просмотр логов
./scripts/dev/stop-all.sh           # Остановить всё
```

**Опции для start-all.sh и restart-all.sh:**
```bash
--force-rebuild     # Принудительная пересборка всех Go сервисов
--no-rebuild        # Пропустить пересборку (быстрый старт)
--parallel-build    # Параллельная пересборка (быстрее)
--verbose           # Детальный вывод
--help              # Справка
```

**Доступные сервисы:**
- `orchestrator`, `celery-worker`, `celery-beat` (Python/Django)
- `api-gateway`, `worker`, `cluster-service` (Go)
- `frontend` (React)
- ras-grpc-gw (внешний, в ../ras-grpc-gw)

### 🛠️ ДОСТУПНЫЕ ИНСТРУМЕНТЫ

**Skill для DevOps:**
- `cc1c-devops` - управление сервисами, логи, health checks

**Slash Commands:**
- `/dev-start` - запустить все сервисы
- `/check-health` - проверить статус всех сервисов
- `/restart-service <name>` - перезапустить сервис
- `/run-migrations` - применить миграции Django
- `/test-all` - запустить все тесты

**Endpoints для проверки:**
- Frontend: http://localhost:5173
- API Gateway: http://localhost:8080/health
- Orchestrator:
  - Admin Panel: http://localhost:8000/admin
  - API Docs (Swagger): http://localhost:8000/api/docs
- Cluster Service: http://localhost:8088/health
- Batch Service: http://localhost:8087/health
- ras-grpc-gw: http://localhost:8081/health (gRPC: 9999)
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090

### ⚠️ КЛЮЧЕВЫЕ ОГРАНИЧЕНИЯ

1. **Транзакции 1С < 15 секунд** - КРИТИЧНО! Разбивай на короткие транзакции
2. **Connection limits:** max 3-5 concurrent connections per база 1С
3. **Worker pool size:** Phase 1: 10-20, Production: auto-scale по queue depth
4. **OData batch:** 100-500 records/batch для групповых операций
5. **Rate limiting:** 100 req/min per user (default)

### 📐 ПРАВИЛА РАЗРАБОТКИ

1. **Работаем ТОЛЬКО по Balanced roadmap** (docs/ROADMAP.md)
2. **Следуй monorepo структуре** - не создавай файлы в неправильных местах
3. **Go shared code** → go-services/shared/ (auth, logger, config)
4. **Django apps независимы** → минимум cross-app imports
5. **Frontend → API Gateway ТОЛЬКО** → без прямых вызовов Orchestrator
6. **ras-grpc-gw запускай первым** → cluster-service зависит от него
7. **Тесты обязательны** → coverage > 70%
8. **Локальная разработка** → используй ./scripts/dev/*.sh, НЕ Docker Compose

---

## 📋 PROJECT CONTEXT

### О проекте

**Цель:** Микросервисная платформа для централизованного управления 700+ базами 1С:Бухгалтерия 3.0 с параллельной обработкой и real-time мониторингом.

**Экономия:** 10-100x ускорение операций, ROI 260-1200% в первый год.

**Масштаб:**
- 700+ баз 1С
- 100-500 параллельных соединений
- Тысячи операций в минуту

### Архитектура (краткая версия)

```
User → Frontend (React:5173)
  ↓
API Gateway (Go:8080) → Orchestrator (Django:8000) → PostgreSQL:5432
                          ↓
                        Redis:6379 → Celery
                          ↓
                    Go Worker Pool (x2) → OData → 1C Bases
                          ↓
                    cluster-service (Go:8088) → ras-grpc-gw:9999 → 1C RAS
```

**Поток данных:**
```
User → Frontend → API Gateway → Orchestrator → Celery → Redis
→ Worker → OData → 1C → Results → WebSocket → User
```

### Текущая фаза

Актуальную информацию о текущей фазе и спринте см. в начале документа (секция "⚡ КРИТИЧНО").

**История выполненных спринтов:**
- ✅ Sprint 1.1-1.4: Завершены (см. [Sprint Progress](docs/archive/sprints/))
- 🟡 Sprint 2.1: Task Queue & Worker (~30% готово, интеграция в TODO)
- 🟡 Sprint 2.2: Template System (~20% готово, engine в TODO)

**Полный план:**
- [ROADMAP.md](docs/ROADMAP.md) - Balanced Approach (Phases 1-5, 14-16 недель)
- [START_HERE.md](docs/START_HERE.md) - Быстрый старт по документации

---

## 🔧 DEVELOPMENT GUIDE

### Первоначальная настройка

**Prerequisites:**
- Docker 20.10+, Docker Compose 2.0+
- Python 3.11+, Go 1.21+, Node.js 18+
- Git 2.30+

**Setup:**
```bash
git clone <repo>
cd command-center-1c
cp .env.local.example .env.local
# Отредактировать .env.local (DB_HOST=localhost, REDIS_HOST=localhost)

# Python dependencies
cd orchestrator && python -m venv venv
source venv/Scripts/activate  # Windows GitBash
pip install -r requirements.txt
cd ..

# Node.js dependencies
cd frontend && npm install && cd ..

# Go dependencies
cd go-services/api-gateway && go mod download && cd ../..
cd go-services/worker && go mod download && cd ../..
cd go-services/cluster-service && go mod download && cd ../..

# Start all
./scripts/dev/start-all.sh
./scripts/dev/health-check.sh
```

### Daily Workflow

**Утром:**
```bash
./scripts/dev/start-all.sh         # Умный запуск с автопересборкой измененных сервисов
./scripts/dev/health-check.sh      # Проверка статуса
```

**После изменений кода:**
```bash
# Для Go сервисов - умный перезапуск с автопересборкой
./scripts/dev/restart-all.sh

# Для одного Go сервиса
./scripts/dev/restart-all.sh --service=api-gateway

# Для Python/Frontend (без пересборки)
./scripts/dev/restart.sh orchestrator
./scripts/dev/restart.sh frontend
```

**Просмотр логов:**
```bash
./scripts/dev/logs.sh <service-name>
./scripts/dev/logs.sh all  # Все сервисы
```

**Вечером:**
```bash
./scripts/dev/stop-all.sh
```

### Тестирование

**Django tests:**
```bash
cd orchestrator
source venv/Scripts/activate
pytest
```

**Go tests:**
```bash
cd go-services/api-gateway
go test ./...
```

**Frontend tests:**
```bash
cd frontend
npm test
```

**Database migrations:**
```bash
cd orchestrator
source venv/Scripts/activate
python manage.py makemigrations
python manage.py migrate
```

### Troubleshooting

**Распространенные проблемы и решения:**

#### Windows Firewall постоянно спрашивает разрешение

**Причина:** Используется `go run` вместо собранных бинарников → каждый раз новая временная директория

**Решение:**
```bash
# Используйте улучшенные скрипты с умной пересборкой:
./scripts/dev/start-all.sh        # Автоматически собирает бинарники
./scripts/dev/restart-all.sh      # Умный перезапуск с пересборкой

# Брандмауэр спросит один раз для каждого сервиса и больше не будет беспокоить!
```

#### Все процессы называются main.exe в Task Manager

**Причина:** Используется `go run` вместо собранных бинарников

**Решение:** См. выше. После использования `start-all.sh` или `restart-all.sh` все процессы будут называться `cc1c-api-gateway.exe`, `cc1c-worker.exe`, и т.д.

#### Сервисы не запускаются

```bash
# 1. Проверить Docker контейнеры (должны быть: postgres, redis)
docker ps

# 2. Проверить логи конкретного сервиса
./scripts/dev/logs.sh <service-name>

# 3. Перезапустить сервис
./scripts/dev/restart-all.sh --service=<service-name>

# 4. Полный перезапуск всех сервисов с принудительной пересборкой
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh --force-rebuild
```

#### cluster-service не подключается к ras-grpc-gw

**Причина:** ras-grpc-gw запускается в отдельном репозитории и должен быть запущен первым.

```bash
# 1. Проверить что ras-grpc-gw запущен
cd ../ras-grpc-gw
./start.sh  # или как запускается у вас

# 2. Проверить HTTP endpoint (должен ответить 200 OK)
curl http://localhost:8081/health

# 3. Проверить что gRPC порт открыт (9999)
netstat -ano | findstr :9999  # Windows
# или
lsof -i :9999  # Linux/Mac

# 4. Посмотреть логи cluster-service
cd /c/1CProject/command-center-1c
./scripts/dev/logs.sh cluster-service
```

**См. также:** [1C_ADMINISTRATION_GUIDE.md](docs/1C_ADMINISTRATION_GUIDE.md) для детальной настройки RAS

#### cluster-service: "connection refused" на порту 9999

**Причина:** ras-grpc-gw не запущен или не готов

**Диагностика:**
```bash
# 1. Проверить что gRPC порт слушает
netstat -ano | findstr :9999  # Windows
lsof -i :9999  # Linux/Mac

# 2. Проверить процесс ras-grpc-gw
ps aux | grep ras-grpc-gw  # Linux/Mac
tasklist | findstr ras-grpc-gw.exe  # Windows

# 3. Проверить health check
curl http://localhost:8081/health
# Ожидается: {"service":"ras-grpc-gw","status":"healthy",...}
```

**Решение:**
```bash
# Запустить ras-grpc-gw ПЕРВЫМ
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545

# Подождать 3-5 секунд, затем запустить cluster-service
cd /c/1CProject/command-center-1c/go-services/cluster-service
go run cmd/main.go
```

**См. также:** [Критичные сервисы → Порядок запуска](#критичные-сервисы)

#### batch-service: "1cv8.exe not found"

**Причина:** Путь к 1cv8.exe не установлен или неправильный

**Диагностика:**
```bash
# Проверить переменную окружения
echo $EXE_1CV8_PATH  # Linux/Mac/GitBash
set EXE_1CV8_PATH  # Windows CMD

# Проверить что файл существует
ls "$EXE_1CV8_PATH"  # Linux/Mac/GitBash
dir "%EXE_1CV8_PATH%"  # Windows CMD
```

**Решение:**
```bash
# Установить правильный путь в .env.local
cat >> .env.local << EOF
EXE_1CV8_PATH=C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe
V8_DEFAULT_TIMEOUT=300
EOF

# Или экспортировать в текущей сессии
export EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"

# Перезапустить batch-service
cd go-services/batch-service
go run cmd/main.go
```

#### ras-grpc-gw: "RAS server not available" на порту 1545

**Причина:** RAS сервер 1С не запущен или недоступен

**Диагностика:**
```bash
# Проверить подключение к RAS серверу
telnet localhost 1545
# или
nc -zv localhost 1545  # Linux/Mac

# Проверить логи ras-grpc-gw
cd ../ras-grpc-gw
cat ras-grpc-gw.log | tail -50
```

**Решение:**

**Вариант 1: Запустить RAS сервер (если он не запущен):**
- Открыть консоль администрирования 1С
- Подключиться к серверу кластера
- Проверить что RAS работает на порту 1545

**Вариант 2: Изменить порт в параметрах запуска:**
```bash
# Если RAS на другом порту (например, 1546)
cd ../ras-grpc-gw
go run cmd/main.go localhost:1546

# Обновить переменную окружения для cluster-service
export RAS_SERVER=localhost:1546
```

**Вариант 3: RAS на удаленном сервере:**
```bash
# Указать IP/hostname RAS сервера
cd ../ras-grpc-gw
go run cmd/main.go 192.168.1.100:1545
```

**См. также:** [1C_ADMINISTRATION_GUIDE.md](docs/1C_ADMINISTRATION_GUIDE.md) для детальной настройки RAS

#### Транзакции 1С падают с timeout

**⚠️ КРИТИЧНО:** Транзакции ДОЛЖНЫ быть < 15 секунд!

**Решения:**
- Разбивай длинные операции на короткие транзакции
- Используй OData `$batch` для групповых операций (100-500 records/batch)
- Избегай сложных вычислений внутри транзакций 1С
- Проверь connection limits (max 3-5 concurrent connections per база)

**См. также:** [ODATA_INTEGRATION.md](docs/ODATA_INTEGRATION.md) для best practices batch операций

#### Database connection error (Django)

```bash
# 1. Проверить что PostgreSQL запущен
docker ps | grep postgres

# 2. Проверить что PostgreSQL готов принимать соединения
docker exec -it postgres pg_isready

# 3. Проверить настройки в .env.local
cat .env.local | grep DB_HOST
# Должно быть: DB_HOST=localhost (НЕ postgres!)

# 4. Проверить подключение вручную
docker exec -it postgres psql -U commandcenter -d commandcenter -c "SELECT 1;"

# 5. Перезапустить Orchestrator
./scripts/dev/restart.sh orchestrator
```

#### Redis connection error (Celery)

```bash
# 1. Проверить что Redis запущен
docker ps | grep redis

# 2. Тест подключения
docker exec -it redis redis-cli ping
# Должно вернуть: PONG

# 3. Проверить настройки в .env.local
cat .env.local | grep REDIS_HOST
# Должно быть: REDIS_HOST=localhost (НЕ redis!)

# 4. Перезапустить Celery workers
./scripts/dev/restart.sh celery-worker
./scripts/dev/restart.sh celery-beat
```

#### Django migrations не применяются

```bash
cd orchestrator
source venv/Scripts/activate  # Windows GitBash
# или: source venv/bin/activate  # Linux/Mac

# 1. Проверить статус миграций
python manage.py showmigrations

# 2. Применить миграции
python manage.py migrate

# 3. Если нужно откатить
python manage.py migrate <app_name> <migration_name>

# 4. Создать новые миграции (после изменения models)
python manage.py makemigrations
python manage.py migrate

cd ..
```

#### Frontend не подключается к API Gateway

**Проверь endpoints:**
```bash
# API Gateway должен быть доступен
curl http://localhost:8080/health
# Ожидается: {"status": "ok"}

# Orchestrator API docs
curl http://localhost:8000/api/docs
# Должна открыться Swagger UI

# Frontend должен быть запущен
curl http://localhost:5173
```

**Важно:** Frontend общается ТОЛЬКО с API Gateway (`:8080`), НЕ напрямую с Orchestrator (`:8000`)!

**Проверь конфиг Frontend:**
```bash
cat frontend/.env.local | grep VITE_API_URL
# Должно быть: VITE_API_URL=http://localhost:8080/api/v1
```

#### PID файлы потеряны или повреждены

```bash
# 1. Очистить все PID файлы
rm -rf pids/*.pid

# 2. Найти и убить процессы вручную по портам
# API Gateway (8080)
netstat -ano | findstr :8080  # Windows
lsof -i :8080  # Linux/Mac

# Убить процесс
taskkill /PID <pid> /F  # Windows
kill -9 <pid>  # Linux/Mac

# 3. Запустить всё заново
./scripts/dev/start-all.sh
```

**Дополнительные ресурсы:**
- Полный troubleshooting guide: [LOCAL_DEVELOPMENT_GUIDE.md](docs/LOCAL_DEVELOPMENT_GUIDE.md#troubleshooting)
- DevOps операции: используй Skill `cc1c-devops` или slash command `/check-health`

---

## 📖 REFERENCE

### Детальная архитектура

```
┌─────────┐
│ React   │ TypeScript + Ant Design
│ (5173)  │
└────┬────┘
     │ HTTP + WebSocket
┌────▼────┐
│ Go API  │ Gin + JWT + Rate Limiting
│ Gateway │
│ (8080)  │
└────┬────┘
     │ HTTP
┌────▼────────┐
│ Django      │ DRF + Celery
│ Orchestr.   │ Business Logic
│ (8000)      │
└──┬────┬─────┘
   │    │
┌──▼──┐ │  ┌──────────┐
│Redis│ └─→│PostgreSQL│
│Queue│    │ (5432)   │
└──┬──┘    └──────────┘
   │
┌──▼──────┐
│Go Worker│ Goroutines pool (x2 replicas)
│Pool     │ Parallel: 100-500 bases
└────┬────┘
     │ OData
┌────▼────────┐     ┌──────────────┐
│ 700+ 1C     │ ←───│cluster-service│ gRPC
│ Bases       │     │ (8088)       │ ↓
└─────────────┘     └──────────────┘ ras-grpc-gw
```

### Структура monorepo

```
command-center-1c/
├── go-services/              # Go микросервисы
│   ├── api-gateway/          # HTTP router, auth, rate limit
│   ├── worker/               # Parallel processing (x2 replicas)
│   ├── batch-service/        # Batch operations (в разработке)
│   ├── cluster-service/      # 1C cluster management (RAS/gRPC)
│   └── shared/               # Общий код (auth, logger, metrics, models)
├── orchestrator/             # Python/Django
│   ├── apps/
│   │   ├── databases/        # Database CRUD, OData, health checks
│   │   ├── operations/       # Operation management
│   │   └── templates/        # Template engine
│   └── config/               # Django settings
├── frontend/                 # React + TypeScript
│   └── src/
│       ├── api/              # API client
│       ├── components/       # UI components
│       ├── pages/            # App pages
│       └── stores/           # State management (Zustand)
├── infrastructure/
│   ├── docker/               # Dockerfiles
│   ├── k8s/                  # Kubernetes manifests
│   ├── monitoring/           # Prometheus + Grafana configs
│   └── terraform/            # IaC (planned)
├── docs/                     # Документация
└── docker-compose.yml        # Dev environment (11 services)
```

### Технологический стек

| Компонент | Язык | Фреймворк | Порт |
|-----------|------|-----------|------|
| **API Gateway** | Go 1.21+ | Gin | 8080 |
| **Workers** | Go 1.21+ | stdlib + goroutines | - |
| **cluster-service** | Go 1.21+ | gRPC client | 8088 |
| **Orchestrator** | Python 3.11+ | Django 4.2+ DRF | 8000 |
| **Task Queue** | Python 3.11+ | Celery 5.3+ | - |
| **Frontend** | TypeScript | React 18.2 + Ant Design | 5173 |

**Data:**
- PostgreSQL 15 (5432) - primary DB
- Redis 7 (6379) - queue + cache
- ClickHouse (8123, 9000) - analytics (в dev окружении)

**Monitoring:**
- Prometheus (9090), Grafana (3001)

**External:**
- ras-grpc-gw (9999 gRPC, 8081 HTTP) - форк для 1C RAS

---

## 🔌 Критичные сервисы

### Разделение ответственности

| Сервис | Назначение | Протокол | Use Case |
|--------|------------|----------|----------|
| **cluster-service** | Мониторинг кластеров | gRPC → RAS | Чтение метаданных, real-time мониторинг |
| **batch-service** | Управление конфигурациями | subprocess → 1cv8.exe | Установка расширений, batch операции |
| **ras-grpc-gw** | Gateway для RAS | gRPC ↔ RAS binary | Прокси для cluster-service |

### ras-grpc-gw (Внешний форк)

**Назначение:** Production-ready gRPC gateway для RAS протокола 1С Enterprise
- Прокси между gRPC и бинарным протоколом RAS (Remote Administration Server)
- Connection pooling для масштабирования на 700+ баз
- Health checks и graceful shutdown

**Технические детали:**
- **Репозиторий:** `C:\1CProject\ras-grpc-gw` (форк v8platform/ras-grpc-gw)
- **Версия:** v1.0.0-cc (форк с production features)
- **Язык:** Go 1.21+
- **Порты:**
  - 9999 (gRPC server)
  - 8081 (HTTP health check)
- **Протокол:** gRPC ↔ RAS binary protocol

**Запуск:**
```bash
cd ../ras-grpc-gw
go run cmd/main.go localhost:1545
# или с параметрами
./bin/ras-grpc-gw.exe --bind :9999 --health :8081 localhost:1545
```

**Health check:**
```bash
curl http://localhost:8081/health
# Ожидается: {"service":"ras-grpc-gw","status":"healthy","version":"v1.0.0-cc"}
```

**⚠️ ВАЖНО:** Запускать ПЕРВЫМ перед cluster-service!

### cluster-service

**Назначение:** Мониторинг и управление кластерами 1С через gRPC протокол
- Получение списка кластеров, информационных баз, сессий
- Real-time мониторинг с низкой latency (<100ms)
- Integration с Django Orchestrator

**Технические детали:**
- **Репозиторий:** `go-services/cluster-service`
- **Язык:** Go 1.21+ / Gin + gRPC client
- **Порт:** 8088
- **Зависимости:** ras-grpc-gw (КРИТИЧНО - должен быть запущен)

**API Endpoints:**
- `GET /health` - health check
- `GET /api/v1/clusters?server=localhost:1545` - список кластеров
- `GET /api/v1/infobases?server=localhost:1545` - список информационных баз
- `GET /api/v1/sessions?cluster=UUID` - активные сессии (Phase 2)

**Запуск:**
```bash
cd go-services/cluster-service
go run cmd/main.go
```

**Переменные окружения:**
```bash
export SERVER_HOST=0.0.0.0
export SERVER_PORT=8088
export GRPC_GATEWAY_ADDR=localhost:9999
export LOG_LEVEL=info
```

**Health check:**
```bash
curl http://localhost:8088/health
# Ожидается: {"status":"healthy","service":"cluster-service","version":"dev"}
```

### batch-service

**Назначение:** Установка расширений (.cfe) в базы 1С через subprocess
- Одиночная установка расширения в базу
- Batch установка на множество баз параллельно
- Использует 1cv8.exe напрямую (subprocess)

**Технические детали:**
- **Репозиторий:** `go-services/batch-service`
- **Язык:** Go 1.21+ / Gin
- **Порт:** 8087
- **Требования:** Путь к 1cv8.exe в переменных окружения

**API Endpoints:**
- `GET /health` - health check
- `POST /api/v1/extensions/install` - установка в одну базу
- `POST /api/v1/extensions/batch-install` - batch установка на несколько баз

**Запуск:**
```bash
cd go-services/batch-service
go run cmd/main.go
```

**Переменные окружения:**
```bash
export SERVER_HOST=0.0.0.0
export SERVER_PORT=8087
export EXE_1CV8_PATH="C:\Program Files\1cv8\8.3.27.1786\bin\1cv8.exe"
export V8_DEFAULT_TIMEOUT=300
```

**Health check:**
```bash
curl http://localhost:8087/health
# Ожидается: {"status":"healthy","service":"batch-service","version":"dev"}
```

### Порядок запуска сервисов

**Правильная последовательность:**

1. **Infrastructure** (если не запущено):
   ```bash
   docker-compose -f docker-compose.local.yml up -d postgres redis
   ```

2. **ras-grpc-gw** (ПЕРВЫМ):
   ```bash
   cd ../ras-grpc-gw
   go run cmd/main.go localhost:1545
   # Подождать 3-5 секунд для инициализации
   ```

3. **cluster-service** (зависит от ras-grpc-gw):
   ```bash
   cd go-services/cluster-service
   go run cmd/main.go
   ```

4. **batch-service** (независим):
   ```bash
   cd go-services/batch-service
   go run cmd/main.go
   ```

5. **Остальные сервисы**:
   ```bash
   ./scripts/dev/start-all.sh
   ```

**Проверка:**
```bash
./scripts/dev/health-check.sh
```

---

### Ключевые зависимости

**Runtime dependencies:**
```
ras-grpc-gw:9999 (gRPC) ← cluster-service:8088
postgres:5432, redis:6379 ← orchestrator:8000, celery-worker, celery-beat
orchestrator:8000 ← api-gateway:8080
redis:6379 ← worker (x2 replicas)
api-gateway:8080 ← frontend:5173
```

**Важно:**
- API Gateway НЕ зависит напрямую от Workers
- Workers автономны, масштабируются независимо (deploy.replicas)
- Frontend общается ТОЛЬКО с API Gateway
- cluster-service требует внешний форк ras-grpc-gw (в ../ras-grpc-gw)

### Документация

**⭐ Обязательно к прочтению:**
- **[ROADMAP.md](docs/ROADMAP.md)** - Balanced план (Phases 1-5, 14-16 недель)
- **[START_HERE.md](docs/START_HERE.md)** - Быстрый старт (2 мин)
- **[EXECUTIVE_SUMMARY.md](docs/EXECUTIVE_SUMMARY.md)** - Краткое резюме

**Практические гайды:**
- **[LOCAL_DEVELOPMENT_GUIDE.md](docs/LOCAL_DEVELOPMENT_GUIDE.md)** - Полное руководство (23KB)
- **[LOCAL_DEV_MIGRATION_SUMMARY.md](LOCAL_DEV_MIGRATION_SUMMARY.md)** - Сводка миграции
- **[1C_ADMINISTRATION_GUIDE.md](docs/1C_ADMINISTRATION_GUIDE.md)** - RAS/RAC, gRPC, endpoint management
- **[DJANGO_CLUSTER_INTEGRATION.md](docs/DJANGO_CLUSTER_INTEGRATION.md)** - cluster-service ↔ Django
- **[ODATA_INTEGRATION.md](docs/ODATA_INTEGRATION.md)** - Batch операции

**Техническая документация:**
- [Architecture](docs/architecture/) - Архитектурные решения
- [API](docs/api/) - REST API спецификация
- [Deployment](docs/deployment/) - Развертывание
- [README.md](README.md) - Main project README

**История:**
- [Sprint Progress](docs/archive/sprints/) - Детальная история спринтов
- [Roadmap Variants](docs/archive/roadmap_variants/) - MVP/Enterprise варианты (архив)


---

## 🔨 Build System

### Naming Convention

**Формат бинарников:** `cc1c-<service-name>.exe` (Windows) / `cc1c-<service-name>` (Linux)

**Все бинарники:**
```
bin/
├── cc1c-api-gateway.exe       - HTTP router, auth, rate limiting
├── cc1c-worker.exe            - Параллельная обработка операций
├── cc1c-cluster-service.exe   - Мониторинг кластеров 1С
└── cc1c-batch-service.exe     - Установка расширений в базы
```

**Преимущества:**
- Уникальность в Windows tasklist: сразу видно что это CommandCenter1C
- Четкая идентификация в логах и мониторинге
- Консистентность с Kubernetes naming (`kube-apiserver`, `kube-proxy`)

### Сборка бинарников

**Quick build (все сервисы):**
```bash
make build-go-all               # Если установлен Make
./scripts/build.sh              # Альтернатива без Make
```

**Отдельные сервисы:**
```bash
make build-api-gateway
make build-worker
make build-cluster-service
make build-batch-service
```

**Альтернативный способ (через scripts/build.sh):**
```bash
./scripts/build.sh --service=api-gateway
./scripts/build.sh --service=worker
./scripts/build.sh --service=cluster-service
./scripts/build.sh --service=batch-service
```

**Cross-compilation:**
```bash
make build-linux       # Linux amd64
make build-windows     # Windows amd64

# Через scripts/build.sh:
./scripts/build.sh --os=linux --arch=amd64
./scripts/build.sh --os=windows --arch=amd64
```

**Параллельная сборка (быстрее):**
```bash
./scripts/build.sh --parallel
```

**Очистка:**
```bash
make clean-binaries
```

### Версионирование

Все бинарники содержат встроенную информацию о версии:

```bash
./bin/cc1c-api-gateway.exe --version
# Вывод:
# Service: cc1c-api-gateway
# Version: v1.2.3
# Commit: abc1234
# Built: 2025-11-05_14:30:00
```

**Версия определяется автоматически:**
- Если есть git tag: используется tag (v1.2.3)
- Если нет tag: используется commit hash (abc1234)
- Если есть uncommitted changes: добавляется `-dirty`

**Версия в логах:**

Все сервисы логируют версию при старте:
```
INFO starting API Gateway service="cc1c-api-gateway" version="v1.2.3" commit="abc1234" buildTime="2025-11-05_14:30:00"
```

### Умная автопересборка (Smart Rebuild)

**scripts/dev/start-all.sh и scripts/dev/restart-all.sh теперь с умной пересборкой!**

**Как работает:**
1. **Автоматическое определение изменений** - сравнивает timestamps `.go` файлов и бинарников
2. **Выборочная пересборка** - пересобирает ТОЛЬКО измененные сервисы
3. **Проверка shared/ модулей** - если изменился `go-services/shared/`, пересобирает ВСЕ сервисы
4. **ВСЕГДА использует бинарники** - больше НЕТ fallback на `go run`

**Преимущества:**
- ✅ **Решена проблема Windows Firewall** - брандмауэр больше не спрашивает разрешение постоянно
- ✅ **Правильные имена процессов** - `cc1c-api-gateway.exe` вместо `main.exe` в Task Manager
- ✅ **Экономия времени** - пересборка только измененного (75-89% быстрее)
- ✅ **Не нужно думать** - просто запускайте `start-all.sh`, всё остальное автоматически

**Примеры использования:**
```bash
# Обычный запуск (умная пересборка)
./scripts/dev/start-all.sh

# Принудительная пересборка всех
./scripts/dev/start-all.sh --force-rebuild

# Быстрый старт без пересборки
./scripts/dev/start-all.sh --no-rebuild

# Параллельная сборка (быстрее)
./scripts/dev/start-all.sh --parallel-build

# То же самое для restart-all.sh
./scripts/dev/restart-all.sh
./scripts/dev/restart-all.sh --service=api-gateway
```

**Пример вывода:**
```
========================================
  Phase 1: Проверка и пересборка Go сервисов
========================================

[1/4] Проверка api-gateway...
✓ Бинарник актуален → пересборка не требуется

[2/4] Проверка worker...
⚠️ Обнаружены изменения → требуется пересборка

[3/4] Проверка cluster-service...
✓ Бинарник актуален → пересборка не требуется

[4/4] Проверка batch-service...
✓ Бинарник актуален → пересборка не требуется

Пересборка Go сервисов...
Building Worker...
✓ Worker built successfully (8.5M)

✓ Сервис worker успешно пересобран
```

### Build + Start (быстрый старт)

```bash
./scripts/dev/build-and-start.sh
# Соберет все бинарники + запустит сервисы
```

**С очисткой:**
```bash
./scripts/dev/build-and-start.sh --clean
# Очистит bin/ → соберет → запустит
```

---

### Дополнительная информация

**Версия:** 2.5
**Последнее обновление:** 2025-11-06

**Изменения в версии 2.5:**
- Реализована умная система автопересборки Go сервисов в start-all.sh и restart-all.sh
- Создан common-functions.sh для централизации общих функций (DRY принцип)
- Решена проблема Windows Firewall (больше не использует go run)
- Исправлен баг зависания в build.sh при сборке всех сервисов
- Добавлены флаги: --force-rebuild, --no-rebuild, --parallel-build, --verbose
- Обновлена документация scripts/dev/README.md с полным описанием всех опций

**Изменения в версии 2.4:**
- Внедрена система правильных наименований Go бинарников (cc1c-*)
- Добавлена централизованная build система (Makefile + scripts/build.sh)
- Добавлено версионирование в код всех сервисов (--version flag)

**Изменения в версии 2.3:**
- Добавлена секция "🔌 Критичные сервисы" (batch-service, cluster-service, ras-grpc-gw)
- Обновлен Troubleshooting с проблемами для критичных сервисов
- Добавлен правильный порядок запуска сервисов
- Детализированы API endpoints и команды запуска для критичных сервисов


**Изменения в версии 2.2:**
- Радикальная реструктуризация: Progressive Disclosure (AI INSTRUCTIONS → CONTEXT → GUIDE → REFERENCE)
- Quick Start перенесен в начало (строка 16 вместо 189+)
- Добавлена секция "🚨 AI AGENT INSTRUCTIONS" для быстрого старта AI сессий
- Устранено дублирование Quick Start секций (Docker vs Hybrid)
- Архитектурные диаграммы: краткая версия в CONTEXT, детальная в REFERENCE
- Добавлены доступные инструменты (Skills, Slash Commands, Endpoints)
- AI startup time: -75% (60 сек → 15 сек)

**Dev Mode:** Hybrid (Infrastructure в Docker, Application на хосте)

Актуальную информацию о текущей фазе и спринте см. в начале документа (секция "⚡ КРИТИЧНО").
