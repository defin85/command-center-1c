# Change: Добавить явный target binding для `extensions.set_flags`

> Status: Superseded by `add-unified-templates-action-catalog-contract`.
> Отдельно не реализуется; требования перенесены в unified change.

## Why
Сейчас `extensions.set_flags` получает бизнес-таргет (`extension_name`) через plan/apply API, но не имеет явного контракта, как этот таргет должен маппиться в обязательные параметры конкретной driver-команды (`name`, `extension` и т.д.).

Из-за этого конфигурация action catalog может выглядеть валидной, но падать только на runtime с ошибками уровня драйвера (например: `Не указано значение параметра: name`). Это архитектурно делает поведение не детерминированным и переносит ошибки из config-time в execution-time.

## What Changes
- Добавляется явный capability-specific контракт для `extensions.set_flags`:
  - `executor.target_binding.extension_name_param` (имя command-level параметра, куда должен быть подставлен runtime `extension_name`).
- Добавляется fail-closed валидация action catalog для `extensions.set_flags`:
  - `target_binding.extension_name_param` обязателен,
  - параметр из binding обязан существовать в `commands_by_id.<command_id>.params_by_name` выбранной команды,
  - при нарушении сохранение каталога отклоняется.
- Plan/apply для `extensions.set_flags` использует этот binding как единственный источник маппинга таргета:
  - перед preview/execute backend подставляет `extension_name` в bound param,
  - при некорректном binding запрос завершается `CONFIGURATION_ERROR` до запуска операции.
- Staff UI Action Catalog editor получает capability hints и guided-поле для `target_binding`, чтобы оператор задавал binding явно, а не через неявные токены.

## Impact
- Affected specs:
  - `extensions-action-catalog`
  - `extensions-plan-apply`
  - `ui-action-catalog-editor`
- Affected code (ожидаемо):
  - Backend: `orchestrator/apps/runtime_settings/action_catalog.py`, `orchestrator/apps/api_v2/views/extensions_plan_apply.py`, `orchestrator/apps/api_v2/views/ui/actions.py`
  - Frontend: `frontend/src/pages/Settings/actionCatalog/ActionCatalogEditorModal.tsx` и валидация action catalog
  - Tests: backend + frontend (unit/browser) для нового binding-контракта

## Scope & Non-Goals
- В scope только `capability="extensions.set_flags"`.
- Не вводится универсальный target-binding DSL для всех capability.
- Не меняется семантика `apply_mask` и selective apply (кроме того, что теперь таргет-мэппинг обязан быть явным).

## Breaking Notes
- Для `extensions.set_flags` отсутствие `executor.target_binding.extension_name_param` считается невалидной конфигурацией.
- Каталоги без этого поля потребуют явного обновления перед сохранением.
- Применяется только strict fail-closed поведение: legacy/compat fallback (включая угадывание binding из токенов `$extension_name`) НЕ поддерживается.
