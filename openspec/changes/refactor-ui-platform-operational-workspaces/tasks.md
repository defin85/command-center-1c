## 1. Shared platform and governance
- [x] 1.1 Расширить `frontend/eslint.config.js` и связанные governance checks с pilot pages на `/`, `/operations`, `/databases`, `/pools/catalog`, `/pools/runs`, а также зафиксировать запрет full-document internal navigation на authenticated route handoff.
- [x] 1.2 Доработать thin design layer и shared shell/runtime helpers только в тех местах, где текущих primitives недостаточно для task-first operational workspaces и shell-safe in-app handoff без raw page-level orchestration.
- [x] 1.3 Провести repo-wide аудит authenticated route handoff и shell context ownership, заменив full-document internal переходы и redundant shell reads (`/system/bootstrap`, `/system/me`, `/tenants/list-my-tenants`) на shared-shell pattern.
- [x] 1.4 Добавить browser-level regression coverage для route-state restore, same-route stability, shell-safe handoff, mobile-safe detail fallback и отсутствия page-wide horizontal overflow на migrated routes и shared shell contract.

## 2. Dashboard and operations workspace
- [x] 2.1 Завершить platform composition для `/` через `DashboardPage` и platform-owned sections, убрав raw `antd` layout containers из route-level orchestration. (после 1.1)
- [x] 2.2 Мигрировать `/operations` на canonical operational workspace с list/detail/timeline separation, semantic actions и URL-addressable selected operation context. (после 1.1; можно выполнять параллельно с 3.1)
- [x] 2.3 Добавить unit/browser tests для reload/back-forward restore, same-route menu stability, shell-safe route handoff и narrow-viewport inspect flow на `/operations`. (после 2.2)

## 3. Databases workspace
- [x] 3.1 Мигрировать `/databases` на canonical workspace с явным разделением database catalog, metadata management, DBMS metadata, connection profile и extensions/manual-operation handoff surfaces. (после 1.1; можно выполнять параллельно с 2.2)
- [x] 3.2 Перевести primary edit/inspection flows на canonical `DrawerFormShell` / `ModalFormShell` или explicit route handoff, убрав конкурирующие page-level raw drawers/modals как основной путь. (после 3.1)
- [x] 3.3 Добавить tests для selected database route state, metadata management handoff, shell-safe internal navigation и accessibility labels в `/databases`. (после 3.2)

## 4. Pools workspaces
- [x] 4.1 Мигрировать `/pools/catalog` на platform workspace с task-first separation между pool basics, topology, workflow attachment workspace и remediation guidance. (после 1.1)
- [x] 4.2 Мигрировать `/pools/runs` на stage-based platform workspace с устойчивым selected run context, progressive disclosure diagnostics и mobile-safe detail fallback. (после 1.1; можно выполнять параллельно с 4.1 после shared primitives)
- [x] 4.3 Добавить unit/browser tests для deep-link restore, stage transitions, binding/remediation handoff, shell-bootstrap budget preservation и responsive fallback на `/pools/catalog` и `/pools/runs`. (после 4.1 и 4.2)

## 5. Validation and rollout
- [x] 5.1 Прогнать `npm --prefix frontend run lint`, `npm --prefix frontend run test:run`, `npm --prefix frontend run test:browser:ui-platform`, `npm --prefix frontend run build`.
- [x] 5.2 Прогнать `openspec validate refactor-ui-platform-operational-workspaces --strict --no-interactive`.
- [x] 5.3 Подготовить follow-up issue/change list для remaining legacy routes и residual duplicate domain reads, которые остаются вне этого migration slice и не покрываются shared-shell contract.
