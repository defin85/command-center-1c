# Action Catalog (ui.action_catalog) — инструкция для операторов

`ui.action_catalog` — runtime-настройка, которая описывает, какие действия по расширениям показывать в UI и как их исполнять (через ibcmd/CLI или workflow).

## Доступ

- Экран **staff-only**: требуется `is_staff=true`.
- Если страница не открывается (403/скрыт пункт меню) — проверь роль пользователя.

## Где находится в UI

- Settings → **Action Catalog**
- Route: `/settings/action-catalog`

## Основные понятия

### Action
Один элемент каталога (запись в `extensions.actions[]`), который описывает:

- `id` — уникальный идентификатор действия (строка).
- `label` — отображаемое имя.
- `contexts` — где показывать действие:
  - `database_card` — карточка одной базы (UI `/databases`).
  - `bulk_page` — bulk-операции по выбранным базам (UI `/databases`, массовые действия).
- `executor` — как исполнять:
  - `kind=ibcmd_cli`
  - `kind=designer_cli`
  - `kind=workflow`

### Executor kinds

#### `ibcmd_cli`
Исполнение через driver catalog `ibcmd`:

- `driver`: обычно `ibcmd`
- `command_id`: выбирается из списка команд драйвера
- Дополнительно (advanced):
  - `mode`: `guided` или `manual` (для ibcmd)
  - `params` (JSON object)
  - `additional_args` (array of strings)
  - `stdin` (string)
  - `fixed.timeout_seconds` (number)
  - `fixed.confirm_dangerous` (boolean)

#### `designer_cli`
Исполнение через CLI driver catalog (обычно `cli`):

- `driver`: обычно `cli`
- `command_id`: выбирается из списка команд драйвера
- Дополнительно (advanced): `params`, `additional_args`, `stdin`, `fixed.*`

#### `workflow`
Запуск workflow template:

- `workflow_id`: выбирается из списка доступных workflow templates
- Дополнительно (advanced): `params`, `fixed.*`

## Режимы редактирования

### Guided
Для большинства случаев:

- **Add**: создать новое действие.
- **Edit/Copy**: правка/копирование действия.
- **Move up/down**: изменение порядка (влияет на порядок отображения в UI).
- **Disable**: удалить действие из каталога (с сохранением в sessionStorage).
- **Restore last disabled**: вернуть последнее отключённое действие (удобно как “undo”).

### Raw JSON
Для power users / тонкой правки:

- Проверка валидности JSON и базовой структуры.
- **Diff/Preview**: сравнение черновика с текущим серверным снимком.
- Read-only **Server snapshot** для контроля, что именно сейчас в backend.

Рекомендация: перед сохранением используй diff, чтобы не унести лишние изменения.

## Сохранение (Save)

- **Save** делает `PATCH /api/v2/settings/runtime/ui.action_catalog/`.
- Кнопка Save активна только при:
  - наличии изменений (dirty),
  - валидном JSON,
  - `catalog_version = 1`.
- После успешного Save UI обновляет server snapshot и сбрасывает “Unsaved changes”.
- Пока есть несохранённые изменения, **Reload** отключён (чтобы случайно не потерять черновик).

## Частые ошибки валидации и что делать

### `catalog_version must be 1`
- Проверь, что в корне объекта стоит `"catalog_version": 1`.

### `extensions.actions[...]...: unknown command_id ...`
- Значит, `executor.command_id` не найден в driver catalog для выбранного `driver`.
- Проверь каталоги команд в UI: `/settings/command-schemas` (driver `ibcmd` или `cli`).

### `extensions.actions[...]...: workflow not found ...`
- Значит, `executor.workflow_id` не найден или workflow template не подходит (например, невалиден/неактивен).
- Проверь список templates в UI (Templates) и доступы.

### Дубликаты `id`
- `extensions.actions[].id` должны быть уникальны.
- Исправь дубликат (guided покажет ошибку на поле ID; raw — через ошибку в Save).

### Ошибки формата JSON
- В raw-режиме используй **Format**.
- Убедись, что корень — JSON object, а не массив/строка.

## Проверка результата (после Save)

- Открой `/databases` и убедись, что в нужных местах появились/обновились действия:
  - `database_card`: в карточке базы (раздел Extensions).
  - `bulk_page`: в массовых действиях по выбранным базам.
- Если действие не отображается обычному пользователю, это может быть “fail-closed” (невалидные ссылки/опасные команды/нет доступа). Проверь ошибки, risk_level команд и RBAC.

