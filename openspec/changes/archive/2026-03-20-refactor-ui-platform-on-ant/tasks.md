## 1. Спецификация и направление
- [x] 1.1 Зафиксировать `ui-platform-foundation` и `ui-frontend-governance` как source-of-truth для новой UI platform поверх Ant.
- [x] 1.2 Зафиксировать single-primary-direction policy и не допускать параллельной реализации двух competing UI foundations.

## 2. Thin design layer
- [x] 2.1 Выделить project-owned thin design layer поверх `antd` и `@ant-design/pro-components` для canonical page patterns и shared UI semantics.
- [x] 2.2 Ввести canonical abstractions минимум для `PageHeader`, `WorkspacePage`, `EntityTable`, `EntityDetails`, `MasterDetailShell`, `DrawerFormShell`, `StatusBadge`, `JsonBlock`, `ErrorState`, `EmptyState`.
- [x] 2.3 Зафиксировать responsive contract для `MasterDetail`: narrow viewport использует `Drawer` или отдельный route/state вместо inline page reflow и horizontal overflow.
- [x] 2.4 Обновить `antd` до поддерживаемой современной `5.x` линии, совместимой с актуальной линией `@ant-design/pro-components`, и зафиксировать target baseline в docs/tooling.
- [x] 2.5 Если после обновления выбран `Splitter`, задокументировать его как допустимый implementation option; если нет, зафиксировать поддерживаемую реализацию через grid + `Drawer` fallback.

## 3. Governance и автоматическая валидация
- [x] 3.1 Расширить `frontend/eslint.config.js` правилами UI platform boundaries (`no-restricted-imports` / `no-restricted-syntax` / локальный plugin при необходимости).
- [x] 3.2 Сделать `npm run lint` частью blocking frontend validation gate, который запускается в CI и при сборке выбранным проектом способом.
- [x] 3.3 Добавить browser-level проверки для non-lintable инвариантов: отсутствие горизонтального overflow, корректный mobile fallback для `MasterDetail`, сохранение a11y labels.
- [x] 3.4 Добавить в `AGENTS.md` отдельный блок UI instructions: canonical stack, page patterns, responsive rules, enforcement boundaries и запреты на второй primary UI foundation.

## 4. Pilot surfaces
- [x] 4.1 Перевести `/decisions` на canonical `MasterDetail` pattern с edit в `Drawer` или отдельном route/state вместо inline editor в общем page flow.
- [x] 4.2 Перевести `/pools/binding-profiles` на тот же platform layer и снизить визуальную перегрузку detail/payload sections через canonical primitives.

## 5. Проверки и выпуск
- [x] 5.1 Прогнать `npm run lint`, `npm run test:run`, релевантные `playwright`-спеки и `npm run build` для frontend.
- [x] 5.2 Прогнать `openspec validate refactor-ui-platform-on-ant --strict --no-interactive`.
