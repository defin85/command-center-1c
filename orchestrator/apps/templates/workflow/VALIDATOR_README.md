# DAGValidator - Week 6 Implementation

## Обзор

DAGValidator - comprehensive validation class для проверки DAG структур в Workflow Engine.

**Реализовано в Week 6, Days 1-2 (2025-11-23)**

## Структура

### Основные компоненты

1. **ValidationSeverity (Enum)**
   - ERROR, WARNING, INFO

2. **ValidationIssue (dataclass)**
   - severity, message, node_ids, details

3. **ValidationResult (dataclass)**
   - is_valid, errors, warnings, info, topological_order, metadata
   - Methods: add_error(), add_warning(), add_info()

4. **DAGValidator (class)**
   - Comprehensive DAG validation with O(V+E) complexity
   - 8-step validation process

5. **Custom Exceptions (5 классов)**
   - DAGValidationError (base)
   - CycleDetectedError
   - UnreachableNodeError
   - InvalidNodeTypeError
   - InvalidEdgeError

## Использование

### Основной сценарий

```python
from apps.templates.workflow.validator import DAGValidator
from apps.templates.workflow.models import DAGStructure

# Create validator
validator = DAGValidator(dag_structure)

# Validate
result = validator.validate()

if result.is_valid:
    print(f"Topological order: {result.topological_order}")
    print(f"Metadata: {result.metadata}")
else:
    for error in result.errors:
        print(f"ERROR: {error.message}")
```

### Через WorkflowTemplate.validate()

```python
from apps.templates.workflow.models import WorkflowTemplate

template = WorkflowTemplate(name="My Workflow", dag_structure=dag_data)

try:
    template.validate()
    print(f"Template is valid: {template.is_valid}")

    # Access validation metadata
    if hasattr(template, '_validation_metadata'):
        topo_order = template._validation_metadata['topological_order']
        metadata = template._validation_metadata['validation_metadata']
except ValueError as e:
    print(f"Validation failed: {e}")
```

## Валидация этапы (8 шагов)

1. **Duplicate node IDs** - O(V)
2. **Edge references** - O(E)
3. **Self-loops** - O(E)
4. **Node types** - O(V)
5. **Cycle detection (Kahn's algorithm)** - O(V+E)
6. **Connectivity (BFS)** - O(V+E)
7. **Component counting (DFS)** - O(V+E)
8. **Topology validation** - O(V)

**Total Complexity:** O(V + E)

## Примеры

### Valid DAG

```python
dag = DAGStructure(
    nodes=[
        WorkflowNode(id="start", name="Start", type="operation", template_id="init"),
        WorkflowNode(id="end", name="End", type="operation", template_id="cleanup"),
    ],
    edges=[
        WorkflowEdge(**{"from": "start", "to": "end"}),
    ],
)

validator = DAGValidator(dag)
result = validator.validate()

# result.is_valid == True
# result.topological_order == ['start', 'end']
```

### Cycle Detection

```python
dag = DAGStructure(
    nodes=[
        WorkflowNode(id="a", name="A", type="operation", template_id="op1"),
        WorkflowNode(id="b", name="B", type="operation", template_id="op2"),
    ],
    edges=[
        WorkflowEdge(**{"from": "a", "to": "b"}),
        WorkflowEdge(**{"from": "b", "to": "a"}),  # Cycle!
    ],
)

validator = DAGValidator(dag)
result = validator.validate()

# result.is_valid == False
# result.errors[0].message == "Cycle detected in DAG. 2 node(s) could not be processed."
```

### Invalid Edge Reference

```python
dag = DAGStructure(
    nodes=[
        WorkflowNode(id="start", name="Start", type="operation", template_id="init"),
    ],
    edges=[
        WorkflowEdge(**{"from": "start", "to": "nonexistent"}),  # Invalid!
    ],
)

validator = DAGValidator(dag)
result = validator.validate()

# result.is_valid == False
# result.errors[0].message contains "non-existent node"
```

## ValidationResult структура

```python
@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: List[ValidationIssue] = []
    warnings: List[ValidationIssue] = []
    info: List[ValidationIssue] = []
    topological_order: Optional[List[str]] = None
    metadata: Dict[str, any] = {
        'component_count': 1,
        'start_nodes': ['start'],
        'end_nodes': ['end'],
        'total_nodes': 3,
        'total_edges': 2,
        'error_count': 0,
        'warning_count': 0,
    }
```

## Custom Exceptions

Все исключения наследуются от `DAGValidationError` и хранят `node_ids` для debugging:

```python
try:
    validator.validate()
except CycleDetectedError as e:
    print(f"Cycle in nodes: {e.node_ids}")
except InvalidEdgeError as e:
    print(f"Invalid edge referencing: {e.node_ids}")
```

## Integration с WorkflowTemplate

`WorkflowTemplate.validate()` теперь использует `DAGValidator` автоматически:

```python
class WorkflowTemplate(models.Model):
    def validate(self) -> bool:
        from apps.templates.workflow.validator import DAGValidator

        dag = self.dag_structure if isinstance(self.dag_structure, DAGStructure) else DAGStructure(**self.dag_structure)

        validator = DAGValidator(dag)
        result = validator.validate()

        if not result.is_valid:
            error_messages = [issue.message for issue in result.errors]
            raise ValueError(f"DAG validation failed: {'; '.join(error_messages)}")

        # Store metadata
        self._validation_metadata = {
            'topological_order': result.topological_order,
            'validation_metadata': result.metadata,
        }

        self.is_valid = True
        return True
```

## Тестирование

Интеграционные тесты подтверждают:

- ✅ Valid DAG validation
- ✅ Cycle detection
- ✅ Invalid edge reference detection
- ✅ Self-loop detection
- ✅ Topological ordering
- ✅ Connectivity analysis
- ✅ Component counting

## Performance

- **Time Complexity:** O(V + E)
- **Space Complexity:** O(V + E)
- **Algorithms:**
  - Kahn's algorithm (topological sort)
  - BFS (connectivity)
  - DFS (component counting)

## Status

**Implementation:** ✅ COMPLETE (Week 6, Days 1-2)
**Tests:** ⚠️ TODO (Week 6, Day 3)

## Next Steps

- Day 3: Unit tests (`test_validator.py`)
- Day 4-5: DAGExecutor implementation
- Day 6-7: NodeHandlers implementation
