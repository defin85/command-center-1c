# Change: Следующая волна UI platform migration для operational workspaces

## Why
Пилотная миграция на новый UI-подход уже зафиксировала canonical platform layer и перевела на него `/decisions` и `/pools/binding-profiles`, но основная operational часть frontend по-прежнему живёт на legacy page composition.

Сейчас самый большой UI-долг сосредоточен в high-traffic рабочих поверхностях:
- `/operations`;
- `/databases`;
- `/pools/catalog`;
- `/pools/runs`;
- `/` (dashboard) как частично переведённый route.

На практике это выражается в трёх устойчивых проблемах:
- page-level orchestration всё ещё строится на raw `antd` containers и ad-hoc `Modal`/`Drawer` flows;
- governance perimeter фактически покрывает только pilot surfaces, поэтому legacy patterns легко возвращаются в новых изменениях;
- крупные монолитные route-page продолжают смешивать catalog, inspect, authoring, diagnostics и remediation в одном canvas, из-за чего растёт вероятность UI loops, regressions по route state и visual overload.
- поверх этого по всему frontend сохраняется отдельный класс runtime regressions: internal handoff между route всё ещё может уходить в full-document navigation, а route pages продолжают дублировать shell-owned reads (`/system/bootstrap`, `/system/me`, `/tenants/list-my-tenants`) вместо переиспользования shared shell context.

Нужен отдельный change, который зафиксирует следующую управляемую волну миграции: завершить platform migration для core operational workspaces и расширить на них автоматический governance perimeter, не пытаясь переписать весь frontend за один шаг.

## What Changes
- Расширить `ui-web-interface-guidelines`, чтобы platform-governed perimeter включал `/`, `/operations`, `/databases`, `/pools/catalog` и `/pools/runs`.
- Зафиксировать, что эти routes используют platform layer на уровне page shell и primary catalog/detail/authoring flows, а не raw `antd` containers как page-level foundation.
- Зафиксировать для `/operations` task-first workspace composition с URL-addressable selected operation context и mobile-safe detail/timeline fallback.
- Зафиксировать для `/databases` canonical workspace composition с явным разделением database catalog, metadata management, DBMS/connection management и extensions/manual-operation handoff paths.
- Зафиксировать для `/pools/catalog` platform workspace composition с task-first separation между pool basics, topology, workflow attachment workspace и remediation handoff.
- Зафиксировать для `/pools/runs` stage-based workspace composition с устойчивым selected run context, progressive disclosure diagnostics и mobile-safe fallback.
- Зафиксировать для всего authenticated frontend shared-shell runtime contract: internal route handoff обязан сохранять SPA shell и не должен потреблять bootstrap budget только из-за перехода между внутренними route.
- Зафиксировать, что staff/user/tenant shell context переиспользуется через shared shell/authz providers, а route pages не дублируют `/system/bootstrap`, `/system/me` и `/tenants/list-my-tenants` на default operator path без явной необходимости.
- Зафиксировать, что lint/browser validation gate расширяется с pilot pages на operational workspaces и ловит platform-boundary regressions, route-state instability и responsive failures.

## Impact
- Affected specs:
  - `ui-web-interface-guidelines`
  - `execution-runtime-unification`
  - `database-metadata-management-ui`
  - `organization-pool-catalog`
  - `pool-distribution-runs`
- Affected code (expected, when implementing this change):
  - `frontend/src/App.tsx`
  - `frontend/src/authz/**`
  - `frontend/src/components/layout/**`
  - `frontend/eslint.config.js`
  - `frontend/src/components/platform/**`
  - `frontend/src/pages/Dashboard/**`
  - `frontend/src/pages/Operations/**`
  - `frontend/src/pages/Databases/**`
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Pools/PoolRunsPage.tsx`
  - `frontend/tests/browser/**`
  - `frontend/src/components/platform/__tests__/**`

## Non-Goals
- Big-bang rewrite всего frontend в рамках одного change.
- Миграция `/workflows`, `/templates`, `/rbac`, `/users`, `/service-mesh`, `/artifacts`, `/settings`, `/dlq`, `/extensions`, `/clusters`, `/command-schemas` и остальных admin/support routes в этом change.
- Переписывание leaf widgets только ради замены каждого raw `antd` import, если page-level platform composition уже соблюдена.
- Изменение backend API, OpenAPI contracts или доменной бизнес-логики runtime.
- Введение второй primary UI foundation поверх уже принятой Ant-based platform.
- Попытка в этом change устранить любой duplicate domain fetch во всех route независимо от shell/runtime ownership. Обязательный scope — shell-safe navigation и устранение redundant shell reads; все оставшиеся domain-specific duplicate reads фиксируются отдельно, если они не нарушают этот контракт.

## Assumptions
- Эта волна миграции сознательно ограничивается operational workspaces с наибольшей плотностью operator flows и наибольшим page-level UI debt.
- При этом shared-shell runtime invariants (`SPA handoff` + `no redundant shell reads`) применяются ко всему authenticated frontend, потому что этот класс regressions живёт выше route-specific page migration и иначе будет возвращаться на неохваченных surfaces.
- `/workflows` и связанные workflow authoring surfaces не входят в этот change, чтобы не конфликтовать с уже активными workflow changes и не смешивать migration slice с параллельной продуктовой работой.
- Dashboard включён в governance perimeter как частично мигрированный route, но не задаёт доменные правила вне общих UI platform guidelines.
- Для remaining admin/support routes будут нужны отдельные follow-up changes после стабилизации operational perimeter.
