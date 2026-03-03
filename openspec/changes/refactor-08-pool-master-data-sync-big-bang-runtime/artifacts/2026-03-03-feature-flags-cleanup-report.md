# Feature-Flags / Compatibility Cleanup Report (2026-03-03)

Change: `refactor-08-pool-master-data-sync-big-bang-runtime`

## Reviewed candidates

1. Runtime keys:
- `pools.master_data.sync.inbound.enabled`
- `pools.master_data.sync.outbound.enabled`

Решение: **retain**. Эти ключи входят в действующий capability spec:
- `openspec/specs/runtime-settings-overrides/spec.md`

Удаление на этом шаге привело бы к нарушению текущего контракта runtime-overrides.

2. Legacy inbound fail-closed guard:
- `SYNC_LEGACY_INBOUND_ROUTE_DISABLED`
- `run_pool_master_data_sync_legacy_inbound_route(...)`

Решение: **retain**. Guard соответствует сценарию fail-closed после cutover в spec:
- `openspec/changes/refactor-08-pool-master-data-sync-big-bang-runtime/specs/pool-master-data-sync/spec.md`

3. Temporary cutover compatibility branches in refactor-08 path

Решение: **no-op cleanup completed**. В текущем refactor-08 runtime не обнаружено дополнительных временных feature-flag веток, не покрытых действующими контрактами.

## Conclusion

Cleanup 8.4 выполнен в границах безопасного изменения:
- удаляемых флагов/веток без нарушения контрактов не выявлено;
- в коде оставлены только контрактно-обязательные runtime keys и fail-closed guardrails.
