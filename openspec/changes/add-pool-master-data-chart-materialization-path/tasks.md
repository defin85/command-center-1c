## 1. Backend source-of-truth contract
- [ ] 1.1 Добавить persisted contract для authoritative chart source на compatibility class `(tenant, chart_identity, config_name, config_version)`.
- [ ] 1.2 Добавить API/read-model для source inspect, preflight, dry-run и materialization jobs без смешивания с generic sync launchers.

## 2. Canonical chart materialization
- [ ] 2.1 Переиспользовать bootstrap/import source adapter для full-snapshot чтения `GLAccount` из authoritative source DB.
- [ ] 2.2 Реализовать deterministic canonical materialization `GLAccount`, где source `Ref_Key` остаётся provenance-only.
- [ ] 2.3 Добавить snapshot provenance, hash/counters и soft-retire semantics вместо implicit hard delete.

## 3. Follower verify and binding backfill
- [ ] 3.1 Добавить verify path для follower databases по `code + chart_identity`.
- [ ] 3.2 Добавить auto-backfill/update path для target-local `GLAccount` bindings с fail-closed ambiguity/stale diagnostics.
- [ ] 3.3 Убедиться, что factual/publication контуры могут использовать этот path без перевода `GLAccount` в sync-capable entity type.

## 4. UI and operator workflow
- [ ] 4.1 Добавить `Chart Import` zone в `/pools/master-data` с preflight -> dry-run -> materialize -> verify lifecycle.
- [ ] 4.2 Показать operator-facing source provenance, counters, drift и remediation handoff в `Bindings`, когда verify/backfill не может завершиться автоматически.
- [ ] 4.3 Сохранить explicit separation между `Chart Import`, `Bootstrap Import` и `Sync` surfaces.

## 5. Verification
- [ ] 5.1 Добавить backend tests на authoritative source selection, full-snapshot materialization, deterministic canonical keys и soft-retire behavior.
- [ ] 5.2 Добавить tests на follower verify/backfill и fail-closed ambiguity/stale diagnostics.
- [ ] 5.3 Добавить frontend tests на `Chart Import` workspace flow и deep-linkable remediation handoff.
- [ ] 5.4 Прогнать `openspec validate add-pool-master-data-chart-materialization-path --strict --no-interactive`.
