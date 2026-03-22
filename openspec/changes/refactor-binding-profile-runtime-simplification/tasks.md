## 1. Contracts

- [ ] 1.1 Обновить binding attachment contracts/read-model expectations так, чтобы authoritative mutable state attachment-а ограничивался pool-local scope и pinned `binding_profile_revision_id`.
- [ ] 1.2 Зафиксировать в контрактах shipped `resolved_profile` только как derived read-only projection, а не как вторую mutable payload surface.

## 2. Read/Runtime Simplification

- [ ] 2.1 Убрать side effects из default list/detail/preview/runtime path для attachment-ов и profile refs.
- [ ] 2.2 Оставить generated one-off profile materialization только в explicit remediation/backfill tooling с явной диагностикой для shipped path.

## 3. Profile Usage Projection

- [ ] 3.1 Добавить dedicated scoped backend read-model для usage summary и per-pool attachment rows на `/pools/binding-profiles`.
- [ ] 3.2 Перевести `/pools/binding-profiles` на новый scoped usage contract без broad tenant-wide pool catalog hydration.

## 4. Validation

- [ ] 4.1 Добавить/update backend tests на side-effect-free reads, explicit remediation diagnostics и derived attachment read-model.
- [ ] 4.2 Добавить/update frontend tests на scoped usage loading и handoff в `/pools/catalog`.
- [ ] 4.3 Прогнать релевантные quality gates: targeted `pytest`, `npm run lint`, `npm run test:run`, `npm run test:browser:ui-platform`.
