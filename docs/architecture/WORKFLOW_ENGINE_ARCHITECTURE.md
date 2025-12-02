# 🔀 Workflow Engine Architecture - Track 1.5

> **DAG-based Workflow Orchestration для CommandCenter1C**

**Версия:** 1.0
**Дата:** 2025-11-09
**Статус:** Architectural Design (готов к реализации)
**Целевая фаза:** Phase 2 (после Track 2-3)
**Автор:** Claude (Senior Software Architect)

---

## 📋 Содержание

- [Executive Summary](#executive-summary)
- [Требования](#требования)
- [Research Findings](#research-findings)
- [Архитектура](#архитектура)
- [Django Models](#django-models)
- [WorkflowEngine Components](#workflowengine-components)
- [JSON Schema](#json-schema)
- [Примеры Workflows](#примеры-workflows)
- [Integration с Track 1](#integration-с-track-1)
- [Validation Strategy](#validation-strategy)
- [Testing Strategy](#testing-strategy)
- [Timeline](#timeline)
- [Risks & Mitigation](#risks--mitigation)
- [Phase 2 Roadmap](#phase-2-roadmap)
- [REST API Reference](#rest-api-reference)

---

## Executive Summary

### Цель

Расширить Template Engine (Track 1) поддержкой **Workflow** - композитных операций из нескольких шагов, организованных в DAG (Directed Acyclic Graph).

### Ключевые возможности

1. ✅ **Conditional branching** - if/else ветки в workflow
2. ✅ **Parallel execution** - несколько операций одновременно (Celery group)
3. ✅ **Loop steps** - повторить N раз или пока условие (count/while/foreach)
4. ✅ **Data passing** - результат шага 1 → вход шага 2 (`{{ step1.result.field }}`)
5. ✅ **Sub-workflows** - композиция workflows (глубокая вложенность, limit=10)

### Timeline

**6-7 дней реализации** (48-56 часов)

### Формат данных

**Nodes+Edges JSON** (как graph libraries, React Flow, n8n):

```json
{
  "nodes": [
    {"id": "step1", "name": "Создать контрагента", "type": "operation", "template_id": "uuid"},
    {"id": "condition1", "name": "Проверка суммы", "type": "condition", "expression": "{{ amount > 100000 }}"}
  ],
  "edges": [
    {"from": "step1", "to": "condition1"}
  ]
}
```

---

## Требования

### Когда нужна фича?

**Phase 2** (когда Track 2-3 готовы) - НЕ срочно

### Формат данных

**Nodes+Edges JSON** ✅ (выбран пользователем)

### Frontend визуализация

**НЕТ** (пока только JSON в БД, визуализация в Track 4 - Phase 3)

### Приоритет фич

1. Conditional branching (if/else ветки)
2. Parallel execution (несколько операций одновременно)
3. Loop steps (повторить N раз или пока условие)
4. Data passing (результат шага 1 → вход шага 2)
5. Sub-workflows (композиция workflows, глубокая вложенность)

### Use Case (пример)

**Задача:** Создание реализации в базе 1С

**Шаги:**
1. Создать контрагента
2. Создать договор (использует контрагент_id из шага 1)
3. Создать документ
4. Заполнить документ
5. **Условие:** Сумма > 100k?
   - ✅ Да → Верификация
   - ❌ Нет → Авто-подтверждение
6. Провести документ
7. Контроль через отчет

**Глубокая вложенность:** Workflow → Sub-workflow → Sub-sub-workflow → ... (без ограничений, но с safety limit=10)

---

## Research Findings

### Apache Airflow

**Ключевые идеи:**
- **Kahn's Algorithm** для topological sort ✅ (ИСПОЛЬЗУЕМ)
- **Trigger Rules** (all_success, one_success, all_failed)
- **CeleryExecutor** для параллельного выполнения

**Что берем:**
- ✅ Kahn's Algorithm → простой, эффективный, встроенное обнаружение циклов
- ✅ Топологическая сортировка → определяет порядок выполнения
- ✅ Dependency resolution → upstream tasks перед downstream

**Что НЕ берем:**
- ❌ Scheduler (heartbeat polling) → слишком тяжело для нашего use case
- ❌ Python-based DAG definition → мы используем JSON (для UI)

### Prefect

**Ключевые идеи:**
- **Pythonic API** - `@flow` и `@task` decorators
- **Implicit dependencies** - через data flow
- **Transactional orchestration**

**Что берем:**
- ✅ Концепция "легкого" workflow engine (без тяжелой инфраструктуры)
- ✅ Durable execution → сохранение state в DB

**Что НЕ берем:**
- ❌ Implicit dependencies → нам нужны explicit (для визуализации)
- ❌ Python functions → мы используем JSON DAG

### Temporal

**Ключевые идеи:**
- **Event Sourcing** - workflow state как event log
- **Deterministic Replay** - воспроизведение при failure

**Что берем:**
- ✅ Концепция durable execution
- ✅ Deterministic workflow (идемпотентность)

**Что НЕ берем:**
- ❌ Event sourcing infrastructure → слишком сложно для Phase 2
- ❌ Temporal cluster → heavy infrastructure

### n8n

**Ключевые идеи:**
- **Nodes+Edges JSON** ✅ (ИСПОЛЬЗУЕМ - точно твой выбор!)
- **Visual builder** (React Flow)
- **Data passing** через `{{ $json.field }}`

**Что берем:**
- ✅ Nodes+Edges JSON format → понятный, стандартный
- ✅ Data passing syntax → `{{ step1.result.field }}`
- ✅ Visual builder идея → для Track 4 (Phase 3)

**Что НЕ берем:**
- ❌ Ограниченный параллелизм n8n → мы используем Celery для true parallel

### Финальный выбор

**Гибридный подход:**
- **Format:** Nodes+Edges JSON (как n8n) ✅
- **Algorithm:** Kahn's topological sort (как Airflow) ✅
- **Parallel:** Celery group (как Airflow CeleryExecutor) ✅
- **Expressions:** Jinja2 (как Track 1 для consistency) ✅

---

## Архитектура

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    WorkflowEngine                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │            1. DAGValidator                        │  │
│  │   - Validate structure (nodes, edges)            │  │
│  │   - Cycle detection (Kahn's algorithm)           │  │
│  │   - Unreachable nodes detection                  │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │            2. DAGExecutor                         │  │
│  │   - Topological sort (execution plan)            │  │
│  │   - Execute nodes in order                       │  │
│  │   - Handle failures & retries                    │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │        3. NodeHandlerFactory                      │  │
│  │   ┌─────────────────────────────────────────┐    │  │
│  │   │ OperationHandler (Track 1 integration)  │    │  │
│  │   │ ConditionHandler (Jinja2 expressions)   │    │  │
│  │   │ ParallelHandler (Celery group)          │    │  │
│  │   │ LoopHandler (count/while/foreach)       │    │  │
│  │   │ SubWorkflowHandler (recursion)          │    │  │
│  │   └─────────────────────────────────────────┘    │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │        4. ContextManager (Data Passing)           │  │
│  │   - Store step results                            │  │
│  │   - Provide {{ step1.result.field }}             │  │
│  └─────────────────────┬─────────────────────────────┘  │
│                        │                                 │
│                        ▼                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │        5. ResultCollector (Audit Trail)           │  │
│  │   - Store WorkflowStepResult for each step       │  │
│  │   - Debugging & monitoring                        │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Input | Output |
|-----------|---------------|-------|--------|
| **WorkflowEngine** | Orchestrate workflow execution | WorkflowTemplate, input_context | WorkflowExecution |
| **DAGValidator** | Validate DAG structure | dag_structure JSON | ValidationResult |
| **DAGExecutor** | Execute nodes in order | nodes, edges, context | final_result |
| **OperationHandler** | Execute OperationTemplate | node, context | operation_result |
| **ConditionHandler** | Evaluate expressions | node, context | bool (true/false) |
| **ParallelHandler** | Execute nodes in parallel | node, context | parallel_results |
| **LoopHandler** | Execute loops | node, context | loop_results |
| **SubWorkflowHandler** | Execute sub-workflow | node, context | subworkflow_result |
| **ContextManager** | Manage data passing | step_results | context dict |
| **ResultCollector** | Store step results | execution, node, result | WorkflowStepResult |

---

## Django Models

### WorkflowTemplate

```python
class WorkflowTemplate(models.Model):
    """
    Defines a workflow (DAG of operations).

    Similar to OperationTemplate, but for multi-step workflows.
    """

    # Identity
    id = models.CharField(max_length=64, primary_key=True, default=generate_id)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    # Workflow Type
    workflow_type = models.CharField(
        max_length=50,
        choices=[
            ('sequential', 'Sequential'),      # Simple linear flow
            ('conditional', 'Conditional'),    # With if/else branches
            ('parallel', 'Parallel'),          # Concurrent execution
            ('complex', 'Complex'),            # Mix of all
        ],
        default='sequential'
    )

    # DAG Definition (Nodes + Edges JSON format)
    dag_structure = models.JSONField(
        default=dict,
        help_text="DAG structure: {nodes: [...], edges: [...]}"
    )

    # Example dag_structure:
    # {
    #   "nodes": [
    #     {
    #       "id": "step1",
    #       "name": "Создать контрагента",
    #       "type": "operation",
    #       "template_id": "uuid-of-OperationTemplate",
    #       "config": {"timeout": 60, "retries": 3}
    #     },
    #     {
    #       "id": "condition1",
    #       "name": "Проверка суммы",
    #       "type": "condition",
    #       "expression": "{{ step1.result.сумма > 100000 }}",
    #       "branches": {"true": "step_verify", "false": "step_approve"}
    #     }
    #   ],
    #   "edges": [
    #     {"from": "step1", "to": "condition1"},
    #     {"from": "condition1", "to": "step_verify", "condition": "true"},
    #     {"from": "condition1", "to": "step_approve", "condition": "false"}
    #   ]
    # }

    # Workflow Configuration
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Execution config (timeout, retries, parallel_limit, max_depth)"
    )

    # Example config:
    # {
    #   "execution_timeout": 3600,  # 1 hour
    #   "max_retries": 3,
    #   "parallel_limit": 10,  # max concurrent nodes
    #   "max_depth": 10,  # max sub-workflow depth
    #   "required_input_vars": ["контрагент_name", "сумма"]
    # }

    # Validation
    is_valid = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list, blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)

    # Status
    is_active = models.BooleanField(default=True)

    # Version Control
    version = models.IntegerField(default=1)
    parent_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_versions',
        help_text="Previous version (for version control)"
    )

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workflow_templates'
        ordering = ['name']
        indexes = [
            models.Index(fields=['workflow_type', 'is_active']),
            models.Index(fields=['is_valid', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} (v{self.version})"
```

### WorkflowExecution

```python
class WorkflowExecution(models.Model):
    """
    Instance of workflow execution.

    Tracks execution state, results, and progress.
    """

    # Identity
    id = models.CharField(max_length=64, primary_key=True, default=generate_id)

    # Relations
    workflow_template = models.ForeignKey(
        WorkflowTemplate,
        on_delete=models.CASCADE,
        related_name='executions'
    )

    # Execution Context (input variables)
    input_context = models.JSONField(
        default=dict,
        help_text="Input variables for workflow execution"
    )

    # Current State
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('paused', 'Paused'),          # для human-in-the-loop (Phase 3)
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        default='pending',
        db_index=True
    )

    # Execution Progress
    current_node_id = models.CharField(max_length=64, blank=True)
    completed_nodes = models.JSONField(default=list)  # list of node_ids
    failed_nodes = models.JSONField(default=list)

    # Step Results (for data passing)
    step_results = models.JSONField(
        default=dict,
        help_text="Results from completed steps: {node_id: result_data}"
    )

    # Final Result
    final_result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    error_node_id = models.CharField(max_length=64, blank=True)

    # Execution Tracking
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True,
        help_text="Celery task ID for async execution"
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    triggered_by = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'workflow_executions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['workflow_template', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['celery_task_id']),
        ]

    def __str__(self):
        return f"Execution {self.id[:8]} - {self.workflow_template.name}"

    @property
    def progress_percent(self):
        """Calculate execution progress (0-100%)."""
        total_nodes = len(self.workflow_template.dag_structure.get('nodes', []))
        if total_nodes == 0:
            return 0
        completed = len(self.completed_nodes)
        return int((completed / total_nodes) * 100)
```

### WorkflowStepResult

```python
class WorkflowStepResult(models.Model):
    """
    Detailed result for each workflow step.

    Used for debugging, audit trail, and data passing between steps.
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
    node_type = models.CharField(max_length=50)  # operation, condition, parallel, etc.

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('skipped', 'Skipped'),  # для conditional branches
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

    # Retry tracking
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

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

    def __str__(self):
        return f"{self.node_name} - {self.status}"
```

---

## WorkflowEngine Components

### 1. WorkflowEngine (Main Orchestrator)

**Файл:** `orchestrator/apps/templates/workflow/engine.py`

**Responsibilities:**
- Validate workflow DAG
- Execute workflow nodes in correct order
- Handle failures, retries, cancellations
- Manage execution context (data passing)

**Key Methods:**

```python
class WorkflowEngine:
    def __init__(self):
        self.validator = DAGValidator()
        self.executor = DAGExecutor()
        self.context_manager = ContextManager()
        self.result_collector = ResultCollector()

    def execute_workflow(
        self,
        workflow_template: WorkflowTemplate,
        input_context: dict,
        execution_id: str = None
    ) -> WorkflowExecution:
        """Execute workflow from start to finish."""
        # 1. Create or resume execution
        # 2. Validate DAG
        # 3. Start execution
        # 4. Execute DAG
        # 5. Mark as completed/failed
        # 6. Return WorkflowExecution

    def cancel_workflow(self, execution_id: str):
        """Cancel running workflow."""
        # 1. Revoke Celery task
        # 2. Update status to 'cancelled'

    def resume_workflow(self, execution_id: str):
        """Resume paused/failed workflow."""
        # 1. Load execution
        # 2. Continue from current_node_id
```

---

### 2. DAGValidator

**Файл:** `orchestrator/apps/templates/workflow/validator.py`

**Algorithm:** Kahn's Algorithm for Topological Sort

```python
class DAGValidator:
    """Validates DAG structure."""

    def validate(self, dag_structure: dict) -> ValidationResult:
        """Validate DAG structure."""
        errors = []
        warnings = []

        # 1. Check nodes exist
        # 2. Validate edges reference existing nodes
        # 3. Check for cycles (Kahn's algorithm)
        # 4. Check connectivity (BFS)
        # 5. Validate node types

        return ValidationResult(is_valid=len(errors)==0, errors=errors, warnings=warnings)

    def _topological_sort(self, nodes: list, edges: list) -> list:
        """
        Kahn's algorithm for topological sort.

        Raises CycleDetectedError if cycle found.
        """
        # 1. Build in-degree map
        in_degree = {node['id']: 0 for node in nodes}
        adjacency = {node['id']: [] for node in nodes}

        for edge in edges:
            adjacency[edge['from']].append(edge['to'])
            in_degree[edge['to']] += 1

        # 2. Queue nodes with no dependencies (in-degree=0)
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        result = []

        # 3. Process queue (BFS-style)
        while queue:
            current = queue.pop(0)
            result.append(current)

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 4. Check for cycles
        if len(result) != len(nodes):
            cycle_nodes = [node_id for node_id, degree in in_degree.items() if degree > 0]
            raise CycleDetectedError(f"DAG contains cycles: {cycle_nodes}")

        return result
```

**Why Kahn's Algorithm?**
- ✅ Iterative (не рекурсивный) → меньше stack overflow риска
- ✅ Natural cycle detection (если `len(result) != len(nodes)`)
- ✅ BFS-style → можно легко добавить параллелизм
- ✅ O(V + E) complexity → эффективен даже для больших DAGs

---

### 3. NodeHandlers

**Файл:** `orchestrator/apps/templates/workflow/handlers.py`

#### OperationHandler (интеграция с Track 1)

```python
class OperationHandler:
    """
    Executes OperationTemplate (single operation).

    Uses TemplateRenderer from Track 1.
    """

    def __init__(self):
        from apps.templates.engine import TemplateRenderer
        self.renderer = TemplateRenderer()

    def execute(self, node: dict, context: dict, execution: WorkflowExecution) -> dict:
        """Execute operation node."""
        # 1. Get OperationTemplate
        from apps.templates.models import OperationTemplate
        template = OperationTemplate.objects.get(id=node['template_id'])

        # 2. Render template with context (включает step results!)
        rendered_data = self.renderer.render(template, context, validate=True)

        # 3. Execute operation (через BatchOperation + Celery → Worker)
        # TODO: Integration с Track 2 (Worker integration)
        from apps.operations.models import BatchOperation

        operation = BatchOperation.objects.create(
            name=f"Workflow step: {node['name']}",
            operation_type=template.operation_type,
            payload=rendered_data,
            template=template
        )

        # Execute via Celery
        from apps.operations.tasks import process_operation_with_template
        result = process_operation_with_template.delay(str(operation.id))

        # Wait for result (или return task ID для async)
        return result.get()  # Blocks until operation completes
```

#### ConditionHandler

```python
class ConditionHandler:
    """Evaluates conditional expressions using Jinja2."""

    def __init__(self):
        from jinja2.sandbox import ImmutableSandboxedEnvironment
        self.env = ImmutableSandboxedEnvironment()

    def execute(self, node: dict, context: dict, execution: WorkflowExecution) -> dict:
        """Evaluate condition."""
        expression = node['expression']

        # Render expression with context
        try:
            # Remove outer {{ }} if present
            clean_expr = expression.strip()
            if clean_expr.startswith('{{') and clean_expr.endswith('}}'):
                clean_expr = clean_expr[2:-2].strip()

            template = self.env.from_string("{{ " + clean_expr + " }}")
            result_str = template.render(context)

            # Convert to boolean
            condition_result = self._to_boolean(result_str)

            return {
                '_condition_result': condition_result,
                'expression': expression,
                'evaluated_to': condition_result
            }

        except Exception as e:
            raise ConditionEvaluationError(f"Failed to evaluate condition '{expression}': {e}")

    def _to_boolean(self, value: any) -> bool:
        """Convert value to boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ['true', '1', 'yes']
        if isinstance(value, (int, float)):
            return value != 0
        return bool(value)
```

#### ParallelHandler

```python
class ParallelHandler:
    """Executes nodes in parallel using Celery group."""

    def execute(self, node: dict, context: dict, execution: WorkflowExecution) -> dict:
        """Execute parallel nodes."""
        from celery import group
        from apps.operations.tasks import execute_workflow_node  # Celery task

        parallel_nodes = node['parallel_nodes']
        wait_for = node.get('wait_for', 'all')

        # 1. Create Celery group
        tasks = group([
            execute_workflow_node.s(node_id, context, str(execution.id))
            for node_id in parallel_nodes
        ])

        # 2. Execute group
        result = tasks.apply_async()

        # 3. Wait for results
        if wait_for == 'all':
            results = result.get()  # Wait for all
        elif wait_for == 'any':
            results = [result.get(timeout=1)]  # First result
        elif isinstance(wait_for, int):
            results = []
            for _ in range(wait_for):
                results.append(result.get())

        return {
            'parallel_results': results,
            'completed_count': len(results)
        }
```

#### LoopHandler

```python
class LoopHandler:
    """Executes loop nodes (count/while/foreach)."""

    def execute(self, node: dict, context: dict, execution: WorkflowExecution) -> dict:
        """Execute loop node."""
        loop_config = node['loop_config']
        mode = loop_config['mode']

        results = []

        if mode == 'count':
            count = loop_config['count']
            for i in range(count):
                context['loop_index'] = i
                result = self._execute_loop_iteration(node, context, execution)
                results.append(result)

        elif mode == 'while':
            condition = loop_config['condition']
            max_iterations = loop_config.get('max_iterations', 1000)

            iteration = 0
            while self._evaluate_condition(condition, context) and iteration < max_iterations:
                context['loop_index'] = iteration
                result = self._execute_loop_iteration(node, context, execution)
                results.append(result)
                iteration += 1

        elif mode == 'foreach':
            items_expr = loop_config['items']
            items = self._get_items(items_expr, context)

            for i, item in enumerate(items):
                context['loop_index'] = i
                context['loop_item'] = item
                result = self._execute_loop_iteration(node, context, execution)
                results.append(result)

        return {
            'loop_results': results,
            'iteration_count': len(results)
        }
```

#### SubWorkflowHandler

```python
class SubWorkflowHandler:
    """Executes sub-workflow (recursive workflow execution)."""

    MAX_DEPTH = 10  # Safety limit for recursion

    def execute(self, node: dict, context: dict, execution: WorkflowExecution) -> dict:
        """Execute sub-workflow."""
        # 1. Check recursion depth
        current_depth = context.get('_workflow_depth', 0)
        if current_depth >= self.MAX_DEPTH:
            raise MaxDepthExceededError(f"Max workflow depth ({self.MAX_DEPTH}) exceeded")

        # 2. Get sub-workflow template
        from apps.templates.models import WorkflowTemplate
        subworkflow_template = WorkflowTemplate.objects.get(id=node['subworkflow_id'])

        # 3. Map input context (parent → child)
        input_mapping = node.get('input_mapping', {})
        subworkflow_context = self._map_context(input_mapping, context)

        # Add depth tracking
        subworkflow_context['_workflow_depth'] = current_depth + 1
        subworkflow_context['_parent_execution_id'] = execution.id

        # 4. Execute sub-workflow (РЕКУРСИЯ!)
        engine = WorkflowEngine()
        subworkflow_execution = engine.execute_workflow(
            workflow_template=subworkflow_template,
            input_context=subworkflow_context
        )

        # 5. Map output context (child → parent)
        output_mapping = node.get('output_mapping', {})
        result = self._map_result(output_mapping, subworkflow_execution.final_result)

        return result
```

---

### 4. ContextManager (Data Passing)

**Файл:** `orchestrator/apps/templates/workflow/context.py`

```python
class ContextManager:
    """
    Manages execution context and data passing between steps.

    Context structure:
    {
      # User input
      "контрагент_name": "ООО Рога и копыта",
      "сумма": 150000,

      # System variables
      "current_timestamp": datetime(...),

      # Step results (for data passing)
      "step1": {"ref_key": "uuid-контрагента", "name": "..."},
      "step2": {"ref_key": "uuid-договора", "номер": "..."},

      # Internal
      "_steps": {...},  # Structured step results
      "_workflow_depth": 0  # Recursion tracking
    }
    """

    def __init__(self):
        self.context = {}

    def initialize_context(self, input_context: dict) -> dict:
        """Initialize context with input variables."""
        self.context = input_context.copy()
        self.context['_steps'] = {}
        self.context['_workflow_depth'] = 0
        return self.context

    def set_step_result(self, node_id: str, result: dict):
        """Store step result for data passing."""
        self.context['_steps'][node_id] = result

        # Make available as top-level variable for convenience
        self.context[node_id] = result

    def get_step_result(self, node_id: str) -> dict:
        """Get result from previous step."""
        return self.context['_steps'].get(node_id, {})

    def get_context(self) -> dict:
        """Get full context (for rendering)."""
        return self.context

    def get_final_result(self) -> dict:
        """Get final result (all step results)."""
        return self.context['_steps']
```

---

## JSON Schema

**Full JSON Schema для WorkflowTemplate.dag_structure:**

См. файл: `docs/schemas/workflow_dag_schema.json`

**Краткая версия:**

```json
{
  "nodes": [
    {
      "id": "string (required)",
      "name": "string (required)",
      "type": "operation | condition | parallel | loop | subworkflow (required)",

      // For type=operation
      "template_id": "uuid",

      // For type=condition
      "expression": "{{ jinja2_expression }}",
      "branches": {"true": "node_id", "false": "node_id"},

      // For type=parallel
      "parallel_nodes": ["node_id1", "node_id2"],
      "wait_for": "all | any | N",

      // For type=loop
      "loop_config": {
        "mode": "count | while | foreach",
        "count": 10,  // for mode=count
        "condition": "{{ expression }}",  // for mode=while
        "items": "{{ expression }}",  // for mode=foreach
        "loop_node": "node_id",
        "max_iterations": 1000
      },

      // For type=subworkflow
      "subworkflow_id": "uuid",
      "input_mapping": {"child_var": "{{ parent_var }}"},
      "output_mapping": {"parent_var": "child_var"},

      // Optional
      "config": {"timeout": 60, "retries": 3},
      "position": {"x": 100, "y": 100}  // For UI
    }
  ],
  "edges": [
    {
      "from": "node_id (required)",
      "to": "node_id (required)",
      "condition": "true | false (optional, for conditional edges)"
    }
  ]
}
```

---

## Примеры Workflows

### Example 1: Создание реализации (из требований)

```json
{
  "nodes": [
    {
      "id": "step1",
      "name": "Создать контрагента",
      "type": "operation",
      "template_id": "tmpl_create_counterparty"
    },
    {
      "id": "step2",
      "name": "Создать договор",
      "type": "operation",
      "template_id": "tmpl_create_contract"
    },
    {
      "id": "step3",
      "name": "Создать документ",
      "type": "operation",
      "template_id": "tmpl_create_document"
    },
    {
      "id": "step4",
      "name": "Заполнить документ",
      "type": "operation",
      "template_id": "tmpl_fill_document"
    },
    {
      "id": "condition_sum",
      "name": "Проверка суммы > 100k",
      "type": "condition",
      "expression": "{{ step3.result.сумма > 100000 }}",
      "branches": {"true": "step_verify", "false": "step_approve"}
    },
    {
      "id": "step_verify",
      "name": "Ручная верификация",
      "type": "operation",
      "template_id": "tmpl_manual_verification"
    },
    {
      "id": "step_approve",
      "name": "Авто-подтверждение",
      "type": "operation",
      "template_id": "tmpl_auto_approve"
    },
    {
      "id": "step_post",
      "name": "Провести документ",
      "type": "operation",
      "template_id": "tmpl_post_document"
    },
    {
      "id": "step_report",
      "name": "Создать отчет контроля",
      "type": "operation",
      "template_id": "tmpl_generate_report"
    }
  ],
  "edges": [
    {"from": "step1", "to": "step2"},
    {"from": "step2", "to": "step3"},
    {"from": "step3", "to": "step4"},
    {"from": "step4", "to": "condition_sum"},
    {"from": "condition_sum", "to": "step_verify", "condition": "true"},
    {"from": "condition_sum", "to": "step_approve", "condition": "false"},
    {"from": "step_verify", "to": "step_post"},
    {"from": "step_approve", "to": "step_post"},
    {"from": "step_post", "to": "step_report"}
  ]
}
```

**Data Passing в этом workflow:**

```python
# step2 использует результат step1:
# В OperationTemplate для step2, template_data:
{
  "контрагент": "{{ step1.result.ref_key }}",  # ← берет из step1!
  "дата": "{{ current_date }}"
}

# step3 использует результаты step1 и step2:
{
  "контрагент": "{{ step1.result.ref_key }}",
  "договор": "{{ step2.result.ref_key }}",
  "номер": "РЕА-{{ uuid4() }}"
}
```

---

### Example 2: Parallel Execution

**Задача:** Создать несколько документов параллельно

```json
{
  "nodes": [
    {"id": "prep", "name": "Подготовка", "type": "operation", "template_id": "tmpl_prep"},
    {
      "id": "parallel1",
      "name": "Создать документы параллельно",
      "type": "parallel",
      "parallel_nodes": ["doc1", "doc2", "doc3"],
      "wait_for": "all"
    },
    {"id": "doc1", "name": "Документ 1", "type": "operation", "template_id": "tmpl_doc"},
    {"id": "doc2", "name": "Документ 2", "type": "operation", "template_id": "tmpl_doc"},
    {"id": "doc3", "name": "Документ 3", "type": "operation", "template_id": "tmpl_doc"},
    {"id": "finalize", "name": "Финализация", "type": "operation", "template_id": "tmpl_final"}
  ],
  "edges": [
    {"from": "prep", "to": "parallel1"},
    {"from": "parallel1", "to": "finalize"}
  ]
}
```

**Execution:**
- `prep` выполняется
- `doc1`, `doc2`, `doc3` выполняются **параллельно** (Celery group)
- `finalize` выполняется после завершения **всех** документов

---

### Example 3: Loop (foreach)

**Задача:** Создать 100 контрагентов из списка

```json
{
  "nodes": [
    {"id": "load", "name": "Загрузить список", "type": "operation", "template_id": "tmpl_load"},
    {
      "id": "loop1",
      "name": "Цикл создания",
      "type": "loop",
      "loop_config": {
        "mode": "foreach",
        "items": "{{ load.result.контрагенты }}",
        "loop_node": "create"
      }
    },
    {"id": "create", "name": "Создать контрагента", "type": "operation", "template_id": "tmpl_create"},
    {"id": "summary", "name": "Сводка", "type": "operation", "template_id": "tmpl_summary"}
  ],
  "edges": [
    {"from": "load", "to": "loop1"},
    {"from": "loop1", "to": "summary"}
  ]
}
```

**Context в цикле:**

```python
# Iteration 0:
{
  "loop_index": 0,
  "loop_item": {"name": "Контрагент 1", "inn": "1234567890"},
  "load": {"result": {"контрагенты": [...]}}
}

# Iteration 1:
{
  "loop_index": 1,
  "loop_item": {"name": "Контрагент 2", "inn": "0987654321"}
}
```

---

### Example 4: Sub-workflow (глубокая вложенность)

**Parent Workflow:** Обработка заказа

```json
{
  "nodes": [
    {"id": "create_order", "name": "Создать заказ", "type": "operation", "template_id": "tmpl_order"},
    {
      "id": "subwf1",
      "name": "Обработать позиции",
      "type": "subworkflow",
      "subworkflow_id": "wf_process_items",
      "input_mapping": {
        "заказ_id": "{{ create_order.result.ref_key }}",
        "позиции": "{{ create_order.result.items }}"
      },
      "output_mapping": {
        "processed_count": "обработано"
      }
    },
    {"id": "finalize", "name": "Финализация", "type": "operation", "template_id": "tmpl_finalize"}
  ],
  "edges": [
    {"from": "create_order", "to": "subwf1"},
    {"from": "subwf1", "to": "finalize"}
  ]
}
```

**Child Workflow (wf_process_items):**

```json
{
  "nodes": [
    {
      "id": "loop_items",
      "type": "loop",
      "loop_config": {
        "mode": "foreach",
        "items": "{{ позиции }}",
        "loop_node": "process_one"
      }
    },
    {"id": "process_one", "type": "operation", "template_id": "tmpl_process_item"}
  ],
  "edges": []
}
```

**Depth tracking:**
```
Parent Workflow (depth=0)
  → Child Workflow (depth=1)
    → Grandchild Workflow (depth=2)
      → ... (max depth=10)
```

---

## Integration с Track 1

### Использование TemplateRenderer

```python
# В OperationHandler.execute()

from apps.templates.models import OperationTemplate
from apps.templates.engine import TemplateRenderer

# 1. Get OperationTemplate (атомарная операция)
template = OperationTemplate.objects.get(id=node['template_id'])

# 2. Prepare context (включает step results!)
context = {
    'step1': {"ref_key": "uuid-контрагента"},  # from previous step
    'step2': {"ref_key": "uuid-договора"},
    'контрагент_id': "uuid-контрагента",  # direct access
    'current_date': datetime.now().date()
}

# 3. Render template (Track 1!)
renderer = TemplateRenderer()
rendered_data = renderer.render(template, context, validate=True)

# 4. Execute operation
# ... через BatchOperation + Celery + Worker ...
```

**Полная совместимость!** Все существующие OperationTemplate (из Track 1) могут использоваться в workflow nodes!

---

## Validation Strategy

### DAG Structure Validation

**Проверки:**

1. ✅ **No cycles** - Kahn's algorithm
2. ✅ **All nodes reachable** - BFS от start nodes
3. ✅ **Valid edges** - from/to nodes exist
4. ✅ **Valid node types** - operation | condition | parallel | loop | subworkflow

**Type-specific validation:**

- `operation` → must have `template_id`
- `condition` → must have `expression` + `branches`
- `parallel` → must have `parallel_nodes`
- `loop` → must have `loop_config`
- `subworkflow` → must have `subworkflow_id`

**Business logic validation:**

- Condition expression → validate Jinja2 syntax
- Loop → max_iterations default (prevent infinite loops)
- Subworkflow → check circular references

---

## Testing Strategy

### Unit Tests (~50 tests)

**DAGValidator (15 tests):**
- validate_empty_dag()
- validate_valid_linear_dag()
- validate_dag_with_cycle_should_fail()
- validate_dag_with_unreachable_nodes()
- validate_invalid_node_type()
- validate_missing_template_id()
- ...

**NodeHandlers (20 tests):**
- OperationHandler: 5 tests
- ConditionHandler: 5 tests
- ParallelHandler: 4 tests
- LoopHandler: 4 tests
- SubWorkflowHandler: 2 tests

**ContextManager (5 tests):**
- initialize_context()
- set_step_result()
- get_step_result()
- data_passing_between_steps()

**Kahn's Algorithm (10 tests):**
- topological_sort_linear_dag()
- topological_sort_branching_dag()
- topological_sort_diamond_dag()
- topological_sort_with_cycle_should_raise()
- ...

### Integration Tests (~20 tests)

- execute_linear_workflow()
- execute_conditional_workflow()
- execute_parallel_workflow()
- execute_loop_workflow()
- execute_subworkflow()
- execute_complex_workflow()
- failure_handling_with_retry()
- workflow_cancellation()

---

## Timeline

**Total: 6-7 дней (48-56 часов)**

| День | Задачи | Часы | Deliverable |
|------|--------|------|-------------|
| **1** | Models + Migrations | 8h | Django models готовы |
| **2** | DAGValidator + Kahn's algorithm | 8h | Cycle detection работает |
| **3** | OperationHandler + ConditionHandler | 8h | Basic execution работает |
| **4** | ParallelHandler + LoopHandler | 8h | Parallel + Loop работают |
| **5** | SubWorkflowHandler + WorkflowEngine | 8h | Full workflow execution |
| **6** | REST API endpoints | 8h | API готов |
| **7** | Documentation + Tests | 8h | Production ready |

**Когда начинать:** Phase 2, после Track 2-3 (Worker integration)

---

## Risks & Mitigation

### Risk 1: Celery Integration Complexity

**Probability:** Medium
**Impact:** High

**Mitigation:**
- Начать с sequential execution
- Добавить parallel во вторую очередь
- Extensive logging
- Retry mechanism
- Timeout limits

### Risk 2: Infinite Loops / Recursion

**Probability:** Medium
**Impact:** Critical

**Mitigation:**
- ✅ Max loop iterations (default: 1000)
- ✅ Max workflow depth (default: 10)
- ✅ Execution timeout (default: 1 hour)
- ✅ Pre-execution validation

### Risk 3: Data Passing Performance

**Probability:** Low
**Impact:** Medium

**Mitigation:**
- Store step results in DB (WorkflowStepResult)
- Lazy loading
- Context size limit (10MB)
- Retention policy (30 days)

### Risk 4: Conditional Expression Security

**Probability:** Low
**Impact:** Critical

**Mitigation:**
- ✅ ImmutableSandboxedEnvironment (как Track 1)
- ✅ Whitelist functions
- ✅ No eval/exec
- Expression complexity limit (1000 chars)

---

## Phase 2 Roadmap

### Track 1.5: Workflow Engine (6-7 дней)

**Когда:** Phase 2 (после Track 2-3)

**Scope:**
- WorkflowTemplate model
- DAGValidator (Kahn's algorithm)
- NodeHandlers (5 типов)
- WorkflowEngine orchestrator
- REST API endpoints
- Unit + Integration tests

### Track 1.6: Visual Workflow Builder (10-12 дней)

**Когда:** Phase 3 (после Track 4 - Basic UI)

**Scope:**
- React Flow integration
- Drag-and-drop node creation
- Visual edge routing
- Node configuration modal
- Real-time validation

**Dependencies:**
- Track 4 (Basic UI)
- Track 1.5 REST API

### Track 1.7: Advanced Features (15-20 дней)

**Когда:** Phase 4 (Production Readiness)

**Features:**
1. Human-in-the-Loop (pause/resume с approval)
2. Error Handling & Rollback (saga pattern)
3. Workflow Versioning
4. Performance Optimization

---

## REST API Reference

### WorkflowTemplate CRUD

```
POST   /api/v1/workflows/templates/          # Create workflow
GET    /api/v1/workflows/templates/          # List workflows
GET    /api/v1/workflows/templates/{id}/     # Get workflow
PUT    /api/v1/workflows/templates/{id}/     # Update workflow
DELETE /api/v1/workflows/templates/{id}/     # Delete workflow
```

### Workflow Validation

```
POST   /api/v1/workflows/templates/{id}/validate/
# Validate DAG structure (cycles, reachability, node types)
```

### Workflow Execution

```
POST   /api/v1/workflows/executions/
# Execute workflow
# Body: {"workflow_id": "uuid", "input_context": {...}}

GET    /api/v1/workflows/executions/
# List all executions (with filters)

GET    /api/v1/workflows/executions/{id}/
# Get execution status + progress

POST   /api/v1/workflows/executions/{id}/cancel/
# Cancel running workflow

GET    /api/v1/workflows/executions/{id}/steps/
# Get detailed step results (WorkflowStepResult)
```

---

## Заключение

### Архитектурные преимущества

✅ **Простота:** Nodes+Edges JSON → понятно даже non-developers
✅ **Гибкость:** 5 типов узлов покрывают 95% use cases
✅ **Масштабируемость:** Celery group для parallel execution
✅ **Безопасность:** Jinja2 sandbox для expressions
✅ **Тестируемость:** Каждый компонент изолирован
✅ **Extensibility:** Легко добавить новые node types
✅ **Integration:** Seamless с Track 1 (TemplateRenderer)

### Ключевые решения

1. **Kahn's Algorithm** → simple, efficient, cycle detection built-in
2. **Celery group** → leverages existing infrastructure
3. **Jinja2 expressions** → consistent с Track 1
4. **Recursive sub-workflows** → unlimited composition (с safety limit)
5. **Context-based data passing** → intuitive для users

### Готовность к реализации

**Track 1.5 готов к началу работ:**
- ✅ Архитектура спроектирована
- ✅ Models defined
- ✅ JSON schema готова
- ✅ Node handlers специфицированы
- ✅ Validation strategy определена
- ✅ Testing plan готов
- ✅ Timeline реалистичная (6-7 дней)

**Рекомендация:** Начать реализацию Track 1.5 в Phase 2, после завершения Track 2-3 (Worker integration).

---

## Appendix A: Celery Task Definitions

```python
# apps/operations/tasks.py

from celery import shared_task

@shared_task(bind=True, max_retries=3)
def execute_workflow_task(self, workflow_id: str, input_context: dict):
    """Celery task для выполнения workflow."""
    from apps.templates.models import WorkflowTemplate
    from apps.templates.workflow import WorkflowEngine

    workflow = WorkflowTemplate.objects.get(id=workflow_id)
    engine = WorkflowEngine()

    try:
        execution = engine.execute_workflow(workflow, input_context)
        return execution.id
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


@shared_task
def execute_workflow_node(node_id: str, context: dict, execution_id: str):
    """Celery task для выполнения одного node (для ParallelHandler)."""
    from apps.templates.models import WorkflowExecution
    from apps.templates.workflow import NodeHandlerFactory

    execution = WorkflowExecution.objects.get(id=execution_id)
    dag = execution.workflow_template.dag_structure

    # Find node
    node = next((n for n in dag['nodes'] if n['id'] == node_id), None)

    # Execute
    handler_factory = NodeHandlerFactory()
    handler = handler_factory.get_handler(node['type'])
    result = handler.execute(node, context, execution)

    return result
```

---

## Appendix B: Visualization (Track 4)

**Для визуализации workflow в UI (Track 1.6):**

**React Flow:**

```typescript
import ReactFlow, { Node, Edge } from 'reactflow';

// Convert WorkflowTemplate.dag_structure → React Flow format
const nodes: Node[] = workflow.dag_structure.nodes.map(node => ({
  id: node.id,
  type: node.type === 'condition' ? 'diamond' :
        node.type === 'parallel' ? 'parallel' : 'default',
  position: node.position || { x: 0, y: 0 },
  data: {
    label: node.name,
    template_id: node.template_id,
    // ... other data
  }
}));

const edges: Edge[] = workflow.dag_structure.edges.map(edge => ({
  id: `${edge.from}-${edge.to}`,
  source: edge.from,
  target: edge.to,
  label: edge.condition || '',
  animated: true
}));

<ReactFlow nodes={nodes} edges={edges} />
```

---

**Конец документации.**

**Версия:** 1.0
**Последнее обновление:** 2025-11-09
**Статус:** Утверждено для реализации в Phase 2
