# Change: Guided params editor в Action Catalog (schema-driven, с Raw JSON fallback)

## Why
Сейчас staff в `/settings/action-catalog` настраивает `executor.params` как JSON-текст с автоподстановкой шаблона. Даже с template это остаётся:
- неудобно (нужно руками вводить значения),
- рискованно (ошибки типов/структуры),
- плохо масштабируется на длинные схемы.

Логичнее дать интерактивный guided‑редактор по `params_by_name` (как в других schema-driven UI), сохранив возможность Raw JSON для power users и нестандартных кейсов.

## What Changes
- В modal Add/Edit action добавить переключатель **`Guided / Raw JSON`** для редактирования `executor.params`:
  - по умолчанию **Guided**;
  - Raw JSON остаётся доступным для ручных правок.
- Guided‑редактор строится из driver catalog v2 `commands_by_id[command_id].params_by_name` и позволяет заполнять значения через UI‑контролы.
- **Сохранение кастомных ключей**: если в `params` есть ключи, отсутствующие в schema, Guided‑режим НЕ должен их терять; при изменении schema‑полей UI делает merge поверх существующего объекта.
- Исправить UX ширины для выбора `driver` / `command_id` (Select не должен сжиматься до ~100px).

## Impact
- Affected specs:
  - `ui-action-catalog-editor`
- Affected code (ожидаемо):
  - `frontend/src/pages/Settings/actionCatalog/ActionCatalogEditorModal.tsx`
  - (возможно) переиспользование `frontend/src/components/driverCommands/builder/*` для ParamField/рендеринга полей
  - `frontend/tests/browser/action-catalog-ui.spec.ts`

## Non-Goals
- Изменение backend/API/контрактов.
- Полная замена Action Catalog editor на отдельный мастер операций.
- Автогенерация `additional_args` из schema.

