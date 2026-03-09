# Change: Закрыть остаточные риски workflow-centric authoring после review

## Why
После `refactor-12-workflow-centric-analyst-modeling` базовый workflow-centric path уже внедрён, но review оставил несколько системных сомнений, которые не стоит размывать в ad-hoc bugfixes:
- `pool_workflow_binding` выглядит как first-class API resource, но canonical persistence до сих пор фактически привязана к `pool.metadata`;
- public create-run / preview boundary всё ещё допускает путь без явного `pool_workflow_binding_id`, что ослабляет determinism для внешних клиентов и операторских интеграций;
- pinned subworkflow contract уже есть в authoring/schema/compiler, но runtime contract должен явно гарантировать исполнение по pinned revision и fail-closed поведение при drift/mismatch;
- `/templates` уже несёт compatibility-only workflow executor path, но этот статус нужно зафиксировать как обязательный shipped UX-contract, а не как incidental UI copy;
- текущий evidence set сильнее на уровне unit/API/component tests, чем на уровне сквозного acceptance path `workflow authoring -> binding preview -> create-run -> inspect lineage`.

Если не оформить это отдельным platform hardening change, следующий rollout и follow-up `add-13-service-workflow-automation` будут опираться на partially hardened workflow-centric base.

## What Changes
- Перевести `pool_workflow_binding` на dedicated canonical persistence/store без dual source-of-truth через `pool.metadata`.
- Сделать explicit `pool_workflow_binding_id` обязательным для public operator-facing create-run и preview contract.
- Дожать runtime contract reusable subworkflows: execution и lineage должны использовать pinned revision из `subworkflow_ref`, а drift/mismatch должны отклоняться fail-closed.
- Зафиксировать `/templates` как atomic operations catalog с обязательной compatibility маркировкой для workflow executor templates.
- Добавить обязательный acceptance/proof path и migration/runbook материалы, подтверждающие default shipped flow, а не только helper code.

## Impact
- Affected specs:
  - `pool-workflow-bindings`
  - `pool-distribution-runs`
  - `workflow-decision-modeling`
  - `operation-templates`
  - `organization-pool-catalog`
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/api_v2/**`
  - `frontend/src/pages/Pools/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Templates/**`
  - `frontend/tests/browser/**`
  - `contracts/orchestrator/src/**`
  - `docs/observability/**`
  - `docs/release-notes/**`

## Dependencies
- Этот change опирается на уже заархивированный `refactor-12-workflow-centric-analyst-modeling`.
- Этот change желательно завершить до широкого rollout `add-13-service-workflow-automation`, потому что `add-13` наследует binding/runtime contracts из workflow-centric platform model.

## Breaking Changes
- **BREAKING**: public `POST /api/v2/pools/runs/` и `POST /api/v2/pools/workflow-bindings/preview/` больше не должны принимать workflow-centric operator path без явного `pool_workflow_binding_id`.
- **BREAKING**: metadata-backed `workflow_bindings` перестают быть runtime source-of-truth и переводятся в migration-only legacy source.

## Non-Goals
- Не перепроектировать заново pool topology, `document_policy.v1` или `document_plan_artifact.v1`.
- Не удалять весь compatibility code в одном change, если он нужен для controlled migration/read-path.
- Не расширять change на service domains (`extensions.*`, `database.ib_user.*`) beyond hardening базовой workflow-centric платформы.
