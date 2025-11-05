# Local Development Migration - Summary

## Overview

Проект успешно мигрирован с полностью Docker-based разработки на **hybrid подход**:
- **Infrastructure** (PostgreSQL, Redis, ClickHouse, ras-grpc-gw) → Docker
- **Application services** (Django, Celery, Go, Frontend) → Host machine

## Created Files

### Scripts (scripts/dev/)

1. **start-all.sh** - Запустить все сервисы локально
   - Запускает Docker infrastructure
   - Применяет Django миграции
   - Запускает все application services в background
   - Сохраняет PID в `pids/` и логи в `logs/`

2. **stop-all.sh** - Остановить все сервисы
   - Graceful shutdown (SIGTERM → SIGKILL)
   - Останавливает Docker infrastructure
   - Очищает PID файлы
   - Проверяет orphan процессы

3. **restart.sh** - Перезапустить конкретный сервис
   - Usage: `./restart.sh <service-name>`
   - Graceful restart с проверкой запуска

4. **logs.sh** - Просмотр логов
   - Usage: `./logs.sh <service-name> [lines]`
   - Поддерживает tail -f и просмотр всех сервисов

5. **health-check.sh** - Проверка статуса всех сервисов
   - Проверяет процессы (PID)
   - Проверяет HTTP endpoints
   - Проверяет Docker services
   - Проверяет порты

6. **README.md** - Документация скриптов

### Docker Compose

**docker-compose.local.yml** - Инфраструктурные сервисы
- PostgreSQL (port 5432)
- Redis (port 6379)
- ClickHouse (port 8123, 9000) - опционально, profile: analytics
- ras-grpc-gw (port 9999) - опционально, profile: ras

### Environment

**.env.local.example** - Пример конфигурации для локальной разработки
- Ключевые отличия от Docker:
  - `DB_HOST=localhost` (не `postgres`)
  - `REDIS_HOST=localhost` (не `redis`)
  - `ORCHESTRATOR_URL=http://localhost:8000` (не `http://orchestrator:8000`)

### Claude Code Integration

#### Skills

**.claude/skills/cc1c-devops/SKILL.md** - Полностью переписан
- Version 2.0 (Local Development)
- Управление локальными процессами
- PID-based process management
- Local logs viewing
- Health checks для host services

#### Commands

1. **.claude/commands/dev-start.md** - Обновлен
   - Запуск через `./scripts/dev/start-all.sh`
   - Детальное описание процесса
   - Troubleshooting секции

2. **.claude/commands/check-health.md** - Обновлен
   - Проверка локальных процессов
   - Проверка Docker infrastructure
   - Детальная диагностика

3. **.claude/commands/restart-service.md** - NEW
   - Перезапуск конкретного сервиса
   - Use cases и примеры
   - Troubleshooting

### Documentation

**docs/LOCAL_DEVELOPMENT_GUIDE.md** - Полное руководство
- Architecture overview
- Prerequisites
- First time setup
- Daily workflow
- Scripts reference
- Environment configuration
- Detailed troubleshooting
- Advanced topics
- FAQ

## Service Architecture

### Before (Docker only)

```
┌───────────────────────────┐
│      Docker Compose       │
├───────────────────────────┤
│  Frontend                 │
│  API Gateway              │
│  Orchestrator             │
│  Workers                  │
│  PostgreSQL               │
│  Redis                    │
└───────────────────────────┘
```

### After (Hybrid)

```
┌───────────────────────────┐
│     HOST MACHINE          │
├───────────────────────────┤
│  Frontend (3000)          │
│  API Gateway (8080)       │
│  Orchestrator (8000)      │
│  Cluster Service (8088)   │
│  Celery Worker/Beat       │
│  Go Worker                │
└──────────┬────────────────┘
           │ localhost
┌──────────▼────────────────┐
│       DOCKER              │
├───────────────────────────┤
│  PostgreSQL (5432)        │
│  Redis (6379)             │
│  ClickHouse (8123, 9000)  │
│  ras-grpc-gw (9999)       │
└───────────────────────────┘
```

## Benefits

### Development Speed
- ✅ Hot reload без rebuild Docker образов
- ✅ Нативная производительность (no virtualization overhead)
- ✅ Быстрый restart отдельных сервисов
- ✅ Instant code changes для Django/Go/React

### Debugging
- ✅ Прямой доступ к процессам (PID-based)
- ✅ Native IDE debugging (VS Code, GoLand, PyCharm)
- ✅ Простой просмотр логов (tail -f logs/*.log)
- ✅ Direct stdout/stderr output

### Resource Efficiency
- ✅ Меньше памяти (no container overhead)
- ✅ Меньше CPU usage
- ✅ Меньше disk space (no duplicate images)

### Simplicity
- ✅ Простое управление (bash scripts)
- ✅ PID-based process management
- ✅ Standard Unix signals (SIGTERM, SIGKILL)
- ✅ Familiar workflow (start, stop, restart, logs)

## Usage

### Quick Start

```bash
# First time
cp .env.local.example .env.local
nano .env.local  # configure
./scripts/dev/start-all.sh

# Daily
./scripts/dev/start-all.sh     # morning
./scripts/dev/restart.sh <svc> # after code changes
./scripts/dev/logs.sh <svc>    # view logs
./scripts/dev/health-check.sh  # check status
./scripts/dev/stop-all.sh      # evening
```

### Integration with Claude Code

```bash
# Through commands
/dev-start           # start all services
/check-health        # check status
/restart-service     # restart specific service

# Through skills
Use cc1c-devops skill for DevOps operations
```

## Migration Checklist

### Completed ✅

- [x] Создан `docker-compose.local.yml` для infrastructure
- [x] Создан `.env.local.example` с правильными хостами (localhost)
- [x] Написаны bash скрипты управления:
  - [x] start-all.sh
  - [x] stop-all.sh
  - [x] restart.sh
  - [x] logs.sh
  - [x] health-check.sh
- [x] Обновлен cc1c-devops SKILL.md (v2.0)
- [x] Обновлены команды:
  - [x] dev-start.md
  - [x] check-health.md
  - [x] restart-service.md (new)
- [x] Создана полная документация (LOCAL_DEVELOPMENT_GUIDE.md)
- [x] Скрипты сделаны исполняемыми (chmod +x)
- [x] .gitignore уже содержит нужные правила

### Not Done (Optional)

- [ ] Makefile targets для удобства (make dev-local, make health, etc.)
- [ ] Windows batch scripts (.bat) для native Windows users
- [ ] VSCode tasks.json для integration с IDE
- [ ] Hot reload configuration (air для Go, watchdog для Python)
- [ ] Process monitoring tool (supervisor, pm2, или custom)
- [ ] Automated testing integration
- [ ] CI/CD adjustments

## Troubleshooting Quick Reference

### Port already in use
```bash
netstat -ano | findstr :<port>  # Windows
taskkill /PID <pid> /F
```

### Database connection error
```bash
# Check .env.local has DB_HOST=localhost (NOT postgres)
docker-compose -f docker-compose.local.yml restart postgres
./scripts/dev/restart.sh orchestrator
```

### Service won't start
```bash
cat logs/<service>.log  # check logs
./scripts/dev/restart.sh <service>
```

### PID files lost
```bash
rm -rf pids/*.pid
./scripts/dev/stop-all.sh
./scripts/dev/start-all.sh
```

## Next Steps (Recommended)

1. **Test the setup:**
   ```bash
   ./scripts/dev/start-all.sh
   ./scripts/dev/health-check.sh
   ```

2. **Create .env.local from example:**
   ```bash
   cp .env.local.example .env.local
   # Edit secrets and passwords
   ```

3. **Install dependencies:**
   ```bash
   # Python
   cd orchestrator && python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt

   # Node.js
   cd frontend && npm install
   ```

4. **First run:**
   ```bash
   ./scripts/dev/start-all.sh
   ```

5. **Verify everything works:**
   ```bash
   ./scripts/dev/health-check.sh
   curl http://localhost:8080/health
   curl http://localhost:8000/health
   ```

## Rollback Plan

If something goes wrong, можно вернуться к Docker:

```bash
# Stop local development
./scripts/dev/stop-all.sh

# Use old docker-compose.yml
docker-compose up -d

# Or keep both approaches available
# - docker-compose.yml - full Docker
# - docker-compose.local.yml - hybrid (infrastructure only)
```

## Support

- **Documentation:** `docs/LOCAL_DEVELOPMENT_GUIDE.md`
- **Scripts README:** `scripts/dev/README.md`
- **Skill:** `.claude/skills/cc1c-devops/SKILL.md`
- **Commands:** `.claude/commands/dev-start.md`, `check-health.md`, `restart-service.md`

---

**Migration Date:** 2025-11-03
**Status:** ✅ Complete
**Version:** 1.0
