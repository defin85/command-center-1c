## MODIFIED Requirements
### Requirement: Authenticated internal navigation MUST сохранять shared shell runtime
Система ДОЛЖНА (SHALL) использовать SPA navigation для внутренних переходов между authenticated frontend route, которые живут под общим application shell.

Такие handoff path НЕ ДОЛЖНЫ (SHALL NOT) использовать full-document navigation как основной путь, если целевой route находится внутри того же frontend приложения и может быть открыт через router navigation.

Shell-backed authenticated routes, разделяющие один visual/application shell, ДОЛЖНЫ (SHALL) быть собраны под единым route-tree owner для:
- shared auth/bootstrap providers;
- `MainLayout` или эквивалентного shared shell container;
- primary `Suspense`/route-content boundary;
- content handoff через `Outlet` или эквивалентный single-owner routing pattern.

Этот contract НЕ ДОЛЖЕН (SHALL NOT) считаться выполненным, если каждый shell-backed route по-прежнему самостоятельно монтирует собственную связку guard + `MainLayout` + route-content boundary, даже если network reads дедуплицируются cache layer'ом.

Обычный переход между такими routes НЕ ДОЛЖЕН (SHALL NOT) пересоздавать shared shell subtree или оставлять stale route content смонтированным после того, как URL уже перешёл на новый route.

Capability/staff guards МОГУТ (MAY) оставаться отдельными логическими decision points, но НЕ ДОЛЖНЫ (SHALL NOT) повторно становиться owner'ами shared shell runtime для каждого route element.

Shared shell/bootstrap + authz providers ДОЛЖНЫ (SHALL) оставаться canonical owner для user/staff/tenant context. Route pages НЕ ДОЛЖНЫ (SHALL NOT) дублировать `/api/v2/system/bootstrap/`, `/api/v2/system/me/` и `/api/v2/tenants/list-my-tenants/` на default operator path, если тот же context уже доступен через shared shell runtime.

Исключения допускаются только для dedicated login/logout path, explicit refresh flows, tenant-management surfaces или authenticated route groups, которые по design остаются no-shell/fullscreen и явно задокументированы как отдельный runtime owner. Route tree ДОЛЖЕН (SHALL) иметь checked-in классификацию, enforced static regression coverage и отличать shell-backed routes от public/redirect/no-shell exceptions.

#### Scenario: Internal CTA переводит оператора на другой route без document reload
- **GIVEN** оператор находится на authenticated route внутри frontend shell
- **WHEN** он нажимает internal CTA или handoff action, ведущий на другой route того же приложения
- **THEN** navigation выполняется внутри SPA shell без full-document reload
- **AND** bootstrap budget не расходуется повторно только из-за этого перехода

#### Scenario: Transition-mode handoff не оставляет stale shell content после смены URL
- **GIVEN** оператор находится на `/service-mesh` внутри shared authenticated shell
- **AND** router updates выполняются в transition-mode
- **WHEN** он переходит в `/pools/master-data` через internal shell navigation
- **THEN** URL и primary heading принадлежат `/pools/master-data`
- **AND** stale content и diagnostics из `/service-mesh` больше не остаются смонтированными как visible route state
- **AND** shared shell не пересоздаётся только ради этого handoff

#### Scenario: Route page использует shell-owned user и tenant context вместо повторных shell reads
- **GIVEN** shared shell runtime уже загрузил bootstrap и синхронизировал `isStaff` и active tenant
- **WHEN** route page монтируется по своему default operator path
- **THEN** страница получает user/staff/tenant context через shared providers
- **AND** не инициирует redundant вызовы `/api/v2/system/bootstrap/`, `/api/v2/system/me/` и `/api/v2/tenants/list-my-tenants/` без явного runtime trigger

#### Scenario: Governance классифицирует no-shell exceptions явно
- **GIVEN** authenticated route не монтируется под shared `MainLayout`
- **WHEN** route tree проходит frontend governance validation
- **THEN** route имеет checked-in classification как `authenticated no-shell/fullscreen` или эквивалентную explicit exception
- **AND** shell-backed route не может случайно выпасть из shared route group без failing validation
