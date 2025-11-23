# Unified Workflow Visualization Platform

**Version:** 2.0
**Date:** 2025-11-23
**Status:** Design Document - Extended with Service Mesh Monitor
**Author:** AI Architect + AI Orchestrator

---

## 📋 Table of Contents

- [Executive Summary](#executive-summary)
- [Problem Statement](#problem-statement)
- [Solution: Unified Platform](#solution-unified-platform)
- [Two-Tab Interface Design](#two-tab-interface-design)
- [Architecture Overview](#architecture-overview)
- [Unified Workflow Concept](#unified-workflow-concept)
- [Component Design](#component-design)
  - [Workflow Components](#workflow-components)
  - [Service Mesh Monitor Components](#service-mesh-monitor-components)
- [Data Models](#data-models)
- [API Specification](#api-specification)
- [UI/UX Design](#uiux-design)
- [Integration Points](#integration-points)
- [Migration Strategy](#migration-strategy)
- [Testing Strategy](#testing-strategy)
- [Timeline & Roadmap](#timeline--roadmap)
- [References](#references)

---

## Executive Summary

### Problem

CommandCenter1C имеет два параллельных направления для визуализации:

1. **Track 1.5: Workflow Engine** - визуальное создание многошаговых workflows (design-time)
2. **Real-Time Operation Tracking** - мониторинг выполнения операций через микросервисы (run-time)

**Проблема:** Разделение design-time и run-time создает:
- ❌ Два разных UI для одной сущности (workflow)
- ❌ Дублирование кода визуализации
- ❌ Сложность debugging (нужно переключаться между интерфейсами)
- ❌ Разный UX для пользователей и администраторов

### Solution

**Unified Workflow Visualization Platform** - единая платформа, объединяющая:

✅ **Design Mode** - визуальное создание workflows (React Flow)
✅ **Monitor Mode** - live execution status на том же UI
✅ **Trace Mode** - detailed debugging через Jaeger integration
✅ **Service Mesh View** - aggregate monitoring всех микросервисов (NEW!)
✅ **Universal Abstraction** - workflows для всех типов задач (данные + админские)

**Two-Tab Interface:**
- **Tab 1: Service Mesh** - system-wide view (все операции, все сервисы)
- **Tab 2: My Workflows** - workflow-specific view (design + monitor)

### Key Insight

**Административные задачи = тоже workflows!**

```
Установка расширения:
1. Lock scheduled jobs    ← Node 1
2. Terminate sessions     ← Node 2
3. Install extension      ← Node 3
4. Unlock scheduled jobs  ← Node 4

= Extension Install Workflow
```

**Работа с данными:**
```
Загрузка прайс-листа:
1. Validate Excel file    ← Node 1
2. Parse rows             ← Node 2 (Loop)
3. Create/Update items    ← Node 3 (Parallel)
4. Generate report        ← Node 4

= Price List Upload Workflow
```

### Benefits

| Benefit | Impact |
|---------|--------|
| **Единый UX** | Одна парадигма для всех пользователей |
| **Design + Runtime** | Создал → запустил → увидел в том же UI |
| **Built-in Debugging** | Click node → see traces |
| **Code Reuse** | React Flow для design и monitor modes |
| **Incremental Migration** | Старый код продолжает работать |

### Timeline

**18 weeks (4.5 months)** от start до production-ready

- **Phase 1:** RAS Adapter MVP ✅ DONE (Week 1-4)
- **Phase 2:** Workflow Engine Backend (Week 5-11)
- **Phase 3:** Real-Time Integration + Service Mesh (Week 12-16)
  - Week 12: OpenTelemetry
  - Week 13: WebSocket
  - Week 14: React Flow Design Mode
  - Week 15: React Flow Monitor Mode
  - Week 16: Service Mesh Monitor (NEW!)
- **Phase 4:** Polish & Documentation (Week 17-18)

**MVP Option:** 11 weeks (до end of Phase 2) - basic workflows без real-time UI
**Full Option:** 18 weeks - workflows + service mesh + documentation

---

## Problem Statement

### Current State

#### Track 1.5: Workflow Engine

**Status:** Design Document, готов к реализации
**Scope:** DAG-based workflow orchestration для composition операций

**Features:**
- ✅ WorkflowTemplate model (Nodes + Edges JSON)
- ✅ DAGValidator (Kahn's algorithm)
- ✅ NodeHandlers (Operation, Condition, Parallel, Loop, SubWorkflow)
- ✅ Data passing между steps (`{{ step1.result.field }}`)

**Gap:** НЕТ визуализации! Только JSON в БД, UI планируется в Track 4 (Phase 3)

#### Real-Time Operation Tracking

**Status:** Design Document
**Scope:** Distributed tracing + real-time monitoring микросервисов

**Features:**
- ✅ OpenTelemetry + Jaeger integration
- ✅ Service Mesh Monitor (aggregate view)
- ✅ Operation Trace Viewer (individual tracking)
- ✅ WebSocket для real-time updates

**Gap:** НЕТ связи с workflows! Tracking arbitrary операций, не workflow executions

### Problems with Separation

**1. Two UIs for One Concept**

```
User Journey:
1. Create workflow (где? Track 1.5 UI - НЕ существует!)
2. Execute workflow (через API call)
3. Monitor execution (где? Track 4 UI - НЕ существует!)
4. Debug failure (Jaeger UI - отдельный интерфейс)

Result: Пользователь прыгает между 3+ интерфейсами!
```

**2. Admin Tasks = Implicit Workflows**

```go
// go-services/worker/internal/processor/extension_install.go

// Это УЖЕ workflow, но неявный!
func (p *Processor) InstallExtension(ctx context.Context, msg *OperationMessage) {
    // Step 1: Lock
    if err := p.LockScheduledJobs(ctx, ...); err != nil { ... }

    // Step 2: Terminate
    if err := p.TerminateSessions(ctx, ...); err != nil { ... }

    // Step 3: Install
    if err := p.InstallExtensionFile(ctx, ...); err != nil { ... }

    // Step 4: Unlock
    if err := p.UnlockScheduledJobs(ctx, ...); err != nil { ... }
}
```

**Why not explicit?** Потому что нет Workflow Engine!

**3. Duplicate Visualization Code**

- Track 1.5: планирует React Flow для workflow builder
- Real-Time Tracking: планирует custom service mesh visualization

**Result:** Два разных компонента для похожих задач!

**4. Different UX for Different Users**

- **Business Users:** "Нужен workflow для загрузки контрагентов"
- **Admins:** "Нужен способ мониторить установку расширений"

**Current approach:** Разные интерфейсы для разных ролей
**Better approach:** Один универсальный workflow UI для всех

---

## Solution: Unified Platform

### Core Concept

```
┌─────────────────────────────────────────────────────────────┐
│            Unified Workflow Visualization                   │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│   DESIGN MODE        │   MONITOR MODE                       │
│   (Create)           │   (Execute & Watch)                  │
│                      │                                      │
│   React Flow         │   React Flow (read-only)             │
│   + Node palette     │   + Live status overlays             │
│   + Drag & drop      │   + Real-time updates (WebSocket)    │
│   + Save workflow    │   + Click node → Trace viewer        │
│                      │                                      │
└──────────────────────┴──────────────────────────────────────┘
         ▲                          ▲
         │                          │
    Design Time                 Run Time
    (Track 1.5)            (Real-Time Tracking)
         │                          │
         └─────────┬────────────────┘
                   │
         Unified Backend API
         (WorkflowEngine + OpenTelemetry)
```

### Key Features

#### 1. Universal Workflow Definition

**ALL tasks = workflows:**

```json
{
  "name": "Install Extension Workflow",
  "description": "Admin task: multi-step extension installation",
  "nodes": [
    {"id": "lock", "type": "operation", "template_id": "tmpl_lock_jobs"},
    {"id": "terminate", "type": "operation", "template_id": "tmpl_terminate"},
    {"id": "install", "type": "operation", "template_id": "tmpl_install_ext"},
    {"id": "unlock", "type": "operation", "template_id": "tmpl_unlock_jobs"}
  ],
  "edges": [
    {"from": "lock", "to": "terminate"},
    {"from": "terminate", "to": "install"},
    {"from": "install", "to": "unlock"}
  ]
}
```

```json
{
  "name": "Upload Price List Workflow",
  "description": "User task: bulk data import from Excel",
  "nodes": [
    {"id": "validate", "type": "operation", "template_id": "tmpl_validate_excel"},
    {"id": "parse", "type": "operation", "template_id": "tmpl_parse_rows"},
    {"id": "import", "type": "parallel", "parallel_nodes": ["create_items"]},
    {"id": "report", "type": "operation", "template_id": "tmpl_generate_report"}
  ],
  "edges": [...]
}
```

**Same format, same engine, same UI!**

#### 2. Mode Switching

```typescript
<WorkflowCanvas mode={mode}>  // mode = "design" | "monitor"
  {mode === "design" ? (
    <DesignView
      workflow={workflow}
      onSave={saveWorkflow}
      onExecute={executeWorkflow}
    />
  ) : (
    <MonitorView
      execution={execution}
      onNodeClick={showTraces}
    />
  )}
</WorkflowCanvas>
```

**User flow:**
1. Create workflow in Design Mode
2. Click "▶️ Run" → switches to Monitor Mode
3. Watch live execution
4. Click failed node → Trace viewer opens
5. Fix workflow → back to Design Mode

#### 3. OpenTelemetry Integration

```python
# WorkflowEngine creates parent span
with tracer.start_as_current_span(f"workflow.{workflow.name}") as parent_span:
    parent_span.set_attribute("workflow.execution_id", execution.id)

    # Execute nodes (each creates child span)
    for node in dag_order:
        with tracer.start_as_current_span(f"node.{node.id}") as node_span:
            result = handler.execute(node, context)
```

**Result:** Every workflow execution → complete trace in Jaeger!

#### 4. Real-Time Status Updates

```python
# WebSocket broadcast on node completion
channel_layer.group_send(
    f"workflow_{execution.id}",
    {
        "type": "node_completed",
        "node_id": node.id,
        "status": "success",
        "duration": 0.8,
        "result": {...}
    }
)
```

```typescript
// Frontend updates node color
<OperationNode
  status={nodeStatus}  // pending | running | completed | failed
  duration={nodeDuration}
  onClick={() => showTraces(node.id)}
/>
```

---

## Two-Tab Interface Design

### Overview

**Unified Dashboard с двумя уровнями визуализации:**

1. **Service Mesh Tab** - System-wide aggregate view
2. **My Workflows Tab** - Workflow-specific design + monitor

### UI Mockup

```
┌────────────────────────────────────────────────────────────┐
│  CommandCenter1C                           [User: admin ▼] │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Tabs: [🌐 Service Mesh] [📋 My Workflows]                │
│        ═══════════════                                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Currently viewing: Service Mesh Tab                       │
│                                                            │
│  ┌─ System Health ─────────────────────────────────────┐  │
│  │ Status: 🟢 Healthy  │  Operations/min: 234          │  │
│  │ Active: 18 ops      │  P95 Latency: 1.2s            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Service Flow ──────────────────────────────────────┐  │
│  │                                                      │  │
│  │     [Frontend]  ↓ 20 ops/min                        │  │
│  │         │                                            │  │
│  │         ▼                                            │  │
│  │     [API GW]    → 20 forwarded  ⏱ P95: 50ms        │  │
│  │         │                                            │  │
│  │     ┌───┴────┐                                       │  │
│  │     │        │                                       │  │
│  │     ▼        ▼                                       │  │
│  │  [Orchestr] [Worker x2]  ⚡ 18 active ✗ 2 failed   │  │
│  │     │        │                                       │  │
│  │     │        └──→ [RAS Adapter]  ⏱ Avg: 1.2s       │  │
│  │     │             └──→ [RAS]                         │  │
│  │     │                                                │  │
│  │     └──→ [PostgreSQL] [Redis]                       │  │
│  │                                                      │  │
│  │  Legend: ⚡Active ✓Success ✗Failed ⏱Latency         │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Recent Operations ─────────────────────────────────┐  │
│  │ ID         │ Type            │ Status  │ Duration   │  │
│  │────────────┼─────────────────┼─────────┼───────────│  │
│  │ op-67890   │ Install Ext     │ ⚡ Run  │ 45.2s     │ ← Click
│  │ op-67889   │ Config Update   │ ✓ Done  │ 2.3s      │  │
│  │ op-67888   │ Backup DB       │ ✗ Fail  │ 120s      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  Click operation → Opens in "My Workflows" tab            │
│                    with Monitor Mode active                │
└────────────────────────────────────────────────────────────┘
```

### Tab 1: Service Mesh Monitor

**Purpose:** Aggregate view всей системы

**Features:**
- ✅ Real-time service flow visualization
- ✅ Operation counts per service (ops/min)
- ✅ Latency metrics (P50, P95, P99)
- ✅ Error rates and failed operations
- ✅ Active operations counter
- ✅ Recent operations table
- ✅ Click service → filter operations
- ✅ Click operation → open in Workflows tab

**Data Source:**
- Prometheus metrics (via Metrics Aggregator)
- WebSocket updates every 2 seconds

**Components:**
```typescript
<ServiceMeshTab>
  <SystemHealthCard />
  <ServiceFlowDiagram>
    <ServiceNode service="frontend" metrics={...} />
    <ServiceNode service="api-gateway" metrics={...} />
    <ServiceNode service="worker" metrics={...} onClick={filterByService} />
  </ServiceFlowDiagram>
  <RecentOperationsTable onRowClick={openInWorkflowsTab} />
</ServiceMeshTab>
```

### Tab 2: My Workflows

**Purpose:** Workflow-specific design and monitoring

**Features:**
- ✅ List of user's workflows
- ✅ Create new workflow (Design Mode)
- ✅ Execute workflow
- ✅ Monitor active executions (Monitor Mode)
- ✅ View execution history
- ✅ Click node → Jaeger traces

**Views:**

#### A. Workflow List View
```
┌────────────────────────────────────────────────────────────┐
│  My Workflows Tab                      [+ Create Workflow] │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─ My Workflows ──────────────────────────────────────┐  │
│  │ Name              │ Type    │ Last Run │ Actions    │  │
│  │───────────────────┼─────────┼──────────┼───────────│  │
│  │ Install Extension │ Admin   │ 5 min ago│ [Run][Edit]│  │
│  │ Upload Price List │ Data    │ 1 hr ago │ [Run][Edit]│  │
│  │ Monthly Close     │ Complex │ 2 days   │ [Run][Edit]│  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ Active Executions ─────────────────────────────────┐  │
│  │ Workflow          │ Status  │ Progress │ Actions    │  │
│  │───────────────────┼─────────┼──────────┼───────────│  │
│  │ Install Extension │ ⚡ Run  │ 60% ████▒│ [Monitor]  │ ← Click
│  │ Upload Price List │ ⚡ Run  │ 20% ██▒▒▒│ [Monitor]  │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

#### B. Design Mode (when creating/editing)
```
┌────────────────────────────────────────────────────────────┐
│  Edit Workflow: Install Extension      [Save] [Validate]  │
├────────────────────────────────────────────────────────────┤
│  [Node Palette]        [Canvas - React Flow]              │
│                                                            │
│  Drag nodes from palette → Canvas → Connect → Save        │
└────────────────────────────────────────────────────────────┘
```

#### C. Monitor Mode (when watching execution)
```
┌────────────────────────────────────────────────────────────┐
│  Monitoring: Install Extension   🟢 Running  [Pause][Stop] │
├────────────────────────────────────────────────────────────┤
│  Progress: 60% ████████▒▒▒▒  Node 3 of 5                  │
│                                                            │
│  [Canvas - React Flow with Live Status]                   │
│  ┌──────────┐ ✓ 0.8s                                      │
│  │Lock Jobs │ ← Click to view traces                      │
│  └────┬─────┘                                              │
│       │                                                    │
│  ┌────▼─────────┐ ✓ 2.3s                                  │
│  │Terminate Ses │                                          │
│  └────┬─────────┘                                          │
│       │                                                    │
│  ┌────▼─────────┐ ⚡ 45.2s (running...)                    │
│  │Install Ext   │ ← Animated spinner                      │
│  └──────────────┘                                          │
└────────────────────────────────────────────────────────────┘
```

### Navigation Flow

**Service Mesh → Workflows:**
```
1. User in Service Mesh tab
2. Sees "Install Extension" operation failed
3. Clicks on operation row
4. Automatically switches to "My Workflows" tab
5. Opens Monitor Mode for that execution
6. Can see detailed node status + traces
```

**Workflows → Service Mesh:**
```
1. User in My Workflows tab
2. Executing workflow
3. Wants to see system-wide impact
4. Clicks "Service Mesh" tab
5. Sees current system load
6. Can click back to continue monitoring workflow
```

### State Management

```typescript
// frontend/src/stores/dashboardStore.ts

interface DashboardState {
  activeTab: 'service-mesh' | 'my-workflows';

  // Service Mesh state
  serviceMeshMetrics: ServiceMetrics[];
  recentOperations: Operation[];

  // Workflows state
  myWorkflows: WorkflowTemplate[];
  activeExecutions: WorkflowExecution[];
  selectedWorkflow: WorkflowTemplate | null;
  selectedExecution: WorkflowExecution | null;

  // Actions
  switchTab: (tab: 'service-mesh' | 'my-workflows') => void;
  openExecutionFromServiceMesh: (operationId: string) => void;
}

export const useDashboardStore = create<DashboardState>((set) => ({
  activeTab: 'service-mesh',

  openExecutionFromServiceMesh: (operationId: string) => {
    // 1. Find execution by operation_id
    const execution = findExecutionByOperationId(operationId);

    // 2. Switch to workflows tab
    set({
      activeTab: 'my-workflows',
      selectedExecution: execution
    });

    // 3. Open Monitor Mode
    // (handled by MyWorkflowsTab component)
  }
}));
```

### Benefits of Two-Tab Approach

| Benefit | Description |
|---------|-------------|
| **Clear Separation** | System-wide vs workflow-specific concerns |
| **Easy Navigation** | Click operation → auto-switch to workflow tab |
| **Context Preservation** | Each tab maintains its own state |
| **Role-Based** | Admins use Service Mesh, Users use Workflows |
| **Unified Platform** | Both tabs in one application |

---

## Architecture Overview

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      Frontend Layer                        │
│                   (React + TypeScript)                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────────────┐   ┌─────────────────────────┐   │
│  │  Workflow Builder    │   │  Workflow Monitor       │   │
│  │  (Design Mode)       │   │  (Runtime Mode)         │   │
│  │                      │   │                         │   │
│  │  • React Flow        │   │  • React Flow           │   │
│  │  • Node Palette      │   │  • Live Status Overlay  │   │
│  │  • Property Editor   │   │  • WebSocket Consumer   │   │
│  │  • Validation        │   │  • Trace Viewer Panel   │   │
│  └──────────┬───────────┘   └──────────┬──────────────┘   │
│             │                          │                   │
└─────────────┼──────────────────────────┼───────────────────┘
              │                          │
              │ REST API                 │ WebSocket
              │                          │
┌─────────────▼──────────────────────────▼───────────────────┐
│                   Backend Services Layer                   │
│                 (Django + Go Services)                     │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌──────────────────────────────────────────────────┐     │
│  │           Django Orchestrator                    │     │
│  │                                                  │     │
│  │  ┌────────────────────────────────────────┐     │     │
│  │  │  WorkflowEngine (Track 1.5)            │     │     │
│  │  │  • DAGValidator                        │     │     │
│  │  │  • DAGExecutor                         │     │     │
│  │  │  • NodeHandlers                        │     │     │
│  │  │  • ContextManager                      │     │     │
│  │  └────────────┬───────────────────────────┘     │     │
│  │               │                                 │     │
│  │  ┌────────────▼───────────────────────────┐     │     │
│  │  │  OpenTelemetry Instrumentation         │     │     │
│  │  │  • Tracer initialization               │     │     │
│  │  │  • Span creation (parent + children)   │     │     │
│  │  │  • Attribute injection                 │     │     │
│  │  └────────────┬───────────────────────────┘     │     │
│  │               │                                 │     │
│  │  ┌────────────▼───────────────────────────┐     │     │
│  │  │  Django Channels (WebSocket)           │     │     │
│  │  │  • WorkflowExecutionConsumer           │     │     │
│  │  │  • Real-time status broadcasts         │     │     │
│  │  └────────────────────────────────────────┘     │     │
│  │                                                  │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
│  ┌──────────────────────────────────────────────────┐     │
│  │           Go Worker Services                     │     │
│  │  • batch-service (extension install)             │     │
│  │  • worker (parallel processing)                  │     │
│  │  • ras-adapter (RAS operations)                  │     │
│  │  • OpenTelemetry instrumentation                │     │
│  └──────────────────────────────────────────────────┘     │
│                                                            │
└────────────────────────────┬───────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────┐
│              Observability Infrastructure                  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────────┐         ┌──────────────────┐         │
│  │     Jaeger      │         │   PostgreSQL     │         │
│  │  (Trace Store)  │         │  (Workflow DB)   │         │
│  │   port 16686    │         │   port 5432      │         │
│  └─────────────────┘         └──────────────────┘         │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Data Flow

#### Design Time (Create Workflow)

```
1. User drags nodes in React Flow
   ↓
2. Frontend: Build DAG structure (nodes + edges)
   ↓
3. POST /api/v1/workflows/templates
   ↓
4. WorkflowEngine: Validate DAG (DAGValidator)
   ↓
5. Save WorkflowTemplate to PostgreSQL
   ↓
6. Return workflow_id to frontend
```

#### Run Time (Execute Workflow)

```
1. User clicks "▶️ Run" in UI
   ↓
2. POST /api/v1/workflows/executions
   ↓
3. WorkflowEngine.execute_workflow()
   ├─ Create WorkflowExecution record
   ├─ Start OpenTelemetry parent span
   ├─ Execute DAG nodes in topological order
   │  ├─ Each node → child span
   │  ├─ Execute OperationTemplate (Celery → Worker)
   │  └─ Broadcast status via WebSocket
   └─ End parent span
   ↓
4. Jaeger: Store complete trace
   ↓
5. Frontend: Display live updates
   ↓
6. User clicks node → Query Jaeger for detailed trace
```

---

## Unified Workflow Concept

### Workflow = Universal Abstraction

**Definition:** Workflow = DAG of operations with defined inputs/outputs

**Components:**
- **Nodes:** Individual operations (atomic or composite)
- **Edges:** Dependencies between nodes
- **Context:** Shared data between nodes
- **Execution:** Runtime instance of workflow

### Workflow Types

#### 1. Administrative Workflows

**Characteristics:**
- System-level operations
- Require elevated permissions
- Multi-step, error-prone
- Need careful orchestration

**Examples:**

```yaml
Extension Install Workflow:
  - Lock scheduled jobs
  - Terminate sessions
  - Install extension file
  - Unlock scheduled jobs
  - Verify installation

Database Backup Workflow:
  - Block new sessions
  - Wait for active transactions
  - Create backup
  - Verify backup integrity
  - Unblock sessions

Configuration Update Workflow:
  - Validate config file
  - Lock database
  - Apply changes
  - Restart services
  - Verify health
```

#### 2. Data Workflows

**Characteristics:**
- Business data operations
- High volume, parallel processing
- User-initiated
- Need progress tracking

**Examples:**

```yaml
Price List Upload Workflow:
  - Validate Excel format
  - Parse rows (loop)
  - Create/Update items (parallel)
  - Generate report

Counterparty Import Workflow:
  - Load CSV file
  - Validate INN/KPP
  - Check duplicates (condition)
  - Create records (parallel)
  - Send notifications

Month Close Workflow:
  - Verify all docs posted
  - Calculate taxes
  - Generate reports
  - Create closing entries
  - Notify accountants
```

#### 3. Hybrid Workflows

**Characteristics:**
- Mix of system and data operations
- Complex branching logic
- Long-running (hours/days)

**Examples:**

```yaml
Year-End Close Workflow:
  - Lock all databases (admin)
  - Generate annual reports (data, parallel)
  - Archive old data (data)
  - Create tax declarations (data)
  - Backup databases (admin, parallel)
  - Unlock databases (admin)
```

### Node Types (from Track 1.5)

| Type | Description | Use Case |
|------|-------------|----------|
| **operation** | Execute OperationTemplate | Single atomic operation |
| **condition** | Evaluate Jinja2 expression | If/else branching |
| **parallel** | Execute multiple nodes concurrently | Parallel processing |
| **loop** | Repeat node N times | Batch operations |
| **subworkflow** | Execute another workflow | Composition, reuse |

### Execution Modes

#### Synchronous (Default)

```python
execution = workflow_engine.execute_workflow(
    workflow_template=template,
    input_context={"database_id": "db-123"}
)

# Blocks until completion
print(execution.status)  # "completed" or "failed"
```

**Use case:** Short workflows (< 5 min), immediate result needed

#### Asynchronous (Celery)

```python
from apps.templates.tasks import execute_workflow_task

# Enqueue to Celery
task = execute_workflow_task.delay(
    workflow_id=template.id,
    input_context={"database_id": "db-123"}
)

# Return immediately
return {"task_id": task.id, "execution_id": execution.id}
```

**Use case:** Long workflows (> 5 min), background processing

#### Scheduled (Celery Beat)

```python
# Register periodic workflow
from celery.schedules import crontab

app.conf.beat_schedule = {
    'nightly-backup': {
        'task': 'apps.templates.tasks.execute_workflow_task',
        'schedule': crontab(hour=2, minute=0),
        'args': ('workflow-backup-all', {})
    }
}
```

**Use case:** Recurring workflows (backups, reports, maintenance)

---

## Component Design

### Frontend Components

#### 1. WorkflowCanvas (Master Component)

```typescript
// frontend/src/components/workflow/WorkflowCanvas.tsx

interface WorkflowCanvasProps {
  mode: 'design' | 'monitor';
  workflow?: WorkflowTemplate;
  execution?: WorkflowExecution;
}

export function WorkflowCanvas({ mode, workflow, execution }: WorkflowCanvasProps) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // Load workflow structure
  useEffect(() => {
    if (workflow) {
      const reactFlowNodes = convertToReactFlowNodes(workflow.dag_structure.nodes);
      const reactFlowEdges = convertToReactFlowEdges(workflow.dag_structure.edges);
      setNodes(reactFlowNodes);
      setEdges(reactFlowEdges);
    }
  }, [workflow]);

  // Listen for live updates (monitor mode only)
  const executionStatus = useWorkflowExecution(execution?.id);

  // Update node statuses in real-time
  useEffect(() => {
    if (mode === 'monitor' && executionStatus) {
      setNodes(prevNodes =>
        prevNodes.map(node => ({
          ...node,
          data: {
            ...node.data,
            status: getNodeStatus(node.id, executionStatus),
            duration: getNodeDuration(node.id, executionStatus),
          }
        }))
      );
    }
  }, [executionStatus, mode]);

  return (
    <div className="workflow-canvas">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={mode === 'design' ? onNodesChange : undefined}
        onEdgesChange={mode === 'design' ? onEdgesChange : undefined}
        fitView
      >
        {mode === 'design' && <DesignModeControls />}
        {mode === 'monitor' && <MonitorModeOverlay execution={execution} />}
      </ReactFlow>
    </div>
  );
}
```

#### 2. OperationNodeWithStatus

```typescript
// frontend/src/components/workflow/nodes/OperationNodeWithStatus.tsx

interface OperationNodeData {
  label: string;
  template_id: string;
  status?: 'pending' | 'running' | 'completed' | 'failed';
  duration?: number;
  error?: string;
  result?: any;
}

export function OperationNodeWithStatus({ data, selected }: NodeProps<OperationNodeData>) {
  const [showTraces, setShowTraces] = useState(false);

  const statusIcon = {
    pending: '○',
    running: <Spinner />,
    completed: '✓',
    failed: '✗'
  }[data.status || 'pending'];

  const statusColor = {
    pending: 'gray',
    running: 'blue',
    completed: 'green',
    failed: 'red'
  }[data.status || 'pending'];

  return (
    <div className={`workflow-node status-${data.status}`}>
      {/* Status Badge */}
      <div className={`status-badge bg-${statusColor}`}>
        {statusIcon}
      </div>

      {/* Node Content */}
      <Handle type="target" position={Position.Top} />

      <div className="node-body">
        <div className="node-header">
          <strong>{data.label}</strong>
        </div>

        {data.duration && (
          <div className="node-duration">
            ⏱️ {data.duration.toFixed(2)}s
          </div>
        )}

        {data.error && (
          <Alert type="error" size="sm">
            {data.error}
          </Alert>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} />

      {/* Actions (only when selected) */}
      {selected && data.status && (
        <div className="node-actions">
          <Button
            size="xs"
            onClick={() => setShowTraces(true)}
          >
            View Traces
          </Button>
        </div>
      )}

      {/* Trace Viewer Modal */}
      {showTraces && (
        <TraceViewerModal
          nodeId={data.id}
          onClose={() => setShowTraces(false)}
        />
      )}
    </div>
  );
}
```

#### 3. useWorkflowExecution Hook

```typescript
// frontend/src/hooks/useWorkflowExecution.ts

interface WorkflowExecutionStatus {
  status: 'pending' | 'running' | 'completed' | 'failed';
  currentNodeId: string | null;
  completedNodes: string[];
  failedNodes: string[];
  progressPercent: number;
  nodeStatuses: Record<string, NodeStatus>;
}

interface NodeStatus {
  status: 'pending' | 'running' | 'completed' | 'failed';
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  error?: string;
  result?: any;
}

export function useWorkflowExecution(executionId: string | undefined): WorkflowExecutionStatus | null {
  const [status, setStatus] = useState<WorkflowExecutionStatus | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!executionId) return;

    // Connect to WebSocket
    const ws = new WebSocket(
      `ws://${window.location.host}/ws/workflow/${executionId}/`
    );

    ws.onopen = () => {
      console.log(`Connected to workflow ${executionId}`);
      // Request initial status
      ws.send(JSON.stringify({ action: 'get_status' }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'status_update') {
        setStatus({
          status: data.status,
          currentNodeId: data.current_node_id,
          completedNodes: data.completed_nodes,
          failedNodes: data.failed_nodes,
          progressPercent: data.progress_percent,
          nodeStatuses: data.node_statuses || {},
        });
      }

      if (data.type === 'node_update') {
        setStatus(prev => {
          if (!prev) return null;

          return {
            ...prev,
            nodeStatuses: {
              ...prev.nodeStatuses,
              [data.node_id]: {
                status: data.status,
                startedAt: data.started_at,
                completedAt: data.completed_at,
                duration: data.duration,
                error: data.error,
                result: data.result,
              }
            }
          };
        });
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('WebSocket closed');
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [executionId]);

  return status;
}
```

#### 4. TraceViewerModal

```typescript
// frontend/src/components/workflow/TraceViewerModal.tsx

interface TraceViewerModalProps {
  nodeId: string;
  executionId: string;
  onClose: () => void;
}

export function TraceViewerModal({ nodeId, executionId, onClose }: TraceViewerModalProps) {
  const [trace, setTrace] = useState<JaegerTrace | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTrace();
  }, [nodeId, executionId]);

  async function loadTrace() {
    try {
      // Query Jaeger for traces with workflow.execution_id tag
      const trace = await jaegerApi.getTraceByTags({
        'workflow.execution_id': executionId,
        'node.id': nodeId,
      });

      setTrace(trace);
    } catch (error) {
      console.error('Failed to load trace:', error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal open onClose={onClose} size="xl">
      <ModalHeader>
        Trace: Node "{nodeId}"
      </ModalHeader>

      <ModalBody>
        {loading ? (
          <Spinner />
        ) : trace ? (
          <div className="trace-viewer">
            {/* Timeline */}
            <TraceTimeline
              trace={trace}
              onSelectSpan={setSelectedSpan}
            />

            {/* Service Flow */}
            <ServiceFlowDiagram trace={trace} />

            {/* Span Details */}
            {selectedSpan && (
              <SpanDetailsPanel span={selectedSpan} />
            )}
          </div>
        ) : (
          <Alert type="warning">
            No traces found for this node
          </Alert>
        )}
      </ModalBody>

      <ModalFooter>
        <Button onClick={onClose}>Close</Button>
      </ModalFooter>
    </Modal>
  );
}
```

### Backend Components

#### 1. WorkflowEngine with OpenTelemetry

```python
# orchestrator/apps/templates/workflow/engine.py

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("workflow-engine")

class WorkflowEngine:
    def __init__(self):
        self.validator = DAGValidator()
        self.executor = DAGExecutor()
        self.context_manager = ContextManager()

    def execute_workflow(
        self,
        workflow_template: WorkflowTemplate,
        input_context: dict,
        execution_id: str = None
    ) -> WorkflowExecution:
        """
        Execute workflow with OpenTelemetry tracing.

        Creates parent span for entire workflow execution.
        Each node execution creates child span.
        """

        # Create or resume execution
        if execution_id:
            execution = WorkflowExecution.objects.get(id=execution_id)
            execution.status = 'running'
        else:
            execution = WorkflowExecution.objects.create(
                workflow_template=workflow_template,
                input_context=input_context,
                status='running'
            )

        # Validate DAG
        validation_result = self.validator.validate(workflow_template.dag_structure)
        if not validation_result.is_valid:
            execution.status = 'failed'
            execution.error_message = '; '.join(validation_result.errors)
            execution.save()
            return execution

        # Start parent span
        with tracer.start_as_current_span(
            f"workflow.execute.{workflow_template.name}",
            attributes={
                "workflow.id": workflow_template.id,
                "workflow.name": workflow_template.name,
                "workflow.execution_id": execution.id,
                "workflow.type": workflow_template.workflow_type,
            }
        ) as parent_span:

            try:
                # Initialize context
                context = self.context_manager.initialize_context(input_context)
                context['_execution_id'] = execution.id

                # Execute DAG
                result = self.executor.execute_dag(
                    workflow_template.dag_structure,
                    context,
                    execution,
                    parent_span  # Pass span for child spans
                )

                # Mark as completed
                execution.status = 'completed'
                execution.final_result = result
                execution.completed_at = timezone.now()

                parent_span.set_status(StatusCode.OK)
                parent_span.set_attribute("workflow.result", "success")

            except Exception as e:
                # Mark as failed
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.error_node_id = context.get('_current_node_id')

                parent_span.set_status(StatusCode.ERROR, str(e))
                parent_span.record_exception(e)

            finally:
                execution.save()

                # Broadcast final status via WebSocket
                self._broadcast_status_update(execution)

        return execution

    def _broadcast_status_update(self, execution: WorkflowExecution):
        """Broadcast workflow status to WebSocket consumers."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"workflow_{execution.id}",
            {
                "type": "workflow_update",
                "status": execution.status,
                "current_node_id": execution.current_node_id,
                "completed_nodes": execution.completed_nodes,
                "failed_nodes": execution.failed_nodes,
                "progress_percent": execution.progress_percent,
            }
        )
```

#### 2. DAGExecutor with Child Spans

```python
# orchestrator/apps/templates/workflow/executor.py

from opentelemetry import trace

tracer = trace.get_tracer("workflow-engine")

class DAGExecutor:
    def __init__(self):
        self.handler_factory = NodeHandlerFactory()

    def execute_dag(
        self,
        dag_structure: dict,
        context: dict,
        execution: WorkflowExecution,
        parent_span: Span
    ) -> dict:
        """
        Execute DAG nodes in topological order.

        Each node execution creates child span under parent_span.
        """

        nodes = dag_structure['nodes']
        edges = dag_structure['edges']

        # Get topological order
        from .validator import DAGValidator
        validator = DAGValidator()
        node_order = validator._topological_sort(nodes, edges)

        # Execute nodes in order
        for node_id in node_order:
            node = next(n for n in nodes if n['id'] == node_id)

            # Create child span for this node
            with tracer.start_as_current_span(
                f"node.{node['type']}.{node['name']}",
                attributes={
                    "node.id": node['id'],
                    "node.type": node['type'],
                    "node.name": node['name'],
                    "workflow.execution_id": execution.id,
                }
            ) as node_span:

                # Update execution status
                execution.current_node_id = node_id
                execution.save()

                # Broadcast node start
                self._broadcast_node_update(execution, node_id, 'running')

                try:
                    # Get handler for node type
                    handler = self.handler_factory.get_handler(node['type'])

                    # Execute node
                    result = handler.execute(node, context, execution, node_span)

                    # Store result in context (for data passing)
                    context[node_id] = result
                    context['_steps'][node_id] = result

                    # Record in WorkflowStepResult
                    WorkflowStepResult.objects.create(
                        workflow_execution=execution,
                        node_id=node_id,
                        node_name=node['name'],
                        node_type=node['type'],
                        status='completed',
                        output_data=result,
                        completed_at=timezone.now()
                    )

                    # Update execution
                    execution.completed_nodes.append(node_id)
                    execution.save()

                    # Broadcast node completion
                    self._broadcast_node_update(execution, node_id, 'completed', result=result)

                    node_span.set_status(StatusCode.OK)
                    node_span.set_attribute("node.result", str(result))

                except Exception as e:
                    # Handle node failure
                    execution.failed_nodes.append(node_id)
                    execution.save()

                    # Broadcast node failure
                    self._broadcast_node_update(execution, node_id, 'failed', error=str(e))

                    node_span.set_status(StatusCode.ERROR, str(e))
                    node_span.record_exception(e)

                    # Re-raise to stop workflow
                    raise

        # Return final context
        return context['_steps']

    def _broadcast_node_update(
        self,
        execution: WorkflowExecution,
        node_id: str,
        status: str,
        result: dict = None,
        error: str = None
    ):
        """Broadcast node status update via WebSocket."""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            f"workflow_{execution.id}",
            {
                "type": "node_update",
                "node_id": node_id,
                "status": status,
                "result": result,
                "error": error,
            }
        )
```

#### 3. Django Channels Consumer

```python
# orchestrator/apps/templates/consumers.py

from channels.generic.websocket import AsyncWebsocketConsumer
import json

class WorkflowExecutionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.execution_id = self.scope['url_route']['kwargs']['execution_id']
        self.room_group_name = f'workflow_{self.execution_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send initial status
        await self.send_current_status()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)

        if data.get('action') == 'get_status':
            await self.send_current_status()

    async def send_current_status(self):
        """Send current workflow execution status."""
        from channels.db import database_sync_to_async

        execution = await database_sync_to_async(
            WorkflowExecution.objects.get
        )(id=self.execution_id)

        await self.send(text_data=json.dumps({
            'type': 'status_update',
            'status': execution.status,
            'current_node_id': execution.current_node_id,
            'completed_nodes': execution.completed_nodes,
            'failed_nodes': execution.failed_nodes,
            'progress_percent': execution.progress_percent,
        }))

    async def workflow_update(self, event):
        """Called when workflow status changes."""
        await self.send(text_data=json.dumps(event))

    async def node_update(self, event):
        """Called when node status changes."""
        await self.send(text_data=json.dumps(event))
```

---

## Data Models

### Enhanced WorkflowExecution

```python
# orchestrator/apps/templates/models.py

class WorkflowExecution(models.Model):
    """
    Enhanced with real-time tracking fields.
    """

    # ... existing fields ...

    # Real-time tracking
    node_statuses = models.JSONField(
        default=dict,
        help_text="Real-time status of each node: {node_id: {status, started_at, completed_at, duration}}"
    )

    # OpenTelemetry integration
    trace_id = models.CharField(
        max_length=32,
        blank=True,
        help_text="OpenTelemetry trace ID for this execution"
    )

    @property
    def progress_percent(self):
        """Calculate execution progress (0-100%)."""
        total_nodes = len(self.workflow_template.dag_structure.get('nodes', []))
        if total_nodes == 0:
            return 0
        completed = len(self.completed_nodes)
        return int((completed / total_nodes) * 100)

    def get_node_status(self, node_id: str) -> dict:
        """Get status of specific node."""
        return self.node_statuses.get(node_id, {
            'status': 'pending',
            'started_at': None,
            'completed_at': None,
            'duration': None,
        })
```

### WorkflowStepResult (from Track 1.5)

```python
class WorkflowStepResult(models.Model):
    """
    Detailed result for each workflow step.

    Used for:
    - Audit trail
    - Data passing between steps
    - Debugging
    - Real-time UI updates
    """

    # Identity
    id = models.CharField(max_length=64, primary_key=True, default=generate_id)

    # Relations
    workflow_execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name='step_results_detailed'
    )

    # Step Info
    node_id = models.CharField(max_length=64, db_index=True)
    node_name = models.CharField(max_length=255)
    node_type = models.CharField(max_length=50)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),
        ],
        default='pending',
        db_index=True
    )

    # Execution Data
    input_data = models.JSONField(default=dict)
    output_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # OpenTelemetry
    span_id = models.CharField(max_length=16, blank=True)
    trace_id = models.CharField(max_length=32, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workflow_step_results'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['workflow_execution', 'node_id']),
            models.Index(fields=['status', 'created_at']),
        ]
        unique_together = [['workflow_execution', 'node_id']]
```

---

## API Specification

### REST API Endpoints

#### Workflow Templates

```
POST   /api/v1/workflows/templates/
GET    /api/v1/workflows/templates/
GET    /api/v1/workflows/templates/{id}/
PUT    /api/v1/workflows/templates/{id}/
DELETE /api/v1/workflows/templates/{id}/
POST   /api/v1/workflows/templates/{id}/validate/
```

#### Workflow Executions

```
POST   /api/v1/workflows/executions/
       Body: {
         "workflow_id": "uuid",
         "input_context": {...},
         "mode": "sync" | "async"  // NEW: execution mode
       }
       Response: {
         "execution_id": "uuid",
         "status": "pending" | "running",
         "websocket_url": "ws://host/ws/workflow/{execution_id}/"  // NEW
       }

GET    /api/v1/workflows/executions/
GET    /api/v1/workflows/executions/{id}/
GET    /api/v1/workflows/executions/{id}/steps/
POST   /api/v1/workflows/executions/{id}/cancel/
```

#### NEW: Trace Integration

```
GET    /api/v1/workflows/executions/{id}/trace/
       Response: {
         "trace_id": "abc123",
         "jaeger_url": "http://localhost:16686/trace/abc123"
       }

GET    /api/v1/workflows/executions/{id}/nodes/{node_id}/trace/
       Response: {
         "span_id": "def456",
         "trace_id": "abc123",
         "jaeger_url": "http://localhost:16686/trace/abc123?uiFind=def456"
       }
```

### WebSocket API

#### Connection

```
ws://localhost:8000/ws/workflow/{execution_id}/
```

#### Client → Server Messages

```json
{
  "action": "get_status"
}
```

#### Server → Client Messages

**Status Update:**
```json
{
  "type": "status_update",
  "status": "running",
  "current_node_id": "install",
  "completed_nodes": ["lock", "terminate"],
  "failed_nodes": [],
  "progress_percent": 50
}
```

**Node Update:**
```json
{
  "type": "node_update",
  "node_id": "install",
  "status": "completed",
  "started_at": "2025-01-15T10:30:00Z",
  "completed_at": "2025-01-15T10:30:45Z",
  "duration": 45.2,
  "result": {...}
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Workflow execution failed",
  "node_id": "install",
  "error": "Extension file not found"
}
```

---

## UI/UX Design

### Page: Workflow Builder (Design Mode)

```
┌─────────────────────────────────────────────────────────────┐
│  Create Workflow: Extension Install          [Save] [Run ▶] │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│  Node Palette        │  Canvas                              │
│  ┌────────────┐      │                                      │
│  │ 🔧 Operation│      │     ┌──────────┐                    │
│  │ Drag me!   │      │     │  Start   │                    │
│  └────────────┘      │     └─────┬────┘                    │
│                      │           │                          │
│  ┌────────────┐      │     ┌─────▼────┐                    │
│  │ ⁉️ Condition│      │     │ Lock Jobs│                    │
│  │ Drag me!   │      │     └─────┬────┘                    │
│  └────────────┘      │           │                          │
│                      │     ┌─────▼────────┐                │
│  ┌────────────┐      │     │ Terminate    │                │
│  │ ⇉ Parallel │      │     │ Sessions     │                │
│  │ Drag me!   │      │     └─────┬────────┘                │
│  └────────────┘      │           │                          │
│                      │     ┌─────▼────────┐                │
│  ┌────────────┐      │     │ Install Ext  │                │
│  │ 🔁 Loop    │      │     └─────┬────────┘                │
│  │ Drag me!   │      │           │                          │
│  └────────────┘      │     ┌─────▼────────┐                │
│                      │     │ Unlock Jobs  │                │
│                      │     └──────────────┘                │
│                      │                                      │
├──────────────────────┴──────────────────────────────────────┤
│  Properties Panel                                           │
│  Selected: "Lock Jobs"                                      │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Template: [Lock Scheduled Jobs         ▼]         │    │
│  │ Timeout:  [30] seconds                             │    │
│  │ Retries:  [3]                                      │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Page: Workflow Monitor (Runtime Mode)

```
┌─────────────────────────────────────────────────────────────┐
│  Extension Install Workflow                    🟢 Running   │
│  Execution: exec-12345                  Progress: 50% █████▒│
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Canvas (Read-Only + Live Status)                          │
│                                                             │
│     ┌──────────┐                                           │
│     │  Start   │ ✓ 0.01s                                   │
│     └─────┬────┘                                           │
│           │                                                 │
│     ┌─────▼────┐                                           │
│     │ Lock Jobs│ ✓ 0.8s                                    │
│     └─────┬────┘     ← Click to view traces               │
│           │                                                 │
│     ┌─────▼────────┐                                       │
│     │ Terminate    │ ✓ 2.3s                                │
│     │ Sessions     │                                        │
│     └─────┬────────┘                                       │
│           │                                                 │
│     ┌─────▼────────┐                                       │
│     │ Install Ext  │ ⚡ Running... 45.2s                   │
│     └─────┬────────┘     ← Animated spinner               │
│           │                                                 │
│     ┌─────▼────────┐                                       │
│     │ Unlock Jobs  │ ○ Pending                             │
│     └──────────────┘                                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  Timeline                                                   │
│  ├─ Lock Jobs (0.8s)    ✓                                  │
│  ├─ Terminate (2.3s)    ✓                                  │
│  ├─ Install Ext (45.2s) ⚡ In progress...                  │
│  └─ Unlock Jobs         ○ Not started                      │
│                                                             │
│  [Pause] [Cancel] [View Full Trace]                        │
└─────────────────────────────────────────────────────────────┘
```

### Modal: Trace Viewer

```
┌─────────────────────────────────────────────────────────────┐
│  Trace: Install Extension Node                      [Close] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Tabs: [Timeline] [Service Flow] [Logs]                    │
│                                                             │
│  ┌─ Timeline ─────────────────────────────────────────┐    │
│  │                                                     │    │
│  │  Worker: Install Extension (45.2s)                 │    │
│  │  ├─ batch-service: Validate file (2.1s)            │    │
│  │  ├─ batch-service: Execute 1cv8.exe (40.5s) ← SEL  │    │
│  │  └─ batch-service: Check exit code (0.5s)          │    │
│  │                                                     │    │
│  └─────────────────────────────────────────────────────    │
│                                                             │
│  ┌─ Selected Span ────────────────────────────────────┐    │
│  │ Span: Execute 1cv8.exe                             │    │
│  │ Duration: 40.5s                                     │    │
│  │ Status: ✓ Success                                   │    │
│  │                                                     │    │
│  │ Attributes:                                         │    │
│  │   operation_id: op-67890                            │    │
│  │   database_id: db-12345                             │    │
│  │   extension_path: /path/to/ext.cfe                  │    │
│  │   exit_code: 0                                      │    │
│  │                                                     │    │
│  │ Command:                                            │    │
│  │   1cv8.exe /S localhost\base /LoadCfg ext.cfe       │    │
│  └─────────────────────────────────────────────────────    │
│                                                             │
│  [Download Trace JSON] [Open in Jaeger]                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration Points

### 1. WorkflowEngine → OpenTelemetry

**When:** Every workflow execution
**How:** Create parent span, pass to DAGExecutor
**Result:** Complete trace in Jaeger

```python
# Parent span created in WorkflowEngine.execute_workflow()
with tracer.start_as_current_span("workflow.execute") as parent_span:
    parent_span.set_attribute("workflow.execution_id", execution.id)

    # Child spans created in DAGExecutor.execute_dag()
    for node in nodes:
        with tracer.start_as_current_span(f"node.{node.id}") as node_span:
            result = handler.execute(node, context, execution, node_span)
```

### 2. DAGExecutor → Django Channels

**When:** Node status changes (start, complete, fail)
**How:** Broadcast via channel layer
**Result:** Real-time UI updates

```python
# DAGExecutor broadcasts node update
channel_layer.group_send(
    f"workflow_{execution.id}",
    {
        "type": "node_update",
        "node_id": node_id,
        "status": "completed",
        "result": result,
    }
)

# Frontend receives via WebSocket
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'node_update') {
        updateNodeStatus(data.node_id, data.status);
    }
}
```

### 3. Frontend → Jaeger API

**When:** User clicks node to view traces
**How:** Query Jaeger by workflow.execution_id + node.id
**Result:** Display detailed trace in modal

```typescript
// Query Jaeger API
const trace = await jaegerApi.getTraceByTags({
  'workflow.execution_id': executionId,
  'node.id': nodeId,
});

// Display in TraceViewerModal
<TraceViewerModal trace={trace} />
```

### 4. Worker → Workflow (NEW)

**Current:** Worker executes operations independently
**After:** Worker operations = workflow nodes

```python
# Before (Worker executes implicit workflow)
def process_extension_install(msg):
    lock_jobs()
    terminate_sessions()
    install_extension()
    unlock_jobs()

# After (Worker executes explicit workflow)
workflow = WorkflowTemplate.objects.get(name="Extension Install")
execution = workflow_engine.execute_workflow(
    workflow_template=workflow,
    input_context={
        "database_id": msg.database_id,
        "extension_path": msg.extension_path
    }
)
```

---

## Migration Strategy

### Phase 1: Foundation (Already Complete ✅)

**Status:** DONE (Week 1-4)

- ✅ RAS Adapter deployed
- ✅ Worker State Machine works
- ✅ Correlation ID exists
- ✅ Prometheus + Grafana running

### Phase 2: Workflow Engine Backend (Week 5-11)

**Goal:** Implement Track 1.5 backend WITHOUT UI

**Tasks:**
- Week 5-6: Models + Migrations + DAGValidator
- Week 7-8: NodeHandlers + WorkflowEngine
- Week 9-10: REST API + Celery tasks
- Week 11: Unit + Integration tests

**Deliverable:** Workflows work via API (curl)

**Migration:** Worker continues using State Machine (no changes yet)

### Phase 3: Real-Time Integration (Week 12-15)

**Goal:** Add OpenTelemetry + WebSocket + UI

**Tasks:**
- Week 12: OpenTelemetry in WorkflowEngine
- Week 13: Django Channels WebSocket
- Week 14: React Flow Design Mode
- Week 15: React Flow Monitor Mode

**Deliverable:** Full unified UI

**Migration:** Worker can optionally use workflows (gradual)

### Phase 4: Worker Migration (Week 16-17)

**Goal:** Migrate Worker to use explicit workflows

**Tasks:**
- Week 16: Create WorkflowTemplates for admin tasks
- Week 17: Update Worker to call WorkflowEngine

**Before:**
```go
// Worker executes implicit workflow
func (w *Worker) ProcessExtensionInstall(msg *OperationMessage) {
    w.stateMachine.Execute(msg)
}
```

**After:**
```go
// Worker calls WorkflowEngine
func (w *Worker) ProcessExtensionInstall(msg *OperationMessage) {
    workflow := w.getWorkflowTemplate("extension-install")

    execution := w.orchestratorClient.ExecuteWorkflow(workflow.ID, map[string]interface{}{
        "database_id": msg.DatabaseID,
        "extension_path": msg.ExtensionPath,
    })

    // Wait for completion or return task ID
    return execution
}
```

**Deliverable:** Worker uses WorkflowEngine

**Migration:** Gradual (one operation type at a time)

### Rollback Strategy

**Phase 2:** Drop workflow tables, no impact on Worker
**Phase 3:** Disable WebSocket, fall back to polling
**Phase 4:** Revert Worker to State Machine (one operation type at a time)

---

## Testing Strategy

### Unit Tests

#### Frontend Tests (Jest + React Testing Library)

```typescript
// frontend/src/components/workflow/__tests__/WorkflowCanvas.test.tsx

describe('WorkflowCanvas', () => {
  it('renders workflow in design mode', () => {
    render(<WorkflowCanvas mode="design" workflow={mockWorkflow} />);
    expect(screen.getByText('Lock Jobs')).toBeInTheDocument();
  });

  it('updates node status in monitor mode', async () => {
    const { rerender } = render(
      <WorkflowCanvas mode="monitor" execution={mockExecution} />
    );

    // Simulate WebSocket update
    act(() => {
      mockWs.emit('message', {
        type: 'node_update',
        node_id: 'lock',
        status: 'completed',
      });
    });

    expect(screen.getByText('✓')).toBeInTheDocument();
  });
});
```

#### Backend Tests (pytest)

```python
# orchestrator/apps/templates/tests/test_workflow_engine.py

def test_execute_workflow_creates_parent_span(mock_tracer):
    workflow = WorkflowTemplateFactory.create()
    engine = WorkflowEngine()

    execution = engine.execute_workflow(workflow, {})

    # Verify parent span created
    assert mock_tracer.start_span.called
    parent_span = mock_tracer.start_span.return_value
    assert parent_span.name == f"workflow.execute.{workflow.name}"
    assert parent_span.attributes['workflow.execution_id'] == execution.id

def test_execute_workflow_broadcasts_status(mock_channel_layer):
    workflow = WorkflowTemplateFactory.create()
    engine = WorkflowEngine()

    execution = engine.execute_workflow(workflow, {})

    # Verify WebSocket broadcast
    assert mock_channel_layer.group_send.called
    call_args = mock_channel_layer.group_send.call_args
    assert call_args[0][0] == f"workflow_{execution.id}"
    assert call_args[0][1]['type'] == 'workflow_update'
```

### Integration Tests

```python
# orchestrator/apps/templates/tests/test_workflow_integration.py

@pytest.mark.django_db
@pytest.mark.integration
def test_execute_workflow_end_to_end(live_server, ws_client):
    # Create workflow
    workflow = WorkflowTemplate.objects.create(
        name="Test Workflow",
        dag_structure={
            "nodes": [
                {"id": "step1", "type": "operation", "template_id": "..."},
                {"id": "step2", "type": "operation", "template_id": "..."},
            ],
            "edges": [{"from": "step1", "to": "step2"}]
        }
    )

    # Connect WebSocket
    ws = ws_client.connect(f"/ws/workflow/{execution.id}/")

    # Execute workflow
    response = client.post(f"/api/v1/workflows/executions/", {
        "workflow_id": workflow.id,
        "input_context": {}
    })
    execution_id = response.json()['execution_id']

    # Wait for status updates
    messages = []
    for _ in range(5):
        msg = ws.receive_json()
        messages.append(msg)
        if msg['type'] == 'workflow_update' and msg['status'] == 'completed':
            break

    # Verify execution completed
    execution = WorkflowExecution.objects.get(id=execution_id)
    assert execution.status == 'completed'
    assert len(execution.completed_nodes) == 2

    # Verify trace created
    traces = jaeger_client.get_traces_by_tag('workflow.execution_id', execution_id)
    assert len(traces) > 0
```

### E2E Tests (Playwright)

```typescript
// frontend/e2e/workflow.spec.ts

test('create and execute workflow', async ({ page }) => {
  // Navigate to workflow builder
  await page.goto('/workflows/new');

  // Drag nodes onto canvas
  await page.dragAndDrop('[data-node="operation"]', '.react-flow');
  await page.fill('[data-property="label"]', 'Lock Jobs');

  // Connect nodes
  await page.click('[data-handle="source"]');
  await page.click('[data-node="step2"] [data-handle="target"]');

  // Save workflow
  await page.click('button:text("Save")');
  await expect(page.locator('.toast')).toHaveText('Workflow saved');

  // Execute workflow
  await page.click('button:text("Run")');

  // Wait for execution to start
  await expect(page.locator('.status-indicator')).toHaveText('Running');

  // Verify nodes update in real-time
  await expect(page.locator('[data-node="step1"] .status-badge')).toHaveText('✓');
  await expect(page.locator('[data-node="step2"] .status-badge')).toHaveClass(/running/);

  // Click node to view traces
  await page.click('[data-node="step1"]');
  await page.click('button:text("View Traces")');

  // Verify trace viewer opens
  await expect(page.locator('.trace-viewer-modal')).toBeVisible();
});
```

---

## Timeline & Roadmap

**Total Duration:** 17 weeks (4 months)

**See detailed roadmap:** [UNIFIED_WORKFLOW_ROADMAP.md](../roadmaps/UNIFIED_WORKFLOW_ROADMAP.md)

### High-Level Phases

| Phase | Duration | Goal | Status |
|-------|----------|------|--------|
| **Phase 1: Foundation** | Week 1-4 | RAS Adapter MVP | ✅ COMPLETE |
| **Phase 2: Workflow Engine** | Week 5-11 | Backend implementation | 🔜 READY |
| **Phase 3: Real-Time** | Week 12-15 | OpenTelemetry + UI | ⏳ PENDING |
| **Phase 4: Polish** | Week 16-17 | Migration + Docs | ⏳ PENDING |

### MVP Option

**11 weeks** (до end of Phase 2):
- ✅ Workflow Engine backend working
- ✅ REST API complete
- ❌ No real-time UI (use API/curl)
- ❌ No trace integration

**Use case:** Workflows work, but debugging через Jaeger UI (отдельно)

### Full Feature Set

**17 weeks:**
- ✅ All MVP features
- ✅ Unified UI (Design + Monitor modes)
- ✅ Real-time status updates
- ✅ Integrated trace viewer
- ✅ Worker migration complete

---

## References

### Related Documents

- **[WORKFLOW_ENGINE_ARCHITECTURE.md](WORKFLOW_ENGINE_ARCHITECTURE.md)** - Track 1.5 design (1600 lines)
- **[TRACK1.5_WORKFLOW_ENGINE_SUMMARY.md](../TRACK1.5_WORKFLOW_ENGINE_SUMMARY.md)** - Quick summary
- **[REAL_TIME_OPERATION_TRACKING.md](REAL_TIME_OPERATION_TRACKING.md)** - Observability design (1540 lines)
- **[OBSERVABILITY_QUICKSTART.md](OBSERVABILITY_QUICKSTART.md)** - Quick start guide
- **[RAS_ADAPTER_ROADMAP.md](../roadmaps/RAS_ADAPTER_ROADMAP.md)** - Phase 1 completed

### External References

- **React Flow:** https://reactflow.dev/ - Visual workflow editor
- **OpenTelemetry:** https://opentelemetry.io/ - Distributed tracing
- **Jaeger:** https://www.jaegertracing.io/ - Trace backend
- **Django Channels:** https://channels.readthedocs.io/ - WebSocket support

---

## Appendix A: Example Workflows

### Admin: Extension Install

```json
{
  "name": "Install Extension to Database",
  "workflow_type": "sequential",
  "dag_structure": {
    "nodes": [
      {
        "id": "lock",
        "name": "Lock Scheduled Jobs",
        "type": "operation",
        "template_id": "tmpl_lock_jobs",
        "config": {"timeout": 30, "retries": 3}
      },
      {
        "id": "terminate",
        "name": "Terminate Active Sessions",
        "type": "operation",
        "template_id": "tmpl_terminate_sessions",
        "config": {"timeout": 60, "retries": 2}
      },
      {
        "id": "check",
        "name": "Check Remaining Connections",
        "type": "condition",
        "expression": "{{ terminate.result.active_connections == 0 }}",
        "branches": {"true": "install", "false": "wait"}
      },
      {
        "id": "wait",
        "name": "Wait 10s",
        "type": "operation",
        "template_id": "tmpl_sleep",
        "config": {"duration": 10}
      },
      {
        "id": "install",
        "name": "Install Extension",
        "type": "operation",
        "template_id": "tmpl_install_extension",
        "config": {"timeout": 300}
      },
      {
        "id": "unlock",
        "name": "Unlock Scheduled Jobs",
        "type": "operation",
        "template_id": "tmpl_unlock_jobs"
      }
    ],
    "edges": [
      {"from": "lock", "to": "terminate"},
      {"from": "terminate", "to": "check"},
      {"from": "check", "to": "install", "condition": "true"},
      {"from": "check", "to": "wait", "condition": "false"},
      {"from": "wait", "to": "terminate"},
      {"from": "install", "to": "unlock"}
    ]
  }
}
```

### User: Price List Upload

```json
{
  "name": "Upload Price List from Excel",
  "workflow_type": "complex",
  "dag_structure": {
    "nodes": [
      {
        "id": "validate",
        "name": "Validate Excel File",
        "type": "operation",
        "template_id": "tmpl_validate_excel"
      },
      {
        "id": "parse",
        "name": "Parse Rows",
        "type": "operation",
        "template_id": "tmpl_parse_excel_rows"
      },
      {
        "id": "loop_items",
        "name": "Process Each Item",
        "type": "loop",
        "loop_config": {
          "mode": "foreach",
          "items": "{{ parse.result.items }}",
          "loop_node": "create_or_update"
        }
      },
      {
        "id": "create_or_update",
        "name": "Create/Update Item",
        "type": "operation",
        "template_id": "tmpl_upsert_item"
      },
      {
        "id": "report",
        "name": "Generate Report",
        "type": "operation",
        "template_id": "tmpl_generate_import_report"
      }
    ],
    "edges": [
      {"from": "validate", "to": "parse"},
      {"from": "parse", "to": "loop_items"},
      {"from": "loop_items", "to": "report"}
    ]
  }
}
```

---

**Document Version:** 1.0
**Last Updated:** 2025-11-23
**Status:** APPROVED FOR IMPLEMENTATION
**Next Step:** See [UNIFIED_WORKFLOW_ROADMAP.md](../roadmaps/UNIFIED_WORKFLOW_ROADMAP.md)
