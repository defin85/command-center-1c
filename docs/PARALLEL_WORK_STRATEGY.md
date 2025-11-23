# Parallel Work Strategy - RAS Adapter + Unified Workflow

**Version:** 1.0
**Date:** 2025-11-23

---

## 📊 Current Status

### RAS Adapter Roadmap

**Status:** ✅ ПОЛНОСТЬЮ ЗАВЕРШЕН

| Week | Task | Status | Date |
|------|------|--------|------|
| Week 4 | Deploy & Validate | ✅ COMPLETE | 2025-11-20 |
| Week 4.5 | Manual Testing Gate | ✅ COMPLETE | 2025-11-23 |
| Week 4.6 | Sessions-deny | ✅ COMPLETE | 2025-11-23 |

**Result:** RAS Adapter в production, старые сервисы готовы к архивации.

---

### Main Roadmap (Balanced Approach)

**Status:** 🟡 Week 3-4 В ПРОЦЕССЕ (~25% готово)

| Component | Status | % Complete |
|-----------|--------|------------|
| Infrastructure | ✅ DONE | 100% |
| Database Models | ✅ DONE | 100% |
| OData Client | ✅ DONE | 100% |
| REST API | ✅ DONE | 100% |
| RAS Integration | ✅ DONE | 100% |
| **Sprint 2.1: Celery ↔ Worker** | 🟡 IN PROGRESS | 30% |
| **Sprint 2.2: Template Engine** | 🟡 IN PROGRESS | 20% |
| E2E Integration | ❌ TODO | 0% |

**Critical GAPs:**
1. ❌ Orchestrator → Worker integration (Redis queue)
2. ❌ Template Engine (variables, expressions, validation)
3. ❌ Real operation execution в Worker
4. ❌ E2E flow (User → API → Worker → 1C)

---

### Unified Workflow Platform

**Status:** 📋 PLANNED (Week 5-22)

| Phase | Weeks | Status |
|-------|-------|--------|
| Phase 1: Foundation | Week 1-4 | ✅ COMPLETE (RAS Adapter) |
| Phase 2: Workflow Engine | Week 5-11 | 📋 PLANNED |
| Phase 3: Real-Time + Service Mesh | Week 12-16 | 📋 PLANNED |
| Phase 4: Polish & Migration | Week 17-18 | 📋 PLANNED |

---

## 🔗 Dependency Analysis

### RAS Adapter → Unified Workflow

**Dependencies:** ✅ NONE (RAS Adapter завершен)

**Conclusion:** RAS Adapter НЕ блокирует Unified Workflow

---

### Sprint 2.1-2.2 → Unified Workflow

**Dependencies:** ⚠️ PARTIAL

#### Week 5-6 (Unified Workflow Models + DAGValidator)

**Needs from Sprint 2.1-2.2:**
- ❌ **NOT NEEDED:** Celery integration
- ❌ **NOT NEEDED:** Worker integration
- ✅ **NEEDED:** OperationTemplate model (уже есть!)

**Conclusion:** ✅ CAN START Week 5-6 IMMEDIATELY

#### Week 7-11 (Unified Workflow NodeHandlers)

**Needs from Sprint 2.1-2.2:**
- ✅ **NEEDED:** Template Engine (Sprint 2.2) для OperationHandler
- ✅ **NEEDED:** Celery integration (Sprint 2.1) для async execution
- ✅ **NEEDED:** Worker (Sprint 2.1) для real operations

**Conclusion:** ❌ CANNOT START Week 7-11 until Sprint 2.1-2.2 COMPLETE

---

## ✅ Parallel Work Plan

### Strategy: Phased Parallelism

**Можно делать ПАРАЛЛЕЛЬНО:**

```
┌─────────────────────────────────────────────────────────────┐
│ СЕЙЧАС (Week 3-4, Nov-Dec 2025)                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Track A: Finish Sprint 2.1-2.2                             │
│  ═══════════════════════════════                            │
│  • Complete Celery → Worker integration                    │
│  • Complete Template Engine                                │
│  • Test E2E flow                                            │
│  Duration: 5-7 days remaining                               │
│                                                             │
│  Track B: Start Unified Workflow (Week 5-6) ⭐             │
│  ════════════════════════════════════════                   │
│  • Create Django models (WorkflowTemplate, etc.)           │
│  • Implement DAGValidator (Kahn's algorithm)               │
│  • Write unit tests                                         │
│  Duration: 10 days (2 weeks)                                │
│                                                             │
│  RESULT: Both tracks finish around same time!              │
│          Sprint 2.1-2.2 done → Week 7 can start            │
└─────────────────────────────────────────────────────────────┘
```

**НЕ МОЖЕМ делать параллельно:**

```
┌─────────────────────────────────────────────────────────────┐
│ ПОЗЖЕ (Week 5+, after Sprint 2.1-2.2)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Track B: Unified Workflow Week 7-11                        │
│  ════════════════════════════════════                       │
│  • NodeHandlers (use Template Engine)                      │
│  • WorkflowEngine (use Celery)                              │
│  • Execute real workflows (use Worker)                      │
│                                                             │
│  DEPENDENCIES: Requires Sprint 2.1-2.2 COMPLETE ✅          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Recommended Parallel Work Schedule

### Option A: Sequential (Safe) ⭐ RECOMMENDED

```
Now - Week 4 (5-7 days):
  └─ Finish Sprint 2.1-2.2 (100% focus)

Week 5-6 (10 days):
  └─ Unified Workflow: Models + DAGValidator

Week 7-11 (5 weeks):
  └─ Unified Workflow: NodeHandlers + Engine + API

Week 12-16 (5 weeks):
  └─ Unified Workflow: Real-Time + Service Mesh

Week 17-18 (2 weeks):
  └─ Polish & Documentation

Total: 18 weeks sequential
```

**Pros:**
- ✅ Чистый focus на одной задаче
- ✅ Меньше context switching
- ✅ Lower risk

**Cons:**
- ❌ Дольше (18 weeks)

---

### Option B: Partial Parallel (Faster) 🚀

```
Now - Week 4 (5-7 days):
  ├─ Track A: Finish Sprint 2.1-2.2 (primary focus)
  └─ Track B: Start Unified Week 5-6 (Models + DAGValidator) (20% time)

Week 5-6 (если Sprint 2.1-2.2 затянулся):
  ├─ Track A: Finish Sprint 2.1-2.2 (if not done)
  └─ Track B: Continue Week 5-6 (80% time)

Week 7-11 (5 weeks):
  └─ Unified Workflow: NodeHandlers + Engine + API (100% focus)

Week 12-16 (5 weeks):
  └─ Unified Workflow: Real-Time + Service Mesh

Week 17-18 (2 weeks):
  └─ Polish & Documentation

Total: ~16-17 weeks (saves 1-2 weeks)
```

**Pros:**
- ✅ Faster completion (1-2 weeks saved)
- ✅ Week 5-6 работа начата раньше
- ✅ Sprint 2.1-2.2 остается priority

**Cons:**
- ⚠️ Context switching overhead
- ⚠️ Risk: Week 5-6 может блокироваться если Sprint 2.1-2.2 затянется

---

### Option C: Full Parallel (Risky) ⚠️

```
Now - Week 4:
  ├─ Team A: Finish Sprint 2.1-2.2
  └─ Team B: Start Unified Week 5-11 (full speed)

Week 5-11:
  └─ Team B: Continue Unified (NodeHandlers, Engine, API)
       WARNING: Will hit blockers if Sprint 2.1-2.2 not done!

Week 12-16:
  └─ Unified: Real-Time + Service Mesh

Week 17-18:
  └─ Polish & Documentation

Total: ~16 weeks (if lucky)
```

**Pros:**
- ✅ Fastest possible (16 weeks)
- ✅ Two teams work independently

**Cons:**
- ❌ HIGH RISK: Team B blocked if Sprint 2.1-2.2 delays
- ❌ Requires 2 separate teams
- ❌ Coordination overhead
- ❌ Potential rework if Template Engine design changes

**Recommendation:** ❌ NOT RECOMMENDED (too risky)

---

## 🎯 Dependency Matrix

### Unified Workflow Dependencies

| Week | Task | Depends On | Can Start? |
|------|------|------------|------------|
| **Week 5** | WorkflowTemplate model | OperationTemplate model | ✅ YES (model exists) |
| **Week 5** | WorkflowExecution model | Nothing | ✅ YES |
| **Week 6** | DAGValidator (Kahn's) | Nothing | ✅ YES |
| **Week 7** | OperationHandler | Template Engine | ❌ NO (Sprint 2.2) |
| **Week 8** | ParallelHandler | Celery integration | ❌ NO (Sprint 2.1) |
| **Week 9** | WorkflowEngine | Celery + Worker | ❌ NO (Sprint 2.1-2.2) |
| **Week 10** | REST API | WorkflowEngine | ❌ NO |
| **Week 11** | Celery tasks | Worker integration | ❌ NO (Sprint 2.1) |

### Sprint 2.1-2.2 Tasks

| Task | Blocks | Criticality |
|------|--------|-------------|
| **Template Engine** | Week 7 (OperationHandler) | 🔥 CRITICAL |
| **Celery → Worker** | Week 8-11 (async execution) | 🔥 CRITICAL |
| **Real operations** | Week 9-11 (testing) | ⚠️ IMPORTANT |
| **E2E testing** | Week 11 (validation) | ⚠️ IMPORTANT |

---

## ✅ Моя рекомендация: Option B (Partial Parallel)

### Timeline

```
┌─────────────────────────────────────────────────────────────┐
│ NOW - Week 4 (5-7 days)                                     │
├─────────────────────────────────────────────────────────────┤
│ 🔥 PRIMARY (80% effort):                                    │
│   Sprint 2.1-2.2 → КРИТИЧНО завершить                      │
│   • Celery → Worker integration                             │
│   • Template Engine                                         │
│   • E2E testing                                             │
│                                                             │
│ 📋 SECONDARY (20% effort):                                  │
│   Unified Week 5-6 (начать, но не blocking)                │
│   • Create WorkflowTemplate model (1 day)                   │
│   • Create WorkflowExecution model (1 day)                  │
│   • Start DAGValidator planning (0.5 day)                   │
│                                                             │
│ TEAM SPLIT:                                                 │
│   • Developer 1-2: Sprint 2.1-2.2 (full focus)             │
│   • Developer 3: Unified Week 5 models (part-time)         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Week 5-6 (10 days)                                          │
├─────────────────────────────────────────────────────────────┤
│ IF Sprint 2.1-2.2 DONE:                                     │
│   ✅ Continue Unified Week 5-6 (100% effort)                │
│   • Finish models                                           │
│   • Complete DAGValidator                                   │
│   • Unit tests                                              │
│                                                             │
│ IF Sprint 2.1-2.2 NOT DONE:                                 │
│   🔥 Finish Sprint 2.1-2.2 FIRST (priority)                 │
│   📋 Unified Week 5-6 continues at 50% effort               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Week 7-11 (5 weeks) - AFTER Sprint 2.1-2.2 complete        │
├─────────────────────────────────────────────────────────────┤
│ ✅ Sprint 2.1-2.2 must be 100% done                         │
│                                                             │
│ 100% focus on Unified Workflow:                             │
│   • Week 7-8: NodeHandlers (uses Template Engine)          │
│   • Week 9: WorkflowEngine (uses Celery)                    │
│   • Week 10: REST API                                       │
│   • Week 11: Testing (uses Worker)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 Gantt Chart

```
Week  Task                         Track        Dependencies
════  ═══════════════════════════  ═══════════  ══════════════════
 1-2  Infrastructure Setup         Main         ✅ DONE
 3-4  Sprint 2.1-2.2 (finish)     Main         🟡 IN PROGRESS

  5   Models                       Unified      OperationTemplate ✅
  5   Sprint 2.1-2.2 (buffer)     Main         (if delayed)

  6   DAGValidator                 Unified      None ✅
  6   Sprint 2.1-2.2 (buffer)     Main         (if delayed)

      ⬇️ GATE: Sprint 2.1-2.2 must be COMPLETE before Week 7

  7   OperationHandler             Unified      Template Engine ⚠️
  8   Other NodeHandlers           Unified      Template Engine ⚠️
  9   WorkflowEngine               Unified      Celery, Worker ⚠️
 10   REST API                     Unified      WorkflowEngine
 11   Testing                      Unified      E2E flow ⚠️

 12   OpenTelemetry                Unified      None ✅
 13   WebSocket                    Unified      Django Channels
 14   React Flow Design            Unified      None ✅
 15   React Flow Monitor           Unified      WebSocket
 16   Service Mesh Monitor         Unified      Prometheus ✅

 17   Worker Migration             Unified      WorkflowEngine
 18   Documentation                Unified      All features

Legend:
  ✅ No dependency / Already satisfied
  ⚠️ Blocked by Sprint 2.1-2.2
  🟡 In progress
```

---

## ⚠️ Critical Gate: End of Week 6

**Before starting Week 7 (Unified NodeHandlers):**

✅ **MUST BE COMPLETE:**
1. Sprint 2.1: Celery → Worker integration (Redis queue)
2. Sprint 2.2: Template Engine (variables, expressions, validation)
3. E2E test: User → API → Celery → Worker → 1C OData

❌ **IF NOT COMPLETE:**
- Week 7-11 BLOCKED
- Unified Workflow cannot execute real operations
- Wasted effort on models/validator (not critical, but inefficient)

**Validation checklist:**

```bash
# 1. Celery → Worker works
curl -X POST http://localhost:8000/api/v1/operations/ -d '{...}'
# Should: Enqueue to Celery → Worker picks up → Executes

# 2. Template Engine works
curl -X POST http://localhost:8000/api/v1/templates/render/ -d '{...}'
# Should: Render template with variables

# 3. E2E flow works
curl -X POST http://localhost:8000/api/v1/operations/execute/ -d '{
  "template_id": "tmpl-create-user",
  "database_id": "db-123",
  "variables": {"username": "test"}
}'
# Should: Create user in 1C database via OData
```

**If all ✅:** Proceed to Week 7
**If any ❌:** Delay Week 7 until fixed

---

## 🚀 Recommended Approach

### Phase 1: Finish Sprint 2.1-2.2 (Priority)

**Duration:** 5-7 days
**Team:** Full team (100% focus)

**Tasks:**
- [ ] Complete Celery → Redis → Worker pipeline
- [ ] Implement Template Engine (Jinja2 rendering)
- [ ] Implement real operation execution в Worker
- [ ] Test E2E: API → Worker → 1C
- [ ] Document Template Engine API

**Deliverable:** Core platform works E2E

---

### Phase 2: Unified Week 5-6 (Parallel Start)

**Duration:** 10 days
**Team:** 1 developer (part-time during Sprint 2.1-2.2, full-time after)

**Tasks:**
- [ ] Create WorkflowTemplate, WorkflowExecution models
- [ ] Create migrations
- [ ] Implement DAGValidator (Kahn's algorithm)
- [ ] Write unit tests (50+ tests)
- [ ] Document workflow JSON schema

**Deliverable:** Foundation for Week 7-11

**Can start:** ✅ IMMEDIATELY (no dependencies)

---

### Phase 3: Unified Week 7-11 (After Sprint 2.1-2.2)

**Duration:** 5 weeks
**Team:** Full team

**Prerequisite:** ✅ Sprint 2.1-2.2 COMPLETE

**Tasks:**
- Week 7-8: NodeHandlers
- Week 9: WorkflowEngine
- Week 10: REST API
- Week 11: Testing

---

## 📊 Resource Allocation

### Team Composition (Suggested)

**3 developers:**

#### Developer 1 (Backend Lead)
- **Now - Week 4:** Sprint 2.1 (Celery + Worker) - 100%
- **Week 5-6:** Sprint 2.1 buffer (if needed) OR Unified models - 50%
- **Week 7-11:** Unified NodeHandlers + Engine - 100%

#### Developer 2 (Backend)
- **Now - Week 4:** Sprint 2.2 (Template Engine) - 100%
- **Week 5-6:** Unified DAGValidator - 100%
- **Week 7-11:** Unified NodeHandlers - 100%

#### Developer 3 (Full-Stack)
- **Now - Week 4:** E2E testing (Sprint 2.1-2.2) - 100%
- **Week 5-6:** Unified models + tests - 100%
- **Week 7-11:** Unified REST API - 100%
- **Week 12-16:** Frontend (React Flow) - 100%

**Result:** Unified Week 5-6 can start with 1-2 devs while Sprint 2.1-2.2 finishing

---

### 1 Developer Team

**Sequential only:**

```
Week 4:    Sprint 2.1-2.2 finish
Week 5-6:  Unified models + validator
Week 7-11: Unified handlers + engine
...
```

**Total: 18 weeks sequential**

---

## ⚡ Optimization: Early Start Benefits

### Start Week 5-6 Now (Parallel)

**Time saved:** 1-2 weeks

**How:**
```
Sprint 2.1-2.2 (5 days remaining)
  + Unified Week 5-6 (10 days)
  = 10 days total (if parallel)

vs

Sprint 2.1-2.2 (5 days)
  then Unified Week 5-6 (10 days)
  = 15 days total (if sequential)

Savings: 5 days (1 week)
```

**Risk:** Low (Week 5-6 не зависит от Sprint 2.1-2.2)

---

## 🎯 My Recommendation

### DO THIS:

**1. Finish Sprint 2.1-2.2 (Priority, 5-7 days)**
- 🔥 Full team focus
- Critical for platform functionality
- Blocking для Week 7-11

**2. Start Unified Week 5-6 in Parallel (Low priority, 10 days)**
- 📋 1 developer part-time (20-30% effort)
- Create models + DAGValidator
- Low risk (no dependencies)
- Early start advantage

**3. Gate at End of Week 6**
- ✅ Validate Sprint 2.1-2.2 complete
- ✅ Validate Week 5-6 models ready
- ✅ Decision: Proceed to Week 7 or delay

**4. Continue Week 7-18 (Sequential, 12 weeks)**
- Full team on Unified Workflow
- No parallel work (Sprint 2.1-2.2 done)

**Total time:** ~16-17 weeks (saves 1-2 weeks vs pure sequential)

---

## ❌ What NOT to Do

### Don't: Start Week 7-11 in Parallel

**Problem:**
```
Week 7: Implement OperationHandler
  ↓ depends on
Template Engine (Sprint 2.2)
  ↓ if not ready
Blocked! Developer sits idle or works on wrong thing
  ↓
Rework needed when Sprint 2.2 completes
```

### Don't: Skip Sprint 2.1-2.2

**Problem:**
```
Unified Workflow Engine implemented
  ↓ tries to execute operations
Celery → Worker pipeline broken (Sprint 2.1 not done)
  ↓
Workflows fail at execution
  ↓
Cannot test or validate anything
```

---

## ✅ Conclusion

### Answer: Частично ДА! ⭐

**ДА для Week 5-6:**
- ✅ Можно начать Models + DAGValidator параллельно
- ✅ Не зависит от Sprint 2.1-2.2
- ✅ Low risk
- ✅ Saves 1 week

**НЕТ для Week 7-11:**
- ❌ Нельзя делать NodeHandlers параллельно
- ❌ Зависит от Template Engine (Sprint 2.2)
- ❌ Зависит от Celery + Worker (Sprint 2.1)
- ❌ High risk of rework

### Recommended Timeline

```
NOW:      Finish Sprint 2.1-2.2 (5-7 days)           🔥 PRIORITY
          + Start Unified Week 5 models (part-time)  📋 OPTIONAL

Week 5-6: Unified models + DAGValidator (10 days)    ✅ CAN DO

          ⬇️ GATE: Sprint 2.1-2.2 complete?

Week 7-18: Unified Workflow (12 weeks)                ✅ SEQUENTIAL

Total: 16-17 weeks (with early start)
       18 weeks (pure sequential)
```

**Decision:** Start Unified Week 5-6 models NOW (low-priority background task) while finishing Sprint 2.1-2.2 (high-priority)

---

**Next Step:** Согласовать с командой resource allocation для параллельной работы
