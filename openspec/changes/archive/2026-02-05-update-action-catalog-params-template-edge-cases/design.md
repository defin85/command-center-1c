# Design: исправления UX/edge cases для params template в Action Catalog

## Архитектурные драйверы
- **Safety-first**: UI не должен неожиданно перезаписывать ручной ввод.
- **Predictability**: поведение при смене `command_id` должно быть простым и объяснимым.
- **Minimal change**: без изменений backend/контрактов.
- **Progressive enhancement**: Guided‑режим улучшает UX, но Raw JSON остаётся доступным для power‑users и edge cases.

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

## Layout driver/command_id (UX)
Текущее поведение: Select для `driver`/`command_id` может схлопываться до узкой ширины, из-за чего `command_id` трудно читать/выбирать.

Решение:
- перейти на реальный flex‑layout (не `Space`) для этих полей;
- задать предсказуемые пропорции (например 1/3 + 2/3) и `width: 100%` для Select;
- сохранить текущие `data-testid` (важно для тестов).

## Guided / Raw JSON для params
### UX
В секции `params`:
- Переключатель (Tabs/Segmented): **Guided** (default) и **Raw JSON**.
- В Guided: интерактивные поля по schema параметрам (из `params_by_name`), с учётом текущей фильтрации disabled + ibcmd connection params.
- В Raw JSON: textarea редактор как сейчас, с ошибкой/подсветкой при невалидном JSON.

### Источник schema
Driver catalog v2: `GET /api/v2/operations/driver-commands/?driver=...` → `commands_by_id[command_id].params_by_name`.

### Каноническое состояние и синхронизация
Рекомендуется один “источник истины” внутри `ActionCatalogEditorModal`:
- `paramsObject: Record<string, unknown>` — каноническое представление параметров;
- `paramsJson: string` — представление для Raw JSON.

Синхронизация:
- При изменении Guided‑поля: `paramsObject = merge(paramsObject, patchForSchemaKey)` → `paramsJson = JSON.stringify(paramsObject, null, 2)`.
- При редактировании Raw JSON:
  - если JSON валиден и это object: обновить `paramsObject`;
  - если невалиден или не object: оставить `paramsObject` прежним, показать ошибку; при попытке перейти в Guided — блокировать/попросить исправить.

### Preserve unknown keys (ключи вне schema)
Guided‑редактор изменяет только schema‑ключи, не удаляя остальные:
- `next = { ...currentParamsObject, [schemaKey]: newValue }`
- удаление ключа — только по явному действию пользователя (если поддерживаем).

### Переиспользование компонентов
Рекомендация: переиспользовать рендеринг параметров из `DriverCommandBuilder` (например `ParamField`) для единообразия по типам/контролам.

## Связанность с builder-utils (опционально)
Текущие helper’ы генерации template лежат в `frontend/src/components/driverCommands/builder/utils.ts`.
Если начнёт мешать связность (или будет риск нежелательных side effects от модуля), вынести в нейтральный модуль, например:
- `frontend/src/lib/driverCommands/paramsTemplate.ts`
или
- `frontend/src/pages/Settings/actionCatalog/paramsTemplate.ts`

## Ссылки (prior art)
- Ant Design v5 рекомендует избегать static методов (`Modal.confirm`) и использовать `App.useApp()` / `Modal.useModal` для доступа к контексту.
- Ant Design Form APIs: `isFieldTouched`/`isFieldsTouched` и `Form.useWatch` полезны, но для “user edited” зачастую надёжнее событие user input (onChange/onFocus) + запрет сброса состояния.

## Риски и крайние случаи (и как их закрыть)
- **Невалидный Raw JSON**: не пытаться синхронизировать в `paramsObject`; явно подсвечивать ошибку и блокировать Guided до исправления.
- **Raw JSON = не object** (например массив/строка/null): Guided не может корректно отобразить; требовать object или предлагать “Reset to {}”.
- **Смена `command_id` после начала ввода**: `pristineParams` остаётся `false`, auto-fill не происходит; пользователь явно выбирает “Insert template”.
- **Schema обновилась/изменилась** (между загрузками): Guided должен быть устойчивым к отсутствующим/новым ключам; unknown keys сохраняются в object.
- **Повторяемые/сложные типы**: если `ParamField` не поддерживает какой-то тип в этом контексте, лучше отдать значение в Raw JSON, чем вводить неверный control.
- **Большие схемы**: schema panel и guided‑форма должны быть ленивыми/сворачиваемыми; избегать рендера “всего сразу”, если это заметно тормозит.
- **Тестовая стабильность**: сохранить `data-testid`, а для width‑проверок предпочесть минимальный порог вместо сравнения точных пикселей.
