## 1. Repo-wide governance inventory
- [ ] 1.1 Ввести единый checked-in inventory для всех operator-facing route-entry modules из `frontend/src/App.tsx` и для shell-backed authoring surfaces на `ModalFormShell` / `DrawerFormShell`.
- [ ] 1.2 Ввести явную governance classification `platform-governed`, `legacy-monitored`, `excluded` и зафиксировать допустимые исключения для public/helper route.

## 2. Lint and governance enforcement
- [ ] 2.1 Доработать `frontend/eslint.config.js` и локальные governance rules так, чтобы unclassified route или shell-backed surface блокировали `npm run lint`.
- [ ] 2.2 Распространить repo-wide safety rules на весь monitored frontend perimeter: competing UI foundations, static `antd` context bypasses, `Modal.*` static methods и shell contract violations.
- [ ] 2.3 Оставить tier-specific platform restrictions для `platform-governed` route и убрать зависимость от ad-hoc file globs там, где route уже должен мониториться через общий inventory.

## 3. Automated coverage and docs
- [ ] 3.1 Добавить governance tests, которые сравнивают route map, inventory и реальные frontend source files и падают при drift или missing classification.
- [ ] 3.2 Обновить локальный UI governance contract в документации/инструкциях так, чтобы новый route нельзя было добавить без явного выбора governance tier.

## 4. Validation
- [ ] 4.1 Прогнать `npm --prefix frontend run lint` и целевые governance tests для inventory/coverage checks.
- [ ] 4.2 Прогнать `openspec validate expand-ui-frontend-governance-coverage --strict --no-interactive`.
