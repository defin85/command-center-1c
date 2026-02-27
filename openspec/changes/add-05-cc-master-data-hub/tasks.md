## 1. Canonical master-data contract (CC)
- [ ] 1.1 Зафиксировать MVP-словарь канонических сущностей (`Party`, `Item`, `Contract`, `TaxProfile`) и инварианты tenant-scope.
- [ ] 1.2 Зафиксировать per-infobase binding контракт (`canonical_id + entity_type + database_id -> ib_ref_key`) и идемпотентные правила resolve/sync.
- [ ] 1.3 Зафиксировать fail-closed коды и diagnostics для конфликтов/неоднозначности при resolve/sync.

## 2. Runtime and publication integration
- [ ] 2.1 Добавить в workflow runtime обязательный pre-publication master-data gate перед `pool.publication_odata`.
- [ ] 2.2 Добавить в execution context immutable `master_data_snapshot_ref` и `master_data_binding_artifact_ref` с обязательным reuse в retry.
- [ ] 2.3 Зафиксировать, что publication transport потребляет только resolved refs из binding artifact и не делает free-text fallback lookup.

## 3. Verification and rollout
- [ ] 3.1 Добавить backend тесты на успешный resolve/sync path и fail-closed блокировку публикации при конфликте master-data.
- [ ] 3.2 Добавить тесты retry/idempotency на повторное использование того же `master_data_snapshot_ref`.
- [ ] 3.3 Обновить operator-facing diagnostics/runbook и прогнать `openspec validate add-05-cc-master-data-hub --strict --no-interactive`.
