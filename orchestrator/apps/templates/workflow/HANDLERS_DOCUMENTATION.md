# NodeHandlers Documentation

**Version:** 1.0
**Date:** 2025-11-23
**Status:** Week 7 Complete (Part 1)

---

## 📋 Overview

NodeHandlers выполняют отдельные nodes в workflow. Week 7 реализовано 2 handler:

1. **OperationHandler** - выполняет OperationTemplate (Track 1 integration)
2. **ConditionHandler** - evaluates Jinja2 boolean expressions

Week 8 добавит: ParallelHandler, LoopHandler, SubWorkflowHandler

---

## 🏗️ Architecture

### Components

**NodeExecutionMode** (Enum):
- `SYNC` - wait for result
- `ASYNC` - return task_id (Week 9)

**NodeExecutionResult** (dataclass):
```python
@dataclass
class NodeExecutionResult:
    success: bool                      # Успешно или ошибка
    output: Any                        # Результат выполнения
    error: Optional[str]               # Сообщение об ошибке
    mode: NodeExecutionMode            # SYNC/ASYNC
    duration_seconds: Optional[float]  # Длительность
```

**BaseNodeHandler** (ABC):
- `execute(node, context, execution, mode)` - abstract method
- `_create_step_result()` - создает WorkflowStepResult
- `_update_step_result()` - обновляет результат

---

## 🔧 OperationHandler

### Purpose

Выполняет OperationTemplate используя Track 1 Template Engine.

### Flow

```
1. Get OperationTemplate by node.template_id
2. Render template with context (TemplateRenderer)
3. TODO Week 9: Create BatchOperation + Celery
4. Return rendered data as output
```

### Example

```python
from apps.templates.workflow.handlers import NodeHandlerFactory, NodeExecutionMode
from apps.templates.workflow.models import WorkflowNode, NodeConfig

# Get handler
handler = NodeHandlerFactory.get_handler('operation')

# Create node
node = WorkflowNode(
    id="create_users",
    name="Create Users",
    type="operation",
    template_id="bulk_user_create_v1"  # OperationTemplate ID
)

# Execute
context = {
    "users": [
        {"name": "John", "email": "john@test.com"},
        {"name": "Jane", "email": "jane@test.com"}
    ]
}

result = handler.execute(node, context, execution, mode=NodeExecutionMode.SYNC)

if result.success:
    print(f"Output: {result.output}")  # Rendered template data
    print(f"Duration: {result.duration_seconds}s")
else:
    print(f"Error: {result.error}")
```

### Error Handling

**Errors caught:**
- `OperationTemplate.DoesNotExist` - template not found
- `TemplateRenderError` - rendering failed
- `TemplateValidationError` - template invalid
- Any unexpected exception

**All errors → NodeExecutionResult(success=False)**

---

## ⚙️ ConditionHandler

### Purpose

Evaluates Jinja2 boolean expressions для branching decisions.

### Security

**ImmutableSandboxedEnvironment:**
- ✅ No dangerous functions (`__import__`, `eval`, `exec`)
- ✅ StrictUndefined - fail on undefined variables
- ✅ Whitelist globals: len, str, int, float, bool

### Flow

```
1. Get expression from node.config.expression
2. Render expression in sandbox
3. Convert result to boolean (_to_bool)
4. Return bool as output
```

### Example

```python
# Simple boolean
node = WorkflowNode(
    id="check_status",
    name="Check Status",
    type="condition",
    config=NodeConfig(expression="{{ status == 'approved' }}")
)

context = {"status": "approved"}
result = handler.execute(node, context, execution)

print(result.output)  # True

# Complex expression
node = WorkflowNode(
    id="check_amount",
    name="Check Amount",
    type="condition",
    config=NodeConfig(
        expression="{{ amount > 100000 and currency == 'USD' }}"
    )
)

context = {"amount": 150000, "currency": "USD"}
result = handler.execute(node, context, execution)

print(result.output)  # True
```

### Boolean Conversion (_to_bool)

**String values:**
- True: "true", "True", "yes", "1" (case-insensitive)
- False: "false", "no", "0", "", "none", "None"
- Other non-empty: True

**Numeric:**
- 0 → False
- Non-zero → True

**None:**
- None → False (with warning)

**Collections:**
- Empty [] {} → False
- Non-empty → True

---

## 🏭 NodeHandlerFactory

### Purpose

Registry-based factory для создания handlers.

### Usage

```python
from apps.templates.workflow.handlers import NodeHandlerFactory

# Get handler by type
operation_handler = NodeHandlerFactory.get_handler('operation')
condition_handler = NodeHandlerFactory.get_handler('condition')

# Singleton pattern - same instance returned
h1 = NodeHandlerFactory.get_handler('operation')
h2 = NodeHandlerFactory.get_handler('operation')
assert h1 is h2  # True

# Unknown type raises ValueError
try:
    handler = NodeHandlerFactory.get_handler('nonexistent')
except ValueError as e:
    print(e)  # "No handler registered for node type 'nonexistent'"
```

### Registry

**Current (Week 7):**
- `'operation'` → OperationHandler
- `'condition'` → ConditionHandler

**Future (Week 8):**
- `'parallel'` → ParallelHandler
- `'loop'` → LoopHandler
- `'subworkflow'` → SubWorkflowHandler

### Thread Safety

Factory использует **threading.Lock** для thread-safe singleton creation (double-checked locking).

---

## 🔗 Integration с Track 1

### OperationTemplate

**Model:**
```python
class OperationTemplate:
    id: str
    name: str
    operation_type: str  # "odata_query", "batch_operation", etc.
    target_entity: str   # "Users", "Documents", etc.
    template_data: JSONField  # Template content
```

### TemplateRenderer

**Usage:**
```python
from apps.templates.engine.renderer import TemplateRenderer

renderer = TemplateRenderer()
rendered = renderer.render(
    template=operation_template,
    context_data={"user_id": 123},
    validate=True  # Validate before rendering
)
```

**Returns:** Dict[str, Any] - rendered template data

### Exceptions

```python
from apps.templates.engine.exceptions import (
    TemplateRenderError,      # Rendering failed
    TemplateValidationError   # Template invalid
)
```

---

## 🧪 Testing

### Run Tests

```bash
cd orchestrator
source venv/Scripts/activate

# All workflow tests
pytest apps/templates/workflow/tests/ -v

# Only handlers
pytest apps/templates/workflow/tests/test_handlers.py -v

# With coverage
pytest apps/templates/workflow/tests/test_handlers.py --cov=apps.templates.workflow.handlers
```

### Test Results

**Week 7:**
- 30 tests (handlers)
- 100% passing
- 90% coverage

**Total (Week 5-7):**
- 102 tests (33 models + 39 validator + 30 handlers)
- 100% passing
- ~89% average coverage

---

## 📊 Performance

**OperationHandler:**
- Template rendering: depends on TemplateRenderer (< 100ms typical)
- Singleton pattern: no per-request object creation

**ConditionHandler:**
- Expression evaluation: < 10ms typical
- Sandbox overhead: minimal (cached environment)

---

## 🔒 Security

### ConditionHandler Sandbox

**Prevented:**
- ❌ Code execution (`__import__`, `eval`, `exec`)
- ❌ File access (`open`, `file`)
- ❌ System calls (`os.system`)
- ❌ Attribute modification (ImmutableSandboxedEnvironment)

**Allowed:**
- ✅ Variables from context
- ✅ Basic functions (len, str, int, float, bool)
- ✅ Jinja2 filters and tests
- ✅ Boolean operators (and, or, not)
- ✅ Comparisons (>, <, ==, !=)

### Example Security Test

```python
# Malicious expression
expression = "{{ __import__('os').system('rm -rf /') }}"

# Result: ConditionHandler catches and returns error
result = handler.execute(node_with_malicious_expr, context, execution)
assert result.success is False  # Sandbox blocks it
```

---

## 🚀 Usage in Workflow

### Example Workflow

```json
{
  "name": "User Approval Workflow",
  "nodes": [
    {
      "id": "load_user",
      "type": "operation",
      "template_id": "get_user_by_id"
    },
    {
      "id": "check_role",
      "type": "condition",
      "config": {
        "expression": "{{ load_user_output.role == 'admin' }}"
      }
    },
    {
      "id": "grant_access",
      "type": "operation",
      "template_id": "grant_admin_access"
    }
  ],
  "edges": [
    {"from": "load_user", "to": "check_role"},
    {"from": "check_role", "to": "grant_access"}
  ]
}
```

### Execution Flow

```python
# Week 9 - WorkflowEngine will orchestrate this

# 1. Execute load_user (OperationHandler)
handler1 = NodeHandlerFactory.get_handler('operation')
result1 = handler1.execute(nodes[0], context, execution)
context['load_user_output'] = result1.output

# 2. Execute check_role (ConditionHandler)
handler2 = NodeHandlerFactory.get_handler('condition')
result2 = handler2.execute(nodes[1], context, execution)

# 3. Branch decision
if result2.output:  # True → execute grant_access
    handler3 = NodeHandlerFactory.get_handler('operation')
    result3 = handler3.execute(nodes[2], context, execution)
```

---

## 🔄 Future Enhancements (Week 8-9)

**Week 8:**
- ParallelHandler (execute multiple nodes concurrently)
- LoopHandler (repeat node N times)
- SubWorkflowHandler (recursive workflows)

**Week 9:**
- Celery async execution в OperationHandler
- BatchOperation creation
- Task result polling
- Retry logic

---

## 📚 References

- **Code:** `orchestrator/apps/templates/workflow/handlers.py`
- **Tests:** `orchestrator/apps/templates/workflow/tests/test_handlers.py`
- **Models:** `orchestrator/apps/templates/workflow/models.py`
- **Roadmap:** `docs/roadmaps/UNIFIED_WORKFLOW_ROADMAP.md` (Week 7)

---

**Status:** ✅ Week 7 Complete (Part 1)
**Next:** Week 8 - NodeHandlers (Part 2): Parallel, Loop, SubWorkflow
