# Unified Workflow Platform with Service Mesh - Quick Summary

**Version:** 2.0
**Date:** 2025-11-23
**Status:** APPROVED - Two-Tab Interface
**Full Design:** [UNIFIED_WORKFLOW_VISUALIZATION.md](architecture/UNIFIED_WORKFLOW_VISUALIZATION.md)
**Roadmap:** [UNIFIED_WORKFLOW_ROADMAP.md](roadmaps/UNIFIED_WORKFLOW_ROADMAP.md) *(updating)*

---

## 🎯 What Changed

### Version 1.0 (Original)
- ✅ Workflow Design + Monitor modes
- ✅ OpenTelemetry tracing
- ❌ NO Service Mesh view

### Version 2.0 (Extended) ⭐ CURRENT
- ✅ Workflow Design + Monitor modes
- ✅ OpenTelemetry tracing
- ✅ **Service Mesh Monitor** (NEW!)
- ✅ **Two-Tab Interface** (NEW!)

---

## 📐 Two-Tab Interface

```
┌────────────────────────────────────────────────────────────┐
│  CommandCenter1C Dashboard                                 │
├────────────────────────────────────────────────────────────┤
│  Tabs: [🌐 Service Mesh] [📋 My Workflows]                │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Tab 1: Service Mesh Monitor                               │
│  ================================                           │
│  System-wide aggregate view:                               │
│  • Real-time service flow (Frontend → API → Worker → RAS) │
│  • Operations/min per service                              │
│  • Latency metrics (P50, P95, P99)                         │
│  • Active/Failed operations counters                       │
│  • Recent operations table                                 │
│  • Click operation → auto-switch to Workflows tab          │
│                                                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Tab 2: My Workflows                                       │
│  ================================                           │
│  Workflow-specific design + monitoring:                    │
│  • List of user's workflows                                │
│  • Create/Edit workflows (Design Mode - React Flow)        │
│  • Execute workflows                                       │
│  • Monitor executions (Monitor Mode - Live status)         │
│  • Click node → Jaeger traces                              │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 🔄 Navigation Flow

### Service Mesh → Workflows

```
1. User в Service Mesh tab
2. Видит "Install Extension" operation failed (✗)
3. Click на operation row
4. ✨ Automatically switches to "My Workflows" tab
5. Opens Monitor Mode for that execution
6. Видит детальный статус nodes + traces
```

### Workflows → Service Mesh

```
1. User в My Workflows tab
2. Запустил workflow
3. Хочет видеть system-wide impact
4. Click на "Service Mesh" tab
5. Видит current system load
6. Может вернуться к monitoring workflow
```

---

## 🎨 Use Cases

### Use Case 1: Admin Monitoring System

**Persona:** System Administrator

**Flow:**
1. Opens CommandCenter1C
2. **Service Mesh tab** открыт по умолчанию
3. Видит:
   - 🟢 System healthy
   - Worker: 18 active operations
   - 2 failed operations в последние 5 минут
4. Click на failed operation → Auto-switch to Workflows tab
5. Видит что Extension Install упал на "Terminate Sessions" step
6. Click на node → Jaeger trace показывает timeout
7. Фиксит проблему (увеличивает timeout)
8. Re-run workflow из того же UI

### Use Case 2: Business User Creating Workflow

**Persona:** Business Analyst

**Flow:**
1. Opens CommandCenter1C
2. Click **My Workflows tab**
3. Click "+ Create Workflow"
4. Drag & drop nodes (Validate Excel → Parse → Import → Report)
5. Connect nodes
6. Save workflow
7. Click "Run"
8. Monitor Mode opens (live status updates)
9. Workflow completes successfully
10. *(Optional)* Switch to Service Mesh tab → see system impact

### Use Case 3: Debugging Failed Workflow

**Persona:** DevOps Engineer

**Flow:**
1. Opens **Service Mesh tab**
2. Sees spike in latency on Worker service
3. Click Worker node → Filters operations
4. Sees 5 "Upload Price List" workflows running
5. Click одну из них → Switches to Workflows tab
6. Monitor Mode показывает node "Create Items" застрял
7. Click на node → Jaeger trace
8. Trace показывает OData batch timeout (> 15s)
9. Identifies problem: слишком большой batch size
10. Edit workflow → Add batch size limit
11. Re-run with new config

---

## 📊 Benefits Comparison

| Benefit | Single Tab | Two-Tab Interface ⭐ |
|---------|-----------|---------------------|
| **System Overview** | ❌ | ✅ Service Mesh tab |
| **Workflow Design** | ✅ | ✅ My Workflows tab |
| **Workflow Monitor** | ✅ | ✅ My Workflows tab |
| **Trace Debugging** | ✅ | ✅ Both tabs |
| **Cross-Navigation** | ❌ | ✅ Auto-switch |
| **Role Separation** | ❌ | ✅ Tab-based |
| **Context Preservation** | ❌ | ✅ Each tab separate |

---

## 🔧 Technical Components

### Service Mesh Tab

**Backend:**
```
Metrics Aggregator (Go, port 8090)
  ↓ Query Prometheus every 2s
  ↓ Aggregate metrics by service
  ↓ Push via WebSocket to frontend
```

**Frontend:**
```typescript
<ServiceMeshTab>
  <SystemHealthCard />
  <ServiceFlowDiagram>
    <ServiceNode service="worker" metrics={...} />
  </ServiceFlowDiagram>
  <RecentOperationsTable
    onRowClick={openInWorkflowsTab}
  />
</ServiceMeshTab>
```

### My Workflows Tab

**Backend:**
```
WorkflowEngine (Django)
  ↓ Execute workflows
  ↓ Create OpenTelemetry traces
  ↓ Broadcast status via Django Channels (WebSocket)
```

**Frontend:**
```typescript
<MyWorkflowsTab>
  <WorkflowList />
  <WorkflowCanvas mode={mode}>
    {mode === 'design' && <DesignView />}
    {mode === 'monitor' && <MonitorView />}
  </WorkflowCanvas>
</MyWorkflowsTab>
```

### Integration

```typescript
// State management connects both tabs
interface DashboardState {
  activeTab: 'service-mesh' | 'my-workflows';

  openExecutionFromServiceMesh: (operationId) => {
    // Find workflow execution
    // Switch to 'my-workflows' tab
    // Open Monitor Mode
  }
}
```

---

## ⏱️ Updated Timeline

### Previous: 17 weeks
- Phase 3: Week 12-15 (Real-Time Integration)
- Phase 4: Week 16-17 (Polish)

### New: 18 weeks ⭐
- Phase 3: Week 12-16 (Real-Time Integration + Service Mesh)
  - Week 12: OpenTelemetry
  - Week 13: WebSocket
  - Week 14: React Flow Design Mode
  - Week 15: React Flow Monitor Mode
  - **Week 16: Service Mesh Monitor** (NEW!)
- Phase 4: Week 17-18 (Polish & Documentation)

**Additional work:** +1 week (Service Mesh Monitor component)

---

## 📋 Week 16 Tasks (Service Mesh Monitor)

### Day 1-2: Metrics Aggregator Service (Go)

**Create:**
```
go-services/metrics-aggregator/
├── cmd/main.go
├── internal/
│   ├── prometheus/client.go
│   ├── aggregator/aggregator.go
│   └── websocket/server.go
├── go.mod
└── go.sum
```

**Implementation:**
- Query Prometheus for service metrics (PromQL)
- Aggregate by service
- Expose WebSocket endpoint `/ws/service-mesh`
- Push updates every 2 seconds

### Day 3: Frontend ServiceFlowDiagram

**Create:**
```typescript
frontend/src/components/service-mesh/
├── ServiceMeshTab.tsx
├── SystemHealthCard.tsx
├── ServiceFlowDiagram.tsx
├── ServiceNode.tsx
└── RecentOperationsTable.tsx
```

**Features:**
- Visual service flow diagram
- Real-time metrics display
- Click service → filter operations
- WebSocket consumer

### Day 4: Tab Navigation Integration

**Tasks:**
- Implement tab switching (Ant Design Tabs)
- Connect Service Mesh → Workflows navigation
- State management (Zustand)
- Test cross-tab navigation

### Day 5: Testing + Polish

**Tasks:**
- Unit tests for components
- Integration tests (WebSocket)
- E2E tests (Playwright)
- UI polish (animations, colors)

---

## 🎯 Success Metrics (Updated)

### Service Mesh Tab

| Metric | Target |
|--------|--------|
| **WebSocket Uptime** | > 99.9% |
| **Update Latency** | < 100ms from Prometheus query |
| **Concurrent Connections** | > 50 users |
| **Metrics Accuracy** | 100% (vs direct Prometheus query) |

### Cross-Tab Navigation

| Metric | Target |
|--------|--------|
| **Switch Time** | < 200ms |
| **State Preservation** | 100% (no data loss) |
| **Auto-Switch Accuracy** | 100% (finds correct execution) |

---

## 🚀 Next Steps

### Immediate

1. **Review updated documents:**
   - [UNIFIED_WORKFLOW_VISUALIZATION.md](architecture/UNIFIED_WORKFLOW_VISUALIZATION.md) v2.0
   - [UNIFIED_WORKFLOW_ROADMAP.md](roadmaps/UNIFIED_WORKFLOW_ROADMAP.md) *(updating)*

2. **Approve Two-Tab Interface design**

3. **Begin Phase 2 (Week 5):**
   - Start with Workflow Engine backend
   - Service Mesh Monitor comes in Week 16

### Phase 2-3 (Week 5-15)

Focus on Workflow Engine:
- Backend implementation (Week 5-11)
- OpenTelemetry + WebSocket (Week 12-13)
- React Flow Design + Monitor (Week 14-15)

### Week 16 (NEW!)

Add Service Mesh Monitor:
- Metrics Aggregator service
- Service Flow visualization
- Recent operations table
- Cross-tab navigation

---

## ❓ FAQs

**Q: Can we skip Service Mesh and only implement Workflows?**
A: YES! Week 16 is optional. You can stop at Week 15 (MVP: workflows only) and add Service Mesh later if needed.

**Q: Will Service Mesh work without Workflows?**
A: YES! Service Mesh Monitor is standalone. But cross-navigation to Workflows tab won't work without Workflow Engine.

**Q: Which tab will users see first?**
A: **Service Mesh** tab by default (shows system overview). Users can switch to Workflows tab when needed.

**Q: Can different users see different default tabs?**
A: YES! Can be role-based: Admins → Service Mesh, Business Users → My Workflows.

---

**Decision:** ✅ APPROVED - Two-Tab Interface with Service Mesh Monitor

**Next:** Update [UNIFIED_WORKFLOW_ROADMAP.md](roadmaps/UNIFIED_WORKFLOW_ROADMAP.md) to include Week 16 details
