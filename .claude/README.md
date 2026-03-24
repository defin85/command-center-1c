# Command Center 1C - Claude Code Configuration

> Статус: legacy/non-authoritative Claude-specific guidance.
> Для текущего agent-facing onboarding используйте [docs/agent/INDEX.md](../docs/agent/INDEX.md).

Если вы открыли этот файл по старой ссылке, вернитесь к `docs/agent/INDEX.md`. Этот каталог сохранён только как исторический Claude-specific слой и не является источником истины для текущего agent workflow.

Конфигурация Claude Code для проекта `command-center-1c`.

## Структура

```
.claude/
├── commands/
│   ├── dev-start.md           # Запустить сервисы для разработки
│   ├── test-all.md            # Запустить все тесты
│   ├── build-docker.md        # Собрать Docker образы
│   ├── check-health.md        # Проверить статус сервисов
│   └── run-migrations.md      # Запустить Django миграции
└── README.md                  # Этот файл
```

## Использование Commands

Команды доступны через slash command interface:

```
/dev-start              - Запустить все сервисы
/test-all              - Запустить тесты для всех компонентов
/build-docker          - Собрать Docker образы
/check-health          - Проверить статус сервисов
/run-migrations        - Запустить migrations для Django
```

## Применимые Skills

### Universal Skills (для всех проектов)

- **`architect`** - Проектирование архитектуры (ОБЯЗАТЕЛЬНО для новых задач)
- **`coder`** - Реализация кода (Go, Python, TypeScript)
- **`tester`** - Написание тестов (ОБЯЗАТЕЛЬНО после реализации)
- **`reviewer`** - Code review (для критичного кода)
- **`git-expert`** - Git workflows и commits
- **`ci-cd`** - GitHub Actions pipelines
- **`docker-expert`** - Docker и docker-compose

### 1C Ecosystem Skills (для command-center-1c)

- **`bsl-expert`** - BSL программирование для 1С интеграции
- **`odata-expert`** - OData запросы к 1С базам
- **`metadata-parser`** - Анализ структуры 1С баз
- **`1c-configs`** - Проектирование конфигураций 1С

### Web Fullstack Skills (для command-center-1c)

- **`react-expert`** - React frontend (frontend/)
- **`api-design`** - REST API дизайн (api-gateway/)

## Pipeline разработки

### 1. Новая задача

```
Пользователь → architect (ВСЕГДА первый!)
             ↓
Architect предлагает план
             ↓
Пользователь одобряет
```

### 2. Реализация кода

```
Approved Plan → coder (ТОЛЬКО после architect)
             ↓
Реализуется код
             ↓
СРАЗУ передача на tester
```

### 3. Тестирование

```
Code from coder → tester (ВСЕГДА после coder)
                ↓
Tests написаны, coverage >= 70%
                ↓
Готово к review/merge
```

### 4. Optional: Code Review

```
Significant code → reviewer (опционально)
                ↓
Review, recommendations
                ↓
Fixes if needed
```

## Компоненты проекта

### Go Services

**API Gateway** (`go-services/api-gateway/`)
- Маршрутизация запросов
- JWT authentication
- Rate limiting
- Интеграция с Orchestrator

**Workers** (`go-services/worker/`)
- Массовая обработка операций
- Goroutines pool для параллелизма
- OData интеграция с 1С базами
- Redis queue processing

### Python/Django (Orchestrator)

**Orchestrator** (`orchestrator/`)
- Бизнес-логика операций
- Template engine для 1С операций
- Celery для async tasks
- PostgreSQL для хранения

### TypeScript/React (Frontend)

**Frontend** (`frontend/`)
- Ant Design Pro компоненты
- Real-time updates через WebSocket
- API integration
- Operation monitoring

## Development Setup

### Первый запуск

```bash
cd /c/1CProject/command-center-1c

# Создать .env (если нет)
cp .env.example .env 2>/dev/null || true

# Запустить сервисы
/dev-start

# Проверить здоровье
/check-health
```

### Регулярная разработка

```bash
# Запустить сервисы
/dev-start

# Работать с кодом
# ... изменить файлы ...

# Запустить тесты перед commit
/test-all

# Смотреть логи если нужно
docker-compose logs -f orchestrator
```

### Перед commit

1. **Убедиться что архитектура обсуждена** - используй architect skill
2. **Запустить тесты** - `/test-all` должен пройти
3. **Code review** - для критичного кода используй reviewer skill
4. **Commit с правильным сообщением** - используй git-expert

## Тестирование

### Команды

```bash
# Все тесты
/test-all

# Python (Orchestrator)
docker-compose exec orchestrator pytest -v

# Go (API Gateway, Workers)
docker-compose exec api-gateway go test -v ./...

# TypeScript (Frontend)
docker-compose exec frontend npm test
```

### Coverage Requirements

- **Python**: >= 70% overall, >= 90% for services.py
- **Go**: >= 70% overall, >= 80% for critical packages
- **TypeScript**: >= 70% overall

## Documentation

### Canonical Documents

- **docs/agent/INDEX.md** - Canonical onboarding surface
- **docs/agent/RUNBOOK.md** - Canonical runtime/debug route
- **docs/agent/VERIFY.md** - Canonical validation route
- **openspec/project.md** - Project context for OpenSpec workflows

### API Documentation

```bash
# API Gateway
# Swagger docs on /api/docs (когда будет реализовано)
# OpenAPI spec on /openapi.json

# Orchestrator
# Django admin on http://localhost:8000/admin (DEBUG=true)
```

## Troubleshooting

### Services не запускаются

```bash
# Проверить лог
docker-compose logs orchestrator

# Перезапустить
docker-compose down
docker-compose up -d

# Очистить всё
docker-compose down -v
docker system prune -a
docker-compose up -d
```

### Тесты падают

```bash
# Убедиться что сервисы запущены
docker-compose ps

# Запустить миграции
/run-migrations

# Запустить тесты с verbose
docker-compose exec orchestrator pytest -vv
```

### Port уже занят

```bash
# Найти процесс
lsof -i :8080

# Убить процесс
kill -9 <PID>

# Или изменить порт в docker-compose.yml
```

## Git Workflow

### Branch naming

```
feature/add-batch-operations
fix/rate-limiting-not-working
bugfix/transaction-timeout
refactor/service-layer
test/api-gateway-auth
docs/architecture-overview
```

### Commit message format

```
feat(orchestrator): implement template validation
fix(worker): resolve goroutine leak
test(api): add comprehensive auth tests
docs(readme): update setup instructions
```

## Ссылки

**Project Documentation:**
- `docs/agent/INDEX.md` - Canonical onboarding surface
- `docs/ROADMAP.md` - Дорожная карта
- `README.md` - Main project README

**External Resources:**
- [1C Developer Docs](https://its.1c.eu/db/v8314doc)
- [Go Documentation](https://golang.org/doc)
- [Django Documentation](https://docs.djangoproject.com)
- [React Documentation](https://react.dev)
- [Ant Design Pro](https://pro.ant.design/)

## Team Communication

Используй следующий процесс для comunicacion с командой:

1. **Для вопросов о архитектуре** - используй architect skill
2. **Для вопросов о коде** - используй coder или reviewer
3. **Для вопросов о тестах** - используй tester skill
4. **Для вопросов о git/workflow** - используй git-expert skill

## Status

**Current Phase:** Phase 1 - Infrastructure Setup (Week 1-2)
**Target:** Balanced Approach (14-16 weeks)
**Metrics:** 200-500 баз параллельно, 1000+ ops/min

---

**Last Updated:** 2025-10-24
**Version:** 1.0
**Maintained by:** Team
