## Context
Для `extensions.set_flags` система сейчас допускает несколько конкурирующих источников данных (`request.apply_mask`, preset mask, policy/runtime substitution), что создаёт неочевидное поведение и регрессионные риски при массовом rollout.

Целевой доменный сценарий: массовое внедрение и включение расширения (для нужного OData metadata доступа) в 700+ базах. Это требует детерминированной workflow-оркестрации, а не ручного точечного UI как основного режима.

## Goals
- Сделать источник значений флагов и mask однозначным и аудируемым.
- Закрепить workflow-first bulk UX как основной путь.
- Сохранить точечный fallback-режим для аварийных/индивидуальных случаев.
- Сохранить fail-closed поведение и прозрачные ошибки конфигурации.

## Non-Goals
- Полный перенос всего домена расширений в `/operations` в этом change.
- Удаление policy API как отдельного capability.

## Decision
### 1. Единый source of truth для `extensions.set_flags`
- `flags_values` и `apply_mask` приходят только из runtime request (включая workflow input context).
- `executor.fixed.apply_mask` больше не участвует в runtime.

### 2. Роль Action Catalog
- Action для `extensions.set_flags` хранит только:
  - executor transport (`kind`, `driver`, `command_id`, `params`, `additional_args`, `stdin`),
  - binding (`target_binding.extension_name_param`),
  - safety (`confirm_dangerous`, `timeout_seconds`).
- Capability-specific preset mask (`apply_mask`) запрещается.

### 3. Детерминизм выбора action
- Для `extensions.set_flags` `action_id` обязателен.
- Неявный выбор по capability (`AMBIGUOUS_ACTION`) для этого capability убирается из основного контракта и заменяется жёсткой валидацией отсутствующего `action_id`.

### 4. UX модель
- Основной путь: запуск workflow rollout из `/extensions` с параметрами волн/порогов ошибок.
- Fallback путь: точечное применение к одной/небольшой группе баз (с явной маркировкой «аварийный режим»).

## API Contract (target)
Для `POST /api/v2/extensions/plan/` при `capability=extensions.set_flags`:
- required: `action_id`, `extension_name`, `flags_values`, `apply_mask`.
- `flags_values`:
  - `active: boolean`
  - `safe_mode: boolean`
  - `unsafe_action_protection: boolean`
- `apply_mask`:
  - `active: boolean`
  - `safe_mode: boolean`
  - `unsafe_action_protection: boolean`
  - минимум один флаг `true`.

Runtime substitution для set_flags использует только `$flags.active`, `$flags.safe_mode`, `$flags.unsafe_action_protection`.

## Migration
- Все published exposures с `capability=extensions.set_flags` и `apply_mask` preset помечаются невалидными до исправления.
- Предоставляется отчёт миграции (alias exposure + путь невалидного поля).
- Операторы переводят preset-логику в workflow input/defaults.

## Risks
- Временная неработоспособность части существующих actions до миграции.
- Рост количества валидационных ошибок у операторов в момент включения strict-контракта.

## Mitigations
- Явный migration report до активации strict-валидации в production.
- Пошаговое включение: сначала read-only диагностика, затем fail-closed enforcement.
- Документация для операторов по новому workflow-first сценарию.
