## Context (Контекст)
Сейчас “Command Schemas” предоставляет UI/API для редактирования schema-driven каталогов команд (`cli`/`ibcmd`).
Каталог описывает команды и их параметры на уровне конкретной команды (`commands_by_id.<id>.params_by_name`), и используется:
- для сборки канонического `argv[]` (и `argv_masked[]`) в API при постановке операции в очередь;
- для валидации “guided” ввода параметров.

Параметры подключения/контекста выполнения (`connection.*`) для некоторых драйверов также выражаются флагами CLI (например `ibcmd --remote`),
но это driver-level options, а не command-level params.

## Goals / Non-Goals (Цели / Не цели)
- Goals (Цели):
  - Ввести единый паттерн: **Driver schema + Command schema** для schema-driven драйверов.
  - Сделать `connection.*` валидируемым и управляемым отдельно от `params_by_name` команды.
  - Сохранить воспроизводимость: итоговый `argv[]` должен формироваться в API (до enqueue) и отражать и connection options, и params.
  - Сформировать основу для будущих аналогичных драйверов (без “if driver == ...” на каждом шаге).
- Non-Goals (Не цели):
  - Полная миграция всех драйверов в schema-driven формат (только те, кто уже schema-driven или планируются такими).
  - Переписывание всей модели “Command Schemas” и UI с нуля.

## Data Model (Данные)
### 1) Driver schema
Добавить в эффективный каталог (и возможность хранить/патчить) driver-level схему:
- `driver_schema`: объект со схемой driver-level connection options, отдельный от `commands_by_id.*.params_by_name`.

Ключевые параметры для `ibcmd` (MVP):
- `driver_schema.connection.remote` → `--remote=<url>` (string, expects_value=true)
- `driver_schema.connection.pid` → `--pid=<pid>` (int, expects_value=true) + ограничения окружения (например запрет в production)
- `driver_schema.connection.offline.*` (nested): `config`, `data`, `dbms`, `db_server`, `db_name`, `db_user`, `db_pwd` (маппятся в соответствующие `--*` флаги)

Примечание: точный набор ключей — в `spec.md` и может отличаться по драйверам.

### 2) Command schema
Остаётся как сейчас:
- `commands_by_id.<command_id>.params_by_name`: параметры конкретной команды.

### 3) Overrides
Нужно обеспечить патчинг driver-level schema через overrides:
- `overrides.driver_schema`: patch для driver-level schema
- `overrides.commands_by_id`: как сейчас

## API / Builder Semantics (Семантика сборки argv)
При сборке `argv` для schema-driven драйверов:
1) Базовый `argv` команды (`command.argv`)
2) Driver options из `connection` (валидируем по driver schema) → добавляются как глобальные флаги драйвера
3) Command params (`params`) валидируем по `params_by_name` команды → добавляются как флаги/позиционалы команды
4) `additional_args` (после нормализации/очистки запрещённых флагов)

## Conflict Policy (Правила конфликтов)
Нужно зафиксировать поведение, когда один и тот же флаг задан из разных источников:
- `connection` vs `additional_args`
- `connection` vs `params` (для ключей, которые могут существовать на обоих уровнях)

Предпочтение (MVP):
- `connection` имеет приоритет над `additional_args` для driver-level флагов;
- дубликаты driver-level флагов в `additional_args` считаются ошибкой валидации или автоматически удаляются (решить в спеках).

## Migration / Backward Compatibility (Миграция / Совместимость)
- Каталоги без `driver_params_by_name` должны продолжить работать.
- Для таких каталогов `connection` не должен приводить к ошибке “params are not supported…”.
  Варианты:
  - fallback: разрешать ограниченный whitelist driver-level connection options даже без явной driver schema;
  - либо требовать driver schema для использования `connection` (хуже по UX, но строже).
  Решить в спеках.

## Open Questions (Открытые вопросы)
### Decisions (Закрытые вопросы / Решения)
- MVP: только для `ibcmd`.
- `offline.*`: оформляем как nested schema внутри driver schema.
- Политика дубликатов driver-level флагов: “ошибка”. В UI отражаем как `errors` (валидация блокирует сохранение/выполнение).
