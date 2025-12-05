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
Week 5-11:  Phase 2 - Workflow Engine Backend (7 weeks) ✅ COMPLETE
            • Week 5: Models + Migrations ✅ COMPLETE (2025-11-23)
            • Week 6: DAGValidator + Kahn's Algorithm ✅ COMPLETE (2025-11-23)
            • Week 7: NodeHandlers (Part 1) ✅ COMPLETE (2025-11-23)
            • Week 8: NodeHandlers (Part 2) ✅ COMPLETE (2025-11-26)
            • Week 9: WorkflowEngine + DAGExecutor ✅ COMPLETE (2025-11-26)
            • Week 10: REST API ✅ COMPLETE (2025-11-26)
            • Week 11: Celery Tasks + Testing ✅ COMPLETE (2025-11-26)
Week 12-16: Phase 3 - Real-Time Integration + Service Mesh (5 weeks) ✅ COMPLETE
            • Week 12: OpenTelemetry ✅ COMPLETE (2025-11-26)
            • Week 13: WebSocket ✅ COMPLETE (2025-11-26)
            • Week 14: React Flow Design Mode ✅ COMPLETE (2025-11-26)
            • Week 15: React Flow Monitor Mode ✅ COMPLETE (2025-11-26)
            • Week 16: Service Mesh Monitor ✅ COMPLETE (2025-11-26)
Week 17-18: Phase 4 - Polish & Migration (2 weeks)
            • Week 17: OperationHandler → Worker Integration 🔄 IN PROGRESS (2025-11-27)

Total: 18 weeks (4.5 months)
Progress: Week 17/18 (94% complete)
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

## Phase 2: Workflow Engine Backend ✅ COMPLETE

**Duration:** Week 5-11 (7 weeks)
**Status:** ✅ COMPLETE (2025-11-26)
**Goal:** Implement Track 1.5 backend WITHOUT UI
**Focus:** Core workflow execution engine

### Phase 2 Achievements

- ✅ 359 workflow tests passing
- ✅ 574 total templates tests passing
- ✅ REST API with 10 endpoints (OpenAPI documented)
- ✅ Performance benchmarks (23 tests)
- ✅ Locust load tests ready
- ✅ Integration tests (37 tests)

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

### Week 10: REST API ✅ COMPLETE (2025-11-26)

**Effort:** 5 days

#### Tasks

**Day 1-2: ViewSets + Serializers**
- [x] Create `WorkflowTemplateViewSet` (CRUD + validate, execute, clone)
- [x] Create `WorkflowExecutionViewSet` (list, retrieve + cancel, steps, status)
- [x] Create `WorkflowTemplateListSerializer` / `WorkflowTemplateDetailSerializer`
- [x] Create `WorkflowExecutionListSerializer` / `WorkflowExecutionDetailSerializer`
- [x] Create `WorkflowStepResultSerializer`
- [x] Nested serializers for DAGStructure (nodes, edges)
- [x] Validation: dag_structure via Pydantic

**Day 3: Permissions + Filters**
- [x] Permission class: IsAuthenticated
- [x] Rate limiting: WorkflowExecuteThrottle (30/min)
- [x] WorkflowTemplateFilter (workflow_type, is_active, is_valid, date range)
- [x] WorkflowExecutionFilter (status, template, date range)

**Day 4: API Tests**
- [x] Test CRUD operations (18 tests)
- [x] Test validation endpoint (3 tests)
- [x] Test execute endpoint (4 tests: sync + async)
- [x] Test cancel endpoint (1 test)
- [x] Test permissions (3 tests)
- [x] Test error responses (4 tests)
- [x] Total: 48 API tests passing

**Day 5: OpenAPI + Code Review**
- [x] Generate OpenAPI schema (drf-spectacular)
- [x] 10 workflow endpoints documented
- [x] @extend_schema on all endpoints
- [x] Code review: Fixed N+1 query, dead code removed

**Deliverable:** ✅ REST API complete with 10 endpoints, 48 tests, OpenAPI docs

**Files created:**
- `orchestrator/apps/templates/workflow/serializers.py` (NEW)
- `orchestrator/apps/templates/workflow/views.py` (NEW)
- `orchestrator/apps/templates/workflow/filters.py` (NEW)
- `orchestrator/apps/templates/workflow/urls.py` (NEW)
- `orchestrator/apps/templates/workflow/tests/test_api.py` (NEW)

```bash
# Validation
pytest apps/templates/workflow/tests/test_api.py -v  # 48 tests passed
pytest apps/templates/workflow/tests/ -v  # 299 tests passed
curl http://localhost:8000/api/docs/  # Swagger UI
```

---

### Week 11: Celery Tasks + Testing ✅ COMPLETE (2025-11-26)

**Effort:** 5 days

#### Tasks

**Day 1-2: Celery Tasks** (completed in Week 9)
- [x] Create `execute_workflow_task` (async workflow execution)
- [x] Create `execute_workflow_node` (for ParallelHandler)
- [x] Add retry logic (max_retries=3, countdown=60)
- [x] Add error handling (capture exceptions, store in execution)
- [x] Add progress tracking (update execution.current_node_id)

**Day 3: Performance Testing**
- [x] Benchmark simple workflow (2-3 nodes)
- [x] Benchmark complex workflow (10+ nodes, parallel, loops)
- [x] Benchmark parallel execution (10 nodes concurrently)
- [x] Measure latency (P50, P95, P99)
- [x] Measure throughput (workflows/min)
- [x] 23 benchmark tests created

**Day 4: Load Testing**
- [x] Locust script for workflow execution
- [x] Test 10 concurrent workflows
- [x] Test 50 concurrent workflows
- [x] Test 100 concurrent workflows
- [x] Identify bottlenecks (database, Celery, Worker)

**Day 5: Integration Testing**
- [x] Test complete flow: API → Celery → Worker → RAS
- [x] Test extension install workflow (mocked RAS)
- [x] Test failure scenarios (RAS unavailable, timeout)
- [x] Test rollback (if workflow fails mid-execution)
- [x] 37 integration tests created

**Deliverable:** ✅ Workflow Engine ready for production (backend only)

**Files created:**
- `orchestrator/apps/templates/workflow/tests/test_benchmarks.py` (NEW - 23 tests)
- `orchestrator/apps/templates/workflow/tests/test_integration.py` (NEW - 37 tests)
- `orchestrator/tests/load/workflow_load_test.py` (NEW - Locust load tests)
- `orchestrator/tests/load/README.md` (NEW)
- `orchestrator/tests/load/run_load_test.sh` (NEW)

```bash
# Validation
pytest apps/templates/workflow/tests/ -v --benchmark-disable  # 359 tests passed
pytest apps/templates/workflow/tests/test_benchmarks.py -v --benchmark-only
locust -f tests/load/workflow_load_test.py --host=http://localhost:8000
```

---

## Phase 3: Real-Time Integration + Service Mesh ✅ COMPLETE

**Duration:** Week 12-16 (5 weeks)
**Status:** ✅ Завершено 2025-11-26
**Goal:** Add OpenTelemetry + WebSocket + Unified UI + Service Mesh Monitor
**Focus:** Observability + User Experience + System-Wide Visibility

### Week 12: OpenTelemetry Integration ✅ COMPLETE (2025-11-26)

**Effort:** 5 days

#### Tasks

**Day 1: Infrastructure Setup**
- [x] Deploy Jaeger (docker-compose.tracing.yml)
- [x] Configure all-in-one container (port 16686 UI, 4317 OTLP)
- [x] Verify Jaeger UI at http://localhost:16686
- [x] OTLP gRPC + HTTP receivers enabled

**Day 2: Shared Tracing Library**
- [x] Create `go-services/shared/tracing/tracer.go`
- [x] Create `go-services/shared/tracing/context.go`
- [x] Create `go-services/shared/tracing/middleware.go` (Gin)
- [x] Helper functions: `StartSpan`, `InjectWorkflowContext`, `InjectOperationContext`
- [x] Add OpenTelemetry dependencies (otel v1.35.0)
- [x] 48 Go tracing tests passing

**Day 3: Django OpenTelemetry**
- [x] Install opentelemetry packages (api, sdk, exporter-otlp)
- [x] Create `apps/templates/tracing.py` (811 lines)
- [x] Graceful degradation when OTEL unavailable
- [x] Celery headers propagation support

**Day 4: Instrument WorkflowEngine**
- [x] Add parent span in `WorkflowEngine.execute_workflow()`
- [x] Add child spans in `DAGExecutor._execute_node()`
- [x] Inject attributes: workflow.id, workflow.execution_id, node.id
- [x] Store trace_id in WorkflowExecution
- [x] Store span_id in WorkflowStepResult

**Day 5: Testing**
- [x] 74 tracing tests created (test_tracing.py)
- [x] Test trace_id/span_id format (32/16 hex chars)
- [x] Test graceful degradation
- [x] Test Celery propagation
- [x] 432 workflow tests passing

**Deliverable:** ✅ OpenTelemetry tracing integrated into Workflow Engine

**Files created:**
- `docker-compose.tracing.yml` (NEW)
- `go-services/shared/tracing/tracer.go` (NEW)
- `go-services/shared/tracing/context.go` (NEW)
- `go-services/shared/tracing/middleware.go` (NEW)
- `orchestrator/apps/templates/tracing.py` (NEW)
- `orchestrator/apps/templates/workflow/tests/test_tracing.py` (NEW - 74 tests)

```bash
# Start Jaeger
docker-compose -f docker-compose.tracing.yml up -d

# Run tests
pytest apps/templates/workflow/tests/test_tracing.py -v  # 74 tests

# Open Jaeger UI
open http://localhost:16686
```

---

### Week 13: Django Channels + WebSocket ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-26

#### Tasks

**Day 1: Django Channels Setup**
- [x] Install `channels`, `channels-redis`
- [x] Configure `ASGI_APPLICATION` in settings.py
- [x] Create `asgi.py` with ProtocolTypeRouter
- [x] Configure channel layers (Redis backend)
- [x] Test: WebSocket connection works

**Day 2: WorkflowExecutionConsumer**
- [x] Create `apps/templates/consumers.py`
- [x] Implement `WorkflowExecutionConsumer`
  - `connect()`: join room group
  - `disconnect()`: leave room group
  - `receive()`: handle client messages (get_status, subscribe_nodes, ping)
  - `workflow_update()`: broadcast workflow status
  - `node_update()`: broadcast node status
- [x] Add routing: `ws/workflow/<execution_id>/`

**Day 3: Broadcast Integration**
- [x] Update `DAGExecutor._broadcast_node_update()`
- [x] Update `WorkflowEngine._broadcast_status_update()`
- [x] Test: execute workflow → WebSocket receives updates
- [x] Test: multiple clients receive same updates
- [x] Test: reconnection works

**Day 4: Frontend WebSocket Consumer**
- [x] Create `frontend/src/hooks/useWorkflowExecution.ts`
- [x] Connect to WebSocket on mount
- [x] Handle messages (workflow_status, node_status, execution_completed, error, pong)
- [x] Update state in real-time
- [x] Handle disconnection + reconnection (exponential backoff)
- [x] Periodic ping to keep connection alive (30s)
- [x] Test: UI updates when workflow status changes

**Day 5: Testing**
- [x] Unit tests for consumer
- [x] Integration tests (execute workflow, verify WebSocket broadcasts)
- [x] Test message types and parsing
- [x] Test reconnection logic

**Deliverable:** ✅ Real-time status updates working

**Files created:**
- `orchestrator/apps/templates/consumers.py`
- `orchestrator/apps/templates/routing.py`
- `orchestrator/config/asgi.py` (updated)
- `frontend/src/hooks/useWorkflowExecution.ts` (400+ lines)

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

### Week 14: React Flow Design Mode ✅ COMPLETE

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-26

#### Tasks

**Day 1-2: WorkflowCanvas Component**
- [x] Install `reactflow` library (v11.11.4 already in package.json)
- [x] Create `WorkflowCanvas.tsx` (350+ lines)
- [x] Render nodes from workflow.dag_structure
- [x] Render edges from workflow.dag_structure
- [x] Implement drag & drop from node palette
- [x] Implement node connection (drag from handle)
- [x] Convert React Flow format ↔ DAG structure JSON
- [x] Create custom node components (OperationNode, ConditionNode, ParallelNode, LoopNode, SubWorkflowNode)
- [x] Support design mode and monitor mode

**Day 3: Node Palette**
- [x] Create `NodePalette.tsx`
- [x] Draggable node templates:
  - 🔧 Operation
  - ⁉️ Condition
  - ⇉ Parallel
  - 🔁 Loop
  - 📦 SubWorkflow
- [x] Add node to canvas on drop
- [x] Color-coded node types

**Day 4: Property Editor**
- [x] Create `PropertyEditor.tsx` (500+ lines)
- [x] Edit selected node properties
  - Operation: template_id, config (timeout, retries, retry_delay)
  - Condition: expression (Jinja2)
  - Parallel: parallel_nodes, wait_for
  - Loop: loop_mode (count, while, foreach), loop_count, loop_condition
  - SubWorkflow: subworkflow_id, input_mapping, output_mapping
- [x] Validation (required fields)
- [x] Delete/Duplicate node actions

**Day 5: Save/Load Workflow**
- [x] POST /api/v1/workflows/templates/ (create workflow)
- [x] PUT /api/v1/workflows/templates/{id}/ (update workflow)
- [x] GET /api/v1/workflows/templates/{id}/ (load workflow)
- [x] Validation endpoint integration
- [x] Toast notifications (success, error)
- [x] WorkflowDesigner page (full page workflow editor)
- [x] WorkflowList page (list of all workflows)
- [x] Routes: /workflows, /workflows/new, /workflows/:id
- [x] Navigation menu item added

**Deliverable:** ✅ Visual workflow builder working

**Files created:**
- `frontend/src/types/workflow.ts` (300+ lines)
- `frontend/src/api/endpoints/workflows.ts` (150+ lines)
- `frontend/src/components/workflow/WorkflowCanvas.tsx` (350+ lines)
- `frontend/src/components/workflow/WorkflowCanvas.css`
- `frontend/src/components/workflow/NodePalette.tsx`
- `frontend/src/components/workflow/NodePalette.css`
- `frontend/src/components/workflow/PropertyEditor.tsx` (500+ lines)
- `frontend/src/components/workflow/PropertyEditor.css`
- `frontend/src/components/workflow/nodes/OperationNode.tsx`
- `frontend/src/components/workflow/nodes/ConditionNode.tsx`
- `frontend/src/components/workflow/nodes/ParallelNode.tsx`
- `frontend/src/components/workflow/nodes/LoopNode.tsx`
- `frontend/src/components/workflow/nodes/SubWorkflowNode.tsx`
- `frontend/src/components/workflow/nodes/nodeStyles.css`
- `frontend/src/components/workflow/nodes/index.ts`
- `frontend/src/components/workflow/index.ts`
- `frontend/src/pages/Workflows/WorkflowDesigner.tsx`
- `frontend/src/pages/Workflows/WorkflowDesigner.css`
- `frontend/src/pages/Workflows/WorkflowList.tsx`
- `frontend/src/pages/Workflows/WorkflowList.css`
- `frontend/src/hooks/useWorkflowExecution.ts`

```bash
# Validation
npm run build  # ✅ PASSED
npm run dev
# Open http://localhost:5173/workflows/new
# Create workflow visually
# Save → verify in database
```

---

### Week 15: React Flow Monitor Mode ✅ COMPLETE (2025-11-26)

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-26

#### Tasks

**Day 1-2: OperationNodeWithStatus**
- [x] Create custom node component (enhanced OperationNode)
- [x] Display status badge (pending, running, completed, failed)
- [x] Display duration
- [x] Display error message (if failed)
- [x] Color coding (gray, blue, green, red)
- [x] Animated spinner for running state
- [x] Click to select node
- [x] Trace link indicator when spanId exists

**Day 3: Live Status Integration**
- [x] Use `useWorkflowExecution()` hook
- [x] Update node statuses in real-time
- [x] Update progress bar
- [x] Update timeline
- [x] Animate status transitions (CSS transitions)
- [x] Current node highlighting (glow effect)

**Day 4: Trace Viewer Integration**
- [x] Create `TraceViewerModal.tsx` (460+ lines)
- [x] Create Jaeger API client (`jaeger.ts`) with timeout support
- [x] Create tracing types (`tracing.ts`) with conversion utilities
- [x] Create `useJaegerTraces.ts` hook
- [x] Display trace timeline
- [x] Display service flow diagram
- [x] Display span details
- [x] "Open in Jaeger" button

**Day 5: Testing & Code Review Fixes**
- [x] Build passes (7.33s, 3264 modules)
- [x] Code review: 3 important issues fixed
  - Added timeout for fetch in jaeger.ts (AbortController)
  - Fixed edge case with empty spans array in tracing.ts
  - Replaced useMemo with useEffect for side effects in TraceViewerModal

**Deliverable:** ✅ Unified UI (Design + Monitor modes) complete

**Files created/updated:**
- `frontend/src/api/endpoints/jaeger.ts` (NEW - 260+ lines)
- `frontend/src/types/tracing.ts` (NEW - 290+ lines)
- `frontend/src/hooks/useJaegerTraces.ts` (NEW - 50+ lines)
- `frontend/src/components/workflow/TraceViewerModal.tsx` (NEW - 460+ lines)
- `frontend/src/components/workflow/TraceViewerModal.css` (NEW - 180+ lines)
- `frontend/src/components/workflow/nodes/nodeStyles.css` (UPDATED - monitor mode styles)
- `frontend/src/components/workflow/nodes/OperationNode.tsx` (UPDATED - trace link)
- `frontend/src/pages/Workflows/WorkflowMonitor.tsx` (UPDATED - TraceViewerModal integration)
- `frontend/src/App.tsx` (UPDATED - route /workflows/executions/:executionId)

```bash
# Validation
npm run build  # ✅ PASSED (7.33s)
```

---

### Week 16: Service Mesh Monitor ✅ COMPLETE (2025-11-26)

**Effort:** 5 days
**Status:** ✅ Завершено 2025-11-26

#### Overview

Added **Service Mesh Tab** для aggregate view всех микросервисов.

**Decision:** Hybrid approach - Django REST API + WebSocket (не Go service)
- Reused existing Django Channels infrastructure (Week 13)
- PrometheusClient в Django для metrics aggregation
- Меньше кода, одна точка развертывания

#### Tasks

**Day 1-2: Backend - Prometheus Client + WebSocket**

**Created:**
- [x] `orchestrator/apps/operations/services/prometheus_client.py` (476 lines)
  - PrometheusClient class with async HTTP client
  - ServiceMetrics, ServiceConnection dataclasses
  - `get_service_metrics()`, `get_all_services_metrics()`
  - `get_service_connections()` for topology
  - `get_historical_metrics()` for charts (range queries)
  - `get_overall_health()` aggregation
  - Parallel queries with `asyncio.gather()`
  - SERVICE_CONFIG + SERVICE_TOPOLOGY definitions
- [x] `orchestrator/apps/operations/consumers.py` (ServiceMeshConsumer)
  - WebSocket consumer for real-time metrics
  - Authentication required (reject anonymous)
  - 2-second periodic updates
  - Set interval support (2-30 seconds)
  - Ping/pong heartbeat
  - Fallback data when Prometheus unavailable
  - Broadcast helpers for external systems
- [x] `orchestrator/apps/operations/views/service_mesh.py`
  - REST API endpoints for history data
  - `/api/operations/service-mesh/history/` endpoint

**PromQL Queries (implemented):**
```promql
# Operations per minute
sum(rate({namespace}_requests_total{job=~"{job_filter}"}[5m])) * 60

# P95 latency
histogram_quantile(0.95, sum(rate({namespace}_request_duration_seconds_bucket{job=~"{job_filter}"}[5m])) by (le)) * 1000

# Error rate
sum(rate({namespace}_requests_total{job=~"{job_filter}",status=~"5.."}[5m])) / sum(rate({namespace}_requests_total{job=~"{job_filter}"}[5m]))

# Active workers
{namespace}_active_workers{job=~"{job_filter}"}
```

**Day 3: Frontend - Service Flow Diagram**

**Created:**
```
frontend/src/components/service-mesh/
├── ServiceMeshTab.tsx          # Main tab component
├── ServiceMeshTab.css
├── SystemHealthCard.tsx        # System-wide health metrics
├── SystemHealthCard.css
├── ServiceFlowDiagram.tsx      # React Flow visualization
├── ServiceFlowDiagram.css
├── ServiceDetailDrawer.tsx     # Right drawer with historical charts
├── ServiceDetailDrawer.css
└── RecentOperationsTable.tsx   # Recent operations table
```

**Implementation:**
- [x] `ServiceFlowDiagram.tsx` - React Flow based service topology
  - Custom ServiceNode component with metrics display
  - Animated edges showing traffic flow
  - Edge labels with request counts
  - Color coded nodes (green/yellow/red)
  - Click to select service → opens drawer
- [x] `SystemHealthCard.tsx` - Overall system health + status indicators
- [x] `ServiceDetailDrawer.tsx` - Recharts-based historical metrics
  - Ops/min + P95 Latency dual Y-axis chart
  - Separate Error Rate chart
  - Time range selector (15m, 30m, 60m)
  - Navigation to operations page
- [x] `RecentOperationsTable.tsx` - Operations list with filtering

**Day 4: Hook + API Integration**

**Created:**
- [x] `frontend/src/hooks/useServiceMesh.ts` (294 lines)
  - WebSocket connection with auto-reconnect
  - Exponential backoff (1s → 30s, max 10 attempts)
  - Memory leak fix (ref for reconnectAttempts)
  - Transform snake_case → camelCase
  - Ping/pong heartbeat (30s interval)
- [x] `frontend/src/types/serviceMesh.ts`
  - ServiceMetrics, ServiceConnection, ServiceMeshWSMessage types
  - STATUS_COLORS, STATUS_TEXT, SERVICE_DISPLAY_CONFIG constants
- [x] `frontend/src/api/endpoints/serviceMesh.ts`
  - REST API client for historical data

**Day 5: Testing + Security Fixes**

**Tests Created:**
- [x] 38 PrometheusClient tests (100% pass)
- [x] Test query(), query_range() methods
- [x] Test _extract_value() edge cases
- [x] Test _determine_status() thresholds
- [x] Test get_service_metrics(), get_all_services_metrics()
- [x] Test get_historical_metrics()

**Security Fixes (from Code Review):**
- [x] WebSocket authentication check (reject anonymous users)
- [x] Error info leak fix (generic message instead of str(e))
- [x] async_to_sync instead of deprecated event loop
- [x] Parallel queries with asyncio.gather (4x performance)
- [x] Memory leak fix in useServiceMesh (reconnectAttemptsRef)
- [x] window.location → useNavigate (SPA navigation)

**Deliverable:** ✅ Service Mesh Monitor complete with real-time metrics

**Files created/updated:**
- `orchestrator/apps/operations/services/prometheus_client.py` (NEW - 476 lines)
- `orchestrator/apps/operations/consumers.py` (UPDATED - ServiceMeshConsumer)
- `orchestrator/apps/operations/views/service_mesh.py` (NEW)
- `frontend/src/types/serviceMesh.ts` (NEW)
- `frontend/src/hooks/useServiceMesh.ts` (NEW - 294 lines)
- `frontend/src/api/endpoints/serviceMesh.ts` (NEW)
- `frontend/src/components/service-mesh/*.tsx` (NEW - 6 components)
- `frontend/src/pages/ServiceMesh/ServiceMeshPage.tsx` (NEW)

```bash
# Validation
npm run build  # ✅ PASSED (9.60s, 3911 modules)
pytest apps/operations/tests/test_prometheus_client.py -v  # 38/38 ✅
```

---

## Phase 4: Polish & Migration

**Duration:** Week 17-18 (2 weeks)
**Goal:** Production readiness + Worker migration
**Focus:** Documentation + Migration

### Week 17: OperationHandler → Worker Integration 🔄 IN PROGRESS

**Effort:** 5 days
**Status:** 🔄 В процессе 2025-11-27
**Goal:** Connect WorkflowEngine (Django) with Go Worker via BatchOperation + Celery

#### Tasks

**Day 1-2: BatchOperationFactory**
- [x] Create `BatchOperationFactory` class
  - `create()` method for BatchOperation + Task creation
  - Transaction atomic for consistency
  - Bulk create for Task objects
  - Operation ID generation (batch-{workflow_id}-{node_id}-{timestamp})
- [x] Tests for factory (9 tests)

**Day 3: ResultWaiter**
- [x] Create `ResultWaiter` class
  - `wait()` method for SYNC mode (DB polling)
  - `check_status()` method for status inspection
  - `_collect_task_results()` for aggregating results
  - Custom `OperationTimeoutError` exception
- [x] Tests for waiter (8 tests)

**Day 4: OperationHandler Integration**
- [x] Extend `NodeExecutionResult` with operation_id, task_id fields
- [x] Update `OperationHandler.execute()`:
  - Extract target_databases from context
  - Create BatchOperation via factory
  - Enqueue to Worker via Celery `enqueue_operation.delay()`
  - SYNC mode: wait via ResultWaiter
  - ASYNC mode: return immediately with operation_id
- [x] Tests for integration (7 tests)

**Day 5: Code Review + Documentation**
- [x] Code review (MINOR_ISSUES - 8/10)
- [x] Update roadmap
- [ ] Create git commit

**Deliverable:** OperationHandler creates real BatchOperations and enqueues to Worker

**Files created:**
- `orchestrator/apps/operations/factory.py` (NEW - 165 lines)
- `orchestrator/apps/operations/waiter.py` (NEW - 220 lines)
- `orchestrator/apps/operations/tests/test_factory_waiter.py` (NEW - 716 lines, 24 tests)

**Files modified:**
- `orchestrator/apps/templates/workflow/handlers/base.py` (NodeExecutionResult extended)
- `orchestrator/apps/templates/workflow/handlers/operation.py` (Full Worker integration)

```bash
# Validation
cd orchestrator && pytest apps/operations/tests/test_factory_waiter.py -v
# Expected: 24/24 passed ✅
```

---

### Week 17.5: Worker Migration (Remaining)

**Effort:** 2-3 days (deferred)
**Status:** ⏸️ DEFERRED

#### Remaining Tasks (from original Week 17 plan)

**Create WorkflowTemplates**
- [ ] Extension Install Workflow (JSON)
- [ ] Configuration Update Workflow (JSON)
- [ ] Database Backup Workflow (JSON)

**Update Worker Code**
- [ ] Add `orchestratorClient.ExecuteWorkflow()` method
- [ ] Maintain backward compatibility (feature flag)

**Gradual Rollout**
- [ ] Feature flag: `ENABLE_WORKFLOW_ENGINE=true`
- [ ] Enable for 10% → 50% → 100%

**Deliverable:** Worker uses WorkflowEngine for all operations

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
