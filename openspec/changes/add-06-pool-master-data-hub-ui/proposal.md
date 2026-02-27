# Change: UI workspace для `add-05-cc-master-data-hub`

## Why
`add-05-cc-master-data-hub` ввёл канонические сущности и pre-publication master-data gate в runtime, но операторский UI для управления этими данными отсутствует.

Сейчас оператор вынужден работать через косвенные механики (raw JSON в policy и диагностика в общем JSON run-репорта), что повышает риск ошибок в токенах и осложняет remediation.

## What Changes
- Добавить отдельный workspace `/pools/master-data` для управления каноническими сущностями:
  - `Party` (единая сущность с role tags),
  - `Item`,
  - `Contract` (строго owner-scoped к counterparty),
  - `TaxProfile` (`vat_rate`, `vat_included`, `vat_code`),
  - `Bindings` (per-infobase scope).
- Зафиксировать и внедрить явную связь `Organization <-> Party` (MVP `1:1`) для устранения конфликта source-of-truth:
  - `Organization` остаётся узлом topology/пулов и владельцем технических полей участия в графе;
  - `Party` остаётся каноническим владельцем юридических реквизитов и publication master-data.
- Добавить operator-facing CRUD/search/filter API для этих сущностей и bindings в tenant scope.
- Добавить в `/pools/catalog` для `document_policy` guided token picker для master-data токенов вместо ручного набора строк.
- Добавить в `/pools/runs` карточку `Master Data Gate` с machine-readable summary/diagnostics (вместо необходимости разбирать raw JSON вручную).
- Добавить поддержку runtime key `pools.master_data.gate_enabled` в tenant overrides, чтобы UI мог управлять включением gate в staged rollout.

## Impact
- Affected specs:
  - `pool-master-data-hub-ui` (new)
  - `organization-pool-catalog`
  - `pool-workflow-execution-core`
  - `runtime-settings-overrides`
- Affected code (expected):
  - `frontend/src/App.tsx`
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/pages/Pools/PoolCatalogPage.tsx`
  - `frontend/src/pages/Pools/PoolRunsPage.tsx`
  - `frontend/src/pages/Pools/**` (new master-data page/components)
  - `frontend/src/api/intercompanyPools.ts`
  - `orchestrator/apps/api_v2/urls.py`
  - `orchestrator/apps/api_v2/views/intercompany_pools.py`
  - `orchestrator/apps/runtime_settings/registry.py`
  - `contracts/orchestrator/src/**` (API contracts)

## Non-Goals
- Не включать full MDM для всех доменов платформы вне pools.
- Не объединять физически модели `Organization` и `Party` в одну таблицу/сущность в рамках этого change.
- Не реализовывать сложный merge/сопоставление с внешними источниками (fuzzy match, conflict resolution wizard).
- Не менять экономическую логику распределения (`top_down`/`bottom_up`) и не менять доменный контракт `document_policy.v1`.

## Dependencies
- Change зависит от `add-05-cc-master-data-hub` как от базового доменного и runtime-контракта.
- `pool-document-policy` остаётся source-of-truth для структуры policy; текущий change добавляет только guided authoring UX поверх существующего контракта.
