# Change: add-ui-workspace-presentation-preferences

## Почему

После последних UI platform waves стало видно, что operator-facing catalog surfaces живут в двух допустимых, но разных interaction models:
- canonical `catalog-detail` с persistent split layout на wide viewport;
- `catalog-workspace` с secondary drawer как primary inspect surface.

На части `catalog-detail` routes оператору действительно может быть удобнее drawer-first reading mode даже на desktop, но сейчас для этого нет governance-safe контракта. `workspaceKind` в inventory описывает тип surface, а не пользовательскую presentation preference. Прямой глобальный switch вида "весь UI в drawer" смешает route families, создаст конфликт с `masterPaneGovernance` и даст inconsistent behaviour на incompatible routes вроде `/artifacts`.

Нужен отдельный change, который зафиксирует управляемую модель user-selectable workspace presentation: только для явно совместимых routes, с понятным precedence contract, persistent preference и сохранением canonical responsive fallback.

## Что меняется

- Добавить новый capability `ui-workspace-presentation-preferences`.
- Зафиксировать, что eligible `catalog-detail` routes МОГУТ (MAY) поддерживать operator-selectable presentation modes `auto`, `split` и `drawer` без смены route family и domain navigation contract.
- Зафиксировать effective mode resolution order:
  - per-route operator override;
  - global operator default;
  - route default;
  - responsive fallback.
- Зафиксировать, что narrow viewport всегда сохраняет mobile-safe detail fallback и не зависит от desktop preference.
- Доработать `ui-platform-foundation`, чтобы canonical `MasterDetail` primitives поддерживали approved wide-viewport presentation variants без превращения route в другой `workspaceKind`.
- Доработать `ui-frontend-governance`, чтобы inventory явно объявлял allowed/default presentation modes только для compatible routes и блокировал конфигурации, которые нарушают `workspaceKind`, `detailMobileFallback` или `masterPaneGovernance`.
- Зафиксировать staged rollout:
  - первая волна только для routes с уже зрелым selected-entity/detail contract;
  - целевой pilot: `/databases`, `/decisions`;
  - `/workflows` и `/templates` допускаются только после дополнительной normalisation master pane;
  - `/artifacts` и прочие non-`catalog-detail` workspaces не включаются автоматически.

## Impact

- Affected specs:
  - `ui-workspace-presentation-preferences` (new)
  - `ui-platform-foundation`
  - `ui-frontend-governance`
- Related specs:
  - `database-metadata-management-ui`
  - `execution-runtime-unification`
  - `workflow-management-workspaces`
- Affected code (expected, when implementing this change):
  - `frontend/src/components/platform/MasterDetailShell.tsx`
  - `frontend/src/uiGovernanceInventory.js`
  - `frontend/src/hooks/**`
  - `frontend/src/pages/Databases/**`
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Templates/**`
  - `frontend/src/components/platform/__tests__/**`
  - `frontend/tests/browser/**`

## Explicitly Out Of Scope

- Принудительное переключение всех routes приложения одним глобальным флагом.
- Автоматическое превращение `catalog-workspace`, `diagnostics-workspace`, `authoring-workspace` или `settings-workspace` в `catalog-detail` / split surfaces.
- Немедленная server-backed sync пользовательской preference между устройствами и браузерами.
- Визуальный redesign catalog surfaces, не связанный с layout/presentation contract.
- Включение `/workflows` и `/templates` в первую волну без предварительной нормализации их master pane composition.

## Assumptions

- `workspaceKind` остаётся source-of-truth для route family и не заменяется presentation preference.
- Первая реализация может использовать local-first persistence, если user-visible contract "выбор переживает reload" соблюдён.
- Existing responsive invariant из `ui-platform-foundation` остаётся обязательным для всех supported modes.
