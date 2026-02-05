# Design: исправления UX/edge cases для params template в Action Catalog

## Архитектурные драйверы
- **Safety-first**: UI не должен неожиданно перезаписывать ручной ввод.
- **Predictability**: поведение при смене `command_id` должно быть простым и объяснимым.
- **Minimal change**: без изменений backend/контрактов.

## Проблема “touched”/auto-fill
В текущем подходе есть риск, что `touched`/“user edited” может быть сброшен при смене `command_id`, что открывает возможность auto-fill в ситуациях, когда пользователь уже взаимодействовал с полем.

Антипаттерн: “обнулить touched при смене команды”.

### Рекомендуемая модель состояния
Внутри `ActionCatalogEditorModal` ввести понятие **pristineParams** (булево), которое:
- становится `false` при первом пользовательском изменении `params_json` (например, `onChange`/`onFocus` на textarea или через `onFieldsChange` по `Form`).
- **никогда не возвращается в `true`** в рамках текущей сессии модалки.

Auto-fill допускается только если:
- `pristineParams === true`
- текущее значение `params_json` пустое или равно `{}` (после `trim`+`parseJson`).
- выбран валидный `command_id` и в схеме есть хотя бы 1 параметр.
- для защиты от “дребезга” — не более 1 раза на конкретный `command_id` за сессию (например, `lastAutoFilledCommandId` или `Set`).

Кнопка “Insert params template”:
- если поле пустое/`{}` — вставляет без confirm;
- иначе — всегда показывает confirm (overwrite).

## Schema panel
Цель: не перегружать модалку при длинных схемах и сделать “подсказку” по параметрам доступной по требованию.

### UI
- Использовать `Collapse` (Ant Design) или collapsible Card.
- Заголовок: “Command parameters (from schema)”, дополнительно “(N)” где N = число параметров после фильтрации.
- По умолчанию: **collapsed**.
- Контент: текущий список/таблица параметров (name + required/kind/value_type/repeatable + default + description).

## Связанность с builder-utils (опционально)
Текущие helper’ы генерации template лежат в `frontend/src/components/driverCommands/builder/utils.ts`.
Если начнёт мешать связность (или будет риск нежелательных side effects от модуля), вынести в нейтральный модуль, например:
- `frontend/src/lib/driverCommands/paramsTemplate.ts`
или
- `frontend/src/pages/Settings/actionCatalog/paramsTemplate.ts`

## Ссылки (prior art)
- Ant Design v5 рекомендует избегать static методов (`Modal.confirm`) и использовать `App.useApp()` / `Modal.useModal` для доступа к контексту.
- Ant Design Form APIs: `isFieldTouched`/`isFieldsTouched` и `Form.useWatch` полезны, но для “user edited” зачастую надёжнее событие user input (onChange/onFocus) + запрет сброса состояния.

