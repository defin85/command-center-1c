## 1. Canonical Binding Workspace
- [ ] 1.1 Зафиксировать публичный contract для atomic collection replace workflow bindings: request/response shape, collection concurrency token, conflict/error semantics и связь с existing single-binding CRUD.
- [ ] 1.2 Реализовать backend transactional replace path поверх canonical binding store без partial apply и без возврата к metadata-backed source-of-truth.
- [ ] 1.3 Перевести default `/pools/catalog` binding workspace на canonical collection read/save path и убрать silent fallback к `pool.metadata["workflow_bindings"]` из shipped flow.
- [ ] 1.4 Добавить backend/frontend coverage для сценариев `atomic replace success`, `stale collection conflict`, `no partial apply` и `legacy metadata requires explicit import`.

## 2. Metadata Catalog Contract Source-of-Truth
- [ ] 2.1 Зафиксировать, что `/api/v2/pools/odata-metadata/catalog/` и `/refresh/` используют generated OpenAPI contract как единственный typed source-of-truth для shipped frontend path.
- [ ] 2.2 Перевести frontend consumer metadata catalog на generated client/models и убрать hand-written runtime DTO drift для shared snapshot markers.
- [ ] 2.3 Добавить parity gates/tests для цепочки `runtime serializer -> OpenAPI source -> generated client -> frontend consumer` по metadata catalog surface.

## 3. Rollout Evidence Contract
- [ ] 3.1 Спроектировать machine-readable schema для tenant-scoped workflow hardening cutover evidence bundle и стабильный capability artifact path для schema/example/verifier contract.
- [ ] 3.2 Добавить verifier/gate semantics, которые fail-closed блокируют staging/prod go/no-go при отсутствии обязательных evidence refs, digest или sign-off.
- [ ] 3.3 Обновить runbook, release notes и cutover notes, чтобы они явно различали repository acceptance evidence и tenant live cutover evidence.

## 4. Validation
- [ ] 4.1 Обновить OpenAPI/contracts/generated clients под collection replace contract и metadata catalog parity requirements.
- [ ] 4.2 Добавить/обновить backend integration tests, frontend unit/browser tests и docs parity checks для нового hardening contract.
- [ ] 4.3 Провести `openspec validate tighten-workflow-hardening-canonical-contracts --strict --no-interactive`.
