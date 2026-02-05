# Change: UX/безопасность schema-driven params template в Action Catalog (edge cases)

## Why
Текущая реализация schema-driven params template для `/settings/action-catalog` закрывает базовый сценарий, но остаются UX/edge-case риски:
- “touched” состояние может сбрасываться при смене `command_id`, что повышает шанс неожиданного auto-fill при последующих действиях пользователя;
- schema panel всегда видимая и может перегружать модалку при длинных схемах;
- логика “pristine vs user-edited” должна опираться на максимально надёжный сигнал (а не на вручную сбрасываемый флаг), чтобы исключить незаметные перезаписи.

## What Changes
- Уточнить/зафиксировать правила **pristine/touched** для `executor.params_json`:
  - auto-fill разрешён только если поле “pristine” (не редактировалось пользователем в рамках текущей сессии модалки) и пустое/`{}`.
  - смена `command_id` НЕ должна сбрасывать “user-edited” состояние.
  - overwrite существующего JSON — только через явное действие пользователя с confirm.
- Сделать schema panel параметров **collapsible** (по умолчанию свернутой) и показывать счётчик параметров.
- (Опционально, если окажется полезно) локализовать/изолировать helper’ы генерации template в более нейтральный модуль, чтобы снизить связанность с `driverCommands/builder`.

## Impact
- Affected specs:
  - `ui-action-catalog-editor`
- Affected code (ожидаемо):
  - `frontend/src/pages/Settings/actionCatalog/ActionCatalogEditorModal.tsx`
  - (опционально) `frontend/src/components/driverCommands/builder/utils.ts` или новый helper-модуль
  - `frontend/tests/browser/action-catalog-ui.spec.ts`

## Non-Goals
- Замена JSON-редактора `params` на полноценный визуальный builder.
- Любые изменения backend/API/контрактов.
- Расширение схемы `ui.action_catalog`.

