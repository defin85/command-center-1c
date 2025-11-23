# Week 5 Quick Start Guide

**Goal:** Начать разработку Django models для Workflow Engine
**Duration:** ~1 минута на setup
**Prerequisites:** Основная ветка запущена (Docker контейнеры работают)

---

## ⚡ Быстрый старт (4 команды)

```bash
# 1. Перейти в worktree
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator

# 2. Активировать venv
source venv/Scripts/activate

# 3. Проверить что shared infrastructure работает
psql -h localhost -p 5432 -U commandcenter -d commandcenter -c "SELECT 1;"
# Должно вернуть: 1

# 4. Запустить Django на порту 8100
python manage.py runserver 8100
```

**Done!** Теперь можешь начинать писать models.

---

## 📝 Week 5 Tasks

### Day 1-2: Create Models

**File:** `orchestrator/apps/templates/workflow/models.py`

**Models to create:**
1. WorkflowTemplate
2. WorkflowExecution
3. WorkflowStepResult

**Commands:**
```bash
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate

# After creating models.py
python manage.py makemigrations templates
python manage.py migrate

# Verify
python manage.py showmigrations templates
```

### Day 3-4: Write Tests

**File:** `orchestrator/apps/templates/workflow/tests/test_models.py`

**Commands:**
```bash
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate

# Run tests
pytest apps/templates/workflow/tests/test_models.py -v

# With coverage
pytest apps/templates/workflow/tests/test_models.py --cov=apps.templates.workflow --cov-report=html
```

### Day 5: Documentation

Update `workflow/models.py` with docstrings

---

## 🔍 Verification

### Check both worktrees work simultaneously

```bash
# Terminal 1: Main worktree
cd /c/1CProject/command-center-1c/orchestrator
source venv/Scripts/activate
python manage.py runserver 8000

# Terminal 2: Feature worktree
cd /c/1CProject/command-center-1c-unified-workflow/orchestrator
source venv/Scripts/activate
python manage.py runserver 8100

# Test both
curl http://localhost:8000/admin/  # Main
curl http://localhost:8100/admin/  # Feature

# Both should work! ✅
```

---

## 🐛 Troubleshooting

### "Port 8100 already in use"

```bash
# Find process
lsof -i :8100

# Kill it
kill -9 <PID>
```

### "Cannot connect to PostgreSQL"

```bash
# Check main worktree Docker is running
cd /c/1CProject/command-center-1c
docker ps | grep postgres

# If not running, start it
docker-compose up -d postgres redis
```

### "Module not found: apps.templates.workflow"

```bash
# Make sure __init__.py exists
ls orchestrator/apps/templates/workflow/__init__.py

# If missing, create it
touch orchestrator/apps/templates/workflow/__init__.py
```

---

## 📖 Reference

**Design Doc:** `docs/architecture/UNIFIED_WORKFLOW_VISUALIZATION.md` (Section: Django Models)
**Roadmap:** `docs/roadmaps/UNIFIED_WORKFLOW_ROADMAP.md` (Week 5)
**Port Config:** `PORTS_CONFIGURATION.md`
**Worktree Setup:** `WORKTREE_SETUP.md`

---

**Status:** ✅ Ready to start Week 5
**Next:** Create `workflow/models.py`
