# Change: Канонический UI для управления configuration profile и metadata snapshot базы

## Why
Сейчас операторские действия вокруг metadata snapshot и business identity конфигурации распределены не по смыслу:
- primary `Load metadata` / `Refresh metadata` спрятаны внутри builder-ветки `/pools/catalog`;
- `/decisions` зависит от metadata context для `decision_revision`, но при отсутствии контекста даёт только общее указание "reload database-specific metadata" без явного canonical management surface;
- в UI почти не артикулировано, что `config_name + config_version` (identity/reuse key) и содержимое metadata snapshot обновляются разными runtime path.

Из-за этого operational flow трудно найти, а consumer-экраны смешивают authoring/runtime use-case и администрирование источника истины.

Нужно вынести управление configuration profile и metadata snapshot в понятный per-database surface на `/databases`, а `/pools/catalog` и `/decisions` оставить consumer/handoff surfaces.

## What Changes
- Добавить на `/databases` canonical management surface для выбранной ИБ, который показывает:
  - business identity / reuse key (`config_name`, `config_version`, `config_generation_id`, verification state);
  - metadata snapshot state (`snapshot_id`, `resolution_mode`, `metadata_hash`, `observed_metadata_hash`, `publication_drift`, provenance markers).
- Явно развести в UI два действия:
  - `Re-verify configuration identity` как async operation path;
  - `Refresh metadata snapshot` как отдельный snapshot refresh path.
- Зафиксировать, что `/pools/catalog` topology editor больше не является primary mutate surface для metadata maintenance и вместо этого даёт status + handoff в `/databases`.
- Зафиксировать, что `/decisions` показывает metadata context в read-only виде и при отсутствии/устаревании контекста направляет пользователя в `/databases`, а не притворяется местом управления snapshot/profile.

## Impact
- Affected specs:
  - `database-metadata-management-ui` (new)
  - `organization-pool-catalog`
  - `workflow-decision-modeling`
- Affected code (expected, when implementing this change):
  - `frontend/src/pages/Databases/**`
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Decisions/DecisionsPage.tsx`
  - existing frontend API clients for metadata catalog read/refresh and operations enqueue

## Non-Goals
- Изменение backend semantics reuse key, `business_configuration_profile` или canonical snapshot storage.
- Замена текущего metadata read/refresh runtime path на новый backend pipeline.
- Введение отдельного top-level route вместо использования `/databases` как existing operational surface.
- Перенос authoring `document_policy` обратно из `/decisions` в topology editor.

## Assumptions
- `/databases` остаётся canonical operational hub для per-infobase действий и может быть расширен ещё одним drawer/panel вместо создания нового route.
- Consumer surfaces (`/pools/catalog`, `/decisions`) сохраняют read-only diagnostics и explicit handoff, но не получают новый primary mutate UX для snapshot/profile.
- Change не вводит новую backend RBAC модель и должен переиспользовать существующие access checks `/databases`.
