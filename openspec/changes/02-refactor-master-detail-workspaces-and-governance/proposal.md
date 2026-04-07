# Change: Рефакторинг master-detail workspaces и enforceable UI governance

## Почему
Сейчас несколько уже migrated platform routes формально используют `WorkspacePage` и `MasterDetailShell`, но по факту кладут в master pane широкие data-heavy таблицы и перегруженные toolbars. Это делает левую колонку плохо читаемой, провоцирует горизонтальный скролл внутри master pane и размывает различие между primary selection context и secondary inspect context.

Скриншоты и текущий код показывают один и тот же structural gap на `/operations`, `/databases` и `/pools/topology-templates`: `master-detail` shell есть, но `master` ведёт себя как сжатая админская таблица вместо compact selection catalog. Текущие lint-правила в основном ловят raw `antd` route shells, но почти не ловят misuse самих platform primitives.

## Что меняется
- Зафиксировать в `ui-platform-foundation`, что master pane в `MasterDetail` не должен быть wide-table workspace по умолчанию и должен оставаться scan-friendly selection surface.
- Усилить `ui-frontend-governance` новыми lint/browser-level invariants для `MasterDetail`:
  - запрет table-first catalog как primary master pane path на governed routes;
  - запрет master-pane horizontal overflow как штатного desktop behaviour;
  - browser-level coverage для layout regressions и misleading empty progress states, которые нельзя надёжно проверить линтером.
- Зафиксировать, что targeting этих route-specific governance rules читается из shared governance inventory change `01-expand-ui-frontend-governance-coverage`, а не из нового hand-maintained route списка.
- Уточнить route-specific contracts для:
  - `/operations`
  - `/databases`
  - `/pools/topology-templates`
  чтобы primary master pane показывал compact catalog/selection rows, а rich inspection/table density уходила в detail pane, dedicated secondary surface или explicit handoff.

## Impact
- Affected specs:
  - `ui-platform-foundation`
  - `ui-frontend-governance`
  - `execution-runtime-unification`
  - `database-metadata-management-ui`
  - `pool-topology-template-catalog`
- Affected code:
  - `frontend/src/components/platform/*`
  - `frontend/eslint.config.js`
  - route inventory рядом с `frontend/src/App.tsx`
  - `frontend/src/pages/Operations/*`
  - `frontend/src/pages/Databases/*`
  - `frontend/src/pages/Pools/PoolTopologyTemplatesPage.tsx`
  - `frontend/tests/browser/ui-platform-contract.spec.ts`
