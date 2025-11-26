# Workflow Engine - Implementation

**Version:** 1.0.0
**Status:** Week 5 - Models + Migrations
**Roadmap:** `docs/roadmaps/UNIFIED_WORKFLOW_ROADMAP.md`

---

## 📁 Directory Structure

```
workflow/
├── __init__.py              # Package init
├── README.md                # This file
├── models.py                # Django models (Week 5)
├── validator.py             # DAGValidator with Kahn's algorithm (Week 6)
├── executor.py              # DAGExecutor (Week 9)
├── handlers.py              # NodeHandlers (Week 7-8)
├── engine.py                # WorkflowEngine main orchestrator (Week 9)
├── context.py               # ContextManager for data passing (Week 9)
├── consumers.py             # Django Channels WebSocket (Week 13)
├── serializers.py           # DRF serializers (Week 10)
├── views.py                 # DRF ViewSets (Week 10)
├── urls.py                  # URL routing (Week 10)
└── tests/
    ├── __init__.py
    ├── test_models.py       # Week 5
    ├── test_validator.py    # Week 6
    ├── test_handlers.py     # Week 7-8
    ├── test_executor.py     # Week 9
    ├── test_engine.py       # Week 9
    └── test_integration.py  # Week 11
```

---

## 🚀 Implementation Plan

### Week 5: Models + Migrations (CURRENT)

**Tasks:**
- [ ] Create `models.py` with WorkflowTemplate, WorkflowExecution, WorkflowStepResult
- [ ] Generate migrations
- [ ] Apply migrations
- [ ] Write unit tests (test_models.py)
- [ ] Document JSON schema

**Files to create:**
- `workflow/models.py`
- `workflow/migrations/0001_initial.py`
- `workflow/tests/test_models.py`

---

### Week 6: DAGValidator

**Tasks:**
- [ ] Implement `validator.py` with Kahn's algorithm
- [ ] Cycle detection
- [ ] Reachability validation
- [ ] Node type validation
- [ ] Write 37+ tests

---

### Week 7-8: NodeHandlers

**Tasks:**
- [ ] OperationHandler (uses Template Engine)
- [ ] ConditionHandler (Jinja2 expressions)
- [ ] ParallelHandler (Celery group)
- [ ] LoopHandler (count/while/foreach)
- [ ] SubWorkflowHandler (recursive)

---

### Week 9: WorkflowEngine + DAGExecutor

**Tasks:**
- [ ] DAGExecutor - execute nodes in topological order
- [ ] WorkflowEngine - main orchestrator
- [ ] ContextManager - data passing
- [ ] Integration tests

---

### Week 10-11: REST API + Testing

**Tasks:**
- [ ] ViewSets (CRUD for workflows)
- [ ] Serializers
- [ ] Celery tasks (async execution)
- [ ] Performance testing
- [ ] Load testing

---

## 📖 Related Documentation

- **Design:** `docs/architecture/UNIFIED_WORKFLOW_VISUALIZATION.md` v2.0
- **Roadmap:** `docs/roadmaps/UNIFIED_WORKFLOW_ROADMAP.md`
- **Summary:** `docs/UNIFIED_PLATFORM_OVERVIEW.md`
- **Original:** `docs/WORKFLOW_ENGINE_ARCHITECTURE.md` (Track 1.5)

---

## 🧪 Testing Strategy

**Target:** >80% coverage

**Test files:**
- `test_models.py` - Django models (~15 tests)
- `test_validator.py` - DAGValidator (~37 tests)
- `test_handlers.py` - NodeHandlers (~50 tests)
- `test_executor.py` - DAGExecutor (~20 tests)
- `test_engine.py` - WorkflowEngine (~30 tests)
- `test_integration.py` - E2E (~20 tests)

**Total:** ~170+ tests

---

## 🚀 Quick Start

### Run Tests

```bash
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate
pytest apps/templates/workflow/tests/ -v
```

### Check Coverage

```bash
pytest apps/templates/workflow/tests/ --cov=apps.templates.workflow --cov-report=html
```

### Apply Migrations

```bash
python manage.py makemigrations templates
python manage.py migrate
```

---

**Current Status:** Week 5 - Ready to start models implementation
**Next:** Create `models.py` with WorkflowTemplate model
