---
name: cc1c-sprint-guide
description: "Track progress in Balanced approach roadmap (16 weeks), identify current phase/week, suggest next tasks from sprint plan, validate completed work."
allowed-tools: ["Read", "Glob", "Grep"]
---

# cc1c-sprint-guide

## Purpose

Отслеживать прогресс разработки CommandCenter1C по Balanced Approach roadmap (14-16 недель), определять текущую фазу и предлагать следующие задачи.

## When to Use

Используй этот skill когда пользователь спрашивает:
- Какой текущий статус проекта?
- Что делать дальше?
- На какой неделе/фазе мы находимся?
- Какие задачи в текущем спринте?
- Что уже завершено?
- Упоминает: roadmap, sprint, progress, phase, week, status, следующие задачи

## ⭐ ВЫБРАННЫЙ ВАРИАНТ: Balanced Approach

**Roadmap:** Balanced Approach (14-16 недель, 5 фаз)
**Документ:** `docs/ROADMAP.md`

**НЕ используем:**
- ~~MVP First (12-14 недель)~~ - отклонен
- ~~Enterprise Grade (18-24 недели)~~ - отклонен

## 📍 ТЕКУЩИЙ СТАТУС

**Текущая фаза:** Phase 1, Week 3-4 - Core Functionality
**Текущий спринт:** Sprint 2.1 - Task Queue & Worker
**Статус:** 🔄 В работе

**Завершено:**
- ✅ Sprint 1.1: Project Setup
- ✅ Sprint 1.2: Database & Core Services  
- ✅ Sprint 1.3: Mock Server Implementation
- ✅ Sprint 1.4: cluster-service Integration

**См. детали:** `{baseDir}/reference/completed-sprints.md`

## Структура Roadmap (5 фаз)

### Phase 1: MVP Foundation (Week 1-6)
- Week 1-2: Infrastructure Setup ✅
- Week 3-4: Core Functionality 🔄 CURRENT
- Week 5-6: Basic Operations ⏳

### Phase 2: Extended Functionality (Week 7-10)
- Week 7-8: Advanced Operations
- Week 9-10: Performance Optimization

### Phase 3: Monitoring & Observability (Week 11-12)
- Week 11: Monitoring Stack
- Week 12: Alerts & Dashboards

### Phase 4: Advanced Features (Week 13-15)
- Week 13: Bulk Operations
- Week 14: Workflow Engine
- Week 15: Analytics

### Phase 5: Production Hardening (Week 16)
- Week 16: Security, Performance Testing, Documentation

**См. детальный план:** `{baseDir}/reference/roadmap-phases.md`

## Следующие задачи (Week 3-4)

### Sprint 2.1: Task Queue & Worker (5 дней) 🔄 CURRENT

**Задачи:**
1. ✅ Configure Celery with Redis backend
2. 🔄 Implement basic task types (ping, test_connection)
3. ⏳ Create Go Worker with goroutine pool (10-20 workers)
4. ⏳ Add task status tracking
5. ⏳ Implement error handling and retry logic

**Completion Criteria:**
- Tasks successfully enqueue and process
- Worker handles 10-20 concurrent tasks
- Failed tasks retry automatically
- Task results persist in database

### Sprint 2.2: Template System & First Operation (5 дней) ⏳ NEXT

**Задачи:**
1. Design template model and storage
2. Implement template rendering (Jinja2)
3. Create "Mass Update Users" operation template
4. Add operation execution tracking
5. Implement basic validation rules

**Completion Criteria:**
- Templates render correctly with test data
- Mass update operation works on mock server
- Operation history saved to database

## Как отслеживать прогресс

### Чеклист для каждого спринта

**Before Sprint:**
- [ ] Review sprint goals и deliverables
- [ ] Проверить dependencies (предыдущие спринты завершены?)
- [ ] Setup branch (если используется Git Flow)

**During Sprint:**
- [ ] Daily progress tracking
- [ ] Update task status (✅/🔄/⏳)
- [ ] Document blockers и challenges

**After Sprint:**
- [ ] Verify completion criteria
- [ ] Run all tests (coverage > 70%)
- [ ] Update metrics
- [ ] Document lessons learned
- [ ] Add entry в `completed-sprints.md`

### Метрики для проверки

**Code Quality:**
- Test coverage > 70%
- Linter warnings = 0
- Security scan: no critical issues

**Performance:**
- API p95 latency < 500ms
- Health checks < 100ms
- Database queries < 50ms (p95)

**Functionality:**
- All acceptance criteria met
- Integration tests passing
- Manual testing completed

## Critical Milestones

### Milestone 1: Basic Infrastructure (Week 2) ✅ DONE
- Docker Compose working
- Health checks passing
- Basic CRUD operations

### Milestone 2: Task Processing (Week 4) 🔄 CURRENT
- Celery + Workers functional
- First operation executable
- Template system working

### Milestone 3: Production MVP (Week 6) ⏳
- API Gateway + Frontend
- 5 operation types working
- Basic monitoring

### Milestone 4: Extended Features (Week 10) ⏳
- Scheduling working
- Performance optimized
- 50-100 workers scaling

### Milestone 5: Production Ready (Week 16) ⏳
- Security hardened
- Load tested
- Fully documented

## Quick Commands

### Проверить текущую фазу
```bash
# Прочитать ROADMAP.md
cat docs/ROADMAP.md | grep "Phase 1"

# Проверить последние commits
git log --oneline -10
```

### Посмотреть завершенные спринты
```bash
ls docs/archive/sprints/
cat docs/archive/sprints/sprint-1.4-summary.md
```

### Проверить метрики
```bash
# Test coverage
cd orchestrator && pytest --cov
cd go-services/api-gateway && go test -cover ./...

# Health checks
./scripts/dev/health-check.sh
```

## Common Questions

**Q: Мы отстаем от roadmap?**
A: Сравни текущую неделю с запланированной фазой. Если Phase 1 Week 3-4, а прошло > 4 недель - да.

**Q: Можно ли пропустить фазу?**
A: Нет. Каждая фаза строится на предыдущей. Phase 2 требует completion Phase 1.

**Q: Как адаптировать roadmap?**
A: Обнови `docs/ROADMAP.md`, но сохрани общую структуру 5 фаз. Документируй changes.

**Q: Что делать если спринт затягивается?**
A: 1) Проверь blockers 2) Reduce scope (move Nice-to-Have items) 3) Не жертвуй quality.

## Tips for Using This Guide

1. **Начинай каждую сессию** с проверки текущего статуса
2. **Обновляй progress** после каждого завершенного таска
3. **Документируй challenges** для будущих спринтов
4. **Проверяй metrics** перед закрытием спринта
5. **Используй checklists** - они предотвращают пропуски

## References

**Skill directory:** `{baseDir}/.claude/skills/cc1c-sprint-guide/`

**Reference docs:**
- `{baseDir}/reference/roadmap-phases.md` - Детальное описание всех 5 фаз
- `{baseDir}/reference/completed-sprints.md` - История завершенных спринтов

**Project docs:**
- `docs/ROADMAP.md` - Основной Balanced Approach roadmap
- `docs/START_HERE.md` - Быстрый старт по документации
- `docs/archive/sprints/` - Детальная история каждого спринта

## Related Skills

- `cc1c-devops` - Запуск сервисов, health checks
- `cc1c-test-runner` - Запуск тестов, проверка coverage
- `cc1c-navigator` - Навигация по структуре проекта
