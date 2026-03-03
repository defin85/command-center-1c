## POOL_MASTER_DATA_SYNC Rollout/Rollback Runbook

Цель: включить двусторонний master-data sync поэтапно (`shadow -> pilot -> full`) с fail-closed поведением и rollback без удаления sync state.

### Scope

- контур: `CC <-> ИБ` (outbound/inbound);
- runtime keys:
  - `pools.master_data.sync.enabled`
  - `pools.master_data.sync.outbound.enabled`
  - `pools.master_data.sync.inbound.enabled`
  - `pools.master_data.sync.default_policy`
  - `pools.master_data.sync.poll_interval_seconds`
  - `pools.master_data.sync.dispatch_batch_size`
  - `pools.master_data.sync.max_retry_backoff_seconds`
- precedence: `tenant override -> global runtime setting -> env default`;
- операторские API:
  - `GET /api/v2/pools/master-data/sync-status/`
  - `GET /api/v2/pools/master-data/sync-conflicts/`
  - `POST /api/v2/pools/master-data/sync-conflicts/{id}/retry|reconcile|resolve/`
- prometheus SLI метрики:
  - `cc1c_orchestrator_pool_master_data_sync_outbox_lag_seconds`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_pending_total`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_retry_total`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturated_total`
  - `cc1c_orchestrator_pool_master_data_sync_outbox_retry_saturation_ratio`
  - `cc1c_orchestrator_pool_master_data_sync_conflicts_pending_total`
  - `cc1c_orchestrator_pool_master_data_sync_conflicts_retrying_total`

### Alert Thresholds

- `PoolMasterDataSyncLagHigh`:
  - условие: `outbox_lag_seconds > 900` в течение 10 минут.
  - действие: проверить backlog в `sync-status`, снизить `dispatch_batch_size`/увеличить `poll_interval_seconds`, при необходимости временно отключить tenant override.
- `PoolMasterDataSyncRetrySaturation`:
  - условие: `outbox_retry_saturation_ratio > 0.25` в течение 10 минут.
  - действие: проверить `last_error_code` в outbox, доступность ИБ/OData, при устойчивой деградации поднять `max_retry_backoff_seconds`.
- `PoolMasterDataSyncConflictBacklogHigh`:
  - условие: `conflicts_pending_total > 25` в течение 10 минут.
  - действие: triage conflict queue по `conflict_code`, выполнить целевые `retry/reconcile/resolve`, не запускать массовый reconcile без RCA.
- `PoolMasterDataSyncConflictSpike`:
  - условие: `delta(conflicts_pending_total[15m]) > 10` в течение 5 минут.
  - действие: считать инцидентом качества входящих/исходящих данных, проверить последние релизы/изменения policy.

### Preflight

1. Применены миграции:
   - `cd orchestrator && ./.venv/bin/python manage.py migrate`
2. Деплой с новыми endpoint-ами и UI вкладкой `Pool Master Data -> Sync`.
3. Global baseline выключен:
   - `pools.master_data.sync.enabled = false`
4. Проверены runtime keys и effective values (global + tenant overrides).
5. Подготовлен список pilot tenant-ов и owner on-call.

### Stage 0: Shadow Mode

1. Для pilot tenant включить overrides:
   - `pools.master_data.sync.enabled = true`
   - `pools.master_data.sync.outbound.enabled = true`
   - `pools.master_data.sync.inbound.enabled = false`
   - `pools.master_data.sync.default_policy = cc_master`
   - `pools.master_data.sync.poll_interval_seconds = 60` (консервативный polling)
   - `pools.master_data.sync.dispatch_batch_size = 25`
2. В shadow mode:
   - мониторить `sync-status` (`lag_seconds`, `pending_count`, `retry_count`);
   - анализировать `sync-conflicts`, но не выполнять массовые reconcile.
3. Критерий выхода:
   - нет неконтролируемого роста `lag_seconds`;
   - нет неконтролируемого роста `retry_count`/`conflict_pending_count`.

### Stage 1: Pilot Apply

1. Для pilot tenant перейти на рабочие параметры:
   - `inbound.enabled = true`
   - `default_policy = bidirectional`
   - `poll_interval_seconds = 30`
   - `dispatch_batch_size = 100`
   - `max_retry_backoff_seconds = 900`
2. Выполнить smoke-сценарии:
   - canonical upsert (`party/item/...`) -> появляется outbound status;
   - manual conflict action (`retry/reconcile/resolve`) -> статус конфликтов меняется корректно.
3. Проверить отсутствие ping-pong:
   - inbound `origin_system=ib` не генерирует обратный outbound intent в ту же ИБ.

### Stage 2: Full Enablement

1. Расширять включение батчами tenant-ов.
2. На каждом батче контролировать:
   - `lag_seconds` по scope;
   - saturation `retry_count`;
   - очередь конфликтов (`pending/retrying`).
3. После стабилизации:
   - установить global `pools.master_data.sync.enabled = true`;
   - оставить tenant override только для исключений.

### Rollback

#### Быстрый tenant rollback

1. Для проблемного tenant:
   - `pools.master_data.sync.enabled = false` (tenant override, status `published`).
2. При необходимости ослабить нагрузку:
   - увеличить `poll_interval_seconds`,
   - уменьшить `dispatch_batch_size`.

#### Массовый rollback

1. Global:
   - `pools.master_data.sync.enabled = false`
2. Проверить, что новые sync actions не исполняются, но данные состояния сохранены.

Важно:
- не удалять таблицы/данные `pool_master_data_sync_*` (`checkpoints/outbox/conflicts/jobs`);
- rollback управляет execution path, а не историей sync.

### Post-Rollback Checklist

1. `sync-status` показывает снижение `pending_count` роста и отсутствие новых apply попыток.
2. `sync-conflicts` остаются доступными для ручной обработки после инцидента.
3. Инцидент задокументирован: причина, затронутые tenant-ы, решение, follow-up.
