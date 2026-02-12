# Change: Сделать OperationExposure first-class binding для workflow

## Why
После big-bang cutover workflow runtime уже исполняет шаблоны через `OperationExposure`, но контракт workflow-ноды и write-time validation остаются частично legacy-ориентированными. Это создаёт риски недетерминированного исполнения (alias drift) и поздних runtime-ошибок при невалидной форме `executor_payload`.

Нужен следующий шаг: зафиксировать `OperationExposure` как явный и проверяемый execution binding для workflow с fail-closed семантикой и совместимой миграцией с текущего `template_id`.

## What Changes
- Расширить контракт workflow operation-node до явного `operation_ref` (alias + exposure identity + binding mode), сохранив backward compatibility с `template_id`.
- Добавить явный data-flow контракт operation-node `io` (`input_mapping`/`output_mapping`, режим `implicit_legacy|explicit_strict`) для прозрачной передачи данных между шагами workflow.
- Добавить deterministic execution режим для workflow:
  - `alias_latest` для текущего поведения,
  - `pinned_exposure` для выполнения по зафиксированному exposure/revision с drift-check.
- Добавить строгую write-time/publish-time validation template exposure payload:
  - `operation_type` обязателен и непустой,
  - `template_data` обязателен и имеет тип object,
  - `operation_type` должен быть поддержан runtime backend registry.
- Провести UX-рефакторинг `/templates` и модалки редактора шаблона:
  - сделать явной связку `Template -> OperationExposure -> OperationDefinition`,
  - показывать provenance полей (`executor.kind`, `executor.command_id`, `operation_type`, `template_exposure_revision`),
  - добавить прозрачный preview «что будет выполнено» и понятные причины validation/publish блокировок.
- Ввести monotonic `exposure_revision` и прокинуть его в API/metadata для контроля drift.
- Расширить enqueue/details wire contract для worker: `template_id + template_exposure_id + template_exposure_revision`.
- Расширить internal template endpoints поддержкой resolve по `template_exposure_id` (при pinned binding), не ломая текущий `template_id` контракт.

## Impact
- Affected specs:
  - `operation-templates`
  - `operation-definitions-catalog`
  - `execution-plan-binding-provenance`
- Affected code (high-level):
  - `orchestrator/apps/templates/workflow/**`
  - `orchestrator/apps/templates/template_runtime.py`
  - `orchestrator/apps/api_v2/views/operation_catalog.py`
  - `orchestrator/apps/templates/operation_catalog_service.py`
  - `orchestrator/apps/api_internal/views_templates.py`
  - `orchestrator/apps/operations/**`
  - `go-services/shared/models/operation_v2.go`
  - `contracts/orchestrator/openapi.yaml`
  - `contracts/orchestrator-internal/openapi.yaml`
  - `frontend/src/components/workflow/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Templates/**`
  - `frontend/src/components/templates/**`

## Non-Goals
- Удаление `template_id` из внешнего API в этом change (поле остаётся для backward compatibility).
- Введение нового API version (`v3`) в рамках этого change.
- Полный redesign action-catalog/tenancy контуров.
