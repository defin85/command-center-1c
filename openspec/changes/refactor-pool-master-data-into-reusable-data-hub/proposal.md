# Change: Refactor Pool Master Data into Reusable Data Hub

## Why
`Pool Master Data` сейчас решает только publication-centric задачу для `Party`, `Item`, `Contract`, `TaxProfile`, тогда как factual monitoring уже требует тот же класс reusable reference data для бухгалтерских счетов. На живой ИБ видно, что счета участвуют и в header, и в табличных частях опубликованных документов, а factual sync при этом использует отдельный hardcoded account scope, что создаёт дублирование модели и fail-closed ошибки совместимости.

## What Changes
- Расширить `Pool Master Data` из publication-only слоя в tenant-scoped reusable-data hub без нового top-level runtime и без замены текущего route `/pools/master-data`.
- Ввести первую новую reusable entity family для бухгалтерских счетов:
  - `GLAccount` как canonical reusable entity с per-infobase binding;
  - `GLAccountSet` как versioned grouped canonical profile для factual/report scopes.
- Сохранить текущие `master_data.*` token contracts и существующие publication entity types как backward-compatible subset нового hub.
- Привязать `GLAccount` и `GLAccountSet` к configuration-scoped compatibility markers, согласованным с metadata snapshot provenance и target business configuration identity.
- Разрешить `document_policy` и publication compile использовать canonical account tokens и resolved account bindings вместо raw GUID/hardcoded literals.
- Перевести factual account scope с hardcoded defaults на pinned revision `GLAccountSet` + fail-closed preflight coverage по target infobases.
- Явно зафиксировать capability matrix:
  - `GLAccount` поддерживает canonical identity, manual upsert, binding и bootstrap import;
  - `GLAccount` в этом change НЕ поддерживает automatic outbound mutation/bidirectional sync в target ИБ;
  - `GLAccountSet` остаётся CC-owned profile и не materialize'ится как direct IB object.
- Подготовить hub к additive onboarding новых reusable entity types без создания отдельного ad hoc каталога и отдельного runtime path под каждый новый тип.

## Impact
- Affected specs:
  - `pool-master-data-hub`
  - `pool-master-data-hub-ui`
  - `pool-master-data-sync`
  - `pool-document-policy`
  - `pool-odata-publication`
  - `pool-factual-balance-monitoring`
- Affected code:
  - `orchestrator/apps/intercompany_pools/**`
  - `orchestrator/apps/api_v2/views/intercompany_pools_master_data.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `frontend/src/pages/Pools/**`
  - `contracts/**`
  - `go-services/worker/internal/drivers/poolops/**`
