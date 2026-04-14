# Change: add-ui-internationalization-rollout

## Почему

Change `add-cross-stack-internationalization-foundation` оформил baseline для i18n: shell bootstrap locale contract, shared runtime, formatter layer, `antd` locale bridge и pilot migration для `Dashboard`, `System Status`, `Clusters` и `RBAC`.

Но repo-wide migration ещё не завершена:
- `frontend/src/uiGovernanceInventory.js` по-прежнему содержит большой хвост `platform-governed` route families вне pilot wave: `/operations`, `/artifacts`, `/databases`, `/extensions`, `/workflows*`, `/templates`, `/decisions`, `/pools/*`, `/service-mesh`, `/users`, `/dlq`, `/settings/*`;
- в `frontend/src` всё ещё остаются десятки raw `toLocaleString()/toLocaleDateString()/toLocaleTimeString()` на этих route families и их shell-backed surfaces;
- текущие locale-boundary lint checks доказали подход на pilot set, но ещё не замкнуты на весь governance inventory;
- `/pools/factual` остаётся `legacy-monitored`, поэтому repo-wide rollout не должен молча считать его частью общего завершения; для него нужен отдельный approved follow-up change.

Без отдельного rollout change продукт останется в смешанном состоянии: часть governed routes уже живёт на canonical i18n layer, а часть продолжает рендерить ad hoc copy и formatting. Это ломает consistency обещанного platform-governed shell и оставляет migration без чёткой точки завершения.

## Что меняется

- Добавить новый capability `ui-internationalization-rollout`, который фиксирует end-state для full migration remaining operator/staff-facing surfaces.
- Доработать `ui-frontend-governance`, чтобы locale-boundary coverage и validation gates опирались на checked-in route/shell inventory для всех `platform-governed` modules, а не на вручную выбранный pilot subset.
- Доработать `ui-platform-foundation`, чтобы thin design layer явно владел localized shared semantics для page chrome, empty/error/status primitives и shell-backed drawers/modals на всех migrated route families.
- Спланировать repo-wide migration remaining frontend route families и их owned shell surfaces на canonical i18n runtime, namespace catalogs, shared formatters и code-first error localization.
- Выполнять rollout не big-bang переписыванием, а bounded waves, сгруппированными по lint profile, shared-helper coupling и объёму residual raw locale formatting.
- Зафиксировать, что `/pools/factual` не входит в этот repo-wide rollout и должен закрываться отдельным approved follow-up change вместо неявного вечного хвоста.

## Impact

- Affected specs:
  - `ui-internationalization-rollout` (new)
  - `ui-frontend-governance`
  - `ui-platform-foundation`
- Affected code (expected, when implementing this change):
  - `frontend/src/i18n/**`
  - `frontend/src/uiGovernanceInventory.js`
  - `frontend/eslint.config.js`
  - `frontend/src/pages/Operations/**`
  - `frontend/src/pages/Artifacts/**`
  - `frontend/src/pages/Databases/**`
  - `frontend/src/pages/Extensions/**`
  - `frontend/src/pages/Workflows/**`
  - `frontend/src/pages/Templates/**`
  - `frontend/src/pages/Decisions/**`
  - `frontend/src/pages/Pools/**`
  - `frontend/src/pages/ServiceMesh/**`
  - `frontend/src/pages/Users/**`
  - `frontend/src/pages/DLQ/**`
  - `frontend/src/pages/Settings/**`
  - related shared modules under `frontend/src/components/**` and `frontend/src/utils/**`
  - `frontend/tests/browser/**`

## Explicitly Out Of Scope

- Добавление новых locales сверх `ru` и `en`.
- Локализация business/domain payload values из 1C, OData, worker-generated artifacts, export bundles, писем и offline документов.
- Server-backed roaming sync пользовательского языка между устройствами.
- Переход на вторую i18n stack/library или route-local vendor locale owners.
- Public auth routes и redirect aliases, уже помеченные как `excluded` в checked-in route inventory.
- `/pools/factual` factual monitoring workspace и его `legacy-monitored` shell surfaces; они закрываются отдельным follow-up change.

## Assumptions

- `add-cross-stack-internationalization-foundation` является baseline для этого rollout и должен быть заархивирован до или вместе с началом реализации.
- Full migration targets all operator/staff-facing SPA surfaces из `frontend/src/uiGovernanceInventory.js` с tier `platform-governed`.
- На момент создания proposal единственный checked-in `legacy-monitored` operator surface — `/pools/factual`; он не должен оставаться implicit gap и поэтому выносится в отдельный follow-up change.
- Реалистичный rollout в этой ветке означает delivery bounded waves с per-wave verification, а не один giant migration diff на все route families сразу.
