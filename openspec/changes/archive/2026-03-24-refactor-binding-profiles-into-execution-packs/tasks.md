## 1. Domain Contracts

- [x] 1.1 Обновить reusable behavior contracts так, чтобы primary operator/domain термином стал `Execution Pack`.
- [x] 1.2 Зафиксировать разделение ответственности: topology templates владеют structural slot namespace, execution packs владеют executable slot implementations.
- [x] 1.3 Зафиксировать clean rename без staged migration и без обязательных compatibility aliases для existing `binding_profile*` identifiers.

## 2. Catalog and Attachment Semantics

- [x] 2.1 Обновить catalog requirements и operator-facing route semantics с `Binding Profiles` на `Execution Packs`.
- [x] 2.2 Обновить attachment/read-model semantics так, чтобы pool binding ссылался на attached execution pack revision как на reusable execution logic source.
- [x] 2.3 Зафиксировать compatibility/coverage expectations между execution pack slot implementations и template-defined structural slots.

## 3. Validation and Rollout

- [x] 3.1 Добавить/update backend tests на execution-pack contracts, attachment projections и compatibility validation без alias fallback.
- [x] 3.2 Добавить/update frontend tests на route/label/handoff смену к `/pools/execution-packs` как единственному required primary path.
- [x] 3.3 Зафиксировать hard-reset rollout: affected `binding_profile*`, attachment и при необходимости `pool` данные удаляются заранее вместо migration legacy catalog.
- [x] 3.4 Прогнать `openspec validate refactor-binding-profiles-into-execution-packs --strict --no-interactive` и релевантные targeted test gates при реализации.
