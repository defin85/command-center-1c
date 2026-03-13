# Change: add-workflow-gateway-branching-contract

## Почему
- Текущий `Decision Gate` на analyst-facing surface фактически сводится к `boolean gate`: pinned `decision_ref` компилируется в `{{ decisions.<key> }}`, а runtime приводит результат к `true/false`.
- Визуальные `true/false/default` handles в workflow designer создают ожидание полноценного branching, но persisted DAG не хранит branch semantics как first-class contract.
- Analyst-facing `/workflows` не даёт канонического способа собирать `one-of-many` и `many-of-many` ветвления без возврата к compatibility-конструкциям `condition` и raw `edge.condition`.

## Что меняется
- Добавляется явная analyst-facing модель `Decision Task -> Exclusive Gateway / Inclusive Gateway`.
- Добавляется first-class `branch edge contract`, который хранится в DAG как typed persisted semantics, а не выводится из handle id, edge label или raw expression.
- `Decision Task` становится отдельным вычислительным шагом: он вызывает pinned decision revision, публикует typed outputs в context и не маршрутизирует ветви напрямую.
- `Exclusive Gateway` и `Inclusive Gateway` становятся каноническими branching-конструктами default workflow surface.
- Legacy `condition`-node и raw `edge.condition` остаются inspectable/executable как compatibility-only path для существующих workflow, но перестают быть primary authoring model.
- Runtime получает fail-closed branching semantics, auditable branch diagnostics и activated-branch provenance для корректного downstream fan-in.

## Impact
- Affected specs:
  - `workflow-decision-modeling`
  - `workflow-branching-contract` (new)
- Affected code:
  - `frontend/src/components/workflow/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/types/workflow.ts`
  - `orchestrator/apps/templates/workflow/schema.py`
  - `orchestrator/apps/templates/workflow/serializers.py`
  - `orchestrator/apps/templates/workflow/executor.py`
  - `orchestrator/apps/templates/workflow/handlers/condition.py`
  - authoring-boundary, validation, API contracts и generated types для workflow DAG
