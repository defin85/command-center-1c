# Change: System-managed pool runtime templates + PoolDomainBackend + pinned binding

## Why
Сейчас pool workflow использует захардкоженные alias шагов (`pool.prepare_input`, `pool.distribution_calculation.*` и т.д.), но эти alias резолвятся через общий template registry в режиме `alias_latest`.

Это создаёт несколько рисков:
- шаг может не выполниться, если alias не создан или случайно изменён;
- поведение может "дрейфовать" между запусками из-за `alias_latest`;
- pool-домен смешивается с обычными пользовательскими templates в `/templates`.

Нужен детерминированный и fail-closed runtime для pool-шагов, управляемый системой, а не ручными действиями в UI.

## What Changes
- Вводится системный набор runtime templates для pool-домена (system-managed):
  - фиксированный реестр alias для обязательных pool-шагов;
  - bootstrap/синхронизация реестра в `OperationDefinition + OperationExposure`;
  - шаблоны помечаются как системные и недоступны для обычного редактирования.
- Вводится отдельный `PoolDomainBackend` для исполнения pool runtime steps:
  - backend исполняет доменные операции (`prepare_input`, `distribution_calculation`, `reconciliation_report`, `approval_gate`, `publication_odata`) без зависимости от внешних CLI executor.
- Pool workflow compiler переходит на pinned binding:
  - при компиляции шага alias резолвится в `template_exposure_id + revision`;
  - в DAG сохраняется `operation_ref(binding_mode="pinned_exposure", ...)`;
  - исполнение fail-closed при drift/missing/inactive.
- Для диагностики добавляется системный read-only introspection статуса pool runtime registry (какие alias синхронизированы, какие pinned ревизии используются).
- Change трактуется как архитектурный baseline для pool runtime и логически вытесняет alias-latest поведение для pool шагов.

## Impact
- Affected specs:
  - `pool-workflow-execution-core` (новые требования по pinned binding и execution backend)
  - `operation-templates` (system-managed templates и ограничение write-path)
- Affected code (expected):
  - `orchestrator/apps/intercompany_pools/workflow_compiler.py`
  - `orchestrator/apps/intercompany_pools/workflow_runtime.py`
  - `orchestrator/apps/templates/workflow/handlers/backends/*`
  - `orchestrator/apps/templates/models.py`
  - `orchestrator/apps/api_v2/views/workflows/*`
  - `contracts/orchestrator/openapi.yaml` (если появляются новые debug/introspection endpoint'ы)

## Compatibility
- Для pool runtime этот change меняет поведение с `alias_latest` на `pinned_exposure`.
- Existing pool runs не должны ломаться: pinned binding фиксируется на момент создания run; переисполнение сохраняет тот же binding snapshot.

## Dependencies
- Может внедряться поверх `enable-full-pool-ui-management`.
- Является альтернативой подходу `add-pool-driver-command-schemas-runtime` (эти два change взаимно исключают друг друга как целевая архитектура runtime).

## Non-Goals
- Добавление pool runtime templates в пользовательский каталог `/templates` как редактируемых сущностей.
- Перевод pool execution на `command-schemas` driver модель.
- Изменение бизнес-формул распределения.
