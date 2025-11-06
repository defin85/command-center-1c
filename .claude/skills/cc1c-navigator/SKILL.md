---
name: cc1c-navigator
description: "Navigate monorepo structure, locate components, explain service dependencies."
allowed-tools: ["Read", "Glob", "Grep"]
---

# cc1c-navigator

## Purpose

Помочь навигировать по CommandCenter1C monorepo, находить компоненты, понимать зависимости между сервисами.

## When to Use

Используй этот skill когда пользователь:
- Ищет где находится конкретный код
- Спрашивает где создать новый файл
- Нужно понять зависимости между сервисами
- Спрашивает о структуре проекта
- Ищет примеры кода
- Упоминает: monorepo, structure, где находится, найти код, dependencies

## Quick Navigation

**Основные директории:**
```
go-services/          # Go микросервисы
orchestrator/         # Django backend
frontend/             # React frontend
infrastructure/       # Docker, K8s, monitoring
docs/                 # Документация
scripts/              # Dev scripts
.claude/              # AI skills
```

**См. полную структуру:** `{baseDir}/reference/monorepo-structure.md`

## Component Location Patterns

### Где находится логика X?

**Go микросервисы:**
- Entry point: `cmd/main.go`
- HTTP handlers: `internal/handlers/`
- Business logic: `internal/service/`
- Data access: `internal/repository/`

**Django apps:**
- Data models: `models.py`
- API endpoints: `views.py`
- Serialization: `serializers.py`
- Async tasks: `tasks.py`

**React:**
- API client: `src/api/`
- UI components: `src/components/`
- Pages: `src/pages/`
- State: `src/stores/`

### Где искать файлы?

| Что | Где | Пример |
|-----|-----|--------|
| Go handlers | `go-services/*/internal/handlers/` | `api-gateway/internal/handlers/auth_handler.go` |
| Django models | `orchestrator/apps/*/models.py` | `databases/models.py` |
| React components | `frontend/src/components/` | `components/databases/DatabaseList.tsx` |
| Celery tasks | `orchestrator/apps/*/tasks.py` | `operations/tasks.py` |
| Config files | Root, `config/`, `infrastructure/` | `.env.local` |
| Scripts | `scripts/dev/` | `start-all.sh` |

## Service Dependencies (Quick)

```
Frontend (:3000)
  ↓
API Gateway (:8080)
  ↓
Orchestrator (:8000)
  ↓
PostgreSQL + Redis
  ↓
Celery → Go Workers → 1C
```

**cluster-service:**
```
cluster-service (:8088) → ras-grpc-gw (:9999) → RAS (:1545)
```

**См. детальный граф:** `{baseDir}/reference/service-dependencies.md`

## Common Searches

### Найти использование Database model
```bash
grep -r "Database" orchestrator/apps/ --include="*.py"
```

### Найти HTTP handlers (Go)
```bash
ls go-services/*/internal/handlers/*_handler.go
```

### Найти React components с API calls
```bash
grep -r "getDatabases" frontend/src/ --include="*.ts*"
```

### Найти Celery tasks
```bash
ls orchestrator/apps/*/tasks.py
grep -r "@task" orchestrator/ --include="*.py"
```

## Data Flow Patterns

**User Operation (Write):**
User → Frontend → API Gateway → Orchestrator → Celery → Go Worker → 1C

**Cluster Monitoring (Read):**
User → Frontend → cluster-service → ras-grpc-gw → RAS

## Critical Constraints

1. Go shared code → `go-services/shared/` (используется всеми)
2. Django apps независимы → минимум cross-app imports
3. Frontend → API Gateway ТОЛЬКО (без прямых вызовов Django)
4. ras-grpc-gw запускай первым (cluster-service зависит)
5. Go binaries: `cc1c-<service>.exe`

## Quick Commands

**Навигация:**
```bash
cd go-services/api-gateway
cd orchestrator/apps/databases
cd frontend/src/components
```

**Поиск:**
```bash
find . -name "models.py"
grep -r "OneCODataAdapter" orchestrator/
grep -r "TODO" --include="*.py" --include="*.go"
```

## References

**Skill directory:** `{baseDir}/.claude/skills/cc1c-navigator/`

**Reference:**
- `{baseDir}/reference/monorepo-structure.md` - Полная структура
- `{baseDir}/reference/service-dependencies.md` - Граф зависимостей

**Project docs:**
- `docs/START_HERE.md` - Быстрый старт
- `CLAUDE.md` - AI инструкции
- `README.md` - Project README

## Related Skills

- `cc1c-devops` - Запуск сервисов
- `cc1c-service-builder` - Создание компонентов
- `cc1c-sprint-guide` - Roadmap и фазы
