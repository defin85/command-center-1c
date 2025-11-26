# Unified Workflow Visualization Platform - Roadmap

**Version:** 2.1
**Date:** 2025-11-26
**Status:** Approved for Implementation - Extended with Service Mesh
**Total Duration:** 18 weeks (4.5 months)
**Design Doc:** [UNIFIED_WORKFLOW_VISUALIZATION.md](../architecture/UNIFIED_WORKFLOW_VISUALIZATION.md) v2.0
**Summary:** [UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md](../UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Phase 1: Foundation ✅](#phase-1-foundation-)
- [Phase 2: Workflow Engine Backend](#phase-2-workflow-engine-backend)
- [Phase 3: Real-Time Integration](#phase-3-real-time-integration)
- [Phase 4: Polish & Migration](#phase-4-polish--migration)
- [Success Metrics](#success-metrics)
- [Risk Mitigation](#risk-mitigation)
- [MVP vs Full Feature Set](#mvp-vs-full-feature-set)

---

## Overview

### Goals

1. **Объединить** Track 1.5 (Workflow Engine) + Real-Time Tracking в единую платформу
2. **Создать** универсальный UI для design и runtime modes
3. **Интегрировать** OpenTelemetry tracing для debugging
4. **Добавить** Service Mesh Monitor для system-wide visibility (NEW!)
5. **Мигрировать** Worker State Machine на explicit workflows

### Key Deliverables

| Deliverable | Description | Phase |
|-------------|-------------|-------|
| **Workflow Engine Backend** | DAG execution, validation, REST API | Phase 2 |
| **OpenTelemetry Integration** | Distributed tracing для workflows | Phase 3 |
| **Unified UI (Workflows Tab)** | Design + Monitor modes | Phase 3 |
| **Service Mesh Monitor** | Aggregate view всех микросервисов (NEW!) | Phase 3 |
| **Two-Tab Interface** | Service Mesh + My Workflows tabs (NEW!) | Phase 3 |
| **Worker Migration** | Explicit workflows для admin tasks | Phase 4 |

### Timeline Summary

```
Week 1-4:   Phase 1 - Foundation ✅ COMPLETE
Week 5-11:  Phase 2 - Workflow Engine Backend (7 weeks) 🔄 IN PROGRESS
            • Week 5: Models + Migrations ✅ COMPLETE (2025-11-23)
            • Week 6: DAGValidator + Kahn's Algorithm ✅ COMPLETE (2025-11-23)
            • Week 7: NodeHandlers (Part 1) ✅ COMPLETE (2025-11-23)
            • Week 8: NodeHandlers (Part 2) ✅ COMPLETE (2025-11-26)
            • Week 9: WorkflowEngine + DAGExecutor ✅ COMPLETE (2025-11-26)
            • Week 10: REST API ⏳ NEXT
            • Week 11: Celery Tasks + Testing
Week 12-16: Phase 3 - Real-Time Integration + Service Mesh (5 weeks)
            • Week 12: OpenTelemetry
            • Week 13: WebSocket
            • Week 14: React Flow Design Mode
            • Week 15: React Flow Monitor Mode
            • Week 16: Service Mesh Monitor ⭐ NEW
Week 17-18: Phase 4 - Polish & Migration (2 weeks)

Total: 18 weeks (4.5 months)
Progress: Week 9/18 (50% complete)
```

---

## Phase 1: Foundation ✅

**Duration:** Week 1-4
**Status:** ✅ COMPLETE (2025-11-23)

### Achievements

- ✅ RAS Adapter deployed (Week 4)
- ✅ Manual testing gate passed (Week 4.5)
- ✅ Sessions-deny implemented (Week 4.6)
- ✅ Worker State Machine working (89 tests pass)
- ✅ Correlation ID exists in Worker
- ✅ Prometheus + Grafana running

### Validation

```bash
# Verify foundation ready
curl http://localhost:8088/health  # RAS Adapter
curl http://localhost:9090/-/healthy  # Prometheus
docker ps | grep worker  # Worker running
```

**Result:** ✅ All prerequisites met for Phase 2

---

## Phase 2: Workflow Engine Backend

**Duration:** Week 5-11 (7 weeks)
**Goal:** Implement Track 1.5 backend WITHOUT UI
**Focus:** Core workflow execution engine

### Week 5: Models + Migrations ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-23
**Commit:** 926b408

#### Tasks

**Day 1-2: Django Models**
- [x] Create `WorkflowTemplate` model
  - Fields: id, name, description, workflow_type, dag_structure, config, is_valid
  - Validation: Pydantic SchemaField for dag_structure
  - Indexes: workflow_type, is_active
- [x] Create `WorkflowExecution` model
  - Fields: id, workflow_template, input_context, status, current_node_id
  - Add: node_statuses (JSONField for real-time tracking)
  - Add: trace_id (for OpenTelemetry integration)
  - Add: FSM state machine (django-fsm-2)
- [x] Create `WorkflowStepResult` model
  - Fields: id, workflow_execution, node_id, status, input_data, output_data
  - Add: span_id, trace_id (for tracing)
- [x] Generate migrations (0002, 0003)
- [x] Apply migrations to dev database

**Day 3-4: Unit Tests**
- [x] Test model creation (33 tests total)
- [x] Test model validation (Pydantic + FSM)
- [x] Test JSON schema validation
- [x] Test relationships (ForeignKey, related_name)
- [x] Test progress_percent property
- [x] Test get_node_status() method
- [x] Test FSM transitions (start, complete, fail, cancel)
- [x] Test race condition protection (SELECT FOR UPDATE)

**Day 5: Documentation**
- [x] Document model fields (MODELS_DOCUMENTATION.md)
- [x] Create ER diagram (in documentation)
- [x] Document JSON schema for dag_structure
- [x] Example workflows (extension install, price list upload)
- [x] Worktree setup guides (PORTS_CONFIGURATION.md, QUICK_START_WEEK5.md)

**Deliverable:** ✅ Django models ready, migrations applied, 33 tests passing, 87% coverage

```bash
# Validation
python manage.py migrate
python manage.py test apps.templates.tests.test_models
```

---

### Week 6: DAGValidator + Kahn's Algorithm ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-23
**Commit:** 22c4485

#### Tasks

**Day 1-2: DAGValidator Implementation**
- [x] Create `DAGValidator` class (629 lines)
- [x] Implement `validate()` method (8-step validation process)
  - Check nodes exist
  - Validate edges reference existing nodes
  - Check for cycles (Kahn's algorithm)
  - Check connectivity (BFS)
  - Validate node types
  - Check isolated nodes
  - Count components (iterative DFS)
  - Validate topology (start/end nodes)
- [x] Implement `_topological_sort()` using Kahn's algorithm O(V+E)
- [x] Create `ValidationResult` dataclass with add_error/warning/info methods
- [x] Create `ValidationIssue` dataclass (severity, message, node_ids, details)
- [x] Custom exceptions: `CycleDetectedError`, `UnreachableNodeError`, `InvalidNodeTypeError`, `InvalidEdgeError`, `DAGValidationError`

**Day 3: Unit Tests**
- [x] Test empty DAG (caught by Pydantic)
- [x] Test valid linear DAG (A → B → C)
- [x] Test DAG with cycle (2-node, 3-node, subgraph)
- [x] Test DAG with unreachable nodes
- [x] Test invalid node type
- [x] Test missing required fields (template_id via Pydantic)
- [x] Test topological sort order correctness
- [x] Test diamond DAG (multiple paths)
- [x] Test fork-join pattern, tree structure
- [x] Test self-loops detection

**Day 4: Integration Tests**
- [x] Test validation via WorkflowTemplate.validate()
- [x] Test error aggregation (multiple errors)
- [x] Test error messages are clear with node_ids
- [x] Test performance: 100 nodes (< 0.5s), 500 nodes (< 2s), 1000 nodes (< 3s)
- [x] Test deeply nested DAG (no stack overflow with iterative DFS)

**Day 5: Documentation**
- [x] Document Kahn's algorithm (VALIDATOR_README.md)
- [x] Document BFS connectivity check
- [x] Document DFS component counting
- [x] Examples of valid/invalid DAGs
- [x] Performance benchmarks (100-1000 nodes)
- [x] Integration guide with WorkflowTemplate

**Deliverable:** ✅ DAGValidator working, validates complex workflows, 39 tests passing, 89% coverage

```bash
# Validation
pytest apps/templates/tests/test_validator.py -v
pytest apps/templates/tests/test_validator_integration.py -v
```

---

### Week 7: NodeHandlers (Part 1) ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-23
**Commit:** 740ac45

#### Tasks

**Day 1: NodeHandlerFactory**
- [x] Create `NodeHandlerFactory` class (registry + singleton pattern)
- [x] Registry pattern for node types (dict-based registry)
- [x] Method: `get_handler(node_type: str) -> BaseNodeHandler`
- [x] Thread-safe singleton creation (threading.Lock + double-checked locking)
- [x] Auto-registration при module import

**Day 2: OperationHandler**
- [x] Create `OperationHandler` class
- [x] Create `BaseNodeHandler` ABC
- [x] Create `NodeExecutionResult` dataclass
- [x] Implement `execute()` method
  - Get OperationTemplate by template_id ✅
  - Render template with context (TemplateRenderer from Track 1) ✅
  - Return rendered data as output ✅
  - BatchOperation + Celery → TODO Week 9
- [x] Error handling (template not found, render error, execution error)
- [x] WorkflowStepResult audit trail

**Day 3: ConditionHandler**
- [x] Create `ConditionHandler` class
- [x] Implement `execute()` method
  - Get expression from node.config.expression ✅
  - Render with ImmutableSandboxedEnvironment ✅
  - Convert to boolean (_to_bool helper) ✅
  - Return boolean as output ✅
- [x] Use ImmutableSandboxedEnvironment (security)
- [x] Handle edge cases (invalid syntax, undefined vars)
- [x] Added expression field to NodeConfig (Pydantic schema)
- [x] Added expression validation for condition nodes

**Day 4: Unit Tests**
- [x] Test OperationHandler with mock TemplateRenderer (5 tests)
- [x] Test OperationHandler with real OperationTemplate (3 tests)
- [x] Test ConditionHandler with various expressions (9 tests)
  - Simple: `{{ True }}`, `{{ False }}`
  - Variables: `{{ amount > 100 }}`
  - Complex: `{{ status == 'approved' and amount > 1000 }}`
  - Edge cases: undefined vars, invalid syntax, filters
- [x] Test _to_bool conversions (bool, str, int, None, collections)
- [x] Test NodeHandlerFactory (registry, singleton, thread-safety)

**Day 5: Integration Tests**
- [x] Test OperationHandler E2E (с TemplateRenderer)
- [x] Test ConditionHandler with workflow context
- [x] Test error propagation (template not found, render errors)
- [x] Test security (sandbox prevents dangerous operations)
- [x] Test thread safety (concurrent handler creation)
- [x] Test Unicode/Cyrillic data handling

**Deliverable:** ✅ OperationHandler + ConditionHandler working, 30 tests passing, 90% coverage

```bash
# Validation
pytest apps/templates/tests/test_handlers.py::TestOperationHandler -v
pytest apps/templates/tests/test_handlers.py::TestConditionHandler -v
```

---

### Week 8: NodeHandlers (Part 2) ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-26
**Commit:** 7e6685d

#### Tasks

**Day 1-2: ParallelHandler**
- [x] Create `ParallelHandler` class
- [x] Implement `execute()` method
  - Create Celery group for parallel nodes
  - Execute all nodes concurrently
  - Wait for results (all, any, or N)
  - Aggregate results
- [x] Error handling (some nodes fail, timeout)

**Day 3: LoopHandler**
- [x] Create `LoopHandler` class
- [x] Implement `execute()` method
  - Mode: count (repeat N times)
  - Mode: while (condition-based)
  - Mode: foreach (iterate over items)
  - Safety limit: max_iterations (prevent infinite loops)
- [x] Update context with loop_index, loop_item

**Day 4: SubWorkflowHandler**
- [x] Create `SubWorkflowHandler` class
- [x] Implement `execute()` method
  - Get sub-workflow template
  - Map input context (parent → child)
  - Execute sub-workflow (RECURSIVE!)
  - Map output context (child → parent)
  - Track depth (safety limit: max_depth=20)

**Day 5: Unit Tests**
- [x] Test ParallelHandler with 3+ nodes
- [x] Test ParallelHandler with wait_for modes
- [x] Test LoopHandler count mode
- [x] Test LoopHandler while mode (with exit condition)
- [x] Test LoopHandler foreach mode
- [x] Test SubWorkflowHandler recursion (2-3 levels)
- [x] Test SubWorkflowHandler max depth limit

**Deliverable:** ✅ All 5 NodeHandlers working, 128 tests passing, 90% coverage

**Additional achievements:**
- Refactored handlers.py into modular handlers/ directory
- Added Pydantic schemas: ParallelConfig, LoopConfig, SubWorkflowConfig
- Thread-safe NodeHandlerFactory with double-checked locking
- Sandboxed Jinja2 for condition evaluation

```bash
# Validation
pytest apps/templates/workflow/tests/ -v  # 128 tests passed
```

---

### Week 9: WorkflowEngine + DAGExecutor ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-26

#### Tasks

**Day 1-2: DAGExecutor + ContextManager**
- [x] Create `ContextManager` class (context.py)
  - Immutable context management with deep copy
  - Dot notation access (node_1.output.field)
  - Jinja2 template interpolation (sandboxed)
  - Thread-safe singleton for Jinja env (double-checked locking)
- [x] Create `DAGExecutor` class (executor.py)
- [x] Implement `execute()` method
  - Get topological order from DAGValidator
  - Execute nodes in order
  - Handle conditional branches
  - Update WorkflowExecution.current_node_id
  - Store results in WorkflowStepResult
  - Handle failures (stop execution, record error_node_id)

**Day 3: WorkflowEngine**
- [x] Create `WorkflowEngine` class (engine.py)
- [x] Implement `execute_workflow()` method
  - Create WorkflowExecution record
  - Validate DAG
  - Initialize context (ContextManager)
  - Execute DAG (DAGExecutor)
  - Mark as completed/failed
  - Return WorkflowExecution
- [x] Implement `cancel_workflow()` method
- [x] Implement `get_execution_status()` method
- [x] Thread-safe singleton pattern

**Day 4: Celery Tasks**
- [x] `execute_workflow_node` task (single node execution)
- [x] `execute_workflow_async` task (full workflow async)
- [x] `execute_parallel_nodes` task (Celery group)
- [x] `cancel_workflow_async` task
- [x] Recoverable exceptions only for retry

**Day 5: Unit Tests**
- [x] Test ContextManager (75 tests)
- [x] Test DAGExecutor (19 tests)
- [x] Test WorkflowEngine (29 tests)
- [x] Test Celery tasks

**Deliverable:** ✅ WorkflowEngine working, 251 tests passing, 90%+ coverage

**Files created/updated:**
- `orchestrator/apps/templates/workflow/context.py` (NEW)
- `orchestrator/apps/templates/workflow/executor.py` (NEW)
- `orchestrator/apps/templates/workflow/engine.py` (UPDATED)
- `orchestrator/apps/templates/tasks.py` (UPDATED)

```bash
# Validation
pytest apps/templates/workflow/tests/ -v  # 251 tests passed
```

---

### Week 10: REST API

**Effort:** 5 days

#### Tasks

**Day 1: ViewSets**
- [ ] Create `WorkflowTemplateViewSet`
  - CRUD endpoints (list, create, retrieve, update, delete)
  - Custom action: `validate` (POST /templates/{id}/validate/)
- [ ] Create `WorkflowExecutionViewSet`
  - List, retrieve executions
  - Custom action: `execute` (POST /executions/)
  - Custom action: `cancel` (POST /executions/{id}/cancel/)
  - Custom action: `steps` (GET /executions/{id}/steps/)

**Day 2: Serializers**
- [ ] Create `WorkflowTemplateSerializer`
- [ ] Create `WorkflowExecutionSerializer`
- [ ] Create `WorkflowStepResultSerializer`
- [ ] Validation: dag_structure JSON schema
- [ ] Nested serializers for related objects

**Day 3: Permissions + Authentication**
- [ ] Permission classes (IsAuthenticated, IsAdminUser for dangerous actions)
- [ ] Filter workflows by user (if needed)
- [ ] Rate limiting (Django REST framework throttle)

**Day 4: API Tests**
- [ ] Test CRUD operations
- [ ] Test validation endpoint
- [ ] Test execute endpoint (sync + async modes)
- [ ] Test cancel endpoint
- [ ] Test permissions (authenticated vs anonymous)
- [ ] Test error responses (400, 404, 500)

**Day 5: API Documentation**
- [ ] Generate OpenAPI schema (drf-spectacular)
- [ ] Swagger UI at /api/docs/
- [ ] Example requests/responses
- [ ] Postman collection

**Deliverable:** REST API complete, documented

```bash
# Validation
pytest apps/templates/tests/test_api.py -v
curl http://localhost:8000/api/docs/  # Swagger UI
```

---

### Week 11: Celery Tasks + Testing

**Effort:** 5 days

#### Tasks

**Day 1-2: Celery Tasks**
- [ ] Create `execute_workflow_task` (async workflow execution)
- [ ] Create `execute_workflow_node` (for ParallelHandler)
- [ ] Add retry logic (max_retries=3, countdown=60)
- [ ] Add error handling (capture exceptions, store in execution)
- [ ] Add progress tracking (update execution.current_node_id)

**Day 3: Performance Testing**
- [ ] Benchmark simple workflow (2-3 nodes)
- [ ] Benchmark complex workflow (10+ nodes, parallel, loops)
- [ ] Benchmark parallel execution (10 nodes concurrently)
- [ ] Measure latency (P50, P95, P99)
- [ ] Measure throughput (workflows/min)

**Day 4: Load Testing**
- [ ] Locust script for workflow execution
- [ ] Test 10 concurrent workflows
- [ ] Test 50 concurrent workflows
- [ ] Test 100 concurrent workflows
- [ ] Identify bottlenecks (database, Celery, Worker)

**Day 5: Integration Testing**
- [ ] Test complete flow: API → Celery → Worker → RAS
- [ ] Test extension install workflow (real RAS + 1C)
- [ ] Test failure scenarios (RAS unavailable, timeout)
- [ ] Test rollback (if workflow fails mid-execution)

**Deliverable:** Workflow Engine ready for production (backend only)

```bash
# Validation
pytest apps/templates/tests/ -v --cov=apps.templates --cov-report=html
locust -f tests/load/workflow_load_test.py --host=http://localhost:8000
```

---

## Phase 3: Real-Time Integration + Service Mesh

**Duration:** Week 12-16 (5 weeks)
**Goal:** Add OpenTelemetry + WebSocket + Unified UI + Service Mesh Monitor
**Focus:** Observability + User Experience + System-Wide Visibility

### Week 12: OpenTelemetry Integration

**Effort:** 5 days

#### Tasks

**Day 1: Infrastructure Setup**
- [ ] Deploy Jaeger (docker-compose.tracing.yml)
- [ ] Configure all-in-one container
- [ ] Verify Jaeger UI at http://localhost:16686
- [ ] Test manual trace creation

**Day 2: Shared Tracing Library**
- [ ] Create `go-services/shared/tracing/jaeger.go`
- [ ] Create `go-services/shared/tracing/context.go`
- [ ] Helper functions: `StartSpan`, `InjectOperationContext`
- [ ] Add OpenTelemetry dependencies to all Go services

**Day 3: Django OpenTelemetry**
- [ ] Install `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-jaeger`
- [ ] Create `apps/templates/tracing.py`
- [ ] Initialize tracer in `settings.py`
- [ ] Test: create span in Django view → see in Jaeger

**Day 4: Instrument WorkflowEngine**
- [ ] Add parent span in `WorkflowEngine.execute_workflow()`
- [ ] Add child spans in `DAGExecutor.execute_dag()`
- [ ] Inject attributes: workflow.id, workflow.execution_id, node.id
- [ ] Store trace_id in WorkflowExecution.trace_id
- [ ] Store span_id in WorkflowStepResult.span_id

**Day 5: Testing**
- [ ] Test workflow execution → trace created in Jaeger
- [ ] Test trace has parent + child spans
- [ ] Test attributes are correct
- [ ] Test failed workflows record exceptions
- [ ] Test trace_id stored in database

**Deliverable:** All workflow executions create traces in Jaeger

```bash
# Validation
curl -X POST http://localhost:8000/api/v1/workflows/executions/ -d '...'
# Open Jaeger UI, search for trace
open http://localhost:16686
```

---

### Week 13: Django Channels + WebSocket

**Effort:** 5 days

#### Tasks

**Day 1: Django Channels Setup**
- [ ] Install `channels`, `channels-redis`
- [ ] Configure `ASGI_APPLICATION` in settings.py
- [ ] Create `asgi.py` with ProtocolTypeRouter
- [ ] Configure channel layers (Redis backend)
- [ ] Test: WebSocket connection works

**Day 2: WorkflowExecutionConsumer**
- [ ] Create `apps/templates/consumers.py`
- [ ] Implement `WorkflowExecutionConsumer`
  - `connect()`: join room group
  - `disconnect()`: leave room group
  - `receive()`: handle client messages (get_status)
  - `workflow_update()`: broadcast workflow status
  - `node_update()`: broadcast node status
- [ ] Add routing: `ws/workflow/<execution_id>/`

**Day 3: Broadcast Integration**
- [ ] Update `DAGExecutor._broadcast_node_update()`
- [ ] Update `WorkflowEngine._broadcast_status_update()`
- [ ] Test: execute workflow → WebSocket receives updates
- [ ] Test: multiple clients receive same updates
- [ ] Test: reconnection works

**Day 4: Frontend WebSocket Consumer**
- [ ] Create `frontend/src/hooks/useWorkflowExecution.ts`
- [ ] Connect to WebSocket on mount
- [ ] Handle messages (status_update, node_update)
- [ ] Update state in real-time
- [ ] Handle disconnection + reconnection
- [ ] Test: UI updates when workflow status changes

**Day 5: Testing**
- [ ] Unit tests for consumer
- [ ] Integration tests (execute workflow, verify WebSocket broadcasts)
- [ ] E2E tests (Playwright: open UI, execute workflow, see live updates)
- [ ] Load testing (100 concurrent WebSocket connections)

**Deliverable:** Real-time status updates working

```bash
# Validation
# Terminal 1: Start Django Channels
python manage.py runserver

# Terminal 2: Connect WebSocket client
wscat -c ws://localhost:8000/ws/workflow/exec-123/

# Terminal 3: Execute workflow
curl -X POST http://localhost:8000/api/v1/workflows/executions/ -d '...'

# Terminal 2 should receive real-time updates
```

---

### Week 14: React Flow Design Mode

**Effort:** 5 days

#### Tasks

**Day 1-2: WorkflowCanvas Component**
- [ ] Install `reactflow` library
- [ ] Create `WorkflowCanvas.tsx`
- [ ] Render nodes from workflow.dag_structure
- [ ] Render edges from workflow.dag_structure
- [ ] Implement drag & drop from node palette
- [ ] Implement node connection (drag from handle)
- [ ] Convert React Flow format ↔ DAG structure JSON

**Day 3: Node Palette**
- [ ] Create `NodePalette.tsx`
- [ ] Draggable node templates:
  - 🔧 Operation
  - ⁉️ Condition
  - ⇉ Parallel
  - 🔁 Loop
  - 📦 SubWorkflow
- [ ] Add node to canvas on drop

**Day 4: Property Editor**
- [ ] Create `PropertyEditor.tsx`
- [ ] Edit selected node properties
  - Operation: template_id, config (timeout, retries)
  - Condition: expression, branches
  - Parallel: parallel_nodes, wait_for
  - Loop: loop_config
  - SubWorkflow: subworkflow_id, input_mapping
- [ ] Validation (required fields, valid Jinja2 expressions)

**Day 5: Save/Load Workflow**
- [ ] POST /api/v1/workflows/templates/ (create workflow)
- [ ] PUT /api/v1/workflows/templates/{id}/ (update workflow)
- [ ] GET /api/v1/workflows/templates/{id}/ (load workflow)
- [ ] Validation endpoint integration
- [ ] Toast notifications (success, error)

**Deliverable:** Visual workflow builder working

```bash
# Validation
npm run dev
# Open http://localhost:5173/workflows/new
# Create workflow visually
# Save → verify in database
```

---

### Week 15: React Flow Monitor Mode

**Effort:** 5 days

#### Tasks

**Day 1-2: OperationNodeWithStatus**
- [ ] Create custom node component
- [ ] Display status badge (pending, running, completed, failed)
- [ ] Display duration
- [ ] Display error message (if failed)
- [ ] Color coding (gray, blue, green, red)
- [ ] Animated spinner for running state
- [ ] Click to select node

**Day 3: Live Status Integration**
- [ ] Use `useWorkflowExecution()` hook
- [ ] Update node statuses in real-time
- [ ] Update progress bar
- [ ] Update timeline
- [ ] Animate status transitions (CSS transitions)

**Day 4: Trace Viewer Integration**
- [ ] Create `TraceViewerModal.tsx`
- [ ] Query Jaeger API by execution_id + node_id
- [ ] Display trace timeline
- [ ] Display service flow diagram
- [ ] Display span details
- [ ] "Open in Jaeger" button

**Day 5: Testing**
- [ ] Unit tests for components
- [ ] Integration tests (mock WebSocket)
- [ ] E2E tests (Playwright)
  - Create workflow
  - Execute workflow
  - Verify live updates
  - Click node → see traces

**Deliverable:** Unified UI (Design + Monitor modes) complete

```bash
# Validation
npm run test
npm run e2e
```

---

### Week 16: Service Mesh Monitor ⭐ NEW

**Effort:** 5 days

#### Overview

Add **Service Mesh Tab** для aggregate view всех микросервисов.

**Goal:** System-wide visibility + cross-navigation to Workflows tab

#### Tasks

**Day 1-2: Metrics Aggregator Service (Go)**

**Create:**
```
go-services/metrics-aggregator/
├── cmd/main.go
├── internal/
│   ├── prometheus/
│   │   └── client.go              # Prometheus API client
│   ├── aggregator/
│   │   └── aggregator.go          # Metrics aggregation logic
│   ├── websocket/
│   │   └── server.go              # WebSocket server
│   └── models/
│       └── service_metrics.go     # ServiceMetrics struct
├── go.mod
└── go.sum
```

**Implementation:**
- [ ] Query Prometheus API every 2 seconds
- [ ] Aggregate metrics by service (frontend, api-gateway, worker, ras-adapter)
- [ ] Calculate: ops/min, active operations, P95 latency, error rate
- [ ] Expose WebSocket endpoint `/ws/service-mesh`
- [ ] Push aggregated metrics to connected clients
- [ ] Handle reconnection + backpressure

**PromQL Queries:**
```promql
# Operations per minute
sum(rate(http_requests_total[5m])) by (service)

# Active operations
sum(active_operations) by (service)

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) by (service)

# Error rate
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
```

**Day 3: Frontend Service Flow Diagram**

**Create:**
```typescript
frontend/src/components/service-mesh/
├── ServiceMeshTab.tsx             # Main tab component
├── SystemHealthCard.tsx           # System-wide health metrics
├── ServiceFlowDiagram.tsx         # Visual service flow
├── ServiceNode.tsx                # Individual service node
└── RecentOperationsTable.tsx     # Table of recent operations
```

**ServiceFlowDiagram.tsx:**
- [ ] Render service nodes (Frontend, API GW, Orchestrator, Worker, RAS)
- [ ] Position nodes in flow (top-to-bottom or left-to-right)
- [ ] Draw connections (SVG lines)
- [ ] Display metrics on each node
  - Operations/min
  - Active operations count
  - P95 latency
  - Error rate
- [ ] Color code by health (green, yellow, red)
- [ ] Click service → filter operations in table

**Day 4: Tab Navigation Integration**

**Create:**
```typescript
frontend/src/stores/dashboardStore.ts   # Zustand store
frontend/src/pages/Dashboard.tsx        # Main dashboard with tabs
```

**Dashboard.tsx:**
- [ ] Implement tab switching (Ant Design Tabs)
- [ ] Tab 1: Service Mesh Monitor
- [ ] Tab 2: My Workflows
- [ ] Persist active tab in localStorage
- [ ] Handle deep links (open specific tab via URL)

**Cross-Tab Navigation:**
- [ ] Service Mesh: Click operation → open in Workflows tab with Monitor Mode
- [ ] Workflows: Click "View System Impact" → switch to Service Mesh tab
- [ ] State preservation (tab state maintained when switching)

**useDashboardStore.ts:**
```typescript
interface DashboardState {
  activeTab: 'service-mesh' | 'my-workflows';

  // Service Mesh state
  serviceMeshMetrics: ServiceMetrics[];
  recentOperations: Operation[];

  // Workflows state
  selectedExecution: WorkflowExecution | null;

  // Actions
  switchTab: (tab) => void;
  openExecutionFromServiceMesh: (operationId) => void;
}
```

**Day 5: Testing + Polish**

**Unit Tests:**
- [ ] ServiceFlowDiagram renders correctly
- [ ] ServiceNode displays metrics
- [ ] RecentOperationsTable handles click events
- [ ] useDashboardStore tab switching
- [ ] WebSocket consumer (mock WebSocket)

**Integration Tests:**
- [ ] Metrics Aggregator queries Prometheus
- [ ] WebSocket pushes updates
- [ ] Frontend receives updates
- [ ] Cross-tab navigation works

**E2E Tests (Playwright):**
- [ ] Open Service Mesh tab → see services
- [ ] Click service → table filters
- [ ] Click operation → switches to Workflows tab
- [ ] Verify state preserved when switching tabs

**UI Polish:**
- [ ] Animations (fade in/out when switching tabs)
- [ ] Loading states (skeleton loaders)
- [ ] Error states (Prometheus unavailable)
- [ ] Responsive design (mobile, tablet, desktop)

**Deliverable:** Service Mesh Monitor working + Two-Tab Interface complete

```bash
# Validation
# Terminal 1: Start Metrics Aggregator
cd go-services/metrics-aggregator
go run cmd/main.go

# Terminal 2: Start Frontend
cd frontend
npm run dev

# Open http://localhost:5173
# Tab 1: Service Mesh → see real-time metrics
# Tab 2: My Workflows → create/monitor workflows
# Test cross-navigation
```

---

## Phase 4: Polish & Migration

**Duration:** Week 17-18 (2 weeks)
**Goal:** Production readiness + Worker migration
**Focus:** Documentation + Migration

### Week 17: Worker Migration

**Effort:** 5 days

#### Tasks

**Day 1: Create WorkflowTemplates**
- [ ] Extension Install Workflow (JSON)
- [ ] Configuration Update Workflow (JSON)
- [ ] Database Backup Workflow (JSON)
- [ ] Save to database via Django admin or API

**Day 2: Update Worker Code**
- [ ] Add `orchestratorClient.ExecuteWorkflow()` method
- [ ] Update `ProcessExtensionInstall()` to call WorkflowEngine
- [ ] Pass operation_id, database_id, extension_path as context
- [ ] Handle workflow result (success, failure)
- [ ] Maintain backward compatibility (feature flag)

**Day 3: Testing**
- [ ] Test extension install via new workflow
- [ ] Test all 21 extension install tests still pass
- [ ] Test failure scenarios (workflow fails at Lock step)
- [ ] Compare old State Machine vs new Workflow (metrics)

**Day 4: Gradual Rollout**
- [ ] Feature flag: `ENABLE_WORKFLOW_ENGINE=true`
- [ ] Enable for 10% of operations
- [ ] Monitor metrics (success rate, latency)
- [ ] Enable for 50%
- [ ] Enable for 100%

**Day 5: Deprecate State Machine**
- [ ] Remove old State Machine code
- [ ] Update documentation
- [ ] Update tests

**Deliverable:** Worker uses WorkflowEngine for all operations

```bash
# Validation
export ENABLE_WORKFLOW_ENGINE=true
./test-extension-install.sh
# Expected: SUCCESS (via workflow)
```

---

### Week 18: Documentation + Polish

**Effort:** 5 days

#### Tasks

**Day 1-2: User Documentation**
- [ ] User Guide: How to use Service Mesh Monitor (NEW!)
- [ ] User Guide: How to create workflows
- [ ] User Guide: How to monitor workflows
- [ ] User Guide: How to navigate between tabs (NEW!)
- [ ] User Guide: How to debug failed workflows
- [ ] Tutorial: Create "Price List Upload" workflow
- [ ] Tutorial: Create "Extension Install" workflow
- [ ] Tutorial: Use Service Mesh to find failed operation → debug in Workflows tab (NEW!)
- [ ] Video walkthrough (optional)

**Day 3: Developer Documentation**
- [ ] Developer Guide: How to add new node types
- [ ] Developer Guide: How to instrument services with OpenTelemetry
- [ ] Developer Guide: How to add metrics to Metrics Aggregator (NEW!)
- [ ] API Reference: REST API endpoints
- [ ] API Reference: WebSocket messages (workflows + service mesh) (NEW!)
- [ ] Architecture diagram (updated with Two-Tab Interface)

**Day 4: Admin Documentation**
- [ ] Admin Guide: Jaeger configuration
- [ ] Admin Guide: Workflow template management
- [ ] Admin Guide: Service Mesh Monitor configuration (NEW!)
- [ ] Admin Guide: Metrics Aggregator deployment (NEW!)
- [ ] Admin Guide: Performance tuning
- [ ] Admin Guide: Troubleshooting
- [ ] Runbook: Common issues + solutions

**Day 5: Polish**
- [ ] UI improvements (tab animations, smooth transitions) (NEW!)
- [ ] Performance optimizations (virtualized lists, lazy loading)
- [ ] Accessibility (a11y) improvements
- [ ] Browser compatibility testing (Chrome, Firefox, Safari)
- [ ] Mobile responsiveness (both tabs)
- [ ] Cross-tab navigation polish (NEW!)

**Deliverable:** Production-ready Two-Tab Platform with full documentation

```bash
# Validation
# Review documentation
open docs/user-guide/CREATE_WORKFLOW.md
open docs/developer-guide/ADD_NODE_TYPE.md
open docs/admin-guide/TROUBLESHOOTING.md
```

---

## Success Metrics

### Phase 2 (Workflow Engine Backend)

| Metric | Target | Validation |
|--------|--------|------------|
| **API Coverage** | 100% endpoints tested | `pytest --cov` |
| **Unit Test Coverage** | > 80% | `pytest --cov-report=html` |
| **Workflow Execution Success** | > 95% | Manual testing |
| **Latency P95** | < 5s (simple workflow) | Performance tests |
| **Throughput** | > 100 workflows/min | Load tests |

### Phase 3 (Real-Time Integration + Service Mesh)

| Metric | Target | Validation |
|--------|--------|------------|
| **Trace Coverage** | 100% workflows traced | Jaeger UI |
| **WebSocket Uptime** | > 99.9% | Monitoring |
| **UI Responsiveness** | < 100ms to status update | E2E tests |
| **Concurrent WebSockets** | > 100 connections | Load tests |
| **Real-time Accuracy** | 100% (no missed updates) | Integration tests |
| **Service Mesh Metrics Accuracy** | 100% vs Prometheus | Manual comparison |
| **Metrics Update Latency** | < 2.5s (2s interval + processing) | Performance tests |
| **Cross-Tab Navigation** | < 200ms switch time | E2E tests |
| **Tab State Preservation** | 100% (no data loss) | Integration tests |

### Phase 4 (Worker Migration)

| Metric | Target | Validation |
|--------|--------|------------|
| **Worker Tests Pass** | 100% (89/89 tests) | `go test ./...` |
| **Extension Install Success** | > 95% | Production metrics |
| **Latency Impact** | < +10% vs State Machine | Benchmarks |
| **Rollback Success** | 100% (if needed) | Feature flag toggle |

---

## Risk Mitigation

### Risk 1: OpenTelemetry Performance Overhead

**Probability:** Medium
**Impact:** Medium

**Mitigation:**
- ✅ Use sampling (10% in production, 100% in dev)
- ✅ Async export (don't block execution)
- ✅ Benchmark before/after
- ✅ Monitor Jaeger resource usage

**Fallback:** Disable tracing via config (workflows still work)

---

### Risk 2: WebSocket Scalability

**Probability:** Low
**Impact:** High

**Mitigation:**
- ✅ Use Django Channels with Redis backend
- ✅ Horizontal scaling (multiple Channels workers)
- ✅ Connection pooling
- ✅ Load testing (100+ concurrent connections)

**Fallback:** Polling API (GET /executions/{id}/status every 2s)

---

### Risk 3: Worker Migration Breaks Production

**Probability:** Low
**Impact:** Critical

**Mitigation:**
- ✅ Feature flag (ENABLE_WORKFLOW_ENGINE)
- ✅ Gradual rollout (10% → 50% → 100%)
- ✅ Monitor metrics (success rate, latency)
- ✅ Maintain backward compatibility
- ✅ Quick rollback (toggle feature flag)

**Fallback:** Revert to State Machine (0 downtime)

---

### Risk 4: Complex Workflows Hard to Debug

**Probability:** Medium
**Impact:** Medium

**Mitigation:**
- ✅ Detailed traces in Jaeger (every node = span)
- ✅ WorkflowStepResult stores all intermediate results
- ✅ UI shows failed node + error message
- ✅ Export trace as JSON
- ✅ Comprehensive logging

**Fallback:** Use Jaeger UI directly (if custom UI insufficient)

---

## MVP vs Full Feature Set

### MVP (11 weeks) - Backend Only

**What you get:**
- ✅ Workflow Engine backend (DAGValidator, NodeHandlers, REST API)
- ✅ Execute workflows via API (curl)
- ✅ Store executions in database
- ✅ Basic error handling

**What you DON'T get:**
- ❌ No visual UI (use API/JSON)
- ❌ No real-time updates (poll API)
- ❌ No integrated traces (use Jaeger UI directly)
- ❌ No Worker migration (manual workflows only)

**Use case:** Workflows work, but debugging is manual

**Timeline:** End of Week 11

---

### Full Feature Set (18 weeks) ⭐ TWO-TAB INTERFACE

**What you get (in addition to MVP):**
- ✅ Visual workflow builder (React Flow Design Mode)
- ✅ Real-time execution monitoring (WebSocket + Monitor Mode)
- ✅ Integrated trace viewer (click node → see traces)
- ✅ **Service Mesh Monitor** (system-wide aggregate view) (NEW!)
- ✅ **Two-Tab Interface** (Service Mesh + My Workflows) (NEW!)
- ✅ **Cross-tab navigation** (operation → workflow drill-down) (NEW!)
- ✅ Worker migration (admin tasks = explicit workflows)
- ✅ Full documentation (user + developer + admin guides)

**Use case:** Production-ready, user-friendly, fully integrated, complete observability

**Timeline:** End of Week 18

---

## Decision Points

### Week 11: Continue to Phase 3?

**Evaluate:**
- ✅ Workflow Engine backend works
- ✅ API tests pass (> 95%)
- ✅ Performance acceptable (P95 < 5s)
- ✅ Team ready for frontend work

**Decision:**
- ✅ YES → Continue to Phase 3 (Real-Time Integration)
- ❌ NO → Stop at MVP, use API only

---

### Week 15: Add Service Mesh Monitor? ⭐

**Evaluate:**
- ✅ Workflows UI works well
- ✅ Real-time updates reliable
- ✅ Team has bandwidth for additional week
- ✅ Users need system-wide visibility

**Decision:**
- ✅ YES → Add Week 16 (Service Mesh Monitor) + Two-Tab Interface
- ❌ NO → Skip Service Mesh, use Grafana dashboards instead

**Note:** Service Mesh Monitor is optional but highly recommended for production observability.

---

### Week 16: Migrate Worker?

**Evaluate:**
- ✅ Unified UI works (with or without Service Mesh)
- ✅ Real-time updates reliable
- ✅ Traces helpful for debugging
- ✅ Team confident in stability

**Decision:**
- ✅ YES → Continue to Phase 4 (Worker Migration)
- ❌ NO → Keep Worker State Machine, workflows for new features only

---

## Next Steps

### Immediate (Week 5)

1. **Start Phase 2:** Django models + migrations
2. **Review design doc:** [UNIFIED_WORKFLOW_VISUALIZATION.md](../architecture/UNIFIED_WORKFLOW_VISUALIZATION.md)
3. **Set up project board:** Track tasks per week
4. **Assign roles:** Backend (Django), Frontend (React), DevOps (OpenTelemetry)

### Prepare

```bash
# Create branch
git checkout -b feature/unified-workflow-phase2

# Set up Python environment
cd orchestrator
source venv/bin/activate
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger

# Set up React environment
cd frontend
npm install reactflow
```

---

## References

- **Design Document:** [UNIFIED_WORKFLOW_VISUALIZATION.md](../architecture/UNIFIED_WORKFLOW_VISUALIZATION.md) v2.0
- **Quick Summary:** [UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md](../UNIFIED_WORKFLOW_TWO_TAB_SUMMARY.md) (NEW!)
- **Track 1.5 Original:** [WORKFLOW_ENGINE_ARCHITECTURE.md](../architecture/WORKFLOW_ENGINE_ARCHITECTURE.md)
- **Real-Time Tracking:** [REAL_TIME_OPERATION_TRACKING.md](../architecture/REAL_TIME_OPERATION_TRACKING.md)
- **RAS Adapter Roadmap:** [RAS_ADAPTER_ROADMAP.md](RAS_ADAPTER_ROADMAP.md)

---

**Document Version:** 2.1
**Last Updated:** 2025-11-26
**Status:** APPROVED FOR IMPLEMENTATION - Extended with Service Mesh Monitor
**Note:** Week 8+ work was lost due to uncommitted changes in deleted worktree. Resuming from Week 8.
**Architecture:** Two-Tab Interface (Service Mesh + My Workflows)
**Start Date:** Week 5 (TBD)
**Expected Completion:** Week 22 (TBD) - 18 weeks total
