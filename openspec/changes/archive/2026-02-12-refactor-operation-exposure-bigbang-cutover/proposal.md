# Change: Big-bang cutover на OperationExposure (один релиз)

## Why
В системе одновременно живут `OperationExposure` (каноническая publish-модель) и `OperationTemplate` (legacy projection), что создаёт постоянный риск drift, усложняет RBAC/runtime цепочки и увеличивает стоимость сопровождения.

Для закрытия технического долга нужен полный cutover в один релиз: единый источник истины для templates без двойной модели данных.

## What Changes
- Перевести templates на единственный persistent/runtime источник: `OperationExposure(surface="template")` + `OperationDefinition`.
- Убрать зависимость runtime и internal API от `OperationTemplate`.
- Перевести template RBAC на exposure-ориентированную модель (alias/exposure), сохранив текущий внешний API-контракт (`template_id`, `operation_templates`) для клиентов.
- Перевести `BatchOperation` и execution metadata на ссылку на template через exposure alias/identifier, а не через FK к `OperationTemplate`.
- Выполнить Big-bang migration в одном релизе: backfill + switch + удаление legacy projection (`operation_templates` и связанные FK/permission tables).
- Зафиксировать строгий wire-контракт metadata/provenance для enqueue/details (`template_id` + `template_exposure_id`) и fail-closed поведение runtime при неразрешённом template alias.
- Зафиксировать обязательные preflight/go-no-go проверки и rollback-процедуру для одного релиза.
- Зафиксировать точный перечень legacy-структур на удаление в contract-фазе и обязательные API/OpenAPI обновления в этом change.

## Impact
- Affected specs:
  - `operation-definitions-catalog`
  - `operation-templates`
  - `execution-plan-binding-provenance`
- Affected code (high-level):
  - `orchestrator/apps/templates/**` (models, rbac, operation_catalog_service, workflow handlers)
  - `orchestrator/apps/api_v2/views/rbac/**`
  - `orchestrator/apps/api_internal/views_templates.py`
  - `orchestrator/apps/operations/**` (models, factory, enqueue/message path)
  - `contracts/orchestrator/openapi.yaml` (обязательная фиксация внутренней семантики и совместимых ответов)

## Non-Goals
- Возврат action-catalog capability или dual-path rollout.
- Новый публичный API versioning в рамках этого change.
- Частичный staged rollout на несколько релизов.
