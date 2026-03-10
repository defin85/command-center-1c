## 1. Discovery and migration contract
- [ ] 1.1 Зафиксировать inventory текущих frontend поверхностей по уровням сложности: `primitive-friendly`, `medium-complexity`, `admin-heavy`.
- [ ] 1.2 Выбрать initial pilot slice для первой миграции без затрагивания критичных CRUD-heavy экранов.
- [ ] 1.3 Зафиксировать parity checklist для migration-ready surface: accessibility, keyboard navigation, form semantics, modal/drawer behavior, testability, bundle impact.

## 2. Foundation scaffolding
- [ ] 2.1 Подключить `Tailwind CSS` и `shadcn/ui` к существующему `frontend` без удаления `Ant Design`.
- [ ] 2.2 Создать локальный project-owned слой UI primitives (`frontend/src/components/ui/**`) и базовых layout/text primitives.
- [ ] 2.3 Зафиксировать shared tokens/theme contract для mixed-mode периода, чтобы новые primitives не расходились по spacing/color/typography semantics.

## 3. Migration guardrails
- [ ] 3.1 Зафиксировать правило: новые или целенаправленно переписываемые UI surfaces используют локальный UI layer как primary path вместо прямых vendor imports.
- [ ] 3.2 Зафиксировать список surface types, которые остаются на `Ant Design` до появления validated parity (`complex tables`, `advanced forms`, `dense admin drawers/modals`).
- [ ] 3.3 Зафиксировать rollback/coexistence правила, если pilot migration ухудшает UX, accessibility или скорость разработки.

## 4. Pilot rollout
- [ ] 4.1 Реализовать один low-risk pilot screen или isolated workspace на новом UI foundation.
- [ ] 4.2 Подтвердить, что pilot route работает внутри существующего app shell, routing, auth guards и query state management без behavioural regressions.
- [ ] 4.3 Сравнить DX / визуальную консистентность / bundle impact / test maintenance cost до и после pilot migration.

## 5. Documentation and validation
- [ ] 5.1 Подготовить migration playbook для команды: когда использовать локальные primitives, когда оставаться на `Ant Design`, как выбирать следующие slices.
- [ ] 5.2 Обновить frontend documentation / ADR-style notes по UI foundation strategy.
- [ ] 5.3 Прогнать `openspec validate add-shadcn-ui-foundation --strict --no-interactive`.
