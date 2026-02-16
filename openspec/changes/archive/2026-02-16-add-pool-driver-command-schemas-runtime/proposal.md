# Change: Pool driver + command-schemas для исполнения pool runtime шагов

## Why
Сейчас pool runtime steps завязаны на захардкоженный pipeline и на alias templates, которые не имеют отдельной driver-level модели.

Это ограничивает повторное использование уже существующей platform-модели `driver + command-schemas`, которая применяется для `ibcmd`/`designer` и даёт:
- прозрачный контракт команд,
- schema-driven валидацию,
- единый UI-поток управления через `/templates`.

Нужна альтернатива, где pool steps становятся командным драйвером и управляются через те же command-schemas механизмы.

## What Changes
- Вводится новый schema-driven driver `pool` в command catalogs:
  - driver-level schema для общих параметров выполнения pool команд;
  - command schemas для шагов (`prepare_input`, `distribution_calculation.top_down`, `distribution_calculation.bottom_up`, `reconciliation_report`, `approval_gate`, `publication_odata`).
- Вводится executor kind `pool_driver` для templates:
  - template payload указывает `driver=pool` и `command_id`;
  - параметры валидируются через command schema, аналогично другим schema-driven executor.
- `/templates` расширяется поддержкой `pool_driver`:
  - создание/редактирование pool runtime templates как обычных template exposures;
  - валидация параметров по command schema в UI/API.
- Pool workflow compiler продолжает связывать шаги с template aliases, но источник правды для payload становится `pool` command schema + template params.
- Execution routing использует schema-driven backend/adapter для `pool_driver` вместо отдельного domain backend.

## Impact
- Affected specs:
  - `command-schemas-driver-options`
  - `operation-templates`
  - `pool-workflow-execution-core`
- Affected code (expected):
  - `orchestrator/apps/settings/services/command_schemas/*`
  - `orchestrator/apps/templates/models.py`
  - `orchestrator/apps/templates/workflow/handlers/backends/*`
  - `orchestrator/apps/intercompany_pools/workflow_compiler.py`
  - `frontend/src/pages/Templates/*`
  - `contracts/orchestrator/openapi.yaml`

## Compatibility
- Этот change сохраняет концепцию template aliases для pool workflow, но переводит реализацию шагов в driver/command-schemas слой.
- Возможен поэтапный rollout: сначала добавить driver и templates, затем переключить pool runtime routing.

## Dependencies
- Может внедряться поверх `enable-full-pool-ui-management`.
- Является альтернативой подходу `add-system-managed-pool-runtime-templates-and-domain-backend` (эти два change взаимно исключают друг друга как целевая архитектура runtime).

## Non-Goals
- Введение отдельного `PoolDomainBackend` как выделенного доменного runtime backend.
- Жесткая system-managed блокировка pool templates от редактирования.
- Изменение бизнес-формул распределения.
