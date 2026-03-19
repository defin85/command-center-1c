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

Нужен отдельный change, который зафиксирует следующую управляемую волну миграции: завершить platform migration для core operational workspaces и расширить на них автоматический governance perimeter, не пытаясь переписать весь frontend за один шаг.

## What Changes
- Расширить `ui-web-interface-guidelines`, чтобы platform-governed perimeter включал `/`, `/operations`, `/databases`, `/pools/catalog` и `/pools/runs`.
- Зафиксировать, что эти routes используют platform layer на уровне page shell и primary catalog/detail/authoring flows, а не raw `antd` containers как page-level foundation.
- Зафиксировать для `/operations` task-first workspace composition с URL-addressable selected operation context и mobile-safe detail/timeline fallback.
- Зафиксировать для `/databases` canonical workspace composition с явным разделением database catalog, metadata management, DBMS/connection management и extensions/manual-operation handoff paths.
- Зафиксировать для `/pools/catalog` platform workspace composition с task-first separation между pool basics, topology, workflow attachment workspace и remediation handoff.
- Зафиксировать для `/pools/runs` stage-based workspace composition с устойчивым selected run context, progressive disclosure diagnostics и mobile-safe fallback.
- Зафиксировать, что lint/browser validation gate расширяется с pilot pages на operational workspaces и ловит platform-boundary regressions, route-state instability и responsive failures.

## Impact
- Affected specs:
  - `ui-web-interface-guidelines`
  - `execution-runtime-unification`
  - `database-metadata-management-ui`
  - `organization-pool-catalog`
  - `pool-distribution-runs`
- Affected code (expected, when implementing this change):
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

## Assumptions
- Эта волна миграции сознательно ограничивается operational workspaces с наибольшей плотностью operator flows и наибольшим page-level UI debt.
- `/workflows` и связанные workflow authoring surfaces не входят в этот change, чтобы не конфликтовать с уже активными workflow changes и не смешивать migration slice с параллельной продуктовой работой.
- Dashboard включён в governance perimeter как частично мигрированный route, но не задаёт доменные правила вне общих UI platform guidelines.
- Для remaining admin/support routes будут нужны отдельные follow-up changes после стабилизации operational perimeter.
