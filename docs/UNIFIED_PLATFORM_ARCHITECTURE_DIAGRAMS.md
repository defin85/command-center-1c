# Unified Platform - Architecture Diagrams

**Version:** 2.0 - Two-Tab Interface
**Date:** 2025-11-23

---

## 🎨 Complete System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            User Browser                                     │
│                         (Chrome, Firefox, Safari)                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ HTTP + WebSocket
                                  │
┌─────────────────────────────────▼───────────────────────────────────────────┐
│                         Frontend (React, port 5173)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────┐      ┌──────────────────────────────────┐   │
│  │  Tab 1: Service Mesh     │      │  Tab 2: My Workflows             │   │
│  ├──────────────────────────┤      ├──────────────────────────────────┤   │
│  │ • SystemHealthCard       │      │ • WorkflowList                   │   │
│  │ • ServiceFlowDiagram     │      │ • WorkflowCanvas (Design)        │   │
│  │ • ServiceNode x5         │      │ • WorkflowCanvas (Monitor)       │   │
│  │ • RecentOperationsTable  │      │ • TraceViewerModal               │   │
│  └────────┬─────────────────┘      └──────────┬───────────────────────┘   │
│           │                                    │                            │
│           │ WebSocket                          │ WebSocket + HTTP           │
│           │ ws://8090/ws/service-mesh          │ ws://8000/ws/workflow/{id} │
│           │                                    │ http://8000/api/v1/        │
└───────────┼────────────────────────────────────┼────────────────────────────┘
            │                                    │
            │                                    │
┌───────────▼──────────────┐   ┌────────────────▼────────────────────────────┐
│  Metrics Aggregator      │   │  Django Orchestrator (port 8000)            │
│  (Go, port 8090)         │   ├─────────────────────────────────────────────┤
├──────────────────────────┤   │                                             │
│ • Query Prometheus       │   │  ┌────────────────────────────────────┐    │
│ • Aggregate by service   │   │  │  WorkflowEngine                    │    │
│ • WebSocket server       │   │  │  • DAGValidator (Kahn's algo)      │    │
│ • Push every 2s          │   │  │  • DAGExecutor                     │    │
└───────────┬──────────────┘   │  │  • NodeHandlers (5 types)          │    │
            │                   │  │  • ContextManager (data passing)   │    │
            │                   │  └────────────┬───────────────────────┘    │
            │                   │               │                             │
            │                   │  ┌────────────▼───────────────────────┐    │
            │                   │  │  OpenTelemetry Instrumentation     │    │
            │                   │  │  • Tracer (create spans)           │    │
            │                   │  │  • Exporter (send to Jaeger)       │    │
            │                   │  └────────────┬───────────────────────┘    │
            │                   │               │                             │
            │                   │  ┌────────────▼───────────────────────┐    │
            │                   │  │  Django Channels (WebSocket)       │    │
            │                   │  │  • WorkflowExecutionConsumer       │    │
            │                   │  │  • Broadcast node updates          │    │
            │                   │  └────────────────────────────────────┘    │
            │                   │                                             │
            │                   └─────────────────────────────────────────────┘
            │                                    │
            │ Query                              │ Store workflows
            │                                    │ Execute operations
            ▼                                    ▼
┌──────────────────────┐       ┌─────────────────────────────────────────────┐
│  Prometheus          │       │  PostgreSQL (port 5432)                     │
│  (port 9090)         │       │  • workflow_templates                       │
│  • Metrics storage   │       │  • workflow_executions                      │
│  • PromQL queries    │       │  • workflow_step_results                    │
└──────────────────────┘       └─────────────────────────────────────────────┘
            ▲
            │ Scrape /metrics
            │ every 15s
            │
┌───────────┴──────────────────────────────────────────────────────────────────┐
│                        Application Services                                  │
│                           (Instrumented)                                     │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [Frontend] [API GW] [Orchestrator] [Worker x2] [RAS Adapter] [Batch Svc]  │
│      │          │          │            │             │             │        │
│      └──────────┴──────────┴────────────┴─────────────┴─────────────┘        │
│                          OpenTelemetry SDK                                   │
│                    (Metrics + Traces + Logs)                                 │
│                              │                                               │
└──────────────────────────────┼───────────────────────────────────────────────┘
                               │ Send traces
                               ▼
                    ┌──────────────────────┐
                    │  Jaeger              │
                    │  (port 16686)        │
                    │  • Trace storage     │
                    │  • Query API         │
                    │  • UI (fallback)     │
                    └──────────────────────┘
```

---

## 🔀 Data Flow: Complete Picture

### Scenario: Admin Installs Extension via Workflow

```
Step 1: Admin создает workflow (Design Mode)
  ↓
  User Browser (My Workflows tab, Design Mode)
    → Drag nodes: Lock → Terminate → Install → Unlock
    → Save workflow
  ↓
  POST /api/v1/workflows/templates
  ↓
  Django: WorkflowTemplate saved to PostgreSQL
  ↓
  Response: {"workflow_id": "wf-123"}

─────────────────────────────────────────────────────────────

Step 2: Admin запускает workflow (Monitor Mode)
  ↓
  User Browser (My Workflows tab, Monitor Mode)
    → Click "Run" button
  ↓
  POST /api/v1/workflows/executions
    Body: {"workflow_id": "wf-123", "input_context": {...}}
  ↓
  Django: WorkflowEngine.execute_workflow()
    ├─ Create WorkflowExecution record (status: 'running')
    ├─ Start OpenTelemetry parent span
    ├─ Execute DAG nodes in topological order
    │
    ├─ Node 1: Lock Jobs
    │   ├─ Create child span "node.lock"
    │   ├─ Execute OperationTemplate (via Celery)
    │   ├─ Celery → Worker → RAS Adapter → RAS
    │   ├─ Result: success
    │   ├─ End child span
    │   └─ Broadcast: {"type": "node_update", "node_id": "lock", "status": "completed"}
    │
    ├─ Node 2: Terminate Sessions
    │   ├─ Create child span "node.terminate"
    │   ├─ Execute OperationTemplate
    │   ├─ Result: success
    │   └─ Broadcast: {"type": "node_update", "node_id": "terminate", "status": "completed"}
    │
    ├─ Node 3: Install Extension
    │   ├─ Create child span "node.install"
    │   ├─ Execute OperationTemplate
    │   ├─ Worker → batch-service → 1cv8.exe (takes 45s)
    │   ├─ Real-time: Broadcast {"type": "node_update", "status": "running"}
    │   ├─ Result: success
    │   └─ Broadcast: {"type": "node_update", "node_id": "install", "status": "completed"}
    │
    └─ Node 4: Unlock Jobs
        ├─ Create child span "node.unlock"
        ├─ Execute OperationTemplate
        ├─ Result: success
        └─ Broadcast: {"type": "node_update", "node_id": "unlock", "status": "completed"}
  ↓
  End parent span
  ↓
  WorkflowExecution.status = 'completed'
  ↓
  Broadcast: {"type": "workflow_update", "status": "completed"}

─────────────────────────────────────────────────────────────

Step 3: User видит live updates (Monitor Mode)
  ↓
  User Browser (WebSocket receives updates)
    ├─ Node "Lock Jobs" → ✓ green (0.8s)
    ├─ Node "Terminate" → ✓ green (2.3s)
    ├─ Node "Install" → ⚡ blue animated (45s)
    └─ Node "Unlock" → ✓ green (0.5s)
  ↓
  Progress bar: 100% ████████████
  ↓
  Status: 🟢 Completed

─────────────────────────────────────────────────────────────

Step 4: Одновременно - Service Mesh tab updates
  ↓
  Metrics Aggregator
    ├─ Query Prometheus:
    │   worker_tasks_active{operation_type="extension_install"}
    │   worker_task_duration_seconds{operation_type="extension_install"}
    ├─ Calculate:
    │   • Active operations: 1 → 0 (completed)
    │   • P95 latency: 45s
    ├─ Aggregate by service
    └─ Push via WebSocket to Service Mesh tab
  ↓
  Service Mesh tab updates:
    Worker node: ✓ 1 completed operation
    Recent Operations table: + new row "Install Ext, 45s, ✓ Success"

─────────────────────────────────────────────────────────────

Step 5: Admin хочет debug (click node)
  ↓
  User Browser (My Workflows tab)
    → Click на node "Install Extension"
    → Click "View Traces"
  ↓
  GET http://localhost:16686/api/traces?tags={"workflow.execution_id":"exec-456","node.id":"install"}
  ↓
  Jaeger returns trace:
    {
      "traceID": "abc123",
      "spans": [
        {
          "operationName": "node.install.Install Extension",
          "duration": 45200000,  // 45.2s
          "tags": {
            "workflow.execution_id": "exec-456",
            "node.id": "install"
          },
          "logs": [...]
        },
        {
          "operationName": "batch-service.execute_1cv8",
          "duration": 40500000,  // 40.5s (child span)
          "tags": {...}
        }
      ]
    }
  ↓
  TraceViewerModal opens
    Timeline:
      Worker: Install Extension (45.2s)
      ├─ batch-service: Validate (2.1s)
      ├─ batch-service: Execute 1cv8.exe (40.5s) ← Selected
      └─ batch-service: Verify (0.5s)

    Span Details:
      Command: 1cv8.exe /S localhost\base /LoadCfg ext.cfe
      Exit Code: 0
      Duration: 40.5s
```

---

## 🔗 Event Flow: Service Mesh → Workflow Drill-Down

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Service Mesh Tab                                        │
│ User видит system overview                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │ User action: Click Worker node      │
         └──────────────────┬──────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ STEP 2: ServiceOperationsModal opens                            │
│ Shows list of operations on Worker service                      │
│                                                                  │
│  Active (18):                                                    │
│    op-67890  Install Extension    ⚡ Running  45s               │
│    op-67891  Price List Upload    ⚡ Running  12s               │
│    ...                                                           │
│                                                                  │
│  Failed (2):                                                     │
│    op-67888  Backup DB            ✗ Failed    120s              │ ← Click
│    op-67885  Config Update        ✗ Failed    5s               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │ User action: Click op-67888 row     │
         └──────────────────┬──────────────────┘
                            │
                            │ dashboardStore.openExecutionFromServiceMesh()
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ STEP 3: Auto-switch to My Workflows tab                         │
│ workflowMode = 'monitor'                                         │
│ selectedExecution = find by operation_id "op-67888"              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ STEP 4: Monitor Mode renders                                    │
│ WorkflowCanvas loads execution data                             │
│ WebSocket connects to /ws/workflow/exec-67888/                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ STEP 5: User видит workflow details                             │
│                                                                  │
│  Workflow: "Backup Database"                                    │
│  Status: ✗ Failed                                               │
│                                                                  │
│  [Block Sessions]   ✓ 1.2s                                      │
│  [Wait Active Tx]   ✓ 15.3s                                     │
│  [Terminate Ses]    ✗ FAILED (timeout)  ← Red highlight        │
│  [Create Backup]    ○ Not started                               │
│  [Verify Backup]    ○ Not started                               │
│  [Unblock Sessions] ○ Not started                               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
         ┌──────────────────┴──────────────────┐
         │ User action: Click failed node      │
         └──────────────────┬──────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ STEP 6: TraceViewerModal opens                                  │
│ Query Jaeger API for traces                                     │
│                                                                  │
│  Trace Timeline:                                                │
│    Worker: Terminate Sessions (120s timeout)                    │
│    ├─ ras-adapter: List sessions (0.5s)                         │
│    ├─ ras-adapter: Terminate each (115s) ← Problem!            │
│    │   ├─ session-1 (2s) ✓                                      │
│    │   ├─ session-2 (2s) ✓                                      │
│    │   ├─ ...                                                    │
│    │   └─ session-50 (timeout) ✗                                │
│    └─ Error: "Timeout after 60s"                                │
│                                                                  │
│  Root Cause: Too many sessions, need higher timeout!           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🌊 Data Flow: Real-Time Updates

### Service Mesh Tab Updates

```
Every 2 seconds:

Prometheus
  ↓ metrics storage
All Services (expose /metrics)
  ↓
Metrics Aggregator queries Prometheus
  ├─ Query: worker_tasks_active
  ├─ Query: worker_task_duration_seconds (P95)
  ├─ Query: worker_tasks_completed_total{status="error"}
  └─ Aggregate: {service: "worker", active: 18, latency: 2.5, errors: 2}
  ↓
WebSocket push to all connected clients
  ↓
Frontend (Service Mesh tab) receives update
  ├─ Update ServiceNode for "worker"
  │   ├─ Active: 18 (animation if changed)
  │   ├─ Failed: 2 (red highlight if > 0)
  │   └─ Latency: 2.5s (yellow if > 2s)
  └─ Update RecentOperationsTable
      └─ Fetch latest operations from API (debounced)
```

### My Workflows Tab Updates

```
On workflow status change (real-time):

WorkflowEngine executes node
  ↓
Node status changes: running → completed
  ↓
DAGExecutor._broadcast_node_update()
  ├─ Update WorkflowExecution.node_statuses in DB
  └─ channel_layer.group_send("workflow_exec-456", {
      "type": "node_update",
      "node_id": "install",
      "status": "completed",
      "duration": 45.2
    })
  ↓
Django Channels broadcasts to all subscribers
  ↓
Frontend (My Workflows tab, Monitor Mode) receives update
  ├─ Update node color (blue → green)
  ├─ Update duration label (45.2s)
  ├─ Update progress bar (60% → 80%)
  └─ Animate transition (CSS animation)
  ↓
User sees instant visual feedback
```

---

## 🧩 Component Integration Map

```
┌───────────────────────────────────────────────────────────────┐
│                    Frontend Components                        │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Dashboard.tsx                                                │
│  ├─ activeTab state                                           │
│  ├─ Tabs component                                            │
│  │                                                             │
│  ├─ ServiceMeshTab.tsx                                        │
│  │   ├─ useServiceMeshMetrics() hook                          │
│  │   │   └─ WebSocket → ws://8090/ws/service-mesh            │
│  │   ├─ ServiceFlowDiagram.tsx                                │
│  │   │   └─ ServiceNode.tsx x5                                │
│  │   │       └─ onClick → ServiceOperationsModal.tsx          │
│  │   │           └─ onRowClick → openExecutionFromServiceMesh()│
│  │   └─ RecentOperationsTable.tsx                             │
│  │       └─ onRowClick → openExecutionFromServiceMesh()       │
│  │                                                             │
│  └─ MyWorkflowsTab.tsx                                        │
│      ├─ workflowMode state (list/design/monitor)              │
│      │                                                         │
│      ├─ WorkflowList.tsx (if mode === 'list')                 │
│      │   └─ onClick → setMode('design' or 'monitor')          │
│      │                                                         │
│      ├─ WorkflowCanvas.tsx mode="design" (if mode === 'design')│
│      │   ├─ NodePalette.tsx                                   │
│      │   ├─ ReactFlow                                         │
│      │   └─ PropertyEditor.tsx                                │
│      │                                                         │
│      └─ WorkflowCanvas.tsx mode="monitor" (if mode === 'monitor')│
│          ├─ useWorkflowExecution() hook                       │
│          │   └─ WebSocket → ws://8000/ws/workflow/{id}/       │
│          ├─ ReactFlow (read-only + status overlays)           │
│          ├─ OperationNodeWithStatus.tsx                       │
│          │   └─ onClick → TraceViewerModal.tsx                │
│          └─ Timeline.tsx                                       │
│                                                               │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                    Backend Services                           │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  Metrics Aggregator (Go:8090)                                 │
│  ├─ Prometheus client (query PromQL)                          │
│  ├─ Aggregator (aggregate by service)                         │
│  └─ WebSocket server (/ws/service-mesh)                       │
│                                                               │
│  Django Orchestrator (Python:8000)                            │
│  ├─ WorkflowEngine (execute workflows)                        │
│  ├─ OpenTelemetry (tracing)                                   │
│  └─ Django Channels (WebSocket /ws/workflow/{id}/)            │
│                                                               │
│  Jaeger (port 16686)                                          │
│  └─ Trace storage + Query API                                 │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## 🎭 Sequence Diagram: Cross-Tab Navigation

```
User            Dashboard       ServiceMeshTab   MyWorkflowsTab   Backend
 │                  │                 │                │             │
 │ Open app         │                 │                │             │
 ├─────────────────>│                 │                │             │
 │                  │ Default: Tab 1  │                │             │
 │                  ├────────────────>│                │             │
 │                  │                 │ Load metrics   │             │
 │                  │                 ├───────────────────────────────>
 │                  │                 │                │  WebSocket  │
 │                  │                 │<───────────────────────────────
 │                  │                 │                │             │
 │ See Worker      │                 │                │             │
 │ has 2 failed    │                 │                │             │
 │                  │                 │                │             │
 │ Click Worker    │                 │                │             │
 ├─────────────────────────────────>│                │             │
 │                  │                 │ Show modal     │             │
 │                  │                 │ (operations)   │             │
 │                  │                 │                │             │
 │ Click failed op │                 │                │             │
 ├─────────────────────────────────>│                │             │
 │                  │ openExecutionFromServiceMesh()   │             │
 │                  │<────────────────┘                │             │
 │                  │                                  │             │
 │                  │ switchTab('my-workflows')        │             │
 │                  ├──────────────────────────────────>             │
 │                  │                                  │ Load exec   │
 │                  │                                  ├─────────────>
 │                  │                                  │ WebSocket   │
 │                  │                                  │<─────────────
 │                  │                                  │             │
 │ See Monitor Mode│                                  │             │
 │ with failed node│                                  │             │
 │                  │                                  │             │
 │ Click node      │                                  │             │
 ├──────────────────────────────────────────────────>│             │
 │                  │                                  │ Query Jaeger│
 │                  │                                  ├─────────────>
 │                  │                                  │ Return trace│
 │                  │                                  │<─────────────
 │                  │                                  │             │
 │ See Jaeger trace│                                  │             │
 │ with root cause │                                  │             │
 │                  │                                  │             │
```

---

## 📊 Metrics & Monitoring

### Service Mesh Tab Metrics

**Displayed in UI:**
```
Per Service:
  • Operations/minute (rate)
  • Active operations (gauge)
  • Failed operations (counter)
  • P50/P95/P99 latency (histogram)

System-Wide:
  • Total ops/min (sum across all services)
  • System health status (healthy/degraded/down)
  • Error rate % (failed / total)
```

**Source:** Prometheus (via Metrics Aggregator)

### My Workflows Tab Metrics

**Displayed in UI:**
```
Per Workflow Execution:
  • Progress % (completed_nodes / total_nodes)
  • Current node
  • Duration (elapsed time)
  • Status (pending/running/completed/failed)

Per Node:
  • Status (pending/running/completed/failed)
  • Duration
  • Error message (if failed)
  • Result data (if completed)
```

**Source:** Django Channels WebSocket (real-time)

### OpenTelemetry Spans

**Created for:**
```
Workflow execution:
  Parent span: "workflow.execute.{name}"
    ├─ Child span: "node.operation.Lock Jobs"
    ├─ Child span: "node.operation.Terminate Sessions"
    ├─ Child span: "node.operation.Install Extension"
    │   ├─ Grandchild: "batch-service.validate"
    │   ├─ Grandchild: "batch-service.execute_1cv8"
    │   └─ Grandchild: "batch-service.verify"
    └─ Child span: "node.operation.Unlock Jobs"

Attributes:
  • workflow.id
  • workflow.execution_id
  • node.id
  • node.type
  • operation.id
  • database.id
```

**Stored in:** Jaeger

---

## 🔐 Security & Permissions

### Tab-Level Permissions

```python
# Backend: Check user permissions

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_service_mesh_metrics(request):
    # Check permission
    if not request.user.has_perm('monitoring.view_service_mesh'):
        return Response(
            {"error": "Permission denied"},
            status=403
        )

    # Return metrics
    # ...
```

```typescript
// Frontend: Hide tabs based on permissions

<Tabs activeKey={activeTab} onChange={handleTabChange}>
  {user.canViewServiceMesh && (
    <TabPane tab="🌐 Service Mesh" key="service-mesh">
      <ServiceMeshTab />
    </TabPane>
  )}

  {user.canViewWorkflows && (
    <TabPane tab="📋 My Workflows" key="my-workflows">
      <MyWorkflowsTab />
    </TabPane>
  )}
</Tabs>
```

### WebSocket Security

```typescript
// Include auth token in WebSocket connection

const token = getAuthToken();

// Service Mesh WebSocket
const ws1 = new WebSocket(
  `ws://localhost:8090/ws/service-mesh?token=${token}`
);

// Workflow WebSocket
const ws2 = new WebSocket(
  `ws://localhost:8000/ws/workflow/${executionId}/?token=${token}`
);
```

### Backend Validation

```go
// Metrics Aggregator: Validate token

func (s *WebSocketServer) HandleConnection(w http.ResponseWriter, r *http.Request) {
    token := r.URL.Query().Get("token")

    // Validate token
    if !s.authService.ValidateToken(token) {
        http.Error(w, "Unauthorized", 401)
        return
    }

    // Upgrade to WebSocket
    conn, err := upgrader.Upgrade(w, r, nil)
    // ...
}
```

```python
# Django Channels: Validate token

class WorkflowExecutionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract token from query params
        token = self.scope['query_string'].decode().split('token=')[1]

        # Validate
        user = await self.get_user_from_token(token)
        if not user:
            await self.close(code=4001)
            return

        # Check permissions
        if not user.has_perm('workflows.view_execution'):
            await self.close(code=4003)
            return

        # Accept connection
        await self.accept()
```

---

## ⚡ Performance Targets

### Service Mesh Tab

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **WebSocket Latency** | < 100ms | Chrome DevTools Network tab |
| **Metrics Update Interval** | 2s ± 100ms | Log timestamps |
| **UI Render Time** | < 50ms | React DevTools Profiler |
| **Concurrent Users** | > 50 | Load testing (k6) |
| **Memory Usage** | < 100MB per tab | Chrome Task Manager |

### My Workflows Tab

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Workflow Load Time** | < 500ms | React DevTools |
| **Node Status Update Latency** | < 200ms | Log timestamps |
| **Trace Load Time** | < 1s | Jaeger API response time |
| **Canvas Render Time** | < 100ms | React Flow performance |
| **WebSocket Reconnect Time** | < 2s | Manual testing |

---

## 🧪 Testing Matrix

### Service Mesh Tab Tests

| Test Type | Count | Coverage |
|-----------|-------|----------|
| **Unit Tests** | 15 | ServiceNode, ServiceFlowDiagram, RecentOperationsTable |
| **Integration Tests** | 8 | WebSocket connection, Metrics aggregation, Cross-tab nav |
| **E2E Tests** | 6 | Open tab, Click service, Click operation, Switch tabs |
| **Load Tests** | 3 | 10/50/100 concurrent WebSocket connections |
| **Manual Tests** | 10 | Visual verification, animations, error states |

### My Workflows Tab Tests

| Test Type | Count | Coverage |
|-----------|-------|----------|
| **Unit Tests** | 40 | All workflow components, hooks, store |
| **Integration Tests** | 20 | Workflow execution, WebSocket, Jaeger API |
| **E2E Tests** | 15 | Create workflow, Run, Monitor, View traces |
| **Load Tests** | 5 | 10/50/100 concurrent workflow executions |
| **Manual Tests** | 20 | Workflow builder UX, Monitor Mode, Trace viewer |

**Total:** ~140 automated tests

---

## 📖 Complete Documentation Set

```
docs/
│
├── UNIFIED_PLATFORM_OVERVIEW.md                 ← You are here (complete overview)
├── UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md          ← Quick summary (10 min read)
├── TWO_TAB_INTERFACE_DESIGN.md                  ← Detailed UI design (30 min read)
├── UNIFIED_PLATFORM_ARCHITECTURE_DIAGRAMS.md    ← This file (diagrams reference)
│
├── architecture/
│   └── UNIFIED_WORKFLOW_VISUALIZATION.md        ← Complete design doc v2.0 (2hr read)
│
├── roadmaps/
│   └── UNIFIED_WORKFLOW_ROADMAP.md              ← 18-week roadmap (1hr read)
│
└── Original docs (for reference):
    ├── WORKFLOW_ENGINE_ARCHITECTURE.md          ← Track 1.5 original
    └── REAL_TIME_OPERATION_TRACKING.md          ← Observability original
```

**Reading Path:**

**For Decision Makers:** (15 min)
1. UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md
2. Review timeline in UNIFIED_WORKFLOW_ROADMAP.md

**For Architects:** (3 hrs)
1. UNIFIED_PLATFORM_OVERVIEW.md
2. architecture/UNIFIED_WORKFLOW_VISUALIZATION.md
3. TWO_TAB_INTERFACE_DESIGN.md

**For Developers:** (2 hrs)
1. roadmaps/UNIFIED_WORKFLOW_ROADMAP.md (specific week)
2. UNIFIED_PLATFORM_ARCHITECTURE_DIAGRAMS.md (this file)
3. Original design docs as needed

---

## ✅ Approval Checklist

**Design:**
- [x] Two-Tab Interface approved
- [x] Service Mesh Monitor scope defined
- [x] Cross-tab navigation flow validated
- [x] Component hierarchy reviewed
- [x] Security considerations addressed

**Documentation:**
- [x] Design document v2.0 created
- [x] Roadmap v2.0 updated (18 weeks)
- [x] Summary documents created
- [x] Architecture diagrams created
- [x] FAQs answered

**Planning:**
- [x] Timeline estimated (18 weeks)
- [x] Week 16 tasks detailed
- [x] Success metrics defined
- [x] Testing strategy outlined
- [ ] Team capacity confirmed
- [ ] Budget approved

**Technical:**
- [x] Architecture validated
- [x] Integration points identified
- [x] Performance targets set
- [x] Security requirements defined
- [x] Rollback strategy planned

---

## 🚀 Ready to Start!

**Status:** ✅ ALL DOCUMENTATION COMPLETE

**Next Actions:**

1. **Stakeholder sign-off** on Two-Tab Interface design
2. **Confirm budget** for 18 weeks (vs 17 weeks original)
3. **Assign team:**
   - Backend: Django developer (Week 5-13)
   - Frontend: React developer (Week 14-16)
   - Go: Metrics Aggregator developer (Week 16)
   - QA: Testing engineer (Week 11, 15, 18)
4. **Begin Phase 2 (Week 5):** Django models + migrations

---

**Document Version:** 1.0
**Last Updated:** 2025-11-23
**Status:** ✅ APPROVED - Ready for implementation
**Start Date:** Week 5 (TBD by stakeholders)
