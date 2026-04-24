# Change: Discovery-backed Chart Import and initial load from reference infobase

## Why
Текущий `Chart Import` уже отделён от generic `Sync`, но source setup всё ещё требует, чтобы оператор заранее знал и вручную ввёл `chart_identity`.

Для реального onboarding плана счетов этого недостаточно: оператор должен выбрать эталонную ИБ, увидеть обнаруженные в ней планы счетов и запустить первичную загрузку canonical chart без ручного угадывания `ChartOfAccounts_*`.

## What Changes
- Добавить discovery path для доступных chart-of-accounts в выбранной ИБ, включая stable `chart_identity`, display name, compatibility profile и источник derivation.
- Заменить free-text-only setup на operator flow: выбрать эталонную ИБ, выбрать обнаруженный план счетов, сохранить authoritative source.
- Добавить initial-load workflow, который из выбранной эталонной ИБ выполняет `preflight -> dry-run -> materialize` как единый guided path с явным review gate перед materialize.
- Привязать discovery и initial-load decisions к конкретному metadata/source evidence (`metadata_hash`/`catalog_version` или equivalent source fingerprint), чтобы source update не позволял materialize-ить stale dry-run.
- Сохранить возможность ручного override только как advanced/fail-closed escape hatch, если discovery не может доказательно вернуть нужный `chart_identity`.
- Зафиксировать, что первичная загрузка из эталонной ИБ остаётся тем же chart materialization contract, а не generic `Sync` или legacy `Bootstrap Import`.

## Impact
- Affected specs:
  - `pool-master-data-chart-materialization`
  - `pool-master-data-hub-ui`
- Affected code:
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_source_adapter.py`
  - `orchestrator/apps/intercompany_pools/master_data_chart_materialization_service.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data_chart.py`
  - `contracts/orchestrator/src/**`
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/pages/Pools/masterData/ChartImportTab.tsx`
  - `frontend/src/pages/Pools/__tests__/poolMasterDataPageTestHarness.tsx`

## Dependencies
- Follow-up to `add-pool-master-data-chart-materialization-path`.
- This change assumes the shipped `Chart Import` lifecycle remains separate from generic `Sync`.

## Non-Goals
- Не делать `GLAccount` generic bidirectional sync entity.
- Не merge-ить несколько эталонных ИБ в один canonical chart.
- Не materialize-ить без operator review dry-run counters.
- Не требовать custom 1C extension для MVP, если identity можно получить из OData/metadata configuration.
- Не сканировать полный chart только ради discovery, когда identity можно вывести из metadata/source config.
