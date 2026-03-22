## 1. Contracts

- [ ] 1.1 Обновить binding attachment contracts/read-model expectations так, чтобы authoritative mutable state attachment-а ограничивался pool-local scope и pinned `binding_profile_revision_id`.
- [ ] 1.2 Зафиксировать в контрактах shipped `resolved_profile` только как derived read-only projection, а не как вторую mutable payload surface.

## 2. Read/Runtime Simplification

- [ ] 2.1 Убрать side effects из default list/detail/preview/runtime path для attachment-ов и profile refs.
- [ ] 2.2 Не добавлять remediation/backfill tooling для legacy residue; rows без resolvable profile refs остаются fail-closed и устраняются через destructive reset данных до rollout.

## 3. Rollout Reset

- [ ] 3.1 Зафиксировать hard-reset rollout: затронутые `pool`, `pool_workflow_binding` и `binding_profile*` данные удаляются заранее вместо in-place migration/backfill.

## 4. Profile Usage Projection

- [ ] 4.1 Добавить dedicated scoped backend read-model для usage summary и per-pool attachment rows на `/pools/binding-profiles`.
- [ ] 4.2 Перевести `/pools/binding-profiles` на новый scoped usage contract без broad tenant-wide pool catalog hydration.

## 5. Validation

- [ ] 5.1 Добавить/update backend tests на side-effect-free reads, fail-closed diagnostics и derived attachment read-model.
- [ ] 5.2 Добавить/update frontend tests на scoped usage loading и handoff в `/pools/catalog`.
- [ ] 5.3 Прогнать релевантные quality gates: targeted `pytest`, `npm run lint`, `npm run test:run`, `npm run test:browser:ui-platform`.
