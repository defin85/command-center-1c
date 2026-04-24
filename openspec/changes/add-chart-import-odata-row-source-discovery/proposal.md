# Change: Chart Import OData row-source discovery for initial load

## Why
`Chart Import` уже умеет обнаруживать `chart_identity`, но metadata catalog snapshot хранит только описание метаданных, а не строки плана счетов. Поэтому candidate, найденный только по metadata, может привести оператора к `initial load`, который не сможет прочитать полный список счетов без заранее настроенного row source mapping.

Для честной первичной загрузки оператор должен выбрать эталонную ИБ, увидеть не только найденный `ChartOfAccounts_*`, но и подтверждённый OData row source, из которого `dry-run/materialize` реально прочитает все счета.

## What Changes
- Расширить Chart Import discovery так, чтобы candidate явно различал:
  - обнаруженный `chart_identity`;
  - готовность источника строк для initial load;
  - доказательство OData row source mapping/probe.
- Автоматически предлагать chart row source для OData entity `ChartOfAccounts_*`, включая field mapping `Ref_Key -> source_ref/canonical_id`, `Code -> code`, `Description -> name` и stamp `chart_identity` из entity name; read-only discovery не создаёт и не изменяет authoritative source.
- Сохранять выбранный row source provenance в authoritative chart source metadata и включать его в source revision/evidence.
- Блокировать `Prepare Initial Load` / `dry-run` / `materialize`, если candidate identity найден, но row source не подтверждён.
- Оставить full row fetch только для `dry-run/materialize`; discovery/preflight выполняют bounded metadata/probe checks.

## Impact
- Affected specs:
  - `pool-master-data-chart-materialization`
  - `pool-master-data-hub-ui`
- Affected code:
  - `orchestrator/apps/intercompany_pools/master_data_chart_materialization_service.py`
  - `orchestrator/apps/intercompany_pools/master_data_bootstrap_import_source_adapter.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data_chart.py`
  - `contracts/orchestrator/src/**`
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/pages/Pools/masterData/ChartImportTab.tsx`
  - `frontend/src/pages/Pools/__tests__/poolMasterDataPageTestHarness.tsx`

## Dependencies
- Follow-up to `add-chart-import-discovery-and-initial-load`.
- Assumes the dedicated Chart Import lifecycle from `add-pool-master-data-chart-materialization-path` remains the only runtime path for canonical `GLAccount` materialization.

## Non-Goals
- Не превращать `GLAccount` в generic bidirectional sync entity.
- Не запускать legacy `Bootstrap Import` job вместо Chart Import materialization.
- Не читать полный план счетов на этапе discovery.
- Не угадывать нестандартные поля без operator review или explicit mapping.
- Не сохранять OData credentials, authorization headers или raw chart rows в discovery/source provenance.
