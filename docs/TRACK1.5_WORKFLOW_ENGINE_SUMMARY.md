# Track 1.5: Workflow Engine - Quick Summary

> **Краткая сводка архитектурного плана для визуального workflow system**

**Статус:** Утверждено для реализации в Phase 2
**Timeline:** 6-7 дней
**Зависимости:** Track 2-3 (Worker integration)

---

## 🎯 Что это?

**Workflow Engine** - система для композиции операций в многошаговые workflows с визуализацией (как n8n).

**Пример:** Вместо выполнения 7 операций вручную → создаешь workflow который выполняет их автоматически:

```
Создать контрагента → Создать договор → Создать документ
  → Заполнить → Условие (сумма > 100k?) → Верификация/Авто
  → Провести → Отчет
```

---

## ✅ Ключевые фичи

1. **Conditional branching** - if/else ветки в workflow
2. **Parallel execution** - несколько операций одновременно (Celery)
3. **Loop steps** - повторить N раз или пока условие
4. **Data passing** - `{{ step1.result.field }}`
5. **Sub-workflows** - workflow внутри workflow (unlimited вложенность)

---

## 📊 Формат данных

**Nodes+Edges JSON:**

```json
{
  "nodes": [
    {"id": "step1", "type": "operation", "template_id": "uuid"},
    {"id": "cond1", "type": "condition", "expression": "{{ x > 100 }}"}
  ],
  "edges": [
    {"from": "step1", "to": "cond1"}
  ]
}
```

---

## 🏗️ Компоненты

- **WorkflowTemplate** - хранит DAG definition (Django model)
- **WorkflowExecution** - instance выполнения workflow
- **WorkflowEngine** - orchestrator (выполняет workflow)
- **DAGValidator** - проверяет циклы, reachability (Kahn's algorithm)
- **NodeHandlers** - 5 типов (operation, condition, parallel, loop, subworkflow)

---

## 🔗 Integration с Track 1

**Использует OperationTemplate:**

```python
# Node в workflow:
{"type": "operation", "template_id": "uuid-of-OperationTemplate"}

# OperationHandler:
template = OperationTemplate.objects.get(id=node['template_id'])
rendered = renderer.render(template, context)  # ← Track 1!
```

**Полная совместимость!** Все существующие templates работают в workflows!

---

## ⏱️ Timeline

**6-7 дней:**

- Day 1: Models + Migrations
- Day 2: DAGValidator + Kahn's algorithm
- Day 3: OperationHandler + ConditionHandler
- Day 4: ParallelHandler + LoopHandler
- Day 5: SubWorkflowHandler + WorkflowEngine
- Day 6: REST API
- Day 7: Documentation + Tests

---

## 📖 Детали

См. полный документ: [`WORKFLOW_ENGINE_ARCHITECTURE.md`](WORKFLOW_ENGINE_ARCHITECTURE.md)

---

## 🚀 Когда начинать?

**Phase 2** (после Track 2-3 готовы)

**Why?** Чтобы иметь возможность E2E тестирования:
```
Workflow → OperationTemplate → Celery → Redis → Go Worker → 1C OData
```

Без Track 2-3 можем только mock Worker responses.

---

**Версия:** 1.0
**Дата:** 2025-11-09
**Автор:** Claude (Architect)
