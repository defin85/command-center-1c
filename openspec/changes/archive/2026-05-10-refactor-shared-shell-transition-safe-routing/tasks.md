## 1. Contract
- [x] 1.1 Обновить `ui-web-interface-guidelines`: зафиксировать single-owner route tree для shell-backed authenticated routes и transition-safe handoff contract.
- [x] 1.2 Обновить `ui-realtime-query-runtime`: зафиксировать single bootstrap owner для authenticated app session и thin-gate consumption для capability/staff guards.

## 2. Frontend route tree
- [x] 2.1 Перестроить `frontend/src/App.tsx` или выделенный route module так, чтобы shell-backed routes разделяли один `MainLayout` + primary `Suspense` + `Outlet` owner.
- [x] 2.2 Ввести один default authenticated shell bootstrap owner/provider и перевести `MainLayout`, `AuthzProvider`, `I18nProvider`, `ProtectedRoute`, `StaffRoute`, `RbacRoute` и `DriverCatalogsRoute` на shared shell context вместо direct route-local bootstrap ownership.
- [x] 2.3 Сохранить explicit no-shell/fullscreen exceptions без возврата к per-route shell ownership; классификация исключений должна быть checked-in и проверяемой.
- [x] 2.4 Включить `BrowserRouter future.v7_startTransition` только после route-tree refactor.
- [x] 2.5 Расширить `frontend/src/uiGovernanceInventory.js` или эквивалентную checked-in route metadata shell-runtime классификацией (`public`, `redirect`, `shell-backed authenticated`, `authenticated no-shell/fullscreen`) и enforce её static governance tests так, чтобы shell-backed route не мог выпасть из shared owner незаметно.

## 3. Regression coverage
- [x] 3.1 Добавить или обновить focused app-level tests на auth redirect restore и transition-safe internal handoff.
- [x] 3.2 Сохранить и при необходимости расширить browser regression `service-mesh -> pool-master-data`, чтобы он ловил stale content и bootstrap replay под transition-mode.
- [x] 3.3 Добавить focused static/unit coverage, которое ловит повторное появление direct `useShellBootstrap` owners в `MainLayout`, `AuthzProvider`, `I18nProvider` или route guards на default shell path.

## 4. Validation
- [x] 4.1 Прогнать `cd frontend && npm run typecheck`.
- [x] 4.2 Прогнать targeted `vitest` для app routing/auth restore checks.
- [x] 4.3 Прогнать `cd frontend && npm run test:browser:ui-platform:runtime-surfaces`.
- [x] 4.4 Прогнать `openspec validate refactor-shared-shell-transition-safe-routing --strict --no-interactive`.
