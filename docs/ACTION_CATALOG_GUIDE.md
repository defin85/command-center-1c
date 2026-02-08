# Action Catalog (unified operation exposures) — инструкция для операторов

Action Catalog управляется через unified persistent контракт (`operation_exposure(surface=\"action_catalog\")` + `operation_definition`) и описывает, какие действия по расширениям показывать в UI и как их исполнять (через ibcmd/CLI или workflow).

## Доступ

- Экран **staff-only**: требуется `is_staff=true`.
- Если страница не открывается (403/скрыт пункт меню) — проверь роль пользователя.

## Где находится в UI

- Templates → вкладка **Action Catalog**
- Route: `/templates?surface=action_catalog`

## Основные понятия

### Action
Один элемент каталога (запись в `extensions.actions[]`), который описывает:

- `id` — уникальный идентификатор действия (строка).
- `capability` (опционально) — семантический маркер, который понимает backend (например `extensions.list`, `extensions.sync`).
  - `id` — UI-ключ (можно переименовывать без изменения семантики).
  - `capability` — стабильный контракт для backend (plan/apply, snapshot-marking и т.п.).
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

- **Save** делает upsert/publish через unified API:
  - `POST /api/v2/operation-catalog/exposures/`
  - `POST /api/v2/operation-catalog/exposures/{exposure_id}/publish/`
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

### Дубликаты `capability` (для зарезервированных значений)
- Для `capability`, которые backend использует для особой семантики (MVP: `extensions.list`, `extensions.sync`), допускается **не более одного** action на каждый такой `capability`.
- Если в каталоге окажется две записи с одним и тем же зарезервированным `capability`, сохранение будет отвергнуто (fail-closed).
- Legacy режим: если `capability` отсутствует, backend временно трактует `id=="extensions.list"`/`"extensions.sync"` как соответствующие `capability`.

### Ошибки формата JSON
- В raw-режиме используй **Format**.
- Убедись, что корень — JSON object, а не массив/строка.

## Проверка результата (после Save)

- Открой `/databases` и убедись, что в нужных местах появились/обновились действия:
  - `database_card`: в карточке базы (раздел Extensions).
  - `bulk_page`: в массовых действиях по выбранным базам.
- Если действие не отображается обычному пользователю, это может быть “fail-closed” (невалидные ссылки/опасные команды/нет доступа). Проверь ошибки, risk_level команд и RBAC.

## Execution Plan / Binding Provenance (staff-only)

Иногда важно понять “что именно будет выполнено” и “откуда система берёт значения”, не раскрывая секреты.
Для этого UI показывает **Execution Plan** и **Binding Provenance** (только для staff):

- **/templates?surface=action_catalog**: кнопка **Preview** у действия показывает план выполнения и provenance (в JSON).
- **/databases**:
  - Для staff перед запуском действия расширений показывается подтверждение с preview (например `argv_masked`).
- **/operations** (details):
  - Для staff отображаются `Execution Plan (staff)` и таблица `Binding Provenance (staff)`.
  - В `tasks[].result.runtime_bindings` могут появляться runtime-заметки от worker (например нормализация argv или `infobase_auth` “skipped” с причиной).

### Что именно показывается

- **Execution Plan** — безопасное описание того, что будет/было выполнено:
  - для CLI: `argv_masked[]` (секреты замаскированы);
  - для workflow: `workflow_id` и `input_context_masked` (секретные поля заменяются на `***`).
- **Binding Provenance** — список “что куда подставляется”:
  - `target_ref` — куда применяется значение,
  - `source_ref` — откуда оно берётся,
  - `resolve_at` — где резолвится (`api` или `worker`),
  - `sensitive` — пометка, что значение секретное (значения не показываются),
  - `status`/`reason` — применилось или было пропущено (и почему).

## Дебаг: ошибки выполнения (например unsupported flags)

Если операция упала (например `exit status 2`), чтобы понять причину:

1) Открой `/operations` → Details нужной операции.
2) Посмотри:
   - `Execution Plan (staff)` — какие аргументы реально ушли (в `argv_masked`).
   - `Binding Provenance (staff)` — откуда эти аргументы взялись (UI params/additional_args/connection и т.п.).
   - `Tasks` → `result.stderr` / `result.exit_code` (часто содержит точное сообщение `ibcmd`).
   - `Tasks` → `result.runtime_bindings` (если есть): runtime-решения worker’а (например `infobase_auth` со `status=skipped` и `reason=unsupported_for_command`).

3) Сверься со справкой драйвера/команды:
   - Флаги должны соответствовать **схеме команды** (driver catalog). Если флаг отсутствует в схеме команды — скорее всего `ibcmd` его не принимает для этой команды.

4) Исправление обычно одно из:
   - Убрать/поправить лишние `additional_args` в action catalog.
   - Перенести driver-level опции в `connection.*` (если это connection options).
   - Пересобрать action catalog так, чтобы `command_id` ссылался на корректную команду каталога.
