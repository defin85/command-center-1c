# Change: Автозаполнение `executor.params` в Action Catalog из command schema

## Why
Сейчас при создании нового action в `/settings/action-catalog` оператору нужно вручную составлять `params (JSON object)` по памяти или открывая документацию/схему команды в другом месте. Это увеличивает вероятность ошибок (неверные ключи, пропущенные required параметры) и делает настройку action catalog заметно менее удобной, чем создание операции через мастер (где параметры видны из schema).

## What Changes
- Guided modal “Add/Edit action” в редакторе `ui.action_catalog` получает поддержку **schema-driven шаблона параметров**:
  - после выбора `driver` + `command_id` UI показывает список параметров команды из driver catalog (имя, required, kind, value_type, default, description).
  - UI предлагает “Insert params template” (и/или auto-fill при пустом поле) для заполнения `params` объектом-шаблоном, построенным из `params_by_name`.
- Правила безопасности UX:
  - UI **не должен** без явного действия пользователя затирать уже введённый JSON.
  - auto-fill допускается только когда поле `params` пустое/`{}` и пользователь ещё не редактировал его вручную.
- Никаких изменений backend / контрактов не требуется: это UI‑улучшение для staff-only редактора.

## Impact
- Affected specs:
  - `ui-action-catalog-editor` (guided editor UX для `params`)
  - (опционально) `ui-driver-command-builder` (консистентность поведения “параметры из schema” в редакторах)
- Affected code (ожидаемо):
  - Frontend: `frontend/src/pages/Settings/actionCatalog/ActionCatalogEditorModal.tsx`
  - Frontend: утилиты/типы driver commands (`frontend/src/api/driverCommands.ts`) и/или общие функции в `frontend/src/components/driverCommands/builder/utils.ts`
  - Tests: Playwright `frontend/tests/browser/action-catalog-ui.spec.ts` или unit-тесты для helper’ов

## Non-Goals
- Полная замена JSON-редактора на `DriverCommandBuilder` внутри Action Catalog (можно рассмотреть отдельно, если потребуется).
- Автоматическое заполнение `additional_args` из schema.
- Добавление новых возможностей backend-выполнения или расширение action catalog schema.
