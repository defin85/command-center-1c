# Event-Driven Architecture: Executive Summary

## Дата: 2025-11-12
## Статус: READY FOR APPROVAL

---

## TL;DR (60 секунд)

**Что:** Миграция с synchronous HTTP calls на fully event-driven architecture через Redis Pub/Sub
**Зачем:** 3100x faster perceived latency, 10x throughput, infinite scalability
**Когда:** 14 календарных дней (10 рабочих дней)
**Кто:** 1.5 FTE (Go Engineer + 0.5 Python Engineer + 0.5 QA Engineer)
**Бюджет:** 176 productive hours
**Риск:** MEDIUM (36% buffer, phased rollout, fast rollback < 5 min)

---

## Проблема

### Текущая архитектура (Hybrid)

```
Worker → cluster-service:  ✅ Events (Redis Pub/Sub)
Worker → Batch Service:    ❌ HTTP POST с timeout 5 минут (BLOCKING!)
Worker → Orchestrator:     ❌ HTTP PATCH для статусов (BLOCKING!)
```

**Критичные проблемы:**
1. **Worker блокируется на 31+ секунд** ждя ответа от Batch Service
2. **Throughput ограничен** размером Worker pool (10-20 workers)
3. **Single point of failure** - если Batch Service unavailable, Worker зависает
4. **Нет масштабируемости** - каждый Worker обрабатывает 1 операцию за раз

---

## Решение

### Fully Event-Driven Architecture

```
Worker → cluster-service:  ✅ Events (Redis Pub/Sub)
Worker → Batch Service:    ✅ Events (Redis Pub/Sub) - NON-BLOCKING!
Worker → Orchestrator:     ✅ Events (Redis Pub/Sub) - NON-BLOCKING!
```

**Ключевые изменения:**
- **Worker как State Machine** (Orchestration pattern)
- **ALL communication через events** (NO HTTP calls)
- **Saga Pattern** для distributed transactions с compensation
- **Graceful degradation** при Redis unavailable

---

## Результаты (Expected)

| Метрика | До (HTTP Sync) | После (Events) | Улучшение |
|---------|----------------|----------------|-----------|
| **Worker latency** | 31,000ms (blocking) | 10ms (publish) | **3100x faster** |
| **Throughput** (100 ops) | 310 sec | 31 sec | **10x faster** |
| **Parallel capacity** | 10 ops | 100+ ops | **10x more** |
| **Success rate** | 95% | 98% | **+3%** |
| **Scalability** | Limited | Infinite | **Horizontal scaling** |

---

## Timeline

### 14 дней (10 рабочих дней)

**Week 1 (Days 1-5): Foundation**
- Shared Events Library (Go)
- Worker State Machine (Orchestration)
- **Milestone:** State Machine can execute full workflow с mock events

**Week 2 (Days 6-10): Services Integration**
- cluster-service event handlers
- Batch Service event handlers
- Orchestrator event subscriber
- **Milestone:** End-to-end event flow working

**Week 3 (Days 11-14): Migration & Testing**
- Integration testing (10 scenarios)
- E2E testing (real 1C database)
- Feature flags & A/B testing
- Production rollout (10% → 50% → 100%)
- **Milestone:** 100% production rollout success

---

## Team & Budget

### Team Allocation

| Роль | Allocation | Hours/Week | Total Hours |
|------|------------|------------|-------------|
| **Go Backend Engineer** | 100% (full-time) | 40h | 100h |
| **Python Backend Engineer** | 50% (part-time) | 10h | 28h |
| **QA Engineer** | 50% (part-time) | 16h | 48h |
| **Total** | | | **176h** |

### Budget Breakdown

| Week | Phase | Effort | % of Total |
|------|-------|--------|------------|
| Week 1 | Foundation + State Machine | 48-64h | 40% |
| Week 2 | Services Integration | 48-64h | 40% |
| Week 3 | Migration & Testing | 24-32h | 20% |
| **Buffer** | Unexpected issues | 5 days | **36%** |

---

## Risks & Mitigation

### Critical Risks

**Risk 1: Redis Single Point of Failure**
- **Impact:** CRITICAL (все event communication breaks)
- **Probability:** MEDIUM
- **Mitigation:**
  - Week 4 (Post-Rollout): Redis Sentinel (HA)
  - Graceful degradation: log events to PostgreSQL
  - Event replay mechanism

**Risk 2: Production Issues Not Caught in Testing**
- **Impact:** CRITICAL (production downtime)
- **Probability:** MEDIUM
- **Mitigation:**
  - Phased rollout (10% → 50% → 100%)
  - Fast rollback (< 5 minutes)
  - A/B testing metrics
  - 36% buffer time

**Risk 3: Increased System Complexity**
- **Impact:** MEDIUM (harder debugging)
- **Probability:** HIGH
- **Mitigation:**
  - Comprehensive logging с correlation_id
  - Distributed tracing (Week 4)
  - State Machine visualization
  - Event replay tool

---

## Success Criteria

### Functional Requirements

- [ ] **Zero HTTP calls** между Worker ↔ cluster-service ↔ Batch Service
- [ ] **Event delivery latency** < 10ms (p99)
- [ ] **End-to-end workflow** < 45 seconds для single installation
- [ ] **Graceful degradation** при Redis unavailable

### Technical Requirements

- [ ] **Unit tests coverage** > 80% для event handlers
- [ ] **Integration tests** 10+ scenarios покрыто
- [ ] **Load test** 100 баз параллельно успешно
- [ ] **Production rollout** 100% без rollback

### Business Impact

- [ ] **Success rate** >= 98% (vs 95% current)
- [ ] **Worker utilization** 80% (vs 20% current - blocking time)
- [ ] **Throughput** 10x increase
- [ ] **Scalability** ready для 700+ баз

---

## Migration Strategy

### Phased Rollout (Day 14)

**Phase 1: 10% Traffic (4 hours monitoring)**
- Set `EVENT_DRIVEN_ROLLOUT_PERCENT=0.10`
- Monitor success rate, latency, errors
- **Go/No-Go:** If success rate < 95% → ROLLBACK

**Phase 2: 50% Traffic (4 hours monitoring)**
- Set `EVENT_DRIVEN_ROLLOUT_PERCENT=0.50`
- Monitor stability
- **Go/No-Go:** If error rate increases → ROLLBACK to 10%

**Phase 3: 100% Traffic (4 hours monitoring)**
- Set `ENABLE_EVENT_DRIVEN_WORKFLOW=true`
- Validate all operations through events
- **Success:** 100% rollout complete, NO rollback needed

### Rollback Plan (< 5 minutes)

```bash
# 1. Update config
ENABLE_EVENT_DRIVEN_WORKFLOW=false

# 2. Restart Workers
./scripts/dev/restart-all.sh --service=worker

# 3. Verify HTTP Sync working
curl -X POST http://localhost:8087/api/v1/extensions/install

# 4. Done! Back to HTTP Sync in < 5 minutes
```

---

## Dependencies & Prerequisites

### Required Infrastructure

- [x] Redis 7 running (already deployed)
- [x] cluster-service deployed (already deployed)
- [x] batch-service deployed (already deployed)
- [x] Worker deployed (already deployed)
- [ ] Grafana dashboard (to be created Week 3)
- [ ] Prometheus alerts (to be configured Week 3)

### Team Skills

- [x] Go 1.21+ experience (Go Backend Engineer)
- [x] Redis Pub/Sub knowledge (Go Backend Engineer)
- [x] State Machine patterns (Go Backend Engineer)
- [x] Django/Celery experience (Python Backend Engineer)
- [x] Integration testing (QA Engineer)

---

## Deliverables

### Code Deliverables

- [ ] `go-services/shared/events/` - Shared Events Library
- [ ] `go-services/worker/internal/statemachine/` - Worker State Machine
- [ ] `go-services/cluster-service/internal/eventhandlers/` - cluster-service handlers
- [ ] `go-services/batch-service/internal/eventhandlers/` - batch-service handlers
- [ ] `orchestrator/apps/operations/event_subscriber.py` - Orchestrator subscriber

### Documentation Deliverables

- [x] `EVENT_DRIVEN_ARCHITECTURE.md` - Концептуальный дизайн (82KB)
- [x] `EVENT_DRIVEN_ROADMAP.md` - Детальный roadmap (60KB)
- [x] `EVENT_DRIVEN_GANTT.md` - Gantt chart & timeline
- [ ] `EVENT_DRIVEN_ROLLBACK_PLAN.md` - Rollback procedures (Week 3)
- [ ] API documentation updates (Week 2-3)

### Testing Deliverables

- [ ] Unit tests (coverage > 80%)
- [ ] Integration tests (10 scenarios)
- [ ] E2E tests (real 1C database)
- [ ] Performance tests (100 parallel ops)
- [ ] Test report (CSV/JSON)

---

## Industry Best Practices Applied

### Source 1: AWS Leave-and-Layer Pattern
**URL:** https://aws.amazon.com/blogs/migration-and-modernization/modernizing-legacy-applications-with-event-driven-architecture-the-leave-and-layer-pattern/

**Applied:**
- Incremental rollout (10% → 50% → 100%)
- Dual-mode operation с feature flags
- Fast rollback strategy

### Source 2: FreeCodeCamp Event-Driven Architectures
**URL:** https://www.freecodecamp.org/news/event-based-architectures-in-javascript-a-handbook-for-devs/

**Applied:**
- Pub/Sub pattern для loose coupling
- Saga Pattern для distributed transactions
- Event Carried State Transfer

### Source 3: BullMQ Production Checklist
**URL:** https://hadoan.medium.com/bullmq-for-beginners-a-friendly-practical-guide-with-typescript-examples-eb8064bef1c4

**Applied:**
- Subscribe to `failed` events → alerts
- Redis persistence (AOF/RDB)
- Worker health monitoring

---

## Next Steps (Approval Required)

### Immediate Actions

1. **User Approval** - Review roadmap, approve начало работы
2. **Team Kickoff** - Schedule Day 1 kickoff meeting
3. **Environment Prep** - Ensure Redis ready, test environment setup

### Week 1 Start Checklist

- [ ] User approval obtained ✅
- [ ] Team kickoff meeting scheduled (Day 1, 09:00)
- [ ] Redis 7 running and accessible
- [ ] Go Backend Engineer available 100%
- [ ] Git branch created: `feature/event-driven-architecture`
- [ ] PROJECT.md updated с current status

### Post-Rollout (Week 4+)

- [ ] Redis Sentinel (HA)
- [ ] State Machine persistence (PostgreSQL)
- [ ] Watchdog process для stuck operations
- [ ] OpenTelemetry distributed tracing
- [ ] Remove legacy HTTP sync code (Week 5)

---

## Questions & Answers

**Q: Почему Orchestration, а не Choreography?**
A: Complex workflow (4 steps), strict SLAs, centralized compensation logic. Orchestration проще debug и maintain для multi-step workflows.

**Q: Что если Redis unavailable на production?**
A: Graceful degradation: events логируются в PostgreSQL, retry после 5 seconds. Week 4: Redis Sentinel (HA).

**Q: Как rollback если что-то пойдет не так?**
A: < 5 minutes: изменить feature flag, restart Workers. HTTP endpoints остаются active до Week 5 cleanup.

**Q: Сколько времени займет реализация?**
A: 14 календарных дней (10 рабочих дней). Week 1-2: implementation, Week 3: testing + rollout.

**Q: Кто будет работать над этим?**
A: 1.5 FTE: Go Backend Engineer (100%), Python Backend Engineer (50%), QA Engineer (50%).

**Q: Какие риски?**
A: Redis SPOF (mitigated Week 4), production issues (mitigated phased rollout), complexity (mitigated logging/tracing).

---

## Approval

**Awaiting User Decision:**

- [ ] **APPROVE** - Start Week 1 implementation (Go/No-Go for Day 1 kickoff)
- [ ] **REQUEST CHANGES** - Provide feedback, update roadmap
- [ ] **REJECT** - Provide reasons, explore alternatives

**Approval Required By:** User
**Target Start Date:** TBD (после approval)
**Target Completion Date:** TBD + 14 calendar days

---

**Документ создан:** 2025-11-12
**Версия:** 1.0
**Статус:** AWAITING APPROVAL
**Связанные документы:**
- EVENT_DRIVEN_ARCHITECTURE.md (Концептуальный дизайн)
- EVENT_DRIVEN_ROADMAP.md (Детальный roadmap)
- EVENT_DRIVEN_GANTT.md (Timeline visualization)
