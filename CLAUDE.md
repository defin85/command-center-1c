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

**Текущая фаза:** Phase 1, Week 3-4 (Core Functionality)
**Статус:** ✅ Sprint 1.4 завершен - cluster-service интеграция с RAS
**Режим разработки:** Hybrid (Infrastructure в Docker, Application на хосте)
**Roadmap:** Balanced Approach (14-16 недель) - ТОЛЬКО этот вариант реализуем

### 🚀 БЫСТРЫЙ СТАРТ

**Запуск проекта в начале сессии:**
```bash
cd /c/1CProject/command-center-1c
./scripts/dev/start-all.sh        # Запустить всё
./scripts/dev/health-check.sh     # Проверить статус
```

**Во время разработки:**
```bash
./scripts/dev/restart.sh <service>  # После изменений кода
./scripts/dev/logs.sh <service>     # Просмотр логов
./scripts/dev/stop-all.sh          # Остановить всё
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
- Frontend: http://localhost:3000
- API Gateway: http://localhost:8080 (+ /health)
- Orchestrator: http://localhost:8000 (+ /api/docs)
- Cluster Service: http://localhost:8088/health
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
User → Frontend (React:3000)
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
- 🔄 Sprint 2.1: Task Queue & Worker (в работе)

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
./scripts/dev/start-all.sh
./scripts/dev/health-check.sh
```

**После изменений кода:**
```bash
./scripts/dev/restart.sh <service-name>
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

#### Сервисы не запускаются

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
curl http://localhost:3000
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
│ (3000)  │
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
| **Frontend** | TypeScript | React 18.2 + Ant Design | 3000 |

**Data:**
- PostgreSQL 15 (5432) - primary DB
- Redis 7 (6379) - queue + cache
- ClickHouse (8123, 9000) - analytics (в dev окружении)

**Monitoring:**
- Prometheus (9090), Grafana (3001)

**External:**
- ras-grpc-gw (9999 gRPC, 8081 HTTP) - форк для 1C RAS

### Ключевые зависимости

**Runtime dependencies:**
```
ras-grpc-gw:9999 (gRPC) ← cluster-service:8088
postgres:5432, redis:6379 ← orchestrator:8000, celery-worker, celery-beat
orchestrator:8000 ← api-gateway:8080
redis:6379 ← worker (x2 replicas)
api-gateway:8080 ← frontend:3000
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

### Дополнительная информация

**Версия:** 2.2
**Последнее обновление:** 2025-11-05

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
