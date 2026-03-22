## 1. Domain Contracts

- [ ] 1.1 Обновить reusable behavior contracts так, чтобы primary operator/domain термином стал `Execution Pack`.
- [ ] 1.2 Зафиксировать разделение ответственности: topology templates владеют structural slot namespace, execution packs владеют executable slot implementations.
- [ ] 1.3 Зафиксировать staged migration и compatibility aliases для existing `binding_profile*` identifiers без немедленного big-bang storage rename.

## 2. Catalog and Attachment Semantics

- [ ] 2.1 Обновить catalog requirements и operator-facing route semantics с `Binding Profiles` на `Execution Packs`.
- [ ] 2.2 Обновить attachment/read-model semantics так, чтобы pool binding ссылался на attached execution pack revision как на reusable execution logic source.
- [ ] 2.3 Зафиксировать compatibility/coverage expectations между execution pack slot implementations и template-defined structural slots.

## 3. Validation and Rollout

- [ ] 3.1 Добавить/update backend tests на execution-pack read/write aliases, attachment projections и compatibility validation.
- [ ] 3.2 Добавить/update frontend tests на route/label/handoff migration с `/pools/binding-profiles` к `/pools/execution-packs`.
- [ ] 3.3 Прогнать `openspec validate refactor-binding-profiles-into-execution-packs --strict --no-interactive` и релевантные targeted test gates при реализации.
