# Git Worktree: Unified Workflow Platform

**Created:** 2025-11-23
**Worktree Path:** `C:\1CProject\command-center-1c-unified-workflow`
**Branch:** `feature/unified-workflow-platform`

---

## 🎯 What is This?

Создан **отдельный git worktree** для разработки Unified Workflow Platform.

**Что это значит:**
- ✅ Есть ДВА рабочих каталога для одного репозитория:
  1. `C:\1CProject\command-center-1c` - **master** (основная работа)
  2. `C:\1CProject\command-center-1c-unified-workflow` - **feature branch** (Unified Workflow)

- ✅ Можно работать параллельно:
  - Main worktree: текущие задачи, bug fixes, hotfixes
  - Feature worktree: Unified Workflow implementation (Week 5-18)

- ✅ Нет необходимости делать `git stash` при переключении веток

---

## 📋 Worktree Commands

### List All Worktrees

```bash
cd /c/1CProject/command-center-1c
git worktree list

# Output:
# C:/1CProject/command-center-1c                   7ecfd4d [master]
# C:/1CProject/command-center-1c-unified-workflow  7ecfd4d [feature/unified-workflow-platform]
```

### Switch to Unified Workflow Worktree

```bash
# Simply cd to worktree directory
cd /c/1CProject/command-center-1c-unified-workflow

# Check branch
git branch
# Output: * feature/unified-workflow-platform
```

### Switch Back to Main Worktree

```bash
cd /c/1CProject/command-center-1c

# Check branch
git branch
# Output: * master
```

### Remove Worktree (When Feature Complete)

```bash
# From main worktree
cd /c/1CProject/command-center-1c

# Remove worktree
git worktree remove ../command-center-1c-unified-workflow

# Delete branch (after merging)
git branch -d feature/unified-workflow-platform
```

---

## 🚀 Working in Unified Workflow Worktree

### Setup (First Time)

```bash
# 1. Go to worktree
cd /c/1CProject/command-center-1c-unified-workflow

# 2. Activate Python venv
cd orchestrator
source venv/Scripts/activate

# 3. Install dependencies (if needed)
pip install opentelemetry-api opentelemetry-sdk channels channels-redis

# 4. Verify Django works
python manage.py check

# 5. Start working on Week 5
cd apps/templates/workflow
# Create models.py
```

### Daily Work

```bash
# 1. Go to worktree
cd /c/1CProject/command-center-1c-unified-workflow

# 2. Pull latest changes
git pull origin feature/unified-workflow-platform

# 3. Work on files
# Edit apps/templates/workflow/models.py

# 4. Run tests
cd orchestrator
pytest apps/templates/workflow/tests/ -v

# 5. Commit changes
git add apps/templates/workflow/
git commit -m "feat(workflow): Implement WorkflowTemplate model"

# 6. Push
git push origin feature/unified-workflow-platform
```

---

## 🔄 Keeping Worktree Synced with Master

### Rebase on Master (Every 2-3 Days)

```bash
# In unified-workflow worktree
cd /c/1CProject/command-center-1c-unified-workflow

# Fetch latest master
git fetch origin master

# Rebase feature branch on master
git rebase origin/master

# If conflicts:
# 1. Resolve conflicts
# 2. git add .
# 3. git rebase --continue

# Force push (if already pushed)
git push --force-with-lease origin feature/unified-workflow-platform
```

### Alternative: Merge Master into Feature

```bash
# In unified-workflow worktree
git fetch origin master
git merge origin/master

# Resolve conflicts if any
git commit
git push
```

---

## 📊 Workflow Timeline in This Worktree

```
Week 5 (NOW):     Models + Migrations
Week 6:           DAGValidator + Kahn's algorithm
Week 7-8:         NodeHandlers (5 types)
Week 9:           WorkflowEngine + DAGExecutor
Week 10:          REST API
Week 11:          Testing + Performance
Week 12:          OpenTelemetry Integration
Week 13:          WebSocket (Django Channels)
Week 14:          React Flow Design Mode
Week 15:          React Flow Monitor Mode
Week 16:          Service Mesh Monitor
Week 17:          Worker Migration
Week 18:          Documentation + Polish

Total: 18 weeks (Week 5-22)
```

---

## 📁 Files in This Worktree

**Created:**
- `WORKTREE_SETUP.md` - Setup instructions
- `orchestrator/apps/templates/workflow/` - Workflow Engine directory
  - `__init__.py`
  - `README.md`
  - `tests/__init__.py`

**Next to create (Week 5):**
- `workflow/models.py` - Django models
- `workflow/tests/test_models.py` - Model tests
- `workflow/migrations/0001_initial.py` - Django migrations

---

## ✅ Verification

### Check Worktree is Ready

```bash
cd /c/1CProject/command-center-1c-unified-workflow

# Should work:
git status
git branch
ls orchestrator/apps/templates/workflow/
cd orchestrator && python manage.py check
```

**All green?** ✅ Ready to start Week 5!

---

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| **Switch to feature** | `cd /c/1CProject/command-center-1c-unified-workflow` |
| **Switch to master** | `cd /c/1CProject/command-center-1c` |
| **Run tests** | `pytest apps/templates/workflow/tests/ -v` |
| **Commit** | `git add . && git commit -m "..."` |
| **Push** | `git push origin feature/unified-workflow-platform` |
| **Sync with master** | `git rebase origin/master` |

---

**Status:** ✅ Worktree готов
**Location:** `C:\1CProject\command-center-1c-unified-workflow`
**Branch:** `feature/unified-workflow-platform`
**Ready for:** Week 5 implementation (Models + Migrations)
