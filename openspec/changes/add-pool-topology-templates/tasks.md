## 1. Contracts

- [ ] 1.1 Добавить новую capability `pool-topology-templates` с tenant-scoped template/revision model для abstract slot graph.
- [ ] 1.2 Зафиксировать contract pool-local instantiation: pinned `topology_template_revision_id` + mapping `slot_key -> organization_id`.
- [ ] 1.3 Зафиксировать contract template edge defaults для `document_policy_key` без runtime inference только по graph shape.

## 2. Pool Catalog Integration

- [ ] 2.1 Расширить `organization-pool-catalog` требования template-based topology instantiation path на `/pools/catalog`.
- [ ] 2.2 Зафиксировать manual topology authoring как fallback path, а не как единственный путь тиражирования типовых схем.
- [ ] 2.3 Зафиксировать, что existing graph read APIs продолжают возвращать concrete materialized topology для pool/runtime.

## 3. Document Policy Integration

- [ ] 3.1 Обновить `pool-document-policy`, чтобы template edge defaults materialize'ились в explicit `edge.metadata.document_policy_key`.
- [ ] 3.2 Зафиксировать fail-closed поведение при отсутствии explicit selector после instantiation и запрет на silent graph-position fallback.

## 4. Rollout Reset

- [ ] 4.1 Зафиксировать hard-reset rollout: существующие `pool` и связанные reusable binding данные удаляются/пересоздаются вместо automatic conversion в templates.

## 5. Validation

- [ ] 5.1 Добавить/update backend tests на template revision pinning, slot assignments и deterministic materialization concrete topology.
- [ ] 5.2 Добавить/update backend/frontend tests на template-based authoring path и explicit selector defaults/diagnostics.
- [ ] 5.3 Прогнать релевантные quality gates: targeted `pytest`, `npm run lint`, `npm run test:run`, `openspec validate add-pool-topology-templates --strict --no-interactive`.
