# Design: params template из command schema в Action Catalog

## Контекст (текущее поведение)
В guided modal создания/редактирования action (`/settings/action-catalog`) поле `params` — это текстовое поле `params (JSON object)` без подсказок по ключам, типам и required параметрам. Команды (`driver`/`command_id`) при этом выбираются из driver catalog, который уже содержит `params_by_name`.

В мастере создания операции параметры команды отображаются schema-driven (через `DriverCommandBuilder`), что снижает ошибки конфигурации.

## Драйверы и источники truth
- Источник параметров: driver catalog v2 (`/api/v2/operations/driver-commands/?driver=...`) → `commands_by_id[command_id].params_by_name`.
- `params_by_name` содержит:
  - `kind`: `flag|positional`
  - `expects_value`, `value_type`, `required`, `default`, `repeatable`, `enum`, `description`, `disabled`, etc.

## Предлагаемый UX (минимальная реализация)
### 1) Schema panel
В modal под выбором `driver/command_id` показывать collapsible блок “Command parameters (from schema)”:
- таблица/список параметров (name, required, kind/value_type, default, description).
- фильтрация:
  - пропускать `disabled` параметры.
  - для `driver=ibcmd` пропускать connection‑параметры, которые должны приходить из профиля базы (аналогично `DriverCommandBuilder`).

### 2) Insert params template (безопасное автозаполнение)
Добавить кнопку “Insert params template” рядом с `params (JSON object)`:
- при клике формировать объект-шаблон из `params_by_name` и вставлять как pretty JSON.
- если пользователь уже вводил JSON — UI должен спросить подтверждение (“Overwrite params?”) либо только предлагать кнопку без авто‑вставки.

Опциональное auto-fill:
- при первом выборе `command_id` (или смене `command_id`) UI может auto-fill, только если:
  - поле `params` пустое или равно `{}` (после trim/parse),
  - и `params` ещё не “touched” пользователем в рамках текущей сессии modal.

## Формирование шаблона params
Алгоритм `buildParamsTemplate(command, driver)`:
- вход: `DriverCommandV2` (из catalog), `driver`.
- шаги:
  1) взять `params_by_name` (object) → отсортировать по имени (или по `sortParams`, если переиспользуем существующую логику).
  2) пропустить `disabled` и (для ibcmd) connection param names.
  3) для каждого param:
     - если `default` определён → использовать его.
     - иначе:
       - если `repeatable=true` → `[]`
       - иначе → `null`
- output: JSON object с ключами param names.

Примечание: `null` как “пустое значение” безопасно, потому что:
- в CLI/ibcmd preview такие значения обычно не приводят к появлению argv токенов;
- action catalog schema не валидирует типы внутри `params`.

## Риски и меры
- Риск: UI затрёт введённые пользователем значения.
  - Мера: auto-fill только когда поле пустое/`{}` и не touched; иначе только по кнопке + confirm.
- Риск: шаблон включает connection параметры для `ibcmd` и вводит в заблуждение.
  - Мера: фильтровать connection param names аналогично `DriverCommandBuilder`.

## i18n
В рамках этого изменения допускается минимум копирайта на английском (как сейчас в modal). В дальнейшем строки должны быть вынесены в i18n слой; изменение не должно усложнять последующую миграцию.
