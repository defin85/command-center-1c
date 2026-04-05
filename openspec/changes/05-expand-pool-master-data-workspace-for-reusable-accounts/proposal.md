# Change: 05. Довести post-platform pool master-data workspace до reusable accounts

## Why
Foundation для reusable accounts уже shipped на backend стороне: registry/capability contract из `01-add-reusable-data-registry-and-capability-gates` и storage/API для `GLAccount` / `GLAccountSet` из `02-extend-master-data-hub-with-reusable-accounts` уже существуют. Но frontend `/pools/master-data` всё ещё живёт на legacy page composition, а shared helper layer по-прежнему держит string-specific assumptions и не покрывает account family целиком.

Если просто "добавить ещё две вкладки" в текущий route, система закрепит legacy `Card + Tabs` foundation, оставит `Bindings` без `chart_identity`, а token picker продолжит ломаться на registry-published `gl_account`. Поэтому change должен быть явно post-platform: стартовать только после canonical shell для `/pools/master-data` и затем доводить account UI поверх него.

Этот change фиксирует отдельную UI-фазу завершения reusable account surfaces внутри уже migrated master-data workspace.

## What Changes
- Выполнять change только после landing canonical multi-zone shell для `/pools/master-data` из `04-refactor-ui-platform-workflow-template-workspaces`.
- Расширить `/pools/master-data` внутри canonical shell новыми рабочими зонами `GLAccount` и `GLAccountSet`.
- Добавить operator-facing list/detail authoring UI для `GLAccount`, account bindings, `chart_identity`, compatibility markers и `GLAccountSet` draft/publish/revision lifecycle.
- Обобщить shared reusable-data helper layer:
  - использовать registry `label` как operator-facing caption вместо raw `entity_type`;
  - убрать string-specific defaults и special-case exclusions вроде `'binding'`, если нужное поведение уже выражается через registry contract и page intent;
  - добавить `gl_account` token catalog adapter и fail-closed coverage для registry-published token entities.
- Подключить token picker, bindings UI, bootstrap import zone и capability states к generated reusable-data registry contract.
- Расширить `/pools/catalog` token picker поддержкой `master_data.gl_account.*.ref`.
- Расширить bootstrap import UI поддержкой `GLAccount` как bootstrap-capable entity.
- Показать capability-gated sync/readiness states для reusable accounts без generic mutating controls.
- Переиспользовать shipped backend/API/contracts как baseline; менять schema только если во время реализации обнаружится реальный UI-blocking contract gap.
- Не вводить новый route-level shell, новый parallel layout contract или альтернативную page foundation.

## Impact
- Affected specs:
  - `pool-master-data-hub-ui`
- Affected code:
  - `frontend/src/pages/Pools/PoolMasterDataPage.tsx`
  - `frontend/src/pages/Pools/masterData/**`
  - `frontend/src/pages/Pools/PoolCatalogRouteCanvas.tsx`
  - `frontend/src/components/platform/**`
  - `frontend/src/pages/Pools/__tests__/**`
  - `frontend/tests/browser/**`
- Related changes:
  - blocked by `04-refactor-ui-platform-workflow-template-workspaces` for `/pools/master-data`
  - builds on archived `2026-04-03-01-add-reusable-data-registry-and-capability-gates`
  - builds on archived `2026-04-04-02-extend-master-data-hub-with-reusable-accounts`

## Non-Goals
- Поставка самого canonical shell для `/pools/master-data`.
- Изменение backend runtime semantics publication или factual execution.
- Добавление новых outbound/bidirectional sync semantics для account entities.
- Введение второго primary design system или page foundation.

## Assumptions
- `/api/v2/pools/master-data/gl-accounts/`, `/api/v2/pools/master-data/gl-account-sets/` и `/api/v2/pools/master-data/registry/` остаются достаточным shipped baseline для UI; schema правки нужны только при обнаружении реального contract gap.
- Platform primitives (`WorkspacePage`, `MasterDetailShell`, `DrawerFormShell`, `ModalFormShell`) считаются canonical foundation для account surfaces после landing prerequisite change.
