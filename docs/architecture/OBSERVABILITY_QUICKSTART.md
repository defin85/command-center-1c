# Observability & Unified Architecture - Quick Start

**Version:** 1.0
**Date:** 2025-11-19

## TL;DR (30 секунд)

**Проблема:** RAS integration не работает (LockInfobase падает) + невозможно отследить операции через микросервисы

**Решение:** Два связанных roadmap'а:

1. **[RADICAL_1C_CONTROL_PLANE_ROADMAP.md](../roadmaps/RADICAL_1C_CONTROL_PLANE_ROADMAP.md)** - Direct RAS in Worker + unified drivers
2. **[REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md)** - 10 weeks: Distributed Tracing + Real-Time UI

**Рекомендация:** Начать с MVP (4 weeks), параллельно стартовать tracing (Week 1-4 из tracking roadmap)

---

## Два Roadmap'а - Как связаны?

### Direct RAS in Worker (Основной)

**Фокус:** Унификация архитектуры + исправление RAS integration

**Scope:**
- Direct RAS operations внутри Worker
- Новая реализация Lock/Unlock (RegInfoBase вместо UpdateInfobase)
- Basic tracing (Phase 1-2)

**Timeline:**
- **MVP:** 4 weeks
- **Full:** 8 weeks (MVP + tracing infrastructure + debug tools)

**Приоритет:** 🔥 КРИТИЧНО - без этого extension install не работает

### Real-Time Operation Tracking (Дополнительный)

**Фокус:** Observability + Real-Time Monitoring

**Scope:**
- OpenTelemetry + Jaeger distributed tracing (full instrumentation)
- Real-time metrics + WebSocket aggregator
- Service Mesh Monitor UI (aggregate view)
- Operation Trace Viewer UI (individual tracking)
- cc1c-debug CLI tools

**Timeline:** 10 weeks (standalone)

**Приоритет:** 💡 ВАЖНО - для debugging и user experience

---

## Выбор стратегии

### Вариант A: MVP Only (4 weeks)

**Делаем:**
- ✅ Direct RAS in Worker
- ✅ New Lock/Unlock implementation
- ✅ Worker migration to gRPC
- ❌ No distributed tracing
- ❌ No real-time UI

**Плюсы:**
- ✅ Быстрый результат (4 weeks)
- ✅ Extension install заработает
- ✅ Минимальный риск

**Минусы:**
- ❌ Debugging = просмотр логов вручную
- ❌ Нет visibility для пользователей
- ❌ Сложно диагностировать проблемы

**Когда выбрать:** Нужно срочно починить extension install, tracing можем добавить позже

---

### Вариант B: MVP + Basic Tracing (6 weeks)

**Делаем:**
- ✅ Direct RAS (4 weeks)
- ✅ Jaeger + OpenTelemetry infrastructure (Week 5-6)
- ✅ Instrument all services
- ✅ Correlation ID propagation
- ❌ No custom UI (используем Jaeger UI)

**Плюсы:**
- ✅ Extension install работает
- ✅ Можно debugging через Jaeger UI
- ✅ Correlation ID во всех логах
- ✅ Foundation для future UI

**Минусы:**
- ❌ Jaeger UI не user-friendly (для админов, не для бизнеса)
- ❌ Нет real-time updates

**Когда выбрать:** Хотим observability, но custom UI не критичен

---

### Вариант C: Full Stack (12 weeks)

**Делаем:**
- ✅ Direct RAS (4 weeks)
- ✅ Distributed Tracing infrastructure (Week 5-6)
- ✅ Real-Time Metrics + WebSocket (Week 7-8)
- ✅ Custom UI components (Week 9-12)
- ✅ Debug CLI tools (Week 12)

**Плюсы:**
- ✅ Полная observability
- ✅ User-friendly UI (Service Mesh Monitor + Trace Viewer)
- ✅ Real-time updates каждые 2 секунды
- ✅ Debug tools для команды

**Минусы:**
- ❌ Долго (12 weeks = 3 месяца)
- ❌ Много работы

**Когда выбрать:** Хотим production-ready observability platform

---

### Вариант D: Hybrid Approach (8.5 weeks) ⭐ РЕКОМЕНДУЕТСЯ

**Week 1-4: Direct RAS MVP**
- Focus: Починить extension install
- Deliverable: Direct RAS deployed to development

**Week 4.5: Manual Endpoint Testing ⭐ CRITICAL GATE**
- Focus: Comprehensive manual validation ALL endpoints
- Testing Checklist: [RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md](RAS_ADAPTER_MANUAL_TESTING_CHECKLIST.md)
- Deliverable: Sign-off on all tests PASSED
- ⚠️ GATE: Must pass before Week 5

**Week 5-6: Tracing Infrastructure**
- Focus: Deploy Jaeger, instrument services, correlation IDs
- Deliverable: Можем debugging через Jaeger UI

**Week 7-8: Metrics + Basic UI**
- Focus: Prometheus metrics, WebSocket aggregator, simple Service Mesh Monitor
- Deliverable: Real-time visibility в UI

**Плюсы:**
- ✅ Баланс между speed и completeness
- ✅ Extension install работает к Week 4
- ✅ **Week 4.5: Manual validation gate** - уверенность перед tracing
- ✅ Observability infrastructure к Week 6
- ✅ Basic UI к Week 8

**Минусы:**
- ⚠️ Дополнительные 0.5 weeks на manual testing (но это критично!)
- ⚠️ Custom Trace Viewer и Debug CLI откладываются (можем добавить позже)

---

## Моя рекомендация

### Start with Вариант D: Hybrid Approach (8.5 weeks)

**Причины:**
1. **Week 1-4:** MVP критичен - extension install должен работать ASAP
2. **Week 4.5:** Manual validation gate - убедимся что всё работает корректно перед tracing
3. **Week 5-6:** Tracing infrastructure даёт debugging capability БЕЗ custom UI
4. **Week 7-8:** Basic Service Mesh Monitor даёт visibility для пользователей
5. **Future (Week 9-12):** Можем добавить Trace Viewer UI и Debug CLI когда появится time/need

**Trade-offs:**
- Custom Trace Viewer UI → используем Jaeger UI (достаточно для начала)
- Debug CLI tools → можем добавить позже (curl + Jaeger UI покрывают 80%)

---

## Quick Start Commands

### Check Current Issues

```bash
# Check if RAS integration is broken
curl -X POST "http://localhost:8088/api/v2/lock-infobase?cluster_id=...&infobase_id=..." \
  -H "Content-Type: application/json" \
  -d '{"db_user":"admin","db_password":"secret"}'

# Expected: HTTP 500 (RAS error: unknown type)
```

### After MVP (Week 4)

```bash
# Test Worker health
curl http://localhost:9191/health
# Expected: {"status":"ok", ...}
```

### After Basic Tracing (Week 6)

```bash
# View traces in Jaeger UI
open http://localhost:16686

# Search for operation
# Service: worker
# Tags: operation.id=op-67890
```

### After Service Mesh Monitor (Week 8)

```bash
# Open real-time UI
open http://localhost:15173/monitoring

# See:
# - Service mesh visualization
# - Real-time metrics
# - Operation counts
```

---

## Decision Matrix

| Критерий | MVP (4w) | MVP+Tracing (6w) | Full (12w) | Hybrid (8.5w) ⭐ |
|----------|----------|------------------|------------|----------------|
| **Extension Install работает** | Week 4 | Week 4 | Week 4 | Week 4 |
| **Manual validation gate** | ❌ | ❌ | ❌ | ✅ Week 4.5 |
| **Можем debug операции** | ❌ | ✅ (Jaeger) | ✅ (Custom UI) | ✅ (Jaeger) |
| **User visibility** | ❌ | ❌ | ✅ | ✅ (Basic) |
| **Time to market** | 4 weeks | 6 weeks | 12 weeks | 8.5 weeks |
| **Risk** | Low | Low | Medium | Very Low ✅ |
| **Future extensibility** | ❌ | ✅ | ✅ | ✅ |

---

## Next Steps

### If you choose MVP (5 weeks):

1. Read: [RADICAL_1C_CONTROL_PLANE_ROADMAP.md](../roadmaps/RADICAL_1C_CONTROL_PLANE_ROADMAP.md)
2. Start: Week 1 - Direct RAS operations in Worker
3. Spike: Week 2 - Test RegInfoBase with real RAS

### If you choose MVP + Basic Tracing (7 weeks):

1. Read: [RADICAL_1C_CONTROL_PLANE_ROADMAP.md](../roadmaps/RADICAL_1C_CONTROL_PLANE_ROADMAP.md)
2. Read: [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md) - Phase 1-2 only
3. Start: Week 1-4 MVP, Week 5-6 Tracing

### If you choose Hybrid (8.5 weeks) ⭐:

1. Read: [RADICAL_1C_CONTROL_PLANE_ROADMAP.md](../roadmaps/RADICAL_1C_CONTROL_PLANE_ROADMAP.md)
2. Read: [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md) - Phase 1-5
3. Start: Week 1-4 MVP → Week 5-8 Tracing+Metrics+UI

### If you choose Full (12 weeks):

1. Read: Both documents completely
2. Start: Comprehensive implementation
3. Prepare: 3 месяца timeline

---

## FAQ

**Q: Можем ли начать с MVP, а потом добавить tracing?**
A: ✅ Да! MVP закладывает foundation (Correlation ID в Worker уже есть). Tracing можно добавить когда угодно.

**Q: Что если RAS RegInfoBase тоже не сработает?**
A: Week 2 Day 1-2 - Technical Spike. Если не работает → fallback: использовать другие RAS commands или 1cv8.exe subprocess.

**Q: Нужен ли custom Trace Viewer UI или достаточно Jaeger?**
A: Для devops/admins - достаточно Jaeger UI. Для business users - нужен custom UI (похожий на твой InstallationProgressModal).

**Q: Сколько стоит Jaeger по ресурсам?**
A: Minimal. all-in-one контейнер: ~200MB RAM, sampling 10% в production (100% в dev).

**Q: Что если не успеем за 8 weeks?**
A: Hybrid подход позволяет остановиться после Week 4 (MVP) или Week 6 (MVP+Tracing) если нужно.

---

## Contact

**Для вопросов:**
- См. основные документы: [RAS_ADAPTER_ROADMAP.md](RAS_ADAPTER_ROADMAP.md), [REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md)
- См. architecture overview: [README.md](README.md)

**Авторы:**
- AI Architect + AI Orchestrator
- Date: 2025-11-19
