# Unified Workflow Visualization Platform - Complete Overview

**Version:** 2.0 - Two-Tab Interface
**Date:** 2025-11-23
**Status:** ✅ APPROVED FOR IMPLEMENTATION

---

## 🎯 Что это?

**Единая платформа визуализации** для CommandCenter1C, объединяющая:

1. **Workflow Engine** (Track 1.5) - создание и выполнение многошаговых workflows
2. **Real-Time Tracking** - мониторинг обмена данными между микросервисами
3. **Two-Tab Interface** - system-wide + workflow-specific views

---

## 📊 Two-Tab Interface

### 🌐 Tab 1: Service Mesh Monitor

**Для кого:** Администраторы, DevOps, мониторинг системы

**Что показывает:**
```
Aggregate view всех микросервисов:
  • Frontend → API Gateway → Orchestrator → Worker → RAS
  • Operations/min по каждому сервису
  • Active/Failed operations counters
  • P95 latency metrics
  • Recent operations table (last 5 min)
```

**Возможности:**
- ✅ Real-time updates каждые 2 секунды (WebSocket)
- ✅ Click на сервис → показать список операций
- ✅ Click на операцию → автопереход в Workflows tab
- ✅ Визуализация system health (зеленый/желтый/красный)

**Use Case:**
```
"Вижу что Worker перегружен (50 active ops)
 → Click на Worker → вижу список операций
 → Click на failed operation
 → Автоматически переходит в My Workflows tab
 → Открывается Monitor Mode для этой операции"
```

---

### 📋 Tab 2: My Workflows

**Для кого:** Все пользователи (бизнес + админы)

**Три режима:**

#### 1️⃣ List Mode (Default)

```
Показывает:
  • Список моих workflows (созданных пользователем)
  • Active executions (workflows выполняющиеся сейчас)
  • Execution history
```

#### 2️⃣ Design Mode

```
Visual workflow builder:
  • Drag & drop nodes (Operation, Condition, Parallel, Loop)
  • Connect nodes (edges)
  • Edit node properties
  • Validate workflow
  • Save workflow
```

**Use Case:**
```
"Создаю workflow 'Upload Price List':
 1. Drag 'Operation' node → Configure as 'Validate Excel'
 2. Drag another → Configure as 'Parse Rows'
 3. Connect nodes
 4. Save
 5. Click Run → switches to Monitor Mode"
```

#### 3️⃣ Monitor Mode

```
Live execution monitoring:
  • Workflow canvas (read-only) с live status
  • Node statuses: pending/running/completed/failed
  • Progress bar (60% complete)
  • Timeline (step 1: 0.8s, step 2: 2.3s, step 3: running...)
  • Click node → Detailed traces (Jaeger)
```

**Use Case:**
```
"Запустил workflow 'Install Extension'
 → Вижу что Lock Jobs ✓ completed (0.8s)
 → Вижу что Terminate ✓ completed (2.3s)
 → Вижу что Install ⚡ running (45s elapsed...)
 → Click на Install node → Jaeger trace показывает progress"
```

---

## 🔄 Cross-Tab Navigation

### Service Mesh → Workflows

```
┌─────────────────────────────────────────────┐
│ Tab: Service Mesh                           │
│                                             │
│ Recent Operations:                          │
│   op-67890  Install Ext  ⚡ Running  45s   │ ← Click
└─────────────────┬───────────────────────────┘
                  │
                  │ Auto-switch
                  ▼
┌─────────────────────────────────────────────┐
│ Tab: My Workflows                           │
│                                             │
│ Monitoring: Install Extension Workflow      │
│   [Lock Jobs]     ✓ 0.8s                   │
│   [Terminate]     ✓ 2.3s                   │
│   [Install Ext]   ⚡ 45s ← Auto-selected   │
│   [Unlock Jobs]   ○ Pending                │
└─────────────────────────────────────────────┘
```

### Workflows → Service Mesh

```
┌─────────────────────────────────────────────┐
│ Tab: My Workflows                           │
│                                             │
│ Monitoring workflow...                      │
│ [View System Impact] ← Click button        │
└─────────────────┬───────────────────────────┘
                  │
                  │ Switch tab
                  ▼
┌─────────────────────────────────────────────┐
│ Tab: Service Mesh                           │
│                                             │
│ Shows current system load:                  │
│   Worker: 50 active ops (HIGH!)            │
│   Your workflow = 1 of 50                   │
└─────────────────────────────────────────────┘
```

---

## 🏗️ Architecture

### Frontend Architecture

```
src/
├── pages/
│   └── Dashboard.tsx                 # Main dashboard with tabs
│
├── components/
│   ├── service-mesh/
│   │   ├── ServiceMeshTab.tsx        # Tab 1 container
│   │   ├── SystemHealthCard.tsx
│   │   ├── ServiceFlowDiagram.tsx
│   │   ├── ServiceNode.tsx
│   │   └── RecentOperationsTable.tsx
│   │
│   └── workflows/
│       ├── MyWorkflowsTab.tsx        # Tab 2 container
│       ├── WorkflowList.tsx
│       ├── WorkflowCanvas.tsx        # Design + Monitor modes
│       ├── NodePalette.tsx
│       ├── PropertyEditor.tsx
│       └── TraceViewerModal.tsx
│
├── hooks/
│   ├── useServiceMeshMetrics.ts      # WebSocket for Service Mesh
│   └── useWorkflowExecution.ts       # WebSocket for Workflows
│
└── stores/
    └── dashboardStore.ts             # Unified state (Zustand)
```

### Backend Architecture

```
Backend Services:

┌─────────────────────────────────────────────────────────┐
│  Metrics Aggregator (Go, port 8090)                     │
│  • Query Prometheus every 2s                            │
│  • Aggregate metrics by service                         │
│  • WebSocket /ws/service-mesh                           │
│  • Push to Service Mesh Tab                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Django Orchestrator (port 8000)                        │
│  • WorkflowEngine (execute workflows)                   │
│  • Django Channels (WebSocket /ws/workflow/{id}/)       │
│  • OpenTelemetry (create traces)                        │
│  • Push to My Workflows Tab                             │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Jaeger (port 16686)                                    │
│  • Store traces                                         │
│  • Query API for Trace Viewer                           │
│  • Integrated in both tabs                              │
└─────────────────────────────────────────────────────────┘
```

---

## 📱 User Personas & Use Cases

### Persona 1: System Administrator (Admin)

**Primary Tab:** Service Mesh Monitor

**Typical Day:**
```
09:00 - Открывает Service Mesh tab
        Видит system healthy, 100 ops/min

10:30 - Spike в latency на Worker (P95: 5s вместо 2.5s)
        Click на Worker → видит 5 "Upload Price List" workflows
        Click на одну → Workflows tab, Monitor Mode
        Видит что batch size слишком большой
        Edit workflow → Reduce batch size
        Problem solved

14:00 - Extension install failed
        Service Mesh tab показывает ✗ в Worker
        Click на failed operation
        Auto-switch to Workflows tab
        Trace показывает "RAS timeout"
        Identifies issue: too many concurrent connections

17:00 - End of day review
        Service Mesh показывает:
          • 2340 operations processed today
          • 2 failures (99.9% success rate)
          • P95 latency stable at 1.2s
```

### Persona 2: Business Analyst (User)

**Primary Tab:** My Workflows

**Typical Day:**
```
09:30 - Открывает My Workflows tab
        Видит список своих workflows

10:00 - Нужно загрузить прайс-лист
        Click "Upload Price List" workflow
        Click [Run]
        Monitor Mode shows progress: 20%

10:15 - Workflow complete ✓
        100 items imported
        Report generated

11:00 - Создает новый workflow "Monthly Close"
        Design Mode: drag & drop 12 nodes
        Configure properties
        Validate → Success
        Save workflow

14:00 - Запускает "Monthly Close" workflow
        Monitor Mode: 8 of 12 steps complete
        Step 9 failed: "Tax calculation error"
        Click на failed node → Trace viewer
        Видит что missing input variable
        Fix workflow → Re-run
```

### Persona 3: DevOps Engineer (Hybrid)

**Primary Tab:** Both (switches frequently)

**Typical Day:**
```
08:00 - Service Mesh tab: Check system health
        All green ✓

09:00 - Deploy new Worker version
        Service Mesh: Monitor Worker metrics
        Latency spike → investigate

09:15 - Switch to Workflows tab
        Check if any workflows affected
        See 3 workflows running on new Worker
        Monitor их progress

09:30 - One workflow failed
        Trace показывает incompatibility
        Rollback Worker to previous version

10:00 - Service Mesh: Verify rollback
        Metrics back to normal ✓

11:00 - My Workflows: Create "Health Check" workflow
        Runs every 5 minutes (Celery Beat)
        Monitors critical endpoints
```

---

## 🚀 Implementation Priority

### Must Have (Week 12-15)

- ✅ Workflow Engine backend (Week 5-11)
- ✅ OpenTelemetry integration (Week 12)
- ✅ WebSocket for workflows (Week 13)
- ✅ React Flow Design Mode (Week 14)
- ✅ React Flow Monitor Mode (Week 15)

### Should Have (Week 16) ⭐

- ✅ Service Mesh Monitor
- ✅ Two-Tab Interface
- ✅ Cross-tab navigation

**Decision Point:** Week 15
- ✅ YES → Add Week 16 (recommended)
- ❌ NO → Use Grafana for service mesh (acceptable)

### Nice to Have (Week 17-18)

- ✅ Worker migration to workflows
- ✅ Full documentation
- ✅ Mobile optimization
- ✅ Advanced features (pause/resume, rollback)

---

## 📋 Quick Start (After Implementation)

### For Admins

```bash
# Open CommandCenter1C
open http://localhost:5173

# Default: Service Mesh tab opens
# See system overview

# Workflow failed? Click → auto-opens in Workflows tab
# Debug with traces
```

### For Business Users

```bash
# Open CommandCenter1C
open http://localhost:5173

# Click "My Workflows" tab
# See your workflows

# Create new workflow:
# 1. Click "+ Create Workflow"
# 2. Drag & drop nodes
# 3. Save
# 4. Run
# 5. Monitor execution
```

---

## 📖 Documentation Structure

```
docs/
├── UNIFIED_PLATFORM_OVERVIEW.md           # ← This file (overview)
├── UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md    # Quick summary
├── TWO_TAB_INTERFACE_DESIGN.md            # Detailed UI design
│
├── architecture/
│   └── UNIFIED_WORKFLOW_VISUALIZATION.md  # Complete design doc (v2.0)
│
├── roadmaps/
│   └── UNIFIED_WORKFLOW_ROADMAP.md        # Implementation roadmap (18 weeks)
│
└── user-guides/ (after Week 18)
    ├── SERVICE_MESH_GUIDE.md              # How to use Service Mesh tab
    ├── WORKFLOW_CREATION_GUIDE.md         # How to create workflows
    └── WORKFLOW_MONITORING_GUIDE.md       # How to monitor workflows
```

---

## 🎉 Benefits Summary

### For Users

| Benefit | Description |
|---------|-------------|
| **Единый интерфейс** | Одно приложение для всех задач |
| **Visual workflow builder** | Не нужно писать JSON вручную |
| **Live monitoring** | Видишь progress в реальном времени |
| **Easy debugging** | Click node → see traces |
| **No context switching** | Design → Run → Monitor в одном UI |

### For Admins

| Benefit | Description |
|---------|-------------|
| **System visibility** | Видишь все микросервисы и обмены |
| **Quick drill-down** | Service Mesh → Workflow в 2 клика |
| **Performance monitoring** | Real-time metrics (latency, throughput) |
| **Proactive alerts** | Видишь проблемы до user complaints |
| **Unified debugging** | Traces в том же интерфейсе |

### For DevOps

| Benefit | Description |
|---------|-------------|
| **Complete observability** | System + Workflow levels |
| **Faster debugging** | От symptom к root cause за минуты |
| **Better testing** | Create test workflows визуально |
| **Deployment validation** | Monitor impact в Service Mesh |
| **Reduced tools** | Меньше нужно Grafana/Jaeger tabs |

---

## ⏱️ Timeline

```
✅ Week 1-4:   Foundation (RAS Adapter) COMPLETE
🔜 Week 5-11:  Workflow Engine Backend (7 weeks)
⏳ Week 12:    OpenTelemetry Integration
⏳ Week 13:    WebSocket Integration
⏳ Week 14:    React Flow Design Mode
⏳ Week 15:    React Flow Monitor Mode
⏳ Week 16:    Service Mesh Monitor ⭐ TWO-TAB INTERFACE
⏳ Week 17:    Worker Migration
⏳ Week 18:    Documentation + Polish

Total: 18 weeks (4.5 months)
```

**MVP Option:** Stop at Week 11 (Workflow Engine backend only, no UI)
**Recommended:** Complete all 18 weeks (full feature set)

---

## 🎨 Visual Preview

### Service Mesh Tab

```
🌐 Service Mesh
═══════════════

System Health: 🟢 234 ops/min, P95: 1.2s

    [Frontend] 20↓
        ↓
    [API GW] 20→ ⏱50ms
        ↓
    [Worker] ⚡18 ✗2
        ↓
    [RAS] ⏱1.2s

Recent: op-67890 Install Ext ⚡45s ← Click
```

### My Workflows Tab

```
📋 My Workflows
═══════════════

My Workflows:
  • Install Extension [Run][Edit]
  • Upload Price List [Run][Edit]

Active Executions:
  • Install Extension ⚡60% [Monitor] ← Click

─────────────────────────────
Monitor Mode:

[Lock Jobs]    ✓ 0.8s   ← Click → Trace
[Terminate]    ✓ 2.3s
[Install Ext]  ⚡ 45s
[Unlock Jobs]  ○ Pending
```

---

## 🚀 Key Features

### 1. Universal Workflow Format

**Любая задача = workflow:**

```
Админские задачи:          Бизнес задачи:
• Extension Install        • Price List Upload
• Config Update            • Counterparty Import
• Database Backup          • Monthly Close

Один формат, один engine, один UI!
```

### 2. Design + Runtime в одном UI

```
Create → Run → Monitor → Debug → Fix
  ↑___________________________________|

Все в одном интерфейсе, без переключений!
```

### 3. Built-in Observability

```
OpenTelemetry spans:
  Workflow execution = Parent span
  Each node = Child span

Result: Full trace в Jaeger автоматически!
```

### 4. Real-Time Updates

```
WebSocket #1: Service Mesh metrics (2s updates)
WebSocket #2: Workflow status (instant on change)

Frontend всегда показывает актуальное состояние!
```

### 5. Two Levels of Abstraction

```
Level 1: Service Mesh (system-wide)
  "Сколько операций где находится?"

Level 2: Workflow (individual)
  "Что происходит с моим workflow?"

Click → drill down между уровнями!
```

---

## 📚 Documentation Index

| Document | Purpose | Audience |
|----------|---------|----------|
| **[UNIFIED_PLATFORM_OVERVIEW.md](UNIFIED_PLATFORM_OVERVIEW.md)** | This file - complete overview | Everyone |
| **[UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md](UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md)** | Quick summary | Decision makers |
| **[TWO_TAB_INTERFACE_DESIGN.md](TWO_TAB_INTERFACE_DESIGN.md)** | Detailed UI design | Frontend devs |
| **[architecture/UNIFIED_WORKFLOW_VISUALIZATION.md](architecture/UNIFIED_WORKFLOW_VISUALIZATION.md)** | Complete design doc | Architects |
| **[roadmaps/UNIFIED_WORKFLOW_ROADMAP.md](roadmaps/UNIFIED_WORKFLOW_ROADMAP.md)** | 18-week roadmap | Project managers |

---

## ❓ FAQs

**Q: Нужно ли реализовывать оба tab сразу?**
A: НЕТ! Можно:
- Week 5-15: Только Workflows tab (stop here = MVP)
- Week 16: Add Service Mesh tab (recommended)

**Q: Можно ли использовать Grafana вместо Service Mesh tab?**
A: ДА! Grafana хорош для historical analysis. Service Mesh tab лучше для real-time + drill-down.

**Q: Workflows tab работает без Service Mesh tab?**
A: ДА! Полностью независимы. Service Mesh tab опционален.

**Q: Service Mesh tab работает без Workflows tab?**
A: ЧАСТИЧНО. Metrics показываются, но cross-navigation не работает (некуда drill down).

**Q: Какие роли нужны для каждого tab?**
A: Гибко настраивается:
- Admin: оба tab
- Business User: только Workflows tab
- Operator: оба tab (read-only)

**Q: Сколько WebSocket connections одновременно?**
A:
- Service Mesh tab visible: 1 connection (metrics)
- Monitoring 1 workflow: +1 connection (workflow status)
- Total: max 2 concurrent WebSocket connections per user

---

## ✅ Approval Checklist

- [x] Two-Tab Interface design reviewed
- [x] Service Mesh Monitor scope defined
- [x] Cross-tab navigation flow approved
- [x] Timeline updated (17 → 18 weeks)
- [x] Documentation created
- [ ] Team capacity confirmed for Week 16
- [ ] Budget approved for additional week
- [ ] Stakeholders signed off

---

## 🚦 Next Steps

### Immediate

1. **Review all documents:**
   - ✅ UNIFIED_PLATFORM_OVERVIEW.md (this file)
   - ✅ UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md
   - ✅ TWO_TAB_INTERFACE_DESIGN.md
   - ✅ architecture/UNIFIED_WORKFLOW_VISUALIZATION.md v2.0
   - ✅ roadmaps/UNIFIED_WORKFLOW_ROADMAP.md v2.0

2. **Get stakeholder approval**

3. **Begin Phase 2 (Week 5)**

### Week 5 Tasks

```bash
# Create branch
git checkout -b feature/unified-workflow-phase2

# Start with Django models
cd orchestrator/apps/templates
# Create models.py for WorkflowTemplate, WorkflowExecution

# See roadmap for detailed week-by-week tasks
```

---

**Status:** ✅ READY TO START
**Decision:** Two-Tab Interface APPROVED
**Start Date:** Week 5 (TBD)
**Expected Completion:** Week 22 (18 weeks from start)
