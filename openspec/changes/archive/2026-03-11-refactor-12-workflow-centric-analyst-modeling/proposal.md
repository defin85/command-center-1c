# Change: Перевести analyst-facing моделирование pools на workflow-centric схему с decision layer

## Why
Изначальная продуктовая идея проекта была такой:
- `/templates` — каталог конкретных атомарных операций;
- `/workflows` — схемы, которые объединяют операции в единый процесс;
- `pool` — конкретный контур организаций, который использует одну или несколько схем.

Фактическая эволюция ушла в сторону, где:
- `workflow` остаётся в первую очередь техническим DAG;
- `pool` несёт topology, document semantics и runtime-смысл одновременно;
- у аналитика нет удобного analyst-facing слоя для переиспользуемых схем и явных business rules.

Это плохо масштабируется на кейс, где один и тот же `pool` должен одновременно использовать несколько разных схем распределения/публикации. Для такого сценария не хочется размножать `pool`; хочется назначать несколько схем на один организационный контур и запускать их как отдельные process instances.

## What Changes
- Сделать `workflow definition` главным analyst-facing артефактом для схем распределения/публикации.
- Ввести versioned `decision` / `rule table` слой как явное разделение business rules и orchestration (DMN-lite на текущем стеке).
- Ввести `pool_workflow_binding` как связь между конкретным `pool` и конкретной pinned revision workflow-схемы с параметрами, effective period и role mapping.
- Сохранить `pool run` как primary domain facade для экземпляров выполнения, а generic workflow execution перевести в secondary diagnostic surface.
- Зафиксировать, что `/templates` остаётся каталогом атомарных операций и не является primary surface для analyst-facing process composition.
- Зафиксировать compile path `workflow + decision + pool binding -> concrete runtime projection`, включая concrete `document_policy.v1` и downstream `document_plan_artifact.v1`, совместимые с существующим runtime.
- Разделить authored workflow definitions и system-managed/generated runtime workflows.
- Выполнить это как workflow-centric big-bang direction для analyst-facing authoring, а не как введение отдельной сущности `business_scheme`.

## Impact
- Affected specs:
  - `workflow-decision-modeling` (new)
  - `pool-workflow-bindings` (new)
  - `operation-templates`
  - `pool-document-policy`
  - `pool-distribution-runs`
- Affected code (expected):
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Templates/**`
  - `frontend/src/pages/Pools/**`
  - `frontend/src/components/workflow/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/**`
  - `contracts/orchestrator/src/**`
  - `contracts/orchestrator/openapi.yaml`

## Sequencing
- `refactor-12-workflow-centric-analyst-modeling` является prerequisite platform change.
- Этот change ДОЛЖЕН (SHALL) сначала зафиксировать новую каноническую authoring model:
  - `workflow definition`;
  - `decision layer`;
  - `pool_workflow_binding`;
  - compiled runtime projection.
- Расширение этой модели на service domains (`extensions.*`, `database.ib_user.*` и другие reusable service operations) НЕ ДОЛЖНО (SHALL NOT) быть обязательной частью данного change и выносится в follow-up change `add-13-service-workflow-automation`.

## Breaking Changes
- **BREAKING**: analyst-facing source-of-truth для схем распределения/публикации переносится в `workflow + decision + pool binding`, а не в прямой authoring `document_policy` на pool topology edges.
- **BREAKING**: `/workflows` меняет роль с generic technical DAG catalog на primary analyst-facing scheme library.
- **BREAKING**: запуск новых `pool runs` требует selection/resolution конкретного `pool_workflow_binding`.

## Non-Goals
- Не внедрять внешний Camunda engine и не переписывать backend на Java.
- Не требовать совместимости 1:1 с BPMN XML/DMN XML в рамках этого change.
- Не превращать `templates` в отдельный analyst-facing low-code конструктор.
- Не удалять runtime workflow core, `document_policy.v1` или `document_plan_artifact.v1` как execution contracts.
- Не сохранять дальнейшее развитие legacy pool-edge authoring как primary моделирование для новых analyst workflows.

## Related Changes
- Этот change фиксирует workflow-centric analyst model как выбранное направление для дальнейшего authoring pools/workflows на текущем стеке.
- Этот change открывает следующий implementation phase для reusable service-domain workflows, описанный в `add-13-service-workflow-automation`.
