# Unified Workflow Platform - Worktree Setup

**Worktree Path:** `C:\1CProject\command-center-1c-unified-workflow`
**Branch:** `feature/unified-workflow-platform`
**Created:** 2025-11-23

---

## 📋 About This Worktree

Это **отдельный worktree** для разработки Unified Workflow Platform.

**Преимущества:**
- ✅ Изолированная работа (не трогает master)
- ✅ Можно переключаться между worktrees без stash
- ✅ Независимое окружение (venv, node_modules)
- ✅ Параллельная работа (main worktree + feature worktree)

---

## 🚀 Quick Start

### 1. Activate This Worktree

```bash
# Перейти в worktree директорию
cd /c/1CProject/command-center-1c-unified-workflow

# Проверить ветку
git branch
# Должно показать: * feature/unified-workflow-platform
```

### 2. Setup Python Environment

```bash
# Activate existing venv (shared with main worktree)
cd orchestrator
source venv/Scripts/activate

# OR create isolated venv (recommended for worktree)
cd orchestrator
python -m venv venv-workflow
source venv-workflow/Scripts/activate
pip install -r requirements.txt
```

### 3. Install Additional Dependencies

```bash
# OpenTelemetry для Week 12
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger

# Django Channels для Week 13
pip install channels channels-redis

# Development tools
pip install pytest-django pytest-cov
```

### 4. Verify Setup

```bash
# Check Django works
python manage.py check

# Check migrations
python manage.py showmigrations templates

# Run existing tests
pytest apps/templates/engine/tests/ -v
```

---

## 📁 Workflow Engine Structure

```
orchestrator/apps/templates/
└── workflow/                    ← NEW (created in this worktree)
    ├── __init__.py
    ├── README.md
    ├── models.py               ← Week 5 (START HERE)
    ├── validator.py            ← Week 6
    ├── executor.py             ← Week 9
    ├── handlers.py             ← Week 7-8
    ├── engine.py               ← Week 9
    ├── context.py              ← Week 9
    ├── consumers.py            ← Week 13 (WebSocket)
    ├── serializers.py          ← Week 10
    ├── views.py                ← Week 10
    ├── urls.py                 ← Week 10
    └── tests/
        ├── __init__.py
        ├── test_models.py      ← Week 5 (START HERE)
        ├── test_validator.py
        ├── test_handlers.py
        ├── test_executor.py
        ├── test_engine.py
        └── test_integration.py
```

---

## 🔄 Working with Worktrees

### Switch Between Worktrees

```bash
# Main worktree (master)
cd /c/1CProject/command-center-1c
git branch  # Shows: master

# Feature worktree (unified-workflow)
cd /c/1CProject/command-center-1c-unified-workflow
git branch  # Shows: feature/unified-workflow-platform
```

### Commit Changes

```bash
# In feature worktree
cd /c/1CProject/command-center-1c-unified-workflow

git add orchestrator/apps/templates/workflow/
git commit -m "feat(workflow): Add WorkflowTemplate model (Week 5 Day 1)"
git push -u origin feature/unified-workflow-platform
```

### Sync with Master

```bash
# In feature worktree
git fetch origin
git rebase origin/master

# Resolve conflicts if any
```

### Remove Worktree (When Done)

```bash
# From main worktree
cd /c/1CProject/command-center-1c
git worktree remove ../command-center-1c-unified-workflow

# Merge feature branch to master
git checkout master
git merge feature/unified-workflow-platform
```

---

## 📋 Week 5 Tasks (CURRENT)

### Day 1-2: Django Models

**Create:** `orchestrator/apps/templates/workflow/models.py`

**Models to implement:**
1. WorkflowTemplate
   - Fields: id, name, description, workflow_type, dag_structure, config
   - JSON schema validation for dag_structure
   - Version control (parent_version)

2. WorkflowExecution
   - Fields: id, workflow_template, input_context, status, current_node_id
   - Progress tracking (completed_nodes, failed_nodes)
   - OpenTelemetry fields (trace_id)

3. WorkflowStepResult
   - Fields: id, workflow_execution, node_id, status, input_data, output_data
   - Timing fields (started_at, completed_at, duration_seconds)
   - OpenTelemetry fields (span_id, trace_id)

**Reference:** `docs/architecture/UNIFIED_WORKFLOW_VISUALIZATION.md` (Django Models section)

### Day 3-4: Unit Tests

**Create:** `orchestrator/apps/templates/workflow/tests/test_models.py`

**Tests to write:**
- test_create_workflow_template()
- test_workflow_template_validation()
- test_workflow_execution_lifecycle()
- test_progress_calculation()
- test_step_result_creation()
- ~15 total tests

### Day 5: Documentation

**Update:**
- Document model fields
- Create ER diagram
- Example workflows (extension install, price list upload)

---

## 🧪 Testing in Worktree

### Run All Tests

```bash
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate

# Run workflow tests only
pytest apps/templates/workflow/tests/ -v

# Run with coverage
pytest apps/templates/workflow/tests/ --cov=apps.templates.workflow --cov-report=html

# Run all template tests (including engine)
pytest apps/templates/ -v
```

### Check Migrations

```bash
python manage.py makemigrations templates --dry-run
python manage.py makemigrations templates
python manage.py migrate
python manage.py showmigrations templates
```

---

## 📖 Documentation References

**In this worktree:**
- `docs/roadmaps/UNIFIED_WORKFLOW_ROADMAP.md` - 18-week plan
- `docs/architecture/UNIFIED_WORKFLOW_VISUALIZATION.md` - Design doc
- `docs/UNIFIED_PLATFORM_OVERVIEW.md` - Overview
- `orchestrator/apps/templates/workflow/README.md` - This file

**Original design:**
- `docs/WORKFLOW_ENGINE_ARCHITECTURE.md` - Track 1.5 original

---

## ⚠️ Important Notes

### Don't Merge Until Complete

**Workflow branch should NOT be merged to master until:**
- [ ] All Week 5-11 tasks complete (backend)
- [ ] Tests pass (>80% coverage)
- [ ] Code review done
- [ ] Documentation updated

**Reason:** Prevent incomplete features in master

### Keep Synced with Master

**Rebase regularly** (every 2-3 days):
```bash
git fetch origin
git rebase origin/master
```

**Avoid:** Long-lived branches (> 2 weeks без sync)

### Python Environment

**Option A:** Share venv with main worktree
- ✅ Saves disk space
- ⚠️ Risk: dependency conflicts

**Option B:** Create isolated venv (RECOMMENDED)
- ✅ Complete isolation
- ✅ No conflicts
- ⚠️ Uses more disk space

**Chosen:** Shared venv (dependencies same as main)

---

## 🔍 Verification Checklist

**Before starting Week 5:**

- [x] Worktree created successfully
- [x] Branch `feature/unified-workflow-platform` exists
- [x] Directory `workflow/` created
- [x] Directory `workflow/tests/` created
- [ ] Python venv activated
- [ ] Dependencies installed
- [ ] Django check passes
- [ ] Can run existing tests

**To verify:**

```bash
cd /c/1CProject/command-center-1c-unified-workflow

# 1. Check worktree
git worktree list
# Should show: command-center-1c-unified-workflow

# 2. Check branch
git branch
# Should show: * feature/unified-workflow-platform

# 3. Check Django
cd orchestrator
source venv/Scripts/activate
python manage.py check
# Should: System check identified no issues

# 4. Check workflow directory
ls apps/templates/workflow/
# Should show: __init__.py, README.md, tests/
```

---

## 📞 Support

**Questions?** See:
- Main roadmap: `docs/roadmaps/UNIFIED_WORKFLOW_ROADMAP.md`
- Week 5 tasks: Section "Week 5: Models + Migrations"
- Design reference: `docs/architecture/UNIFIED_WORKFLOW_VISUALIZATION.md`

---

**Status:** ✅ Worktree готов к работе
**Next:** Implement `workflow/models.py` (Week 5 Day 1-2)
