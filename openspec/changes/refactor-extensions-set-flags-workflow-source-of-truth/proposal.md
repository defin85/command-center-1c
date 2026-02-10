# Change: Перевести `extensions.set_flags` на workflow-first модель с единым source of truth

## Why
Текущая модель `extensions.set_flags` имеет конфликтующие источники данных:
- `apply_mask` может приходить из UI request,
- `apply_mask` может подтягиваться как preset из `executor.fixed.apply_mask`,
- значения флагов могут задаваться как через runtime вход, так и через отдельные механизмы policy.

Это делает поведение неоднозначным для оператора, особенно при массовых изменениях (700+ баз), где нужен детерминированный и аудируемый rollout.

Для нашей доменной задачи (массовое внедрение/включение расширения, открывающего нужный OData metadata доступ) основной путь должен быть workflow-оркестрацией с явным входом, а ручные точечные изменения — только fallback.

## What Changes
- Вводится workflow-first контракт для `extensions.set_flags`:
  - source of truth для значений флагов и mask — только runtime input (включая workflow input context),
  - fallback на `executor.fixed.apply_mask` удаляется.
- `action_id` для `extensions.set_flags` становится обязательным (fail-closed, без неявного выбора по capability).
- `Action Catalog` для `extensions.set_flags` становится transport/binding-слоем:
  - разрешены только executor/binding/safety поля,
  - capability-specific preset `apply_mask` запрещается.
- UI `/extensions` переводится на основной bulk-сценарий через workflow launch (wave rollout, threshold),
  а точечное применение оставляется как fallback-режим.
- Контракт `POST /api/v2/extensions/plan/` для `extensions.set_flags` ужесточается:
  - строгая схема `apply_mask` (3 bool, минимум один `true`),
  - добавляется `flags_values` как явный runtime payload.

## Breaking Changes
- Удаляется поддержка preset mask через `executor.fixed.apply_mask` для `extensions.set_flags`.
- Старые exposures с `capability_config.apply_mask` / `executor.fixed.apply_mask` для `extensions.set_flags` перестают считаться валидными для publish/runtime.
- Для `extensions.set_flags` планирование без `action_id` больше не поддерживается.
- Для `extensions.set_flags` планирование без `flags_values` больше не поддерживается.

## Impact
- Affected specs:
  - `extensions-plan-apply`
  - `extensions-action-catalog`
  - `ui-action-catalog-editor`
  - `extensions-overview`
- Affected code:
  - Backend: `orchestrator/apps/api_v2/views/extensions_plan_apply.py`, валидация unified exposure, editor hints
  - Frontend: `/extensions`, `/templates` (action editor), generated API types/contracts
  - Contracts: `contracts/orchestrator/openapi.yaml`

## Non-Goals
- Полная замена fallback-точечных операций на single-db.
- Удаление существующих policy endpoints в рамках этого change.
- Перенос всего UI управления расширениями в `/operations` в рамках этого change.
