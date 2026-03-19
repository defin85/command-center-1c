## 1. Shared platform and governance
- [ ] 1.1 Расширить `frontend/eslint.config.js` и связанные governance checks с pilot pages на `/`, `/operations`, `/databases`, `/pools/catalog`, `/pools/runs`.
- [ ] 1.2 Доработать thin design layer только в тех местах, где текущих primitives недостаточно для task-first operational workspaces без raw page-level orchestration.
- [ ] 1.3 Добавить browser-level regression coverage для route-state restore, same-route stability, mobile-safe detail fallback и отсутствия page-wide horizontal overflow на migrated routes.

## 2. Dashboard and operations workspace
- [ ] 2.1 Завершить platform composition для `/` через `DashboardPage` и platform-owned sections, убрав raw `antd` layout containers из route-level orchestration. (после 1.1)
- [ ] 2.2 Мигрировать `/operations` на canonical operational workspace с list/detail/timeline separation, semantic actions и URL-addressable selected operation context. (после 1.1; можно выполнять параллельно с 3.1)
- [ ] 2.3 Добавить unit/browser tests для reload/back-forward restore, same-route menu stability и narrow-viewport inspect flow на `/operations`. (после 2.2)

## 3. Databases workspace
- [ ] 3.1 Мигрировать `/databases` на canonical workspace с явным разделением database catalog, metadata management, DBMS metadata, connection profile и extensions/manual-operation handoff surfaces. (после 1.1; можно выполнять параллельно с 2.2)
- [ ] 3.2 Перевести primary edit/inspection flows на canonical `DrawerFormShell` / `ModalFormShell` или explicit route handoff, убрав конкурирующие page-level raw drawers/modals как основной путь. (после 3.1)
- [ ] 3.3 Добавить tests для selected database route state, metadata management handoff и accessibility labels в `/databases`. (после 3.2)

## 4. Pools workspaces
- [ ] 4.1 Мигрировать `/pools/catalog` на platform workspace с task-first separation между pool basics, topology, workflow attachment workspace и remediation guidance. (после 1.1)
- [ ] 4.2 Мигрировать `/pools/runs` на stage-based platform workspace с устойчивым selected run context, progressive disclosure diagnostics и mobile-safe detail fallback. (после 1.1; можно выполнять параллельно с 4.1 после shared primitives)
- [ ] 4.3 Добавить unit/browser tests для deep-link restore, stage transitions, binding/remediation handoff и responsive fallback на `/pools/catalog` и `/pools/runs`. (после 4.1 и 4.2)

## 5. Validation and rollout
- [ ] 5.1 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [ ] 5.2 Прогнать `openspec validate refactor-ui-platform-operational-workspaces --strict --no-interactive`.
- [ ] 5.3 Подготовить follow-up issue/change list для remaining legacy routes, которые остаются вне этого migration slice.
