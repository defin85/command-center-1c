# Change: Action Catalog editor — Guided params + безопасный schema-driven template (edge cases)

## Why
В `/settings/action-catalog` редактирование `executor.params` сейчас ориентировано на Raw JSON, а schema-driven template закрывает только базовый сценарий. Это оставляет UX и safety проблемы:
- Select выбора `driver`/`command_id` может схлопываться до узкой ширины, что делает выбор команды неудобным.
- Параметры приходится вручную заполнять JSON’ом по шаблону — логичнее предоставить Guided‑режим с интерактивными полями по schema.
- Есть edge cases безопасности ввода: auto-fill и overwrite не должны неожиданно перезаписывать ручной ввод; `user-edited` состояние не должно “сбрасываться” при смене `command_id`.
- Schema panel параметров при длинных схемах перегружает модалку, если всегда развёрнута.

## What Changes
- Секция `params` получает переключатель **Guided / Raw JSON** (по умолчанию Guided).
- В Guided режиме UI рендерит интерактивные поля по `params_by_name` (после фильтрации disabled + ibcmd connection params), переиспользуя существующие компоненты (напр. `ParamField`) для единообразия типов.
- Guided‑редактирование **сохраняет кастомные/unknown keys** (ключи, отсутствующие в schema): Guided меняет только schema‑ключи, не удаляя остальные.
- Raw JSON остаётся доступным; при невалидном JSON Guided‑режим не должен “ломаться”/терять данные.
- Fix layout: выбор `driver`/`command_id` получает стабильную ширину (flex‑layout, без схлопывания).
- Уточнить/зафиксировать правила **pristine/touched** для auto-fill schema template:
  - auto-fill разрешён только если поле pristine и пустое/`{}`.
  - смена `command_id` НЕ сбрасывает “user-edited”.
  - overwrite существующего JSON — только через явное действие пользователя с confirm.
- Сделать schema panel параметров **collapsible** (по умолчанию свернутой) и показывать счётчик параметров.

## Impact
- Affected specs:
  - `ui-action-catalog-editor`
- Affected code (ожидаемо):
  - `frontend/src/pages/Settings/actionCatalog/ActionCatalogEditorModal.tsx`
  - `frontend/src/components/driverCommands/builder/ParamField.tsx` (переиспользование)
  - (опционально) `frontend/src/components/driverCommands/builder/utils.ts` или новый helper-модуль
  - `frontend/tests/browser/action-catalog-ui.spec.ts`

## Non-Goals
- Полноценный “workflow builder” или изменения UX за пределами редактора Action Catalog.
- Любые изменения backend/API/контрактов.
- Расширение схемы `ui.action_catalog`.
