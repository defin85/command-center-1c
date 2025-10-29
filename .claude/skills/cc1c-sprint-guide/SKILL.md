---
name: cc1c-sprint-guide
description: "Track progress in Balanced approach roadmap (16 weeks), identify current phase/week, suggest next tasks from sprint plan, validate completed work against roadmap checkpoints. Use when user asks about project status, what to do next, current sprint, roadmap progress, or mentions phases, weeks, balanced approach."
allowed-tools: ["Read"]
---

# cc1c-sprint-guide

## Purpose

Помочь команде ориентироваться в roadmap проекта (Balanced approach - 16 недель), отслеживать прогресс и понимать что делать дальше.

> ⚠️ **ВНИМАНИЕ:** Статус проекта в этом документе может устареть. Всегда проверяй актуальную информацию в `docs/ROADMAP.md` для получения последних данных о прогрессе.

## When to Use

Используй этот skill когда:
- Вопросы о текущем статусе проекта
- "Что делать дальше?"
- "Где мы сейчас в roadmap?"
- Проверка выполнения задач спринта
- Пользователь упоминает: roadmap, sprint, phase, week, progress, status, balanced approach

## ⭐ ВЫБРАННЫЙ ВАРИАНТ: Balanced Approach

**Критически важно:**
- Проект реализуется **ТОЛЬКО по варианту Balanced**
- В ROADMAP.md описаны 3 варианта (MVP, Balanced, Enterprise) для справки
- **НО:** Работа ведется **строго по Balanced плану** (Phases 1-5)

**Основные параметры Balanced:**
- **Срок:** 14-16 недель (4 месяца)
- **Команда:** 3-4 разработчика
- **Результат:** Production-ready система с полным мониторингом
- **Масштаб:** До 500 баз параллельно, 1000+ ops/min

## Структура Roadmap (Balanced)

### Overview - 5 Phases

```
Phase 1: MVP Foundation          (Week 1-6)
    ├─ Week 1-2: Infrastructure Setup
    ├─ Week 3-4: Core Functionality
    └─ Week 5-6: Basic Operations

Phase 2: Extended Functionality  (Week 7-10)
    ├─ Week 7-8: Advanced Operations
    └─ Week 9-10: Performance Optimization

Phase 3: Monitoring & Observability (Week 11-12)
    ├─ Week 11: Monitoring Stack
    └─ Week 12: Alerts & Dashboards

Phase 4: Advanced Features       (Week 13-15)
    ├─ Week 13: Bulk Operations
    ├─ Week 14: Workflow Engine
    └─ Week 15: Analytics

Phase 5: Production Hardening    (Week 16)
    └─ Week 16: Security, Performance, Docs
```

## 📍 ТЕКУЩИЙ СТАТУС

**Дата:** 2025-01-17
**Текущая фаза:** Phase 1 - MVP Foundation
**Неделя:** Week 1-2 (Infrastructure Setup)
**Статус:** ✅ Sprint 1.2 ЗАВЕРШЕН + Mock Server ГОТОВ

### Завершенные спринты

| Sprint | Период | Статус | Дата завершения |
|--------|--------|--------|-----------------|
| Sprint 1.1 | Week 1-2 | ✅ DONE | 2025-01-16 |
| Sprint 1.2 | Week 1-2 | ✅ DONE | 2025-01-17 |
| Mock Server | Week 1-2 | ✅ DONE | 2025-01-17 |

### Достигнутые метрики

| Метрика | Цель Phase 1 | Результат | Статус |
|---------|--------------|-----------|--------|
| Mock Server throughput | 100 ops/min | **616 req/s** | ✅ Превышено 369x |
| Success rate | 95%+ | **100%** | ✅ Превышено |
| Response time | <100ms | **14ms avg** | ✅ В 7 раз лучше |
| Test coverage | Unit tests | Unit + Integration + Perf | ✅ Превышено |

## Phase 1: MVP Foundation (Week 1-6)

### Week 1-2: Infrastructure Setup ✅ COMPLETED

#### Sprint 1.1: Project Setup (5 дней) ✅
- [x] Monorepo structure created
- [x] Docker Compose configured
- [x] Makefile commands implemented
- [x] Go modules initialized
- [x] Django project setup
- [x] Basic Dockerfiles created

#### Sprint 1.2: Database & Core Services (5 дней) ✅
- [x] Django models (Database, Operation, Task)
- [x] Django migrations
- [x] OData client implementation
- [x] REST API (13 endpoints)
- [x] Django Admin interface
- [x] Health check endpoints

#### Mock Server Implementation ✅
- [x] Flask Mock 1C OData v3 server
- [x] 3 mock instances (different data)
- [x] Docker demo environment
- [x] Automated test suite (41 tests)
- [x] Performance benchmarks

**Достижения Week 1-2:**
- ✅ Инфраструктура готова
- ✅ База данных работает
- ✅ OData integration реализован
- ✅ REST API доступен
- ✅ Тесты проходят

### Week 3-4: Core Functionality 🔄 NEXT

#### Sprint 2.1: Task Queue & Worker (5 дней)

**Цель:** Создать систему очередей и базовый Go Worker

**Задачи Orchestrator:**
- [ ] Celery setup (config/celery.py)
- [ ] Redis integration для queue
- [ ] Базовые Celery tasks (apps/operations/tasks.py)
- [ ] Task dispatching logic
- [ ] Task status tracking

**Задачи Go Worker:**
- [ ] Worker main.go structure
- [ ] Redis queue consumer
- [ ] OData client integration
- [ ] Worker pool implementation (goroutines)
- [ ] Result reporting to Redis

**Интеграция:**
- [ ] Orchestrator → Redis → Worker flow
- [ ] Task serialization/deserialization
- [ ] Error handling & retries

**Тесты:**
- [ ] Unit tests (Celery tasks)
- [ ] Integration test (end-to-end)
- [ ] Worker pool concurrency test

**Deliverable:** Operation запущенная через Orchestrator обрабатывается Worker-ом

**Estimated time:** 5 дней

#### Sprint 2.2: Template System & First Operation (5 дней)

**Цель:** Реализовать Template Engine и первую операцию

**Задачи Template System:**
- [ ] OperationTemplate model (apps/templates/models.py)
- [ ] Template engine implementation (apps/templates/engine.py)
- [ ] Template validation logic
- [ ] CRUD API для templates
- [ ] Template renderer (подстановка переменных)

**Задачи First Operation:**
- [ ] Operation type: "create_users_bulk"
- [ ] Template для создания пользователей в 1С
- [ ] Batch processing logic
- [ ] Соблюдение ограничения транзакций < 15 секунд

**Frontend (начало):**
- [ ] React app initialized
- [ ] Basic layout (header, sidebar)
- [ ] Operations list page (stub)

**Тесты:**
- [ ] Template engine unit tests
- [ ] Operation execution integration test
- [ ] Template validation tests

**Deliverable:** Можно создать операцию "создать 100 пользователей в 10 базах" и она выполнится

**Estimated time:** 5 дней

**Week 3-4 Completion Criteria:**
- ✅ Task queue работает
- ✅ Worker обрабатывает задачи
- ✅ Template system функционирует
- ✅ Первая операция выполняется успешно

### Week 5-6: Basic Operations

#### Sprint 3.1: API Gateway & Frontend (5 дней)

**API Gateway (Go):**
- [ ] Gin router setup
- [ ] Proxy routes to Orchestrator
- [ ] JWT authentication middleware
- [ ] Rate limiting
- [ ] Request logging

**Frontend:**
- [ ] Operations dashboard page
- [ ] Create operation form
- [ ] Operation status monitoring
- [ ] WebSocket для real-time updates
- [ ] Basic UI components

**Тесты:**
- [ ] API Gateway integration tests
- [ ] Frontend unit tests (React components)
- [ ] E2E test (create operation → see result)

**Deliverable:** User может создать операцию через UI и видеть её выполнение в real-time

**Estimated time:** 5 дней

#### Sprint 3.2: Multiple Operation Types (5 дней)

**Новые типы операций:**
- [ ] Update existing records
- [ ] Delete records
- [ ] Read/Export data

**Улучшения:**
- [ ] Parallel processing (multiple bases)
- [ ] Progress tracking
- [ ] Error aggregation
- [ ] Retry failed tasks

**Тесты:**
- [ ] Each operation type test
- [ ] Parallel execution test
- [ ] Error handling test

**Deliverable:** 4 типа операций работают на 50+ базах

**Estimated time:** 5 дней

**Week 5-6 Completion Criteria:**
- ✅ API Gateway работает
- ✅ Frontend UI функционален
- ✅ 4+ типов операций реализованы
- ✅ 50+ баз обрабатываются параллельно

**Phase 1 Target Metrics (Week 6):**
- 50+ баз параллельно
- 100 ops/min
- 1 тип операций работает стабильно
- 95%+ success rate

## Phase 2: Extended Functionality (Week 7-10)

### Week 7-8: Advanced Operations

#### Sprint 4.1: Complex Operations
- [ ] Multi-step operations (workflows)
- [ ] Conditional logic в templates
- [ ] Data transformations
- [ ] Cross-database operations

#### Sprint 4.2: Scheduling & Automation
- [ ] Scheduled operations (cron-like)
- [ ] Recurring operations
- [ ] Operation dependencies
- [ ] Automatic retries

**Week 7-8 Target:**
- Advanced template features
- Scheduled operations work
- 100+ баз параллельно

### Week 9-10: Performance Optimization

#### Sprint 5.1: Scaling Workers
- [ ] Auto-scaling workers по queue depth
- [ ] Load balancing
- [ ] Connection pooling optimization
- [ ] Memory usage optimization

#### Sprint 5.2: Database Optimization
- [ ] Query optimization
- [ ] Database indexing
- [ ] Caching strategy (Redis)
- [ ] Pagination для больших datasets

**Week 9-10 Target:**
- 200+ баз параллельно
- 500 ops/min
- Optimized resource usage

**Phase 2 Target Metrics (Week 10):**
- 200+ баз параллельно
- 500 ops/min
- 4+ типов операций
- Auto-scaling work

## Phase 3: Monitoring & Observability (Week 11-12)

### Week 11: Monitoring Stack

#### Sprint 6.1: Prometheus & Grafana
- [ ] Prometheus setup
- [ ] Metrics collection (Go services)
- [ ] Metrics collection (Django)
- [ ] Grafana dashboards
- [ ] Service discovery

**Metrics to track:**
- Request rate
- Error rate
- Response time (p50, p95, p99)
- Queue depth
- Worker utilization
- Database connections
- Cache hit rate

### Week 12: Alerts & Dashboards

#### Sprint 6.2: Alerting
- [ ] AlertManager setup
- [ ] Critical alerts (service down, high error rate)
- [ ] Warning alerts (high latency, queue buildup)
- [ ] Notification channels (Slack, email)

#### Custom Dashboards
- [ ] Operations dashboard
- [ ] System health dashboard
- [ ] Performance dashboard
- [ ] Business metrics dashboard

**Phase 3 Target Metrics (Week 12):**
- Full monitoring stack operational
- Real-time dashboards
- Alerting configured
- 95%+ uptime

## Phase 4: Advanced Features (Week 13-15)

### Week 13: Bulk Operations

#### Sprint 7.1: Large Scale Processing
- [ ] Chunking strategy для 10k+ operations
- [ ] Progress tracking для bulk ops
- [ ] Pause/Resume functionality
- [ ] Rollback mechanism

**Target:** 10,000+ objects в одной операции

### Week 14: Workflow Engine

#### Sprint 8.1: Workflow System
- [ ] Workflow definition (YAML/JSON)
- [ ] Step execution engine
- [ ] State management
- [ ] Error handling per step

**Example workflow:**
```yaml
workflow:
  - step: create_users
  - step: assign_permissions
  - step: send_notifications
```

### Week 15: Analytics

#### Sprint 9.1: Analytics & Reporting
- [ ] ClickHouse integration
- [ ] Historical data storage
- [ ] Analytics queries
- [ ] Reports generation
- [ ] Export functionality

**Phase 4 Target Metrics (Week 15):**
- 500 баз параллельно
- 1000+ ops/min
- Workflow engine работает
- Analytics доступны

## Phase 5: Production Hardening (Week 16)

### Week 16: Final Sprint

#### Sprint 10.1: Security Hardening
- [ ] Security audit
- [ ] Input validation everywhere
- [ ] Rate limiting tuning
- [ ] HTTPS enforcement
- [ ] Secrets management (Vault)

#### Sprint 10.2: Performance Testing
- [ ] Load testing (500 баз)
- [ ] Stress testing
- [ ] Failure scenario testing
- [ ] Recovery testing

#### Sprint 10.3: Documentation
- [ ] API documentation complete
- [ ] Deployment guide
- [ ] Operations runbook
- [ ] User manual
- [ ] Architecture docs

**Phase 5 Target Metrics (Week 16) - PRODUCTION READY:**
- 500 баз параллельно
- 1000+ ops/min
- 4+ типов операций
- Full monitoring
- 95%+ success rate
- 99% uptime
- Complete documentation

## Следующие задачи (Week 3-4)

### Immediate Next Steps

**Sprint 2.1 (5 дней):**
1. Setup Celery в Orchestrator
2. Создать базовый Go Worker
3. Реализовать Redis queue integration
4. Написать integration tests

**Sprint 2.2 (5 дней):**
1. Создать OperationTemplate model
2. Реализовать Template Engine
3. Создать первую операцию (create_users_bulk)
4. End-to-End тестирование

### Priority Order

1. **Highest:** Celery setup (критично для architecture)
2. **High:** Go Worker базовая версия
3. **High:** Template Engine
4. **Medium:** First operation implementation
5. **Medium:** Frontend initial setup

## Как отслеживать прогресс

### Чеклист для каждого спринта

**Перед началом:**
- [ ] Прочитать описание спринта в ROADMAP.md
- [ ] Понять deliverables
- [ ] Оценить сложность задач

**Во время спринта:**
- [ ] Выполнять задачи по списку
- [ ] Писать тесты параллельно с кодом
- [ ] Commit-ить часто с правильными сообщениями
- [ ] Обновлять статус в ROADMAP.md

**После спринта:**
- [ ] Проверить все задачи выполнены
- [ ] Все тесты проходят
- [ ] Code review завершен
- [ ] Обновить ROADMAP.md со статусом ✅ DONE

### Метрики для проверки

**Week 6 (Phase 1 complete):**
```bash
# Test 50 bases processing
python test_operations.py --bases=50 --operation=create_users

# Expected:
# - Throughput: 100+ ops/min
# - Success rate: 95%+
# - All tests passing
```

**Week 10 (Phase 2 complete):**
```bash
# Test 200 bases processing
python test_operations.py --bases=200 --operation=bulk_create

# Expected:
# - Throughput: 500+ ops/min
# - Success rate: 95%+
# - Auto-scaling works
```

**Week 16 (Production ready):**
```bash
# Load test
python load_test.py --bases=500 --duration=1h

# Expected:
# - Throughput: 1000+ ops/min
# - Success rate: 95%+
# - 99% uptime
# - All monitors green
```

## Common Questions

**Q: Где мы сейчас?**
A: Phase 1, Week 1-2 ЗАВЕРШЕНО. Sprint 1.2 + Mock Server готовы. Переходим к Week 3-4 (Core Functionality).

**Q: Что делать дальше?**
A: Sprint 2.1 - Task Queue & Worker implementation (5 дней). См. детальный план выше.

**Q: Когда Phase 1 будет готова?**
A: Week 6 (конец января 2025). Осталось 4 недели работы.

**Q: Отстаем ли мы от графика?**
A: Нет! Week 1-2 завершены успешно, даже с превышением целевых метрик.

**Q: Что если не успеваем?**
A: Balanced approach имеет буфер. Можно перенести менее критичные задачи в следующий спринт.

**Q: Как понять что Phase готова?**
A: Проверить Target Metrics для этой Phase. Все метрики должны быть достигнуты.

## Tips for Using This Guide

1. **Всегда проверяй текущий статус** - см. раздел "ТЕКУЩИЙ СТАТУС"
2. **Читай полный ROADMAP.md** - там больше деталей
3. **Следуй порядку спринтов** - не прыгай вперед
4. **Проверяй метрики** - они показывают реальный прогресс
5. **Обновляй ROADMAP.md** - держи документацию актуальной

## References

- **Полный roadmap:** `docs/ROADMAP.md` (⭐ ГЛАВНЫЙ ДОКУМЕНТ)
- **Project overview:** `CLAUDE.md`
- **Quick start:** `docs/START_HERE.md`
- **Executive summary:** `docs/EXECUTIVE_SUMMARY.md`

## Quick Commands

```bash
# Check current progress
cat docs/ROADMAP.md | grep "ТЕКУЩИЙ СТАТУС" -A 20

# View next tasks
cat docs/ROADMAP.md | grep "Week 3-4" -A 50

# Check metrics
cat docs/ROADMAP.md | grep "метрики" -A 10
```

## Related Skills

При планировании спринта используй:
- `cc1c-navigator` - для понимания текущей структуры перед началом задач
- `cc1c-service-builder` - для реализации запланированных компонентов
- `cc1c-test-runner` - для проверки completion criteria
- `cc1c-devops` - для deployment задач из спринта

---

**Version:** 1.0
**Last Updated:** 2025-01-17
**Changelog:**
- 1.0 (2025-01-17): Initial release for Balanced approach tracking
