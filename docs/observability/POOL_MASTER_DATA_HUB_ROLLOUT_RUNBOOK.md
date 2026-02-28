## POOL_MASTER_DATA_HUB Rollout/Rollback Runbook

Цель: поэтапно включить `pools.master_data.gate_enabled` без silent fallback и с быстрым rollback в tenant scope.

### Scope

- master-data gate шаг: `pool.master_data_gate`;
- runtime key: `pools.master_data.gate_enabled`;
- rollout precedence: `tenant override -> global runtime setting -> env default`.

### Preflight (до rollout)

1. Миграции применены: `python manage.py migrate`.
2. Бэкенд и UI с endpoint-ами `/api/v2/pools/master-data/**` задеплоены.
3. Global baseline выставлен в `false` (deploy with gate off):
   - UI: `/settings/runtime`, key `pools.master_data.gate_enabled`.
   - API: `PATCH /api/v2/settings/runtime/pools.master_data.gate_enabled/` с payload `{"value": false}`.
4. Подготовлен список pilot tenant-ов.

### Stage 1: Backfill + remediation

1. Dry-run backfill:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_organization_master_party_bindings --dry-run --json`
2. Проверить `remediation_count` и причины:
   - `no_match`
   - `ambiguous_match`
   - `candidate_already_bound`
3. Исправить данные (Organization/Party/bindings), затем выполнить apply-run:
   - `cd orchestrator && ./venv/bin/python manage.py backfill_organization_master_party_bindings --json`
4. Критерий завершения Stage 1:
   - нет критичных unresolved для tenant-ов, которые входят в pilot.

### Stage 2: Pilot enable (tenant override)

1. Для pilot tenant включить override:
   - `PATCH /api/v2/settings/runtime-overrides/pools.master_data.gate_enabled/`
   - Header `X-CC1C-Tenant-ID: <pilot-tenant-id>`
   - Payload: `{"value": true, "status": "published"}`
2. Проверить effective value в tenant context:
   - `GET /api/v2/settings/runtime-effective/`
   - key `pools.master_data.gate_enabled` должен быть `true`.
3. Выполнить smoke run для pilot tenant и проверить:
   - `run.master_data_gate.status` в `/api/v2/pools/runs/{run_id}/` и `/report/`;
   - отсутствие fail-closed spike по кодам:
     - `MASTER_DATA_GATE_CONFIG_INVALID`
     - `MASTER_DATA_ORGANIZATION_PARTY_BINDING_MISSING`
     - `MASTER_DATA_ENTITY_NOT_FOUND`
     - `MASTER_DATA_BINDING_AMBIGUOUS`
     - `MASTER_DATA_BINDING_CONFLICT`
4. Критерий перехода к Stage 3:
   - pilot tenant-ы проходят целевые сценарии без блокирующих инцидентов.

### Stage 3: Scale-out

1. Расширять включение батчами tenant-ов через tenant override (`value=true`).
2. На каждом батче проверять run diagnostics и remediation backlog.
3. После стабилизации:
   - выставить global baseline `true`;
   - убрать лишние override `true` (оставить только исключения с `false`, если нужны).

### Rollback

#### Быстрый rollback (предпочтительно)

1. Для проблемного tenant сразу выставить override `false`:
   - `PATCH /api/v2/settings/runtime-overrides/pools.master_data.gate_enabled/`
   - Header `X-CC1C-Tenant-ID: <tenant-id>`
   - Payload: `{"value": false, "status": "published"}`
2. Если инцидент массовый, выставить global `false`:
   - `PATCH /api/v2/settings/runtime/pools.master_data.gate_enabled/` с `{"value": false}`.

#### Release rollback

Если проблема в релизном коде, выполнить стандартный release rollback после отключения gate через runtime settings.

Важно:
- не удалять данные `Organization.master_party` и `PoolMasterDataBinding`;
- rollback управляет только execution-path, данные остаются для повторного включения после фикса.

### Post-rollback checks

1. Новые run-ы показывают `master_data_gate.status=skipped` (или `master_data_gate=null` для historical).
2. `pool.publication_odata` снова стартует без master-data gate blocking.
3. Инцидент и remediation actions задокументированы.
