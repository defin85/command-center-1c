## 1. Domain model and policy
- [ ] 1.1 Добавить persisted модели и миграции для source provenance, dedupe clusters и review-required resolution items.
- [ ] 1.2 Расширить executable registry dedupe capabilities: eligibility, identity signals, normalization rules, survivor precedence, review-required conditions, rollout eligibility.
- [ ] 1.3 Зафиксировать `V1` entity coverage и fail-closed exclusions, включая non-auto-dedupe status для `GLAccountSet`.

## 2. Collection and canonical resolution
- [ ] 2.1 Пропустить bootstrap collection и inbound ingress через source-record ingestion до canonical promotion.
- [ ] 2.2 Реализовать deterministic auto-resolution для safe matches и reuse existing canonical entity для already-resolved cluster.
- [ ] 2.3 Реализовать review-required resolution path для ambiguous matches с machine-readable reason codes и conflicting field snapshot.
- [ ] 2.4 Сохранять provenance links на source database, source ref/fingerprint и origin batch/job/launch.

## 3. Runtime gates and API
- [ ] 3.1 Добавить API list/detail/action endpoints для dedupe review/history/read-model в namespace `/api/v2/pools/master-data/`.
- [ ] 3.2 Заблокировать outbound outbox fan-out, manual sync launches и publication/source-of-truth consumption для unresolved dedupe clusters.
- [ ] 3.3 Возвращать machine-readable blocker/outcome codes для unresolved dedupe вместо silent partial success.
- [ ] 3.4 Обновить OpenAPI/generated contracts для новых read-model и mutating review actions.

## 4. UI workspace
- [ ] 4.1 Добавить зону `Dedupe Review` в `/pools/master-data` внутри canonical workspace shell.
- [ ] 4.2 Реализовать queue/detail UI с provenance, normalized match signals, conflicting fields и canonical survivor summary.
- [ ] 4.3 Реализовать operator actions `accept merge`, `choose survivor`, `mark distinct` и сохранить URL-addressable review context.
- [ ] 4.4 Показать deep-link handoff из blocked collection/sync/publication surfaces в `Dedupe Review`.

## 5. Verification
- [ ] 5.1 Добавить domain tests для safe auto-resolution, capability fail-closed и review-required ambiguous cases.
- [ ] 5.2 Добавить API tests для review list/detail/actions и blocker responses.
- [ ] 5.3 Добавить UI tests для `Dedupe Review` queue/detail/actions и rollout blocker handoff.
- [ ] 5.4 Добавить runtime tests, подтверждающие блокировку outbound/manual rollout/publication при unresolved dedupe.
- [ ] 5.5 Прогнать `openspec validate add-02-pool-master-data-cross-infobase-dedupe --strict --no-interactive`.
