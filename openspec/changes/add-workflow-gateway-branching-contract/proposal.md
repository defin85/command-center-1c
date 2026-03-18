# Change: add-workflow-gateway-branching-contract

## Почему
- Текущий `Decision Gate` на analyst-facing surface фактически сводится к `boolean gate`: pinned `decision_ref` компилируется в `{{ decisions.<key> }}`, а runtime приводит результат к `true/false`.
- Визуальные `true/false/default` handles в workflow designer создают ожидание полноценного branching, но persisted DAG не хранит branch semantics как first-class contract.
- Analyst-facing `/workflows` не даёт канонического способа собирать `one-of-many` и `many-of-many` ветвления без возврата к compatibility-конструкциям `condition` и raw `edge.condition`.

## Что меняется
- Change фиксируется как phase 1 branching foundation, а не как попытка за один шаг переписать весь workflow authoring UX.
- Добавляется явная analyst-facing модель `Decision Task -> Exclusive Gateway / Inclusive Gateway`.
- Добавляется first-class `branch edge contract`, который хранится в DAG как typed persisted semantics, а не выводится из handle id, edge label или raw expression.
- `Decision Task` становится отдельным вычислительным шагом: он вызывает pinned decision revision, публикует typed outputs в context и не маршрутизирует ветви напрямую.
- `Exclusive Gateway` и `Inclusive Gateway` становятся каноническими branching-конструктами default workflow surface для новых authoring flows.
- Legacy `condition`-node и raw `edge.condition` остаются inspectable/executable как compatibility-only path для существующих workflow, но этот change НЕ ДОЛЖЕН (SHALL NOT) обещать полный auto-migration wizard или big-bang rewrite historical DAG.
- Runtime получает fail-closed branching semantics, auditable branch diagnostics и activated-branch provenance для корректного downstream fan-in.

## Impact
- Affected specs:
  - `workflow-decision-modeling`
  - `workflow-branching-contract` (new)
- Delivery scope note:
  - этот change должен доставить contract/runtime foundation и minimal canonical authoring path для новых branching flows; richer migration helpers, bulk conversion и advanced gateway UX допускаются только как follow-up changes.
- Affected code:
  - `frontend/src/components/workflow/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/types/workflow.ts`
  - `orchestrator/apps/templates/workflow/schema.py`
  - `orchestrator/apps/templates/workflow/serializers.py`
  - `orchestrator/apps/templates/workflow/executor.py`
  - `orchestrator/apps/templates/workflow/handlers/condition.py`
  - authoring-boundary, validation, API contracts и generated types для workflow DAG
