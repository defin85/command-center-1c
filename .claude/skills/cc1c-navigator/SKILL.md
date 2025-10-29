---
name: cc1c-navigator
description: "Navigate monorepo structure, locate components, explain service dependencies and data flow. Use when searching for code or understanding architecture."
allowed-tools: ["Read", "Glob", "Grep"]
---

# cc1c-navigator

## Purpose

Помочь разработчикам быстро ориентироваться в monorepo структуре CommandCenter1C, понимать зависимости между компонентами и находить нужный код.

## When to Use

Используй этот skill когда:
- Пользователь спрашивает "где находится X?"
- Нужно объяснить как взаимодействуют сервисы
- Требуется найти конкретный компонент (модель, endpoint, React компонент)
- Пользователь упоминает: structure, architecture, dependencies, где код, как работает, data flow

## Project Structure Overview

```
command-center-1c/
├── go-services/              # Go микросервисы
│   ├── api-gateway/          # Port 8080 - HTTP routing, auth, rate limiting
│   │   ├── cmd/main.go       # Entry point
│   │   ├── internal/         # Private application code
│   │   │   ├── handlers/     # HTTP handlers
│   │   │   ├── middleware/   # Auth, logging, rate limiting
│   │   │   └── router/       # Route definitions
│   │   └── go.mod
│   ├── worker/               # Scalable workers - parallel processing
│   │   ├── cmd/main.go       # Entry point
│   │   ├── internal/
│   │   │   ├── pool/         # Worker pool implementation
│   │   │   ├── processor/    # Task processing logic
│   │   │   └── odata/        # OData client for 1C
│   │   └── go.mod
│   └── shared/               # Общий код между Go сервисами
│       ├── auth/             # JWT validation
│       ├── logger/           # Structured logging
│       ├── metrics/          # Prometheus metrics
│       └── models/           # Shared data structures
├── orchestrator/             # Python/Django - Port 8000
│   ├── apps/
│   │   ├── operations/       # Логика операций над 1С
│   │   │   ├── models.py     # Operation, OperationLog
│   │   │   ├── views.py      # DRF API endpoints
│   │   │   ├── serializers.py
│   │   │   ├── services.py   # Business logic
│   │   │   └── tasks.py      # Celery tasks
│   │   ├── databases/        # Управление базами 1С
│   │   │   ├── models.py     # Database, DatabaseGroup
│   │   │   ├── views.py
│   │   │   └── services.py
│   │   └── templates/        # Template engine для операций
│   │       ├── models.py     # OperationTemplate
│   │       ├── views.py
│   │       └── engine.py     # Template rendering logic
│   ├── config/
│   │   ├── settings/         # Django settings
│   │   │   ├── base.py
│   │   │   ├── development.py
│   │   │   └── production.py
│   │   ├── urls.py
│   │   └── celery.py         # Celery configuration
│   └── manage.py
├── frontend/                 # React - Port 3000
│   └── src/
│       ├── api/              # API client
│       │   ├── client.ts     # Axios instance
│       │   └── endpoints/    # API methods grouped by domain
│       │       ├── operations.ts
│       │       ├── databases.ts
│       │       └── templates.ts
│       ├── components/       # Reusable UI components
│       │   ├── common/       # Buttons, Forms, Tables
│       │   ├── layout/       # Header, Sidebar, Layout
│       │   └── domain/       # Domain-specific components
│       ├── pages/            # Page components (routes)
│       │   ├── Dashboard/
│       │   ├── Operations/
│       │   ├── Databases/
│       │   └── Templates/
│       ├── stores/           # State management
│       │   ├── useOperations.ts
│       │   ├── useDatabases.ts
│       │   └── useAuth.ts
│       └── App.tsx
├── infrastructure/           # DevOps
│   ├── docker/
│   │   ├── api-gateway.Dockerfile
│   │   ├── worker.Dockerfile
│   │   ├── orchestrator.Dockerfile
│   │   └── frontend.Dockerfile
│   ├── k8s/                  # Kubernetes manifests (Phase 5)
│   └── terraform/            # Infrastructure as Code (Phase 5)
├── docs/                     # Documentation
│   ├── ROADMAP.md           # ⭐ Balanced approach plan (16 weeks)
│   ├── START_HERE.md
│   ├── EXECUTIVE_SUMMARY.md
│   └── architecture/         # (будет добавлено)
└── scripts/                  # Утилиты
```

## Service Dependencies Map

### Build-time Dependencies

```
go-services/shared
    ├─→ api-gateway
    └─→ worker

orchestrator/apps/*
    └─→ orchestrator/config

frontend/src/*
    └─→ frontend (build)
```

### Runtime Dependencies

```
User → Frontend (3000)
        ↓ HTTP + WebSocket
        API Gateway (8080)
            ↓ HTTP
            Orchestrator (8000) ←→ PostgreSQL
                ↓                   ↓
              Redis Queue       Redis Cache
                ↓
            Worker Pool (Go)
                ↓ OData
            700+ 1C Bases
```

**Важно:**
- Frontend общается ТОЛЬКО с API Gateway
- API Gateway НЕ зависит от Workers
- Workers автономны, масштабируются независимо
- Orchestrator координирует всё через Redis

## Data Flow Patterns

### User Operation Flow (Write)

```
1. User создает операцию в UI
   └─→ Frontend: POST /api/operations

2. API Gateway валидирует и проксирует
   └─→ Orchestrator: POST /operations/

3. Orchestrator сохраняет операцию
   └─→ PostgreSQL: INSERT INTO operations

4. Celery task создает задачи в очереди
   └─→ Redis: LPUSH operations_queue

5. Go Workers забирают задачи
   └─→ Redis: RPOP operations_queue

6. Worker обрабатывает базы параллельно
   └─→ 1C Bases: OData batch requests

7. Результаты отправляются обратно
   └─→ Redis → Orchestrator → WebSocket → Frontend
```

### Monitoring Flow (Read)

```
User → Frontend → API Gateway → Orchestrator
                                    ↓
                               PostgreSQL (operation status)
                                    ↓
                               WebSocket push → Frontend (real-time)
```

## Quick Navigation Guide

### "Где находится логика X?"

| Что ищешь | Где искать |
|-----------|-----------|
| HTTP routing, auth | `go-services/api-gateway/internal/` |
| Параллельная обработка | `go-services/worker/internal/pool/` |
| OData интеграция с 1С | `go-services/worker/internal/odata/` или `orchestrator/apps/operations/services.py` |
| Business logic операций | `orchestrator/apps/operations/services.py` |
| Django models | `orchestrator/apps/*/models.py` |
| API endpoints (Django) | `orchestrator/apps/*/views.py` |
| Celery tasks | `orchestrator/apps/*/tasks.py` |
| Template engine | `orchestrator/apps/templates/engine.py` |
| React UI компоненты | `frontend/src/components/` |
| API calls (Frontend) | `frontend/src/api/endpoints/` |
| State management | `frontend/src/stores/` |

### "Как добавить новый endpoint?"

1. **API Gateway** (если нужен новый route):
   - `go-services/api-gateway/internal/handlers/` - handler
   - `go-services/api-gateway/internal/router/router.go` - route definition

2. **Orchestrator** (business logic):
   - `orchestrator/apps/X/views.py` - DRF ViewSet
   - `orchestrator/apps/X/serializers.py` - serializer
   - `orchestrator/apps/X/services.py` - business logic

3. **Frontend** (UI):
   - `frontend/src/api/endpoints/X.ts` - API method
   - `frontend/src/pages/X/` - page component

### "Как найти все места где используется X?"

Используй Grep:
```bash
# Найти все использования модели Operation
grep -r "Operation" --include="*.py" orchestrator/

# Найти все API calls к /operations
grep -r "/operations" --include="*.ts" --include="*.tsx" frontend/

# Найти все Celery tasks
grep -r "@shared_task" --include="*.py" orchestrator/
```

## Component Location Cheatsheet

### Go Services

```
Что                          Файл
─────────────────────────────────────────────────────────────────
Main entry point             cmd/main.go
HTTP handlers                internal/handlers/*.go
Middleware                   internal/middleware/*.go
Worker pool                  internal/pool/pool.go
OData client                 internal/odata/client.go
Shared auth logic            ../shared/auth/jwt.go
Shared logger                ../shared/logger/logger.go
```

### Django Orchestrator

```
Что                          Файл
─────────────────────────────────────────────────────────────────
Models                       apps/*/models.py
API Views                    apps/*/views.py
Serializers                  apps/*/serializers.py
Business Logic               apps/*/services.py
Celery Tasks                 apps/*/tasks.py
Django Settings              config/settings/*.py
URL routing                  config/urls.py
Admin panel                  apps/*/admin.py
```

### React Frontend

```
Что                          Файл
─────────────────────────────────────────────────────────────────
Page components              pages/*/index.tsx
Reusable components          components/common/*.tsx
Domain components            components/domain/*.tsx
API client                   api/client.ts
API endpoints                api/endpoints/*.ts
State management             stores/use*.ts
Routing                      App.tsx
```

## Key Files Reference

| Файл | Назначение |
|------|-----------|
| `CLAUDE.md` | ⭐ Главная инструкция для AI агентов |
| `docs/ROADMAP.md` | ⭐ Balanced approach plan (16 weeks) |
| `docs/START_HERE.md` | Quick start guide |
| `docs/EXECUTIVE_SUMMARY.md` | Краткое резюме проекта |
| `Makefile` | DevOps команды (make dev, make logs, etc.) |
| `docker-compose.yml` | Локальная разработка |
| `.env.example` | Environment variables template |

## Understanding Dependencies

### Как проверить зависимости компонента?

**Go Services:**
```bash
cd go-services/api-gateway
go mod graph | grep shared  # Найти зависимости на shared
```

**Django:**
```bash
cd orchestrator
python manage.py show_urls  # Показать все URLs
python manage.py graph_models -a -o models.png  # Граф моделей
```

**Frontend:**
```bash
cd frontend
npm list --depth=0  # Top-level dependencies
```

## Quick Search Commands

### Find all models
```bash
# Using Glob
Glob pattern="**/models.py"

# Using Bash
find . -name "models.py" -type f
```

### Find all API endpoints
```bash
# Using Grep - Django ViewSets
Grep pattern="class.*ViewSet" --type py

# Using Grep - API routes (Go)
Grep pattern="router\.(GET|POST|PUT|DELETE)" --type go
```

### Find React components
```bash
# Using Glob - All TSX files
Glob pattern="frontend/src/components/**/*.tsx"

# Using Glob - Specific page
Glob pattern="frontend/src/pages/Operations/**/*.tsx"
```

### Find Celery tasks
```bash
# Using Grep
Grep pattern="@shared_task" --type py
```

### Find all handlers (Go)
```bash
# Using Glob
Glob pattern="go-services/**/handlers/*.go"
```

### Find OData usage
```bash
# Using Grep - OData imports
Grep pattern="import.*odata" --type py --type go

# Using Grep - OData operations
Grep pattern="odata.*batch|odata.*get|odata.*post"
```

### Find all tests
```bash
# Python tests
Glob pattern="**/test_*.py"
Glob pattern="**/*_test.py"

# Go tests
Glob pattern="**/*_test.go"

# React tests
Glob pattern="**/*.test.tsx"
Glob pattern="**/*.spec.tsx"
```

## Examples

### Пример 1: Найти где создаются операции

1. Frontend: `frontend/src/api/endpoints/operations.ts` - `createOperation()`
2. API Gateway: `go-services/api-gateway/internal/handlers/operations.go` - proxy
3. Orchestrator: `orchestrator/apps/operations/views.py` - `OperationViewSet.create()`
4. Business Logic: `orchestrator/apps/operations/services.py` - `OperationService.create_operation()`
5. Celery Task: `orchestrator/apps/operations/tasks.py` - `process_operation_task.delay()`

### Пример 2: Найти Worker pool implementation

```
go-services/worker/internal/pool/
├── pool.go          # Worker pool structure
├── worker.go        # Individual worker logic
└── semaphore.go     # Concurrency control
```

### Пример 3: Найти OData adapter

**Go implementation (Worker):**
`go-services/worker/internal/odata/client.go`

**Python implementation (Orchestrator):**
`orchestrator/apps/operations/services.py` - класс `OneCODataAdapter`

## Common Questions

**Q: Где находится аутентификация?**
A:
- JWT validation: `go-services/shared/auth/jwt.go`
- Middleware: `go-services/api-gateway/internal/middleware/auth.go`
- Django auth: `orchestrator/apps/users/` (будет создано в Phase 1)

**Q: Где логика работы с Redis?**
A:
- Queue producer: `orchestrator/apps/operations/tasks.py`
- Queue consumer: `go-services/worker/internal/pool/queue.go`
- Cache: `orchestrator/config/cache.py`

**Q: Где WebSocket для real-time updates?**
A:
- Backend: `orchestrator/apps/operations/consumers.py` (Django Channels)
- Frontend: `frontend/src/api/websocket.ts`

**Q: Где Template Engine?**
A: `orchestrator/apps/templates/engine.py` - рендеринг шаблонов операций

## Tips

1. **Всегда начинай с CLAUDE.md** - там overview всей архитектуры
2. **Используй Glob для быстрого поиска** - `**/*.py` найдет все Python файлы
3. **Grep для поиска по содержимому** - быстрее чем читать каждый файл
4. **Следуй data flow** - от Frontend до 1C и обратно
5. **Проверяй зависимости** - если меняешь shared код, проверь кто его использует

## References

- Главная документация: `CLAUDE.md`
- Архитектурный план: `docs/ROADMAP.md` (Balanced approach)
- Структура проекта: `docs/START_HERE.md`
- Docker setup: `docker-compose.yml`
- DevOps команды: `Makefile`

## Related Skills

После навигации по коду используй:
- `cc1c-service-builder` - для создания новых компонентов
- `cc1c-odata-integration` - для работы с 1С через OData
- `cc1c-devops` - для запуска и отладки сервисов

---

**Version:** 1.0
**Last Updated:** 2025-01-17
**Changelog:**
- 1.0 (2025-01-17): Initial release with Quick Search Commands
