# Change: Bootstrap import from IB для master-data (UI + backend)

## Why
Сейчас в проекте нет отдельного операторского сценария для первичного заполнения canonical master-data в CC из существующей ИБ.
Текущие пути:
- ручной ввод через `/pools/master-data` для `Party/Item/Contract/TaxProfile/Bindings`;
- bulk sync только для каталога организаций через `/api/v2/pools/organizations/sync/`;
- runtime sync-контур ориентирован на регулярную двустороннюю синхронизацию, а не на управляемый первичный bootstrap.

Для крупных tenant это приводит к высокой ручной нагрузке, длинному time-to-onboard и риску ошибок при ручной подготовке данных перед запуском pool-сценариев.

## What Changes
- Добавить отдельный backend-контур `Bootstrap import from IB` для master-data:
  - асинхронный job lifecycle (`preflight`, `dry-run`, `execute`, `status`, `cancel`, `retry-failed-chunks`);
  - chunked и resumable исполнение с идемпотентным upsert;
  - детерминированный dependency order сущностей (`party -> item -> tax_profile -> contract -> binding`);
  - fail-closed diagnostics и conflict-aware поведение без silent overwrite.
- Добавить UI workflow в `/pools/master-data`:
  - операторский wizard импорта из выбранной ИБ;
  - обязательный preflight + dry-run до execute;
  - отображение прогресса, итогового отчёта и повторного запуска только для failed chunks.
- Зафиксировать контракт, что bootstrap-путь маркирует изменения как inbound origin (`origin_system=ib`), чтобы исключить ping-pong репликацию.

## Impact
- Affected specs:
  - `pool-master-data-sync`
  - `pool-master-data-hub-ui`
- Affected code:
  - `orchestrator/apps/intercompany_pools/*` (bootstrap job model/service/executor)
  - `orchestrator/apps/api_v2/views/*` + `orchestrator/apps/api_v2/urls.py` (новые master-data bootstrap endpoints)
  - `contracts/orchestrator/src/paths/*` и aggregated OpenAPI
  - `frontend/src/api/intercompanyPools.ts`
  - `frontend/src/pages/Pools/masterData/*` (новая UI-зона bootstrap import)

