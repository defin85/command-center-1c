# Two-Tab Interface - Detailed Design

**Version:** 1.0
**Date:** 2025-11-23
**Parent Doc:** [UNIFIED_WORKFLOW_VISUALIZATION.md](architecture/UNIFIED_WORKFLOW_VISUALIZATION.md)

---

## 📐 Visual Design

### Master Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│  CommandCenter1C                                      [User: admin ▼] [⚙️] │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Tabs: [🌐 Service Mesh] [📋 My Workflows]                                │
│        ═══════════════                                                     │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │                      ACTIVE TAB CONTENT                              │ │
│  │                                                                      │ │
│  │  (Service Mesh Monitor OR My Workflows depending on selection)      │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Tab 1: Service Mesh Monitor

### Full Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│  CommandCenter1C                                      [User: admin ▼] [⚙️] │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Tabs: [🌐 Service Mesh] [📋 My Workflows]                                │
│        ═══════════════                                                     │
│                                                                            │
│  ┌─ System Health ──────────────────────────────────────────────────────┐ │
│  │ Status: 🟢 Healthy    Operations/min: 234    P95 Latency: 1.2s       │ │
│  │ Active: 18 ops        Failed: 2 ops          Uptime: 99.9%            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ Service Flow ───────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │                           ┌────────────┐                             │ │
│  │                           │  Frontend  │                             │ │
│  │                           │  (React)   │                             │ │
│  │                           │            │                             │ │
│  │                           │ ↓ 20 ops   │ ← Click to filter          │ │
│  │                           │ ⏱ 45ms     │                             │ │
│  │                           └──────┬─────┘                             │ │
│  │                                  │                                    │ │
│  │                           ┌──────▼─────┐                             │ │
│  │                           │  API GW    │                             │ │
│  │                           │  (Go)      │                             │ │
│  │                           │            │                             │ │
│  │                           │ ↓ 20 recv  │                             │ │
│  │                           │ → 20 fwd   │                             │ │
│  │                           │ ⏱ 50ms P95 │                             │ │
│  │                           └──────┬─────┘                             │ │
│  │                                  │                                    │ │
│  │                   ┌──────────────┴───────────────┐                   │ │
│  │                   │                              │                   │ │
│  │            ┌──────▼─────┐              ┌─────────▼────────┐          │ │
│  │            │Orchestrator│              │  Worker Pool     │          │ │
│  │            │  (Django)  │              │  (Go x2)         │          │ │
│  │            │            │              │                  │          │ │
│  │            │ ↓ 20 recv  │              │ ⚡ 18 active    │ ← Click  │ │
│  │            │ → 20 queue │              │ ✓ 16 success    │          │ │
│  │            │ 📦 15 pend │              │ ✗ 2 failed      │ ← Shows  │ │
│  │            └──────┬─────┘              └─────────┬────────┘   modal │ │
│  │                   │                              │                   │ │
│  │                   │                    ┌─────────▼────────┐          │ │
│  │                   │                    │  RAS Adapter     │          │ │
│  │                   │                    │  (Go)            │          │ │
│  │                   │                    │                  │          │ │
│  │                   │                    │ ↓ 5 lock        │          │ │
│  │                   │                    │ ⏱ Avg: 1.2s     │          │ │
│  │                   │                    └──────────────────┘          │ │
│  │                   │                                                   │ │
│  │            ┌──────▼─────────┐                                        │ │
│  │            │  PostgreSQL    │   [Redis]                              │ │
│  │            └────────────────┘                                        │ │
│  │                                                                      │ │
│  │  Legend: ⚡Active ✓Success ✗Failed ⏱Latency 📦Queued               │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ Recent Operations (Last 5 min) ────────────────────────────────────┐ │
│  │ Operation ID │ Workflow         │ Service │ Status │ Duration │ Time │ │
│  │──────────────┼──────────────────┼─────────┼────────┼──────────┼──────│ │
│  │ op-67890     │ Install Ext      │ Worker  │ ⚡ Run │ 45.2s    │ Now  │ │
│  │ op-67889     │ Config Update    │ Worker  │ ✓ Done │ 2.3s     │ 2m   │ │
│  │ op-67888     │ Backup DB        │ Worker  │ ✗ Fail │ 120s     │ 5m   │ │
│  │ op-67887     │ Price List       │ Worker  │ ✓ Done │ 34.5s    │ 3m   │ │
│  └──────────────┴──────────────────┴─────────┴────────┴──────────┴──────┘ │
│                                                                            │
│  Click row → Auto-switch to "My Workflows" tab + open Monitor Mode        │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### Service Node (Detailed)

```
┌────────────────────────┐
│       Worker x2        │
├────────────────────────┤
│                        │
│  ⚡ 18 Active          │ ← Gauge animation
│  ✓ 16 Success          │
│  ✗ 2 Failed            │ ← Red highlight
│                        │
│  ↓ 20 ops/min          │
│  ⏱ P95: 2.5s           │
│                        │
│  [View Details]        │ ← Click shows modal
└────────────────────────┘
```

**On Click:**
```
┌────────────────────────────────────────────────────────────┐
│  Worker Operations                                 [Close] │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Filter: [All ▼] [Active] [Failed]                        │
│                                                            │
│  ┌─ Active Operations (18) ──────────────────────────┐    │
│  │ ID       │ Workflow        │ Step       │ Duration │    │
│  │──────────┼─────────────────┼────────────┼─────────│    │
│  │ op-67890 │ Install Ext     │ Install    │ 45.2s   │ ← Click
│  │ op-67891 │ Price List      │ Import     │ 12.3s   │    │
│  │ ...                                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                            │
│  ┌─ Failed Operations (2) ───────────────────────────┐    │
│  │ ID       │ Workflow        │ Failed At  │ Error    │    │
│  │──────────┼─────────────────┼────────────┼─────────│    │
│  │ op-67888 │ Backup DB       │ Terminate  │ Timeout │ ← Click
│  │ op-67885 │ Config Update   │ Validate   │ Invalid │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                            │
│  Click row → Switch to "My Workflows" tab                 │
│              + Open Monitor Mode for that execution        │
└────────────────────────────────────────────────────────────┘
```

---

## Tab 2: My Workflows

### A. List View (Default)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  CommandCenter1C                                      [User: admin ▼] [⚙️] │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Tabs: [🌐 Service Mesh] [📋 My Workflows]                                │
│                          ═══════════════                                   │
│                                                                            │
│  ┌─ My Workflows ──────────────────────────────────────────────────────┐  │
│  │                                               [+ Create Workflow]    │  │
│  │                                                                      │  │
│  │  Filter: [All ▼] [Admin] [Data] [Complex]    Search: [________]    │  │
│  │                                                                      │  │
│  │  Name                  │ Type    │ Steps │ Last Run  │ Actions      │  │
│  │────────────────────────┼─────────┼───────┼───────────┼─────────────│  │
│  │ Install Extension      │ Admin   │ 4     │ 5 min ago │ [Run][Edit]  │  │
│  │ Config Update          │ Admin   │ 3     │ 1 hr ago  │ [Run][Edit]  │  │
│  │ Upload Price List      │ Data    │ 5     │ 2 hr ago  │ [Run][Edit]  │  │
│  │ Monthly Close          │ Complex │ 12    │ 2 days    │ [Run][Edit]  │  │
│  │ Database Backup        │ Admin   │ 6     │ Daily     │ [Run][Edit]  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  ┌─ Active Executions ─────────────────────────────────────────────────┐  │
│  │  Workflow              │ Started   │ Progress      │ Status │ Actions │ │
│  │────────────────────────┼───────────┼───────────────┼────────┼────────│ │
│  │ Install Extension      │ 45s ago   │ 60% ████████▒ │ ⚡ Run │ [View] │ │
│  │ Upload Price List      │ 2m ago    │ 20% ████▒▒▒▒▒ │ ⚡ Run │ [View] │ │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  Click [View] → Opens Monitor Mode for that execution                     │
│  Click [Run] → Starts new execution + Opens Monitor Mode                  │
│  Click [Edit] → Opens Design Mode                                         │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### B. Design Mode

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Edit Workflow: Install Extension                [Save] [Validate] [Run ▶]│
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─ Node Palette ──┐  ┌─ Canvas (React Flow) ───────────────────────────┐│
│  │                 │  │                                                  ││
│  │ 🔧 Operation    │  │         ┌──────────────┐                        ││
│  │ Drag to canvas  │  │         │    Start     │                        ││
│  │                 │  │         └───────┬──────┘                        ││
│  │ ⁉️ Condition    │  │                 │                               ││
│  │ Drag to canvas  │  │         ┌───────▼──────┐                        ││
│  │                 │  │         │  Lock Jobs   │ ← Selected             ││
│  │ ⇉ Parallel      │  │         └───────┬──────┘                        ││
│  │ Drag to canvas  │  │                 │                               ││
│  │                 │  │         ┌───────▼────────┐                      ││
│  │ 🔁 Loop         │  │         │  Terminate     │                      ││
│  │ Drag to canvas  │  │         │  Sessions      │                      ││
│  │                 │  │         └───────┬────────┘                      ││
│  │ 📦 SubWorkflow  │  │                 │                               ││
│  │ Drag to canvas  │  │         ┌───────▼────────┐                      ││
│  │                 │  │         │ Install Ext    │                      ││
│  └─────────────────┘  │         └───────┬────────┘                      ││
│                       │                 │                               ││
│                       │         ┌───────▼────────┐                      ││
│                       │         │  Unlock Jobs   │                      ││
│                       │         └────────────────┘                      ││
│                       │                                                  ││
│                       └──────────────────────────────────────────────────┘│
│                                                                            │
│  ┌─ Properties (Selected: Lock Jobs) ───────────────────────────────────┐ │
│  │ Node Name:     [Lock Scheduled Jobs                              ]   │ │
│  │ Template:      [Lock Scheduled Jobs Template          ▼]            │ │
│  │ Timeout:       [30] seconds                                          │ │
│  │ Max Retries:   [3]                                                   │ │
│  │                                                          [Apply]     │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### C. Monitor Mode

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Monitoring: Install Extension              🟢 Running  [Pause] [Cancel]  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  Progress: 60% ████████████▒▒▒▒▒▒▒▒  |  Node 3 of 5  |  Duration: 48.3s │
│                                                                            │
│  ┌─ Workflow Canvas (Read-Only + Live Status) ─────────────────────────┐ │
│  │                                                                      │ │
│  │                    ┌──────────────┐                                  │ │
│  │                    │    Start     │                                  │ │
│  │                    └───────┬──────┘                                  │ │
│  │                            │                                         │ │
│  │                    ┌───────▼──────┐                                  │ │
│  │                    │  Lock Jobs   │ ✓ 0.8s                          │ │
│  │                    └───────┬──────┘   ▲                             │ │
│  │                            │          │                              │ │
│  │                            │      Click to view traces               │ │
│  │                            │                                         │ │
│  │                    ┌───────▼────────┐                                │ │
│  │                    │  Terminate     │ ✓ 2.3s                        │ │
│  │                    │  Sessions      │                                │ │
│  │                    └───────┬────────┘                                │ │
│  │                            │                                         │ │
│  │                    ┌───────▼────────┐                                │ │
│  │                    │ Install Ext    │ ⚡ Running... 45.2s           │ │
│  │                    │                │ ◄─── Animated spinner         │ │
│  │                    └───────┬────────┘                                │ │
│  │                            │                                         │ │
│  │                    ┌───────▼────────┐                                │ │
│  │                    │  Unlock Jobs   │ ○ Pending                      │ │
│  │                    └────────────────┘                                │ │
│  │                                                                      │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                            │
│  ┌─ Timeline ─────────────────────────────────────────────────────────┐  │
│  │ 0s                          25s                          50s        │  │
│  │ ├─ Lock Jobs (0.8s)    ✓                                           │  │
│  │ ├─ Terminate (2.3s)    ✓                                           │  │
│  │ ├─ Install Ext (45.2s) ⚡━━━━━━━━━━━━━━━▶                         │  │
│  │ └─ Unlock Jobs         ○ Not started                               │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
│  [View System Impact] ← Click to switch to Service Mesh tab              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Cross-Tab Navigation Flows

### Flow 1: Service Mesh → Workflow Drill-Down

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: User на Service Mesh tab                        │
│         Видит: Worker ✗ 2 failed operations             │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: Click на Worker node                            │
│         Modal показывает список операций                │
│         Видит: op-67888 "Backup DB" FAILED              │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Click на operation row (op-67888)               │
│         Auto-switch to "My Workflows" tab               │
│         Opens Monitor Mode для этого execution          │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: Monitor Mode показывает:                        │
│         • Workflow canvas с node statuses               │
│         • Red node: "Terminate Sessions" FAILED         │
│         • Error: "Timeout after 60s"                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 5: Click на failed node                            │
│         Opens Trace Viewer modal                        │
│         Jaeger trace показывает:                        │
│         • RAS Adapter timeout                           │
│         • 15 active connections (too many)              │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 6: User понимает root cause:                       │
│         • Too many concurrent sessions                  │
│         • Need to increase timeout OR                   │
│         • Need to reduce concurrent operations          │
└─────────────────────────────────────────────────────────┘
```

### Flow 2: Workflow → System Impact Check

```
┌─────────────────────────────────────────────────────────┐
│ Step 1: User на My Workflows tab                        │
│         Запускает "Upload Price List" workflow          │
│         Monitor Mode активен, видит progress: 20%       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 2: User хочет проверить system impact              │
│         Click "View System Impact" button               │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 3: Auto-switch to Service Mesh tab                 │
│         Видит:                                          │
│         • Worker: 50 active operations (high load!)     │
│         • His workflow = one of 50                      │
│         • P95 latency increased to 5s (от 2.5s)         │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│ Step 4: User решает:                                    │
│         • Cancel his workflow (не хочет перегружать)    │
│         • OR wait (system load is acceptable)           │
│         • OR schedule for later (off-peak hours)        │
└─────────────────────────────────────────────────────────┘
```

---

## State Management

### Zustand Store

```typescript
// frontend/src/stores/dashboardStore.ts

import create from 'zustand';
import { persist } from 'zustand/middleware';

interface DashboardState {
  // Active tab
  activeTab: 'service-mesh' | 'my-workflows';

  // Service Mesh state
  serviceMeshMetrics: ServiceMetrics[];
  recentOperations: Operation[];
  selectedService: string | null;

  // My Workflows state
  myWorkflows: WorkflowTemplate[];
  activeExecutions: WorkflowExecution[];
  selectedWorkflow: WorkflowTemplate | null;
  selectedExecution: WorkflowExecution | null;
  workflowMode: 'list' | 'design' | 'monitor';

  // Actions
  switchTab: (tab: 'service-mesh' | 'my-workflows') => void;

  // Service Mesh actions
  setServiceMeshMetrics: (metrics: ServiceMetrics[]) => void;
  selectService: (service: string) => void;

  // Workflows actions
  openExecutionFromServiceMesh: (operationId: string) => void;
  createWorkflow: () => void;
  editWorkflow: (workflow: WorkflowTemplate) => void;
  monitorExecution: (execution: WorkflowExecution) => void;
  backToList: () => void;
}

export const useDashboardStore = create<DashboardState>(
  persist(
    (set, get) => ({
      activeTab: 'service-mesh',

      serviceMeshMetrics: [],
      recentOperations: [],
      selectedService: null,

      myWorkflows: [],
      activeExecutions: [],
      selectedWorkflow: null,
      selectedExecution: null,
      workflowMode: 'list',

      switchTab: (tab) => set({ activeTab: tab }),

      setServiceMeshMetrics: (metrics) =>
        set({ serviceMeshMetrics: metrics }),

      selectService: (service) =>
        set({ selectedService: service }),

      openExecutionFromServiceMesh: (operationId) => {
        // 1. Find execution by operation_id
        const execution = findExecutionByOperationId(operationId);

        // 2. Switch to workflows tab
        set({
          activeTab: 'my-workflows',
          selectedExecution: execution,
          workflowMode: 'monitor'
        });

        // 3. Monitor Mode will open automatically
      },

      createWorkflow: () =>
        set({
          workflowMode: 'design',
          selectedWorkflow: null
        }),

      editWorkflow: (workflow) =>
        set({
          workflowMode: 'design',
          selectedWorkflow: workflow
        }),

      monitorExecution: (execution) =>
        set({
          workflowMode: 'monitor',
          selectedExecution: execution
        }),

      backToList: () =>
        set({
          workflowMode: 'list',
          selectedWorkflow: null,
          selectedExecution: null
        }),
    }),
    {
      name: 'dashboard-storage',
      partialize: (state) => ({
        activeTab: state.activeTab // Persist only active tab
      })
    }
  )
);
```

---

## Component Hierarchy

```
<App>
  └─ <Dashboard>
      ├─ <Header>
      │   ├─ Logo
      │   ├─ User menu
      │   └─ Settings
      │
      ├─ <Tabs>
      │   ├─ Tab "Service Mesh"
      │   └─ Tab "My Workflows"
      │
      ├─ <ServiceMeshTab> (if activeTab === 'service-mesh')
      │   ├─ <SystemHealthCard>
      │   ├─ <ServiceFlowDiagram>
      │   │   ├─ <ServiceNode> (Frontend)
      │   │   ├─ <ServiceNode> (API Gateway)
      │   │   ├─ <ServiceNode> (Orchestrator)
      │   │   ├─ <ServiceNode> (Worker x2) ← Click shows modal
      │   │   │   └─ <ServiceOperationsModal>
      │   │   │       └─ <OperationsTable>
      │   │   └─ <ServiceNode> (RAS Adapter)
      │   └─ <RecentOperationsTable>
      │       └─ onRowClick → openExecutionFromServiceMesh()
      │
      └─ <MyWorkflowsTab> (if activeTab === 'my-workflows')
          ├─ <WorkflowList> (if mode === 'list')
          │   ├─ <WorkflowsTable>
          │   └─ <ActiveExecutionsTable>
          │
          ├─ <WorkflowCanvas mode="design"> (if mode === 'design')
          │   ├─ <NodePalette>
          │   ├─ <ReactFlow>
          │   └─ <PropertyEditor>
          │
          └─ <WorkflowCanvas mode="monitor"> (if mode === 'monitor')
              ├─ <ExecutionHeader>
              ├─ <ProgressBar>
              ├─ <ReactFlow> (read-only + status overlays)
              ├─ <Timeline>
              └─ <TraceViewerModal> (if node clicked)
```

---

## WebSocket Architecture

### Two Independent WebSocket Connections

```
Frontend
  ├─ WebSocket 1: Service Mesh Metrics
  │   ws://localhost:8090/ws/service-mesh
  │   ├─ Connection: Always active when tab visible
  │   ├─ Updates: Every 2 seconds
  │   └─ Data: Aggregated metrics per service
  │
  └─ WebSocket 2: Workflow Execution Status
      ws://localhost:8000/ws/workflow/{execution_id}/
      ├─ Connection: Only when monitoring specific execution
      ├─ Updates: On status change (real-time)
      └─ Data: Node statuses, progress, errors
```

### Connection Management

```typescript
// frontend/src/hooks/useServiceMeshMetrics.ts

export function useServiceMeshMetrics() {
  const activeTab = useDashboardStore(state => state.activeTab);
  const [metrics, setMetrics] = useState<ServiceMetrics[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Only connect when Service Mesh tab is active
    if (activeTab !== 'service-mesh') {
      // Close connection if tab switched
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    // Connect to Metrics Aggregator
    const ws = new WebSocket('ws://localhost:8090/ws/service-mesh');

    ws.onopen = () => {
      console.log('Service Mesh WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const newMetrics: ServiceMetrics[] = JSON.parse(event.data);
      setMetrics(newMetrics);
    };

    ws.onerror = (error) => {
      console.error('Service Mesh WebSocket error:', error);
      setConnected(false);
    };

    ws.onclose = () => {
      console.log('Service Mesh WebSocket closed');
      setConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [activeTab]);

  return { metrics, connected };
}
```

---

## Data Flow Diagrams

### Service Mesh Tab Data Flow

```
Prometheus (metrics storage)
  ↓ scrape every 15s
All Services (expose /metrics)
  ↓
Prometheus (query API)
  ↓ query every 2s
Metrics Aggregator (Go service)
  ↓ aggregate by service
  ↓ WebSocket push
Frontend (Service Mesh Tab)
  ↓ render
User sees real-time service flow
```

### My Workflows Tab Data Flow

```
User action (create/execute/monitor workflow)
  ↓ REST API call
Django Orchestrator (WorkflowEngine)
  ↓ execute workflow
  ↓ create OpenTelemetry traces
  ↓ broadcast via Django Channels
Frontend (My Workflows Tab)
  ↓ WebSocket receives updates
  ↓ update node statuses
User sees live workflow execution
```

### Cross-Tab Navigation Data Flow

```
User click operation in Service Mesh tab
  ↓
Frontend: useDashboardStore.openExecutionFromServiceMesh(operationId)
  ↓
1. Find WorkflowExecution by operation_id
2. Switch activeTab to 'my-workflows'
3. Set selectedExecution
4. Set workflowMode to 'monitor'
  ↓
My Workflows Tab renders Monitor Mode
  ↓
WorkflowCanvas loads execution data
  ↓
WebSocket connects to workflow/{execution_id}/
  ↓
User sees detailed workflow status
```

---

## Responsive Design

### Desktop (> 1200px)

```
┌────────────────────────────────────────────────────────────┐
│  Full width layout                                         │
│  Service Flow: Horizontal layout (left to right)          │
│  Recent Operations: Full table with all columns           │
│  Workflow Canvas: Full size (1000x600px)                  │
└────────────────────────────────────────────────────────────┘
```

### Tablet (768px - 1200px)

```
┌──────────────────────────────────────┐
│  Compact layout                      │
│  Service Flow: Vertical (top-bottom) │
│  Recent Ops: Hide duration column    │
│  Workflow Canvas: Scaled (800x500px) │
└──────────────────────────────────────┘
```

### Mobile (< 768px)

```
┌──────────────────────┐
│  Stack layout        │
│  Service Flow: List  │
│  Recent Ops: Cards   │
│  Workflow: Not ideal │
│  (show warning)      │
└──────────────────────┘
```

**Note:** Workflow Design Mode not recommended for mobile (too complex). Monitor Mode works with simplified view.

---

## Accessibility (a11y)

### Keyboard Navigation

```
Tab 1: Service Mesh
  Tab key        → Navigate between service nodes
  Enter/Space    → Activate node (show operations modal)
  Arrow keys     → Navigate operations table
  Escape         → Close modal

Tab 2: My Workflows
  Tab key        → Navigate between nodes in canvas
  Enter          → Select node
  Arrow keys     → Move selected node (Design Mode)
  Ctrl+Z         → Undo last change (Design Mode)
  Ctrl+S         → Save workflow
```

### Screen Reader Support

```html
<!-- Service Node -->
<div
  role="button"
  aria-label="Worker service, 18 active operations, 2 failed, P95 latency 2.5 seconds"
  tabindex="0"
  onClick={handleClick}
>
  <span aria-hidden="true">⚡ 18 active</span>
  <span className="sr-only">18 active operations</span>
</div>

<!-- Workflow Node -->
<div
  role="treeitem"
  aria-label="Lock Jobs node, status completed, duration 0.8 seconds"
  aria-selected={selected}
  tabindex="0"
>
  ...
</div>
```

### Color Contrast

```css
/* WCAG AA compliant colors */

.status-pending {
  background: #6B7280; /* gray-500 */
  color: #FFFFFF;
}

.status-running {
  background: #3B82F6; /* blue-500 */
  color: #FFFFFF;
}

.status-completed {
  background: #10B981; /* green-500 */
  color: #FFFFFF;
}

.status-failed {
  background: #EF4444; /* red-500 */
  color: #FFFFFF;
}
```

---

## Performance Optimizations

### Service Mesh Tab

**1. Throttle WebSocket Updates**
```typescript
const throttledUpdate = useThrottle(
  (metrics: ServiceMetrics[]) => setMetrics(metrics),
  100 // Max 10 updates/second
);
```

**2. Memoize Service Nodes**
```typescript
const MemoizedServiceNode = React.memo(ServiceNode, (prev, next) => {
  return (
    prev.metrics.activeRequests === next.metrics.activeRequests &&
    prev.metrics.failedRequests === next.metrics.failedRequests
  );
});
```

**3. Virtualize Operations Table**
```typescript
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={400}
  itemCount={operations.length}
  itemSize={50}
>
  {({ index, style }) => (
    <OperationRow operation={operations[index]} style={style} />
  )}
</FixedSizeList>
```

### My Workflows Tab

**1. Lazy Load Traces**
```typescript
// Only load trace when node clicked
const loadTrace = async (nodeId: string) => {
  const trace = await jaegerApi.getTrace(executionId, nodeId);
  setSelectedTrace(trace);
};

<OperationNode onClick={() => loadTrace(node.id)} />
```

**2. Memoize React Flow Nodes**
```typescript
const memoizedNodes = useMemo(
  () => convertToReactFlowNodes(workflow.dag_structure.nodes),
  [workflow.dag_structure]
);
```

**3. Debounce Property Editor Updates**
```typescript
const debouncedSave = useDebouncedCallback(
  (nodeId: string, properties: any) => {
    updateNodeProperties(nodeId, properties);
  },
  500 // Wait 500ms after last change
);
```

---

## Security Considerations

### Tab Permissions

```typescript
// Role-based tab visibility

interface UserRole {
  canViewServiceMesh: boolean;
  canViewWorkflows: boolean;
  canCreateWorkflows: boolean;
  canExecuteWorkflows: boolean;
}

// Admin
const adminRole: UserRole = {
  canViewServiceMesh: true,   // ✅ Can see system-wide view
  canViewWorkflows: true,
  canCreateWorkflows: true,
  canExecuteWorkflows: true,
};

// Business User
const userRole: UserRole = {
  canViewServiceMesh: false,  // ❌ Cannot see system internals
  canViewWorkflows: true,
  canCreateWorkflows: true,
  canExecuteWorkflows: true,
};

// Operator
const operatorRole: UserRole = {
  canViewServiceMesh: true,
  canViewWorkflows: true,
  canCreateWorkflows: false,  // ❌ Read-only
  canExecuteWorkflows: true,
};
```

### WebSocket Authentication

```typescript
// Add auth token to WebSocket connection

const ws = new WebSocket(
  `ws://localhost:8090/ws/service-mesh?token=${authToken}`
);

// Backend validates token
func handleWebSocket(w http.ResponseWriter, r *http.Request) {
  token := r.URL.Query().Get("token")

  if !validateToken(token) {
    http.Error(w, "Unauthorized", 401)
    return
  }

  // Upgrade to WebSocket
  conn, _ := upgrader.Upgrade(w, r, nil)
  // ...
}
```

---

## Mobile Experience

### Service Mesh Tab (Mobile)

```
┌──────────────────────┐
│ Service Mesh         │
├──────────────────────┤
│                      │
│ System Health        │
│ 🟢 Healthy           │
│ 234 ops/min          │
│                      │
├──────────────────────┤
│ Services (Cards)     │
│                      │
│ ┌──────────────────┐ │
│ │ Frontend         │ │
│ │ ↓ 20 ops/min     │ │
│ │ ⏱ 45ms P95       │ │
│ └──────────────────┘ │
│                      │
│ ┌──────────────────┐ │
│ │ Worker           │ │
│ │ ⚡ 18 active     │ │
│ │ ✗ 2 failed      │ │
│ └──────────────────┘ │
│                      │
│ Recent Ops           │
│ ┌──────────────────┐ │
│ │ Install Ext      │ │
│ │ ⚡ Running 45s   │ │
│ └──────────────────┘ │
└──────────────────────┘
```

### My Workflows Tab (Mobile)

```
┌──────────────────────┐
│ My Workflows         │
├──────────────────────┤
│                      │
│ ⚠️ Design Mode      │
│ not optimized        │
│ for mobile.          │
│ Use desktop.         │
│                      │
├──────────────────────┤
│ Monitor Mode (OK)    │
│                      │
│ Workflow Progress    │
│ ████████▒▒ 60%       │
│                      │
│ Current Step:        │
│ Install Extension    │
│ ⚡ 45.2s             │
│                      │
│ ┌──────────────────┐ │
│ │ Step 1 ✓ 0.8s   │ │
│ │ Step 2 ✓ 2.3s   │ │
│ │ Step 3 ⚡ 45s    │ │
│ │ Step 4 ○ Pend   │ │
│ └──────────────────┘ │
└──────────────────────┘
```

---

## Error States

### Service Mesh Tab Errors

**1. Prometheus Unavailable**
```
┌─────────────────────────────────────┐
│ ⚠️ Service Mesh Unavailable         │
│                                     │
│ Cannot connect to metrics backend.  │
│                                     │
│ Possible causes:                    │
│ • Prometheus is down                │
│ • Metrics Aggregator is down        │
│ • Network issue                     │
│                                     │
│ [Retry] [View Logs] [Switch to     │
│          My Workflows tab]          │
└─────────────────────────────────────┘
```

**2. WebSocket Disconnected**
```
┌─────────────────────────────────────┐
│ 🔴 Live Updates Disconnected        │
│                                     │
│ Reconnecting in 5s...               │
│                                     │
│ [Reconnect Now]                     │
└─────────────────────────────────────┘
```

### My Workflows Tab Errors

**1. Workflow Execution Failed**
```
Monitor Mode:

┌──────────────┐
│ Install Ext  │ ✗ FAILED
│              │ Timeout after 60s
└──────┬───────┘
       │
       └─ Click to see error details
```

**2. Cannot Load Workflow**
```
┌─────────────────────────────────────┐
│ ❌ Failed to Load Workflow          │
│                                     │
│ Workflow "abc-123" not found.       │
│                                     │
│ [Go Back] [View All Workflows]     │
└─────────────────────────────────────┘
```

---

## Integration with Existing Features

### Grafana Dashboards

**Service Mesh Tab complements Grafana:**

| Feature | Service Mesh Tab | Grafana |
|---------|------------------|---------|
| **Real-time updates** | ✅ 2s (WebSocket) | ⚠️ 15s (scrape interval) |
| **Visual service flow** | ✅ Yes | ❌ No |
| **Click to drill down** | ✅ → Workflows tab | ❌ No |
| **Historical data** | ❌ Last 5 min only | ✅ Unlimited |
| **Custom queries** | ❌ No | ✅ PromQL |
| **Alerting** | ❌ No | ✅ Yes |

**Use Case Distribution:**
- **Service Mesh Tab:** Real-time monitoring, quick drill-down, user-friendly
- **Grafana:** Historical analysis, custom queries, alerting, deep metrics

### Jaeger UI

**My Workflows Tab complements Jaeger:**

| Feature | Workflows Tab | Jaeger UI |
|---------|---------------|-----------|
| **Workflow context** | ✅ Shows workflow DAG | ❌ Just spans |
| **Live status** | ✅ WebSocket updates | ❌ Static |
| **User-friendly** | ✅ Simplified view | ⚠️ Technical |
| **Detailed traces** | ⚠️ Basic timeline | ✅ Full detail |
| **Search/Filter** | ⚠️ Limited | ✅ Advanced |

**Use Case Distribution:**
- **Workflows Tab:** Quick debugging, workflow context, user-friendly
- **Jaeger UI:** Deep dive, advanced search, correlation analysis

---

## Summary

### What We Get with Two-Tab Interface

**Tab 1: Service Mesh Monitor**
- ✅ System-wide visibility (all services, all operations)
- ✅ Real-time metrics (ops/min, latency, errors)
- ✅ Click service → filter operations
- ✅ Click operation → drill down to workflow

**Tab 2: My Workflows**
- ✅ Workflow management (create, edit, execute)
- ✅ Design Mode (visual workflow builder)
- ✅ Monitor Mode (live execution status)
- ✅ Trace Mode (debugging with Jaeger)

**Cross-Tab Navigation:**
- ✅ Seamless switching between system view and workflow view
- ✅ Auto-switch when clicking operations
- ✅ State preservation (no data loss)

**Benefits:**
- ✅ Complete observability (system + workflow levels)
- ✅ Unified platform (one UI, one login, one deployment)
- ✅ Role-based (admins → Service Mesh, users → Workflows)
- ✅ Incremental adoption (can use one tab without the other)

---

**Next:** Implementation in Week 16 (see [UNIFIED_WORKFLOW_ROADMAP.md](roadmaps/UNIFIED_WORKFLOW_ROADMAP.md))
