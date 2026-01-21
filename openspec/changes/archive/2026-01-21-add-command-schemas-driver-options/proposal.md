# Change: Driver schema + Command schema для schema-driven драйверов

## Why
Сейчас schema-driven выполнение команд (например `ibcmd_cli`) валидирует `params` строго по `params_by_name` у конкретной команды.
При этом параметры подключения/контекста выполнения (`connection.remote`, `connection.pid`, `connection.offline.*`) логически не относятся
к конкретной команде, но технически превращаются в `params`, что может приводить к ошибкам вида:
`VALIDATION_ERROR: params are not supported for this command` даже для валидных конфигураций и UX.

Нужна долгосрочная схема, которая:
- отделяет driver-level connection options от command-level params;
- масштабируется на будущие аналогичные драйверы без ad-hoc исключений;
- сохраняет принцип schema-driven валидации и канонический `argv[]` для аудита/воспроизводимости.

## What Changes
- Ввести разделение схемы на 2 уровня:
  - **Driver schema**: параметры подключения/контекста (driver-level connection options)
  - **Command schema**: параметры конкретной команды (`params_by_name` как сейчас)
- Расширить “Command Schemas” (backend API + UI) так, чтобы можно было просматривать/редактировать driver-level schema отдельным блоком.
- Обновить сборку `argv[]` для schema-driven драйверов: сначала применяются driver-level options, затем command-level params, затем `additional_args`.
- Определить правила конфликтов/приоритета (например, дубликаты `--remote` из разных источников).

## Impact
- Затронутые спеки: `command-schemas-driver-options` (new)
- Затронутый код (план): Orchestrator `settings/command-schemas/*`, сборка `argv` для schema-driven драйверов (минимум `ibcmd`), Frontend `CommandSchemasPage`
- Ломающих изменений быть не должно (additive), но потребуется миграция/совместимость для существующих каталогов и UI

