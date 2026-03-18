# Change: Единая UI platform поверх Ant (`antd` + `pro-components` + thin design layer)

## Why
Текущий frontend использует `Ant Design`, но делает это несистемно: рядом живут разные page layouts, ad-hoc композиции `Table`/`Descriptions`/`Drawer`, ручные grid-решения, inline editors в общем page flow и прямые vendor imports без единого platform boundary.

На практике это уже приводит к визуальному и архитектурному дрейфу:
- новые и старые экраны используют разные interaction patterns;
- responsive поведение не стандартизовано и легко ломается;
- у команды нет автоматической защиты от появления ещё одной “самодельной” страницы;
- правила по UI существуют только как устные договорённости и разовые ревью.

В репозитории уже есть `antd` и `@ant-design/pro-components`, при этом `Tailwind`/`shadcn` foundation не подключены.

Нужен отдельный change, который:
- фиксирует `Ant Design + Pro Components + project-owned thin design layer` как canonical UI platform для backoffice/frontend surfaces;
- вводит canonical page patterns, начиная с `MasterDetail`;
- добавляет lint/CI enforcement для архитектурных UI-границ;
- добавляет явный блок UI-инструкций в `AGENTS.md`;
- не допускает параллельного внедрения второй competing primary UI foundation без отдельного approved architectural change.

## What Changes
- Добавить новую capability `ui-platform-foundation`.
- Добавить новую capability `ui-frontend-governance`.
- Зафиксировать, что новые или существенно переписываемые admin/backoffice surfaces используют `antd` + `@ant-design/pro-components` через project-owned thin design layer как primary path.
- Зафиксировать dependency baseline, при котором `antd` обновляется до поддерживаемой современной `5.x` линии, совместимой с актуальной линией `@ant-design/pro-components`.
- Зафиксировать canonical page patterns: `List`, `Detail`, `MasterDetail`, `DrawerForm`/`ModalForm`, `Workspace`, `Dashboard`.
- Зафиксировать responsive contract для `MasterDetail`: на узких viewport detail/edit не должен вызывать горизонтальный overflow и должен уходить в `Drawer` или отдельный route/state.
- Зафиксировать lint-enforced архитектурные правила для UI composition boundaries и blocking frontend validation gate.
- Зафиксировать обязательный блок UI-инструкций в `AGENTS.md` для разработчиков и агентов.
- Зафиксировать, что Ant-based UI platform является единственным approved primary direction для новых platform migrations.

## Impact
- Affected specs:
  - `ui-platform-foundation` (new)
  - `ui-frontend-governance` (new)
- Affected code (expected, when implementing this change):
  - `frontend/eslint.config.js`
  - `frontend/package.json`
  - `frontend/src/components/**` и/или `frontend/src/lib/ui/**` для thin design layer
  - `frontend/src/components/layout/**`
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/pages/Pools/**`
  - `frontend/tests/browser/**`
  - `AGENTS.md`

## Non-Goals
- Немедленный rewrite всего frontend за один change.
- Переход на `shadcn/ui`, `Tailwind CSS` или другую вторую primary design system в рамках этого направления.
- Полная миграция всех legacy страниц до внедрения thin design layer и governance rules.
- Замена backend API, OpenAPI contracts или бизнес-логики.
- Автоматическое исправление всех существующих UI inconsistencies без выделенных pilot surfaces.

## Assumptions
- `@ant-design/pro-components` остаётся допустимой и желательной частью canonical UI stack.
- `antd` должен оставаться в поддерживаемом диапазоне peer-совместимости для актуальной линии `@ant-design/pro-components`; неподтверждённый major jump не входит в этот change.
- Новый thin design layer остаётся project-owned слоем поверх `antd`/`pro-components`, а не новой независимой design system.
- Вторая competing primary UI foundation не должна внедряться параллельно с этим change без отдельного approved architectural change.
