## Context

`add-cross-stack-internationalization-foundation` уже дал рабочий baseline:
- canonical locale contract через shell bootstrap;
- frontend i18n runtime c namespace catalogs и fallback;
- shared formatter layer;
- `antd` locale bridge;
- code-first problem localization;
- pilot migration for `Dashboard`, `System Status`, `Clusters`, `RBAC`.

Этого достаточно для foundation, но недостаточно для finish-state. Repo всё ещё содержит большой массив platform-governed и legacy-monitored surfaces, которые:
- держат raw `toLocale*`;
- используют ad hoc route copy;
- не имеют route-family namespace coverage;
- не защищены тем же governance perimeter, что pilot wave.

Full migration — это уже не новый foundation, а controlled rollout across route families, shell surfaces и shared helper modules.

## Goals

- Довести remaining operator/staff-facing route families до canonical i18n path на frontend.
- Сделать locale governance inventory-backed и repo-wide, а не pilot-only.
- Убрать remaining raw locale formatting и hardcoded locale tags из `platform-governed` surfaces, входящих в этот rollout.
- Довести platform-governed perimeter до finish-state и не оставлять `/pools/factual` implicit gap внутри этого rollout.

## Non-Goals

- Не менять locale transport contract, bootstrap shape и supported locale set, уже введённые foundation change.
- Не локализовывать business data и worker-produced artifacts.
- Не внедрять roaming locale preferences или server-owned user settings.
- Не переводить `excluded` public/redirect routes.
- Не мигрировать `/pools/factual` внутри этого rollout; он закрывается отдельным approved follow-up change.

## Locked Decisions

### 1. Full migration опирается на существующий runtime, а не создаёт второй i18n слой

Используется тот же `frontend/src/i18n/**`, тот же `X-CC1C-Locale`, тот же shell bootstrap contract и тот же `ConfigProvider locale` owner. Дополнительный route-local translation runtime, новый vendor locale owner или alternate library в этот rollout не входят.

### 2. Единица миграции — route family плюс все owned shell surfaces и shared helpers

Нельзя считать route migrated, если:
- route entry переведён, но его drawer/modal/detail shell остался на raw strings;
- route table/column helpers всё ещё используют raw `toLocale*`;
- shared utility, рендерящий user-visible timestamps или durations для этого route family, остался ad hoc.

Следствие: rollout планируется не по одиночным файлам, а по family slices.

### 3. Governance coverage должна выводиться из checked-in inventory

Pilot-specific hardcoded allow/block set не масштабируется на full migration. Для finish-state источник истины — checked-in:
- `routeGovernanceInventory`
- `shellSurfaceGovernanceInventory`

Locale lint/test coverage должна автоматически совпадать с этим inventory, иначе full migration будет постоянно разъезжаться с route map.

### 4. Namespace strategy остаётся route-family oriented

Один гигантский словарь на весь продукт не нужен. Расширение идёт по route/domain namespaces:
- `operations`
- `artifacts`
- `databases`
- `extensions`
- `templates`
- `workflows`
- `decisions`
- `serviceMesh`
- `users`
- `dlq`
- `settings`
- pool-domain namespaces для `catalog`, `schema templates`, `topology templates`, `execution packs`, `master data`, `runs`, `factual`

Shared copy остаётся в `common`, `shell`, `platform`, `errors`.

### 5. `/pools/factual` carved out в отдельный follow-up change

Current repo-wide rollout не включает миграцию `/pools/factual` и не должен silently считать его частью своих wave completion criteria.

Для этого change finish-state означает:
- все `platform-governed` route families из checked-in inventory migrated на canonical i18n path;
- `/pools/factual` остаётся вне scope этого rollout, но покрыт отдельным approved follow-up change;
- current rollout не заявляет repo-wide completion, если factual route остаётся просто implicit legacy tail без такого follow-up.

## Rollout Slices

### Wave A: Low-coupling admin/support routes

Target surfaces:
- `/extensions`
- `/users`
- `/dlq`
- `/settings/runtime`
- `/settings/command-schemas`
- `/settings/timeline`

Reason:
- одинаковый privileged/settings governance profile;
- comparatively небольшой residual raw locale debt;
- минимальная cross-route shared-helper coupling по сравнению с heavier families.

### Wave B: Shared support/governance surfaces with secondary shells

Target surfaces:
- `/artifacts`
- `/service-mesh`
- `/decisions`

Reason:
- route families завязаны на drawers/detail panels и shared helper modules;
- migration здесь проверяет, что shared shell semantics и observability/support copy не распадаются на route-local islands.

### Wave C: Operational catalog/detail routes

Target surfaces:
- `/operations`
- `/databases`
- `/templates`

Reason:
- data-heavy catalog/detail surfaces со сравнительно умеренным количеством raw formatter debt;
- хороший mid-stage stress test для formatter layer без authoring/runtime complexity workflow family.

### Wave D: Workflow family

Target surfaces:
- `/workflows`
- `/workflows/executions`
- `/workflows/new`
- `/workflows/:id`
- `/workflows/executions/:executionId`

Reason:
- highest complexity outside pools: catalog, authoring, execution monitor, node/detail drawers;
- заметный хвост timestamps и detail-owned semantics;
- отдельная волна уменьшает риск, что workflow authoring regressions заблокируют остальные route families.

### Wave E: Pool reusable authoring/catalog surfaces

Target surfaces:
- `/pools/catalog`
- `/pools/templates`
- `/pools/topology-templates`
- `/pools/execution-packs`

Reason:
- reusable catalog/editor surfaces с bounded formatter debt;
- логично мигрировать до самых тяжёлых operational pool surfaces.

### Wave F: Pool operational closure

Target surfaces:
- `/pools/master-data`
- `/pools/runs`

Reason:
- самый высокий domain/runtime coupling среди remaining `platform-governed` pool surfaces;
- nested shells, helper modules и operator consequence surface;
- `/pools/factual` вынесен отдельно, чтобы не смешивать governed closure с legacy-monitored graduation/refactor.

## Wave-Level Definition Of Done

Для каждой wave migration считается завершённой, только если:
- route entries, owned shell surfaces и owned user-visible helper modules переведены на canonical i18n/formatter path;
- scoped search больше не находит raw `toLocale*` и hardcoded locale tags в wave-owned modules;
- добавлены namespace catalogs и минимальный targeted browser evidence для representative surface этой wave;
- inventory-backed governance coverage не оставляет wave modules вне locale boundary checks.

## Verification Strategy

- Static proof:
  - repo-wide locale governance checks match route/shell inventory;
  - remaining raw `toLocale*` и hardcoded locale tags не остаются в targeted surfaces;
  - shared helper modules не обходят formatter layer.
- Unit/integration proof:
  - catalog parity tests для новых namespaces;
  - formatter/error-code tests для remaining route families;
  - inventory/coverage tests для locale governance wiring.
- Browser proof:
  - representative locale-switch + reload smoke per migration wave;
  - representative route-family checks на отсутствие mixed-language shell copy и broken empty/error states;
  - factual-specific browser evidence остаётся responsibility отдельного follow-up change.

## Risks

- Большой объём UI copy и helper ownership.
  - Mitigation: мигрировать route families целиком, а не по случайным файлам.
- Drift между route inventory и locale governance coverage.
  - Mitigation: сделать coverage inventory-backed, а не hand-maintained.
- Скрытые raw formatter paths в shared helpers.
  - Mitigation: включить shared `components/**` и `utils/**` в scoped search и acceptance gates.
- Развод repo-wide rollout и factual follow-up добавляет cross-change coordination risk.
  - Mitigation: зафиксировать carve-out в spec/tasks этого change и создать отдельный approved factual proposal до объявления full migration complete.
